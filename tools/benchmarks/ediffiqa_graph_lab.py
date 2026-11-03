"""Analyze and generate eDifFIQA ONNX candidates for DirectML.

Repository-side only. Produces:
- graph summaries for legacy/current-upstream models;
- a fixed-batch legacy model using ORT's official dynamic-shape utility semantics;
- an ORT-optimized fixed-batch legacy model;
- CPU semantic comparison against the legacy shipped model.

This tool does not make a production selection and does not require DirectML.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import onnx
import onnxruntime as ort
from onnxruntime.tools.onnx_model_utils import (
    fix_output_shapes,
    make_dim_param_fixed,
)


SHAPE_OPS = {"Shape", "Gather", "Concat", "Reshape", "Flatten", "Unsqueeze", "Squeeze", "Slice"}


def shape_of(value):
    tensor = value.type.tensor_type
    if not tensor.HasField("shape"):
        return None
    dims = []
    for dim in tensor.shape.dim:
        if dim.HasField("dim_value"):
            dims.append(int(dim.dim_value))
        elif dim.HasField("dim_param"):
            dims.append(str(dim.dim_param))
        else:
            dims.append("?")
    return dims


def iter_graphs(graph):
    yield graph
    for node in graph.node:
        for attr in node.attribute:
            if attr.HasField("g"):
                yield from iter_graphs(attr.g)
            elif attr.graphs:
                for subgraph in attr.graphs:
                    yield from iter_graphs(subgraph)


def graph_summary(path: Path):
    model = onnx.load(str(path), load_external_data=False)
    op_counts = Counter()
    shape_nodes = []
    dynamic_values = []
    initializer_names = set()

    for graph in iter_graphs(model.graph):
        initializer_names.update(x.name for x in graph.initializer)
        for node in graph.node:
            op_counts[node.op_type] += 1
            if node.op_type in SHAPE_OPS:
                shape_nodes.append({
                    "name": node.name,
                    "op_type": node.op_type,
                    "inputs": list(node.input),
                    "outputs": list(node.output),
                })
        for value in list(graph.input) + list(graph.value_info) + list(graph.output):
            shape = shape_of(value)
            if shape and any(isinstance(dim, str) for dim in shape):
                dynamic_values.append({"name": value.name, "shape": shape})

    return {
        "path": str(path),
        "size_bytes": path.stat().st_size,
        "ir_version": int(model.ir_version),
        "opsets": [{"domain": x.domain, "version": int(x.version)} for x in model.opset_import],
        "inputs": [{"name": x.name, "shape": shape_of(x)} for x in model.graph.input],
        "outputs": [{"name": x.name, "shape": shape_of(x)} for x in model.graph.output],
        "node_count": sum(op_counts.values()),
        "initializer_count": len(initializer_names),
        "op_counts": dict(sorted(op_counts.items())),
        "shape_related_count": len(shape_nodes),
        "shape_related_nodes": shape_nodes,
        "dynamic_value_count": len(dynamic_values),
        "dynamic_values": dynamic_values,
    }


def make_fixed_legacy(source: Path, output: Path):
    model = onnx.load(str(source))
    make_dim_param_fixed(model.graph, "batch", 1)
    fix_output_shapes(model)
    model = onnx.shape_inference.infer_shapes(model)
    onnx.checker.check_model(model)
    onnx.save(model, str(output))


def optimize_cpu(source: Path, output: Path):
    options = ort.SessionOptions()
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    options.optimized_model_filepath = str(output)
    session = ort.InferenceSession(
        str(source),
        sess_options=options,
        providers=["CPUExecutionProvider"],
    )
    # Force initialization and one run. Model input is fixed batch=1.
    data = np.zeros((1, 3, 112, 112), dtype=np.float32)
    session.run(None, {session.get_inputs()[0].name: data})
    if not output.is_file():
        raise RuntimeError("ORT did not write optimized model")


def cpu_outputs(model: Path, seeds=(11, 29, 47, 71, 101)):
    session = ort.InferenceSession(str(model), providers=["CPUExecutionProvider"])
    input_name = session.get_inputs()[0].name
    rows = []
    for seed in seeds:
        rng = np.random.default_rng(seed)
        data = rng.standard_normal((1, 3, 112, 112), dtype=np.float32)
        value = np.asarray(session.run(None, {input_name: data})[0], dtype=np.float64)
        rows.append({"seed": seed, "shape": list(value.shape), "value": value.reshape(-1).tolist()})
    return rows


def compare_outputs(reference_rows, candidate_rows):
    if len(reference_rows) != len(candidate_rows):
        return {"comparable": False, "reason": "row_count"}
    rows = []
    allclose = True
    max_abs = 0.0
    for ref, cand in zip(reference_rows, candidate_rows):
        a = np.asarray(ref["value"], dtype=np.float64)
        b = np.asarray(cand["value"], dtype=np.float64)
        if a.shape != b.shape:
            return {"comparable": False, "reason": "shape", "seed": ref["seed"]}
        delta = float(np.max(np.abs(a - b))) if a.size else 0.0
        close = bool(np.allclose(a, b, rtol=1e-6, atol=1e-7))
        max_abs = max(max_abs, delta)
        allclose = allclose and close
        rows.append({"seed": ref["seed"], "max_abs_diff": delta, "allclose": close})
    return {"comparable": True, "allclose": allclose, "max_abs_diff": max_abs, "rows": rows}


def reshape_producer_paths(path: Path):
    model = onnx.load(str(path), load_external_data=False)
    producers = {}
    nodes = list(model.graph.node)
    for node in nodes:
        for output in node.output:
            producers[output] = node

    paths = []
    for node in nodes:
        if node.op_type not in {"Reshape", "Flatten"}:
            continue
        entry = {
            "node": node.name,
            "op_type": node.op_type,
            "inputs": list(node.input),
            "shape_input_chain": [],
        }
        if node.op_type == "Reshape" and len(node.input) > 1:
            current = node.input[1]
            seen = set()
            for _ in range(12):
                if current in seen:
                    break
                seen.add(current)
                producer = producers.get(current)
                if producer is None:
                    entry["shape_input_chain"].append({"value": current, "producer": None})
                    break
                entry["shape_input_chain"].append({
                    "value": current,
                    "producer": producer.op_type,
                    "name": producer.name,
                    "inputs": list(producer.input),
                })
                if not producer.input:
                    break
                dynamic_candidates = [
                    x for x in producer.input
                    if x in producers and producers[x].op_type in SHAPE_OPS
                ]
                if not dynamic_candidates:
                    break
                current = dynamic_candidates[0]
        paths.append(entry)
    return paths


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--legacy", type=Path, required=True)
    parser.add_argument("--upstream", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    fixed = args.out_dir / "ediffiqa_t_legacy_batch1_fixed.onnx"
    optimized = args.out_dir / "ediffiqa_t_legacy_batch1_optimized.onnx"

    make_fixed_legacy(args.legacy, fixed)
    optimize_cpu(fixed, optimized)

    reference = cpu_outputs(args.legacy)
    candidates = {
        "legacy_fixed": fixed,
        "legacy_fixed_optimized": optimized,
        "upstream_current": args.upstream,
    }

    report = {
        "schema_version": 1,
        "legacy": graph_summary(args.legacy),
        "legacy_reshape_paths": reshape_producer_paths(args.legacy),
        "candidates": {},
    }

    for name, path in candidates.items():
        outputs = cpu_outputs(path)
        report["candidates"][name] = {
            "summary": graph_summary(path),
            "reshape_paths": reshape_producer_paths(path),
            "cpu_equivalence": compare_outputs(reference, outputs),
        }

    report_path = args.out_dir / "ediffiqa-graph-lab.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(report_path)


if __name__ == "__main__":
    main()
