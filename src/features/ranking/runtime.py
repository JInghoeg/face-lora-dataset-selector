"""ONNX Runtime configuration owned by the Ranking feature."""
from __future__ import annotations

from infrastructure.runtime_tuning import configure_ort_cpu_options


EDIFFIQA_BATCH_DIMENSION = "batch"
EDIFFIQA_BATCH_SIZE = 1


def configure_ediffiqa_session_options(ort_module):
    """Build eDifFIQA session options for the app's real batch-1 usage.

    eDifFIQA-T is exported with a symbolic input batch dimension, while the
    selector always evaluates exactly one aligned face at a time. Pinning the
    symbolic dimension to 1 is semantically exact for this product path and is
    also the DirectML-recommended way to avoid dynamic-shape execution where
    the input size is actually known.
    """
    options = configure_ort_cpu_options(ort_module)
    options.add_free_dimension_override_by_name(
        EDIFFIQA_BATCH_DIMENSION,
        EDIFFIQA_BATCH_SIZE,
    )
    return options
