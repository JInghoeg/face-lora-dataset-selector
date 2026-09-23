"""本地 LoRA 数据集筛选与批量字幕清理。"""
from __future__ import annotations
import csv, hashlib, json, math, os, pickle, shutil, sys, tempfile, time, traceback, uuid
from collections import Counter, defaultdict, OrderedDict
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

try:
    import cv2, numpy as np
    from PIL import Image, ImageOps
    from PySide6.QtCore import QCoreApplication, QEvent, QObject, QThread, Qt, Signal, QSize, QTimer, QRectF
    from PySide6.QtGui import QColor, QIcon, QImage, QImageReader, QPainter, QPen, QPixmap
    from PySide6.QtWidgets import QApplication, QButtonGroup, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QDialog, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QInputDialog, QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPushButton, QProgressBar, QSpinBox, QSplitter, QTabWidget, QVBoxLayout, QWidget
    import pyqtgraph as pg
    from application import SelectorApplication
    from core.models import AnalysisFinding, FaceDetection, AISuggestion, ViewSpec, Photo, TextPhoto, view_field_value, photo_matches_filters, derive_eligibility
    from features.ranking import SCALES, YAWS, rank, recommendation_blockers, recommendation_qualified
    from ui.qt import AutoCropROIWidget, AutoCropReviewDialog, DatasetListModel, DatasetListView, DatasetViewRow, DuplicateReviewDialog, ImagePreview, SubtitleTab, ThumbnailWorker
    from ui.i18n import SUPPORTED_LANGUAGES, get_language_manager, initialize_i18n
    from infrastructure.filesystem import IMAGE_EXTENSIONS as EXT
except ImportError as exc:
    msg=f"缺少依赖：{exc}\n请先双击运行 安装.bat，或在本目录运行：python -m pip install -r requirements.txt"
    print(msg)
    if getattr(sys,'frozen',False):
        try:Path(sys.executable).with_name('startup-error.txt').write_text(msg,encoding='utf-8')
        except Exception:pass
    sys.exit(1)

APP_DIR=Path(__file__).resolve().parent; MODELS=APP_DIR/'models'
BACKEND=SelectorApplication()
CACHE=BACKEND.cache_root;THUMB_CACHE=CACHE/'thumbnails'
POSE=MODELS/'pose_landmarker_lite.task'; YUNET=MODELS/'yunet_2023mar.onnx'; EDIFF=MODELS/'ediffiqa_t.onnx'; BRISQUE=MODELS/'brisque_model_live.yml'; BRISQUE_RANGE=MODELS/'brisque_range_live.yml'; DDDFA=MODELS/'mb1_120x120.onnx'; DDDFA_NORM=MODELS/'param_mean_std_62d_120x120.pkl'; COMPOSITE_MODEL_CACHE=MODELS/'composite_split_cache'
POSE_URL='https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task'
ANALYSIS_VERSION=4
PAGE=120; PRESET_TARGETS=(40,50,60,70,80); COLORS={'推荐':'#d9f4df','备选':'#fff2bf','淘汰':'#ffd9d9'}; PITCHES=('正常','仰头','低头')

def key(path): return str(path.resolve()).casefold()
def human_bytes(value):
    n=float(max(0,value))
    for unit in ('B','KB','MB','GB'):
        if n<1024 or unit=='GB':return f'{n:.0f} {unit}' if unit in ('B','KB') else f'{n:.1f} {unit}'
        n/=1024
def combo_value(combo):
    value=combo.currentData()
    return combo.currentText() if value is None else value
def set_combo_value(combo,value):
    i=combo.findData(value)
    if i<0:i=combo.findText(value)
    if i>=0:combo.setCurrentIndex(i)

def ui_language_manager():
    try:return get_language_manager()
    except RuntimeError:
        app=QApplication.instance()
        if app is None:raise
        return initialize_i18n(app)

def clamp_page(page,item_count,page_size=PAGE):
    pages=max(1,math.ceil(max(0,item_count)/page_size))
    return max(0,min(int(page),pages-1)),pages
def infer_target_mode(target,saved_mode=None):
    if saved_mode in ('preset','custom'):return saved_mode
    return 'preset' if int(target) in PRESET_TARGETS else 'custom'

def load_data(folder): return BACKEND.load_dataset_state(folder)
def load_cached(folder): return BACKEND.cache.load_cached(folder)
def load_cached_by_hash(folder): return BACKEND.cache.load_cached_by_hash(folder)
def historical_records(folder): return BACKEND.cache.historical_records(folder)
def legacy_manual_states(folder): return BACKEND.cache.legacy_manual_states(folder)
def finding_from_dict(value): return BACKEND.cache._finding_from_dict(value)
def face_detection_from_dict(value): return BACKEND.cache._face_detection_from_dict(value)
def ai_suggestion_from_dict(value): return BACKEND.cache.ai_suggestion_from_dict(value)
def photo_to_dict(photo): return BACKEND.cache.photo_to_dict(photo)
def photo_from_dict(data,path,size,mtime): return BACKEND.cache.photo_from_dict(data,path,size,mtime)
def view_spec_from_dict(value): return BACKEND.decode_view_spec(value)
def saved_views_from_data(folder): return BACKEND.saved_views(folder)
def save_data(folder,records,target,saved_views=None,bundle_ids=None,last_view=None,pending_composite_outputs=None,target_mode=None):
    return BACKEND.save_dataset_state(folder,records,target,saved_views,bundle_ids,last_view,pending_composite_outputs,target_mode)


def finding_text(f):
    return f.detail or f.code
AI_BUNDLE_SCHEMA=1

def relative_export_path(path,root):
    try:return str(path.resolve().relative_to(root.resolve()))
    except Exception:return path.name

def export_source_label(photo,root):
    if '_frame_' in photo.path.stem:return photo.path.stem.split('_frame_',1)[0]
    try:
        rel=photo.path.parent.resolve().relative_to(root.resolve())
        return str(rel) if str(rel)!='.' else root.name
    except Exception:return photo.path.parent.name

def manifest_entry(photo,root):
    return {
        'sample_id':photo.sample_id,
        'content_sha256':photo.content_sha256,
        'relative_path':relative_export_path(photo.path,root),
        'filename':photo.path.name,
        'source':export_source_label(photo,root),
        'width':photo.width,
        'height':photo.height,
        'selection':{
            'auto_status':photo.auto_status,
            'manual_status':photo.manual_status,
            'effective_status':photo.status,
            'eligibility':photo.eligibility,
        },
        'analysis':{
            'face_count':photo.faces,
            'primary_face_id':photo.primary_face_id,
            'face_ratio':photo.face_ratio,
            'face_px':photo.face_px,
            'face_quality':photo.face_quality,
            'brisque':photo.brisque,
            'sharpness':photo.blur,
            'brightness':photo.brightness,
            'yaw':photo.yaw,
            'pitch':photo.pitch,
            'roll':photo.roll,
            'angle_class':photo.angle_class,
            'pitch_class':photo.pitch_class,
            'person_scale':photo.person_scale,
            'duplicate_group':photo.duplicate_group,
            'duplicate_ignore':photo.duplicate_ignore,
        },
        'face_detections':[asdict(x) for x in photo.face_detections],
        'review_flags':[asdict(x) for x in photo.review_flags],
        'hard_rejects':[asdict(x) for x in photo.hard_rejects],
        'recommendation_reasons':list(photo.recommendation_reasons),
        'ai_suggestion':asdict(photo.ai_suggestion) if photo.ai_suggestion else None,
    }

def flat_manifest_entry(photo,root):
    return {
        'sample_id':photo.sample_id,
        'filename':photo.path.name,
        'relative_path':relative_export_path(photo.path,root),
        'width':photo.width,
        'height':photo.height,
        'effective_status':photo.status,
        'manual_status':photo.manual_status or '',
        'eligibility':photo.eligibility,
        'face_count':photo.faces,
        'face_ratio':photo.face_ratio,
        'face_px':photo.face_px,
        'face_quality':photo.face_quality,
        'brisque':photo.brisque,
        'sharpness':photo.blur,
        'brightness':photo.brightness,
        'yaw':photo.yaw,
        'pitch':photo.pitch,
        'roll':photo.roll,
        'angle_class':photo.angle_class,
        'pitch_class':photo.pitch_class,
        'person_scale':photo.person_scale,
        'duplicate_group':photo.duplicate_group,
        'review_flag_codes':'|'.join(x.code for x in photo.review_flags),
        'hard_reject_codes':'|'.join(x.code for x in photo.hard_rejects),
        'recommendation_reasons':'|'.join(photo.recommendation_reasons),
    }

def dataset_summary(records,view_description=''):
    return {
        'total_samples':len(records),
        'status_counts':dict(Counter(r.status for r in records)),
        'eligibility_counts':dict(Counter(r.eligibility for r in records)),
        'shot_size_distribution':dict(Counter(r.person_scale for r in records)),
        'yaw_distribution':dict(Counter(r.angle_class for r in records)),
        'pitch_distribution':dict(Counter(r.pitch_class for r in records)),
        'duplicate_group_count':len({r.duplicate_group for r in records if r.duplicate_group}),
        'duplicate_member_count':sum(bool(r.duplicate_group) for r in records),
        'duplicate_ignored_count':sum(r.duplicate_ignore for r in records),
        'secondary_face_flag_count':sum(any(x.code=='secondary_faces_detected' for x in r.review_flags) for r in records),
        'no_face_count':sum(r.faces==0 for r in records),
        'hard_reject_count':sum(bool(r.hard_rejects) for r in records),
        'view_description':view_description,
    }

def prepare_review_patch(data,records,patch_id='review_patch'):
    if not isinstance(data,dict):raise ValueError('review patch 必须是 JSON object')
    if data.get('schema_version')!=AI_BUNDLE_SCHEMA:raise ValueError(f'不支持的 schema_version：{data.get("schema_version")}')
    bundle_id=str(data.get('bundle_id','')).strip()
    if not bundle_id:raise ValueError('缺少 bundle_id')
    suggestions=data.get('suggestions')
    if not isinstance(suggestions,list):raise ValueError('suggestions 必须是数组')
    ids=[x.get('sample_id') for x in suggestions if isinstance(x,dict)]
    if len(ids)!=len(suggestions) or any(not isinstance(x,str) or not x for x in ids):raise ValueError('每条 suggestion 都必须有有效 sample_id')
    if len(set(ids))!=len(ids):raise ValueError('同一 patch 中存在重复 sample_id')
    by_id={r.sample_id:r for r in records};pending=[];unknown=[];stale=[];allowed_e={None,'PASS','REVIEW','REJECT'};allowed_s={None,'推荐','备选','淘汰'}
    for item in suggestions:
        sid=item['sample_id'];target=by_id.get(sid)
        if target is None:unknown.append(sid);continue
        supplied=item.get('content_sha256')
        if supplied and supplied!=target.content_sha256:stale.append(sid);continue
        se=item.get('suggested_eligibility');ss=item.get('suggested_status');flags=item.get('flags',[]);note=item.get('note','');full=item.get('request_full_resolution',False)
        if se not in allowed_e:raise ValueError(f'{sid}: suggested_eligibility 无效')
        if ss not in allowed_s:raise ValueError(f'{sid}: suggested_status 无效')
        if not isinstance(flags,list) or any(not isinstance(x,str) for x in flags):raise ValueError(f'{sid}: flags 必须是字符串数组')
        if not isinstance(note,str) or not isinstance(full,bool):raise ValueError(f'{sid}: note/request_full_resolution 类型无效')
        pending.append((target,AISuggestion(patch_id,bundle_id,se,ss,list(flags),note,full,'pending')))
    return bundle_id,pending,unknown,stale

def write_contact_sheets(records,out_dir,prefix):
    out_dir.mkdir(parents=True,exist_ok=True)
    cols,rows=4,4;tile_w,tile_h=250,220;img_w,img_h=220,150;per_page=cols*rows
    written=[]
    for page_no,start in enumerate(range(0,len(records),per_page),1):
        page=QImage(cols*tile_w,rows*tile_h,QImage.Format_RGB32);page.fill(QColor('#ffffff'));p=QPainter(page)
        for slot,r in enumerate(records[start:start+per_page]):
            row,col=divmod(slot,cols);x=col*tile_w;y=row*tile_h
            p.setPen(QPen(QColor('#c8c8c8')));p.drawRect(x+4,y+4,tile_w-8,tile_h-8)
            reader=QImageReader(str(r.path));reader.setAutoTransform(True);im=reader.read()
            if not im.isNull():
                scaled=im.scaled(img_w,img_h,Qt.KeepAspectRatio,Qt.SmoothTransformation);px=x+(tile_w-scaled.width())//2;py=y+8+(img_h-scaled.height())//2;p.drawImage(px,py,scaled)
            p.setPen(QPen(QColor('#111111')));p.drawText(x+10,y+170,r.sample_id);p.drawText(x+10,y+188,r.path.name[:30]);p.drawText(x+10,y+206,f'{r.status} / {r.eligibility}')
        p.end();path=out_dir/f'{prefix}_{page_no:03d}.jpg';page.save(str(path),'JPG',88);written.append(path.name)
    return written

def required(paths):
    missing=[str(x) for x in paths if not x.exists()]
    if missing:raise RuntimeError('缺少模型文件：\n'+'\n'.join(missing))
class Analyzer(QObject):
    status=Signal(str); progress=Signal(int,int,str); finished=Signal(object); failed=Signal(str)
    def __init__(self,folder):
        super().__init__();self.folder=folder;self.had_v3_cache=False;self.changed_count=0;self.added_count=0;self.modified_count=0;self.deleted_count=0;self.unchanged_count=0
    def run(self):
        try:
            result=BACKEND.refresh_dataset(
                self.folder,
                status=self.status.emit,
                progress=self.progress.emit,
            )
            self.had_v3_cache=result.had_v3_cache
            self.changed_count=result.changed_count
            self.added_count=result.added_count
            self.modified_count=result.modified_count
            self.deleted_count=result.deleted_count
            self.unchanged_count=result.unchanged_count
            self.finished.emit(result.records)
        except Exception:
            self.failed.emit(traceback.format_exc())
class CompositeScanWorker(QObject):
    progress=Signal(int,int,str); finished=Signal(object); failed=Signal(str)
    def __init__(self,records):super().__init__();self.records=records
    def run(self):
        try:
            todo=[r for r in self.records if r.status=='推荐' and r.composite_scan_version!=BACKEND.composite_proposal_version]
            total=len(todo)
            for i,r in enumerate(todo,1):
                with Image.open(r.path) as im:
                    try:im.seek(0)
                    except EOFError:pass
                    image=ImageOps.exif_transpose(im).convert('RGB')
                r.composite_proposal=BACKEND.composite_detect_proposal(image,COMPOSITE_MODEL_CACHE)
                r.composite_scan_version=BACKEND.composite_proposal_version
                self.progress.emit(i,total,r.path.name)
            self.finished.emit(self.records)
        except Exception:self.failed.emit(traceback.format_exc())

class AutoCropScanWorker(QObject):
    progress=Signal(int,int,str); finished=Signal(object); failed=Signal(str)
    def __init__(self,records):super().__init__();self.records=records
    def run(self):
        try:
            result=BACKEND.scan_auto_crop(
                self.records,
                progress=self.progress.emit,
            )
            self.finished.emit(result)
        except Exception:self.failed.emit(traceback.format_exc())

class SourceOrganizerWorker(QObject):
    progress=Signal(int,int,str); finished=Signal(object); failed=Signal(str)
    def __init__(self,plan):super().__init__();self.plan=plan
    def run(self):
        try:
            result=BACKEND.execute_source_organizer(
                self.plan,
                progress=self.progress.emit,
            )
            self.finished.emit(result)
        except Exception:self.failed.emit(traceback.format_exc())

class IncrementalAnalysisWorker(QObject):
    progress=Signal(int,int,str); finished=Signal(object); failed=Signal(str)
    def __init__(self,items):super().__init__();self.items=list(items)
    def run(self):
        try:
            records=BACKEND.analyze_generated(
                self.items,
                progress=self.progress.emit,
            )
            self.finished.emit(records)
        except Exception:self.failed.emit(traceback.format_exc())

class CompositeSplitReviewDialog(QDialog):
    def __init__(self,records,changed,accept_materialized,parent=None):
        super().__init__(parent);self.records=[r for r in records if r.status=='推荐' and r.composite_proposal is not None];self.changed=changed;self.accept_materialized=accept_materialized;self.current=-1;self.output_keep={}
        self.resize(1320,820);self.ui();self.retranslate();self.reload()
    @staticmethod
    def quad(box):
        x0,y0,x1,y1=map(int,box);return [[x0,y0],[x1,y0],[x1,y1],[x0,y1]]
    @staticmethod
    def pixmap_from_bgr(img,max_size=220):
        if img is None or not img.size:return QPixmap()
        h,w=img.shape[:2];rgb=cv2.cvtColor(img,cv2.COLOR_BGR2RGB);q=QImage(rgb.data,w,h,rgb.strides[0],QImage.Format_RGB888).copy();pix=QPixmap.fromImage(q)
        return pix.scaled(max_size,max_size,Qt.KeepAspectRatio,Qt.SmoothTransformation)
    def ui(self):
        root=QVBoxLayout(self);split=QSplitter(Qt.Horizontal)
        self.items=QListWidget();self.items.setMinimumWidth(310);self.items.itemClicked.connect(self.show_item);split.addWidget(self.items)
        right=QWidget();rl=QVBoxLayout(right);self.info=QLabel('');self.info.setWordWrap(True);self.info.setStyleSheet('font-weight:600;');rl.addWidget(self.info)
        self.preview=ImagePreview();rl.addWidget(self.preview,1)
        self.output_hint=QLabel('');rl.addWidget(self.output_hint);self.outputs=QListWidget();self.outputs.setViewMode(QListWidget.IconMode);self.outputs.setResizeMode(QListWidget.Adjust);self.outputs.setMovement(QListWidget.Static);self.outputs.setIconSize(QSize(220,220));self.outputs.setGridSize(QSize(250,280));self.outputs.setMaximumHeight(320);self.outputs.itemChanged.connect(self.output_selection_changed);rl.addWidget(self.outputs)
        actions=QHBoxLayout();self.accept_button=QPushButton('');self.accept_button.clicked.connect(lambda:self.set_decision('accepted'));self.reject_button=QPushButton('');self.reject_button.clicked.connect(lambda:self.set_decision('rejected'));self.pending_button=QPushButton('');self.pending_button.clicked.connect(lambda:self.set_decision('pending'));actions.addWidget(self.accept_button);actions.addWidget(self.reject_button);actions.addWidget(self.pending_button);actions.addStretch(1);self.close_button=QPushButton('');self.close_button.clicked.connect(self.accept);actions.addWidget(self.close_button);rl.addLayout(actions)
        split.addWidget(right);split.setSizes([330,990]);root.addWidget(split)
    @staticmethod
    def _tr_composite(source):
        return QCoreApplication.translate('CompositeSplitReviewDialog',source)
    def decision_text(self,value):
        return {'accepted':self._tr_composite('已接受'),'rejected':self._tr_composite('已拒绝'),'pending':self._tr_composite('待定')}.get(value,value)
    def retranslate(self):
        self.setWindowTitle(self._tr_composite('组合图拆分复核'))
        self.output_hint.setText(self._tr_composite('建议输出预览（默认全选；取消勾选 = 生成后直接送入淘汰）'))
        self.accept_button.setText(self._tr_composite('接受建议'));self.reject_button.setText(self._tr_composite('拒绝'));self.pending_button.setText(self._tr_composite('恢复待定'));self.close_button.setText(self._tr_composite('关闭'))
        if not self.records:self.info.setText(self._tr_composite('当前没有待复核的组合图拆分推荐图'))
        for row,r in enumerate(self.records):
            item=self.items.item(row)
            if item is not None:item.setText(self.label(r))
        current=self.items.currentItem()
        if current is not None:self.show_item(current)
    def changeEvent(self,event):
        if event.type()==QEvent.LanguageChange and hasattr(self,'accept_button'):self.retranslate()
        super().changeEvent(event)
    def label(self,r):
        p=r.composite_proposal;mark={'accepted':'✓','rejected':'×','pending':'•'}.get(p.decision,'•');mode=self._tr_composite('拆分') if p.mode=='split_people' else self._tr_composite('群组裁剪');return f'{mark} {r.path.name}\n'+self._tr_composite('{mode} · {count} 个输出').format(mode=mode,count=len(p.output_boxes))
    def reload(self,select=None):
        self.items.clear()
        for i,r in enumerate(self.records):
            it=QListWidgetItem(self.label(r));it.setData(Qt.UserRole,i);self.items.addItem(it)
        if self.records:
            target=0 if select is None else max(0,min(select,len(self.records)-1));self.items.setCurrentRow(target);self.show_item(self.items.item(target))
    def show_item(self,it):
        if it is None:return
        self.current=it.data(Qt.UserRole);r=self.records[self.current];p=r.composite_proposal
        try:
            with Image.open(r.path) as source:
                try:source.seek(0)
                except EOFError:pass
                source=ImageOps.exif_transpose(source).convert('RGB')
                rgb=np.asarray(source)
            im=cv2.cvtColor(rgb,cv2.COLOR_RGB2BGR)
        except Exception:return
        boxes=[self.quad(b) for b in p.output_boxes];self.preview.set_data(im,boxes,[True]*len(boxes),[False]*len(boxes))
        mode=self._tr_composite('拆成独立人物/视角') if p.mode=='split_people' else self._tr_composite('重叠多人合并裁剪')
        self.info.setText(f'{r.path.name}\n'+self._tr_composite('{mode} · 输出 {count} 张').format(mode=mode,count=len(p.output_boxes))+'\n'+self._tr_composite('状态：{state}').format(state=self.decision_text(p.decision))+f'\n{p.detail}')
        record_key=r.sample_id or key(r.path);keep=self.output_keep.get(record_key)
        if not isinstance(keep,list) or len(keep)!=len(p.output_boxes):keep=[True]*len(p.output_boxes);self.output_keep[record_key]=keep
        self.outputs.blockSignals(True);self.outputs.clear()
        h,w=im.shape[:2]
        for n,b in enumerate(p.output_boxes,1):
            x0,y0,x1,y1=map(int,b);x0=max(0,min(w,x0));x1=max(0,min(w,x1));y0=max(0,min(h,y0));y1=max(0,min(h,y1));crop=im[y0:y1,x0:x1]
            state=self._tr_composite('推荐') if keep[n-1] else self._tr_composite('淘汰');item=QListWidgetItem(QIcon(self.pixmap_from_bgr(crop)),self._tr_composite('输出 {index}').format(index=n)+f'\n{x1-x0} × {y1-y0}\n→ {state}');item.setData(Qt.UserRole,n-1);item.setFlags(item.flags()|Qt.ItemIsUserCheckable);item.setCheckState(Qt.Checked if keep[n-1] else Qt.Unchecked);self.outputs.addItem(item)
        self.outputs.blockSignals(False)
    def output_selection_changed(self,item):
        if self.current<0:return
        r=self.records[self.current];record_key=r.sample_id or key(r.path);p=r.composite_proposal;keep=self.output_keep.setdefault(record_key,[True]*len(p.output_boxes));index=item.data(Qt.UserRole)
        if isinstance(index,int) and 0<=index<len(keep):
            keep[index]=item.checkState()==Qt.Checked;self.outputs.blockSignals(True);state=self._tr_composite('推荐') if keep[index] else self._tr_composite('淘汰');item.setText(item.text().rsplit('\n→ ',1)[0]+f"\n→ {state}");self.outputs.blockSignals(False)
    def set_decision(self,value):
        if self.current<0:return
        r=self.records[self.current]
        if value=='accepted':
            record_key=r.sample_id or key(r.path);keep=list(self.output_keep.get(record_key,[True]*len(r.composite_proposal.output_boxes)))
            if not self.accept_materialized(r,keep):return
            self.records.pop(self.current);self.changed()
            if self.records:self.reload(min(self.current,len(self.records)-1))
            else:
                self.current=-1;self.items.clear();self.outputs.clear();self.info.setText(self._tr_composite('当前没有待复核的组合图拆分推荐图'));self.preview.set_data(None,[],[],[])
            return
        r.composite_proposal.decision=value;self.changed();next_index=min(self.current+1,len(self.records)-1);self.reload(next_index)

class Window(QMainWindow):
    def __init__(self):super().__init__();self.records=[];self.folder=None;self.thread=None;self.worker=None;self.composite_thread=None;self.composite_worker=None;self.auto_crop_thread=None;self.auto_crop_worker=None;self.organizer_thread=None;self.organizer_worker=None;self.incremental_thread=None;self.incremental_worker=None;self.pending_composite_outputs={};self.page=0;self.target=60;self.target_mode='preset';self.quick_mode='';self.saved_views=[];self.exported_bundle_ids=[];self.pending_last_view=None;self.thumb_memory=OrderedDict();self.thumb_generation=0;self.thumb_threads=[];self.resize(1400,880);self.ui();self.retranslate_shell()
    @staticmethod
    def _tr_main(source):
        return QCoreApplication.translate('MainWindow',source)
    def retranslate_shell(self):
        self.setWindowTitle(self._tr_main('LoRA 数据集筛选与字幕清理'))
        if hasattr(self,'tabs'):
            self.tabs.setTabText(self.dataset_tab_index,self._tr_main('LoRA 数据集筛选'))
            if self.text_cleanup_tab_index>=0:
                self.tabs.setTabText(self.text_cleanup_tab_index,self._tr_main('批量去字幕 / 水印'))
        if hasattr(self,'language_combo'):
            manager=ui_language_manager();index=self.language_combo.findData(manager.language)
            if index>=0 and index!=self.language_combo.currentIndex():
                self.language_combo.blockSignals(True);self.language_combo.setCurrentIndex(index);self.language_combo.blockSignals(False)
        self.update_composite_button();self.update_auto_crop_button()
    def change_language(self):
        if not hasattr(self,'language_combo'):return
        manager=ui_language_manager();language=self.language_combo.currentData()
        if language==manager.language:return
        if not manager.set_language(language):
            QMessageBox.warning(self,'Language / 语言',f'无法加载语言资源：\n{manager.last_error}')
            index=self.language_combo.findData(manager.language)
            if index>=0:
                self.language_combo.blockSignals(True);self.language_combo.setCurrentIndex(index);self.language_combo.blockSignals(False)
    def changeEvent(self,event):
        if event.type()==QEvent.LanguageChange:self.retranslate_shell()
        super().changeEvent(event)
    def ui(self):
        self.tabs=QTabWidget();self.setCentralWidget(self.tabs);w=QWidget();self.dataset_tab_index=self.tabs.addTab(w,'');self.sub=SubtitleTab(BACKEND,APP_DIR,THUMB_CACHE) if BACKEND.feature_available('text_cleanup') else None
        self.text_cleanup_tab_index=-1
        if self.sub is not None:self.text_cleanup_tab_index=self.tabs.addTab(self.sub,'')
        l=QVBoxLayout(w);t=QHBoxLayout();self.pick=QPushButton('选择图片文件夹');self.pick.clicked.connect(self.choose);self.rescan=QPushButton('刷新文件夹（F5）');self.rescan.clicked.connect(self.start);self.rescan.setShortcut('F5');self.rescan.setToolTip('重新扫描当前文件夹：只分析新增/修改图片，删除的从列表移除，未变化图片读取缓存。');self.rescan.setEnabled(False);self.folder_label=QLabel('尚未选择文件夹');self.progress=QLabel('准备就绪');t.addWidget(self.pick);t.addWidget(self.rescan);t.addWidget(self.folder_label,1);t.addWidget(self.progress);self.language_label=QLabel('语言 / Language');self.language_combo=QComboBox()
        for code,label in SUPPORTED_LANGUAGES:self.language_combo.addItem(label,code)
        manager=ui_language_manager();language_index=self.language_combo.findData(manager.language)
        if language_index>=0:self.language_combo.setCurrentIndex(language_index)
        self.language_combo.currentIndexChanged.connect(lambda _=None:self.change_language());t.addWidget(self.language_label);t.addWidget(self.language_combo);l.addLayout(t)
        rec=QHBoxLayout();rec.addWidget(QLabel('自动推荐目标：'));self.group=QButtonGroup(self);self.group.setExclusive(True)
        for n in PRESET_TARGETS:
            b=QPushButton(str(n));b.setCheckable(True);b.setChecked(n==60);b.clicked.connect(lambda _,x=n:self.run_rec(x,'preset'));self.group.addButton(b,n);rec.addWidget(b)
        self.custom_mode=QPushButton('自定义');self.custom_mode.setCheckable(True);self.custom_mode.clicked.connect(self.apply_custom_target);self.group.addButton(self.custom_mode,0);rec.addWidget(self.custom_mode)
        self.custom=QSpinBox();self.custom.setRange(1,3000);self.custom.setValue(60);self.custom.setToolTip('仅输入数字；点击“应用”后切换到自定义目标。');ap=QPushButton('应用');ap.clicked.connect(self.apply_custom_target);rec.addWidget(self.custom);rec.addWidget(ap);rec.addSpacing(14)
        self.show_face_boxes=QCheckBox('显示人脸检测框');self.show_face_boxes.toggled.connect(lambda _=False:self.refresh());rec.addWidget(self.show_face_boxes);dup_review=QPushButton('Duplicate Group 复核…');dup_review.clicked.connect(self.open_duplicate_review);dup_review.setVisible(BACKEND.feature_available('duplicates'));rec.addWidget(dup_review);self.composite_btn=QPushButton('');self.composite_btn.clicked.connect(self.open_composite_review);self.composite_btn.setEnabled(False);self.composite_btn.setVisible(BACKEND.feature_available('composite'));rec.addWidget(self.composite_btn);self.auto_crop_btn=QPushButton('自动裁剪 复核…');self.auto_crop_btn.clicked.connect(self.open_auto_crop_review);self.auto_crop_btn.setEnabled(False);self.auto_crop_btn.setVisible(BACKEND.feature_available('auto_crop'));rec.addWidget(self.auto_crop_btn);self.organizer_btn=QPushButton('整理源文件…');self.organizer_btn.clicked.connect(self.open_source_organizer);self.organizer_btn.setEnabled(False);self.organizer_btn.setVisible(BACKEND.feature_available('source_organizer'));self.organizer_btn.setToolTip('可选：按当前最终状态移动到 推荐 / 备选 / 淘汰；先预览计划，确认后事务执行。');rec.addWidget(self.organizer_btn);rec.addStretch(1);self.export=QPushButton('导出推荐图片…');self.export.clicked.connect(self.exported);self.export.setEnabled(False);rec.addWidget(self.export);l.addLayout(rec)

        filter_box=QGroupBox('1. 筛选：只决定“显示哪些图片”');fg=QHBoxLayout(filter_box)
        self.view_combo=QComboBox();self.view_combo.addItems(['全部','推荐','备选','淘汰']);self.view_combo.currentTextChanged.connect(self.filters_changed);fg.addWidget(QLabel('最终状态'));fg.addWidget(self.view_combo)
        self.eligibility_combo=QComboBox();self.eligibility_combo.addItem('全部','全部');self.eligibility_combo.addItem('可直接用','PASS');self.eligibility_combo.addItem('需复核','REVIEW');self.eligibility_combo.addItem('硬淘汰','REJECT');self.eligibility_combo.currentIndexChanged.connect(self.filters_changed);fg.addWidget(QLabel('判定'));fg.addWidget(self.eligibility_combo)
        self.scale_combo=QComboBox();self.scale_combo.addItems(['全部',*SCALES]);self.scale_combo.currentTextChanged.connect(self.filters_changed);fg.addWidget(QLabel('景别'));fg.addWidget(self.scale_combo)
        self.yaw_combo=QComboBox();self.yaw_combo.addItems(['全部',*YAWS]);self.yaw_combo.currentTextChanged.connect(self.filters_changed);fg.addWidget(QLabel('水平角度'));fg.addWidget(self.yaw_combo)
        self.pitch_combo=QComboBox();self.pitch_combo.addItems(['全部',*PITCHES]);self.pitch_combo.currentTextChanged.connect(self.filters_changed);fg.addWidget(QLabel('俯仰'));fg.addWidget(self.pitch_combo)
        self.best_only=QCheckBox('重复组只看最佳');self.best_only.toggled.connect(self.filters_changed);fg.addWidget(self.best_only);clear_filters=QPushButton('清除筛选');clear_filters.clicked.connect(self.clear_filters);fg.addWidget(clear_filters);fg.addStretch(1);l.addWidget(filter_box)

        order_row=QHBoxLayout();sort_box=QGroupBox('2. 排序：只改变顺序');sg=QHBoxLayout(sort_box);self.sort_field_combo=QComboBox()
        for label,value in [('原始顺序','默认顺序'),('质量排序（FIQA→BRISQUE→清晰度）','质量排序'),('人脸识别质量（FIQA）','Face Quality'),('整图质量（BRISQUE）','BRISQUE'),('主脸清晰度','Sharpness'),('主脸像素','Face Pixels'),('最终状态','状态'),('判定状态','Eligibility'),('重复组','Duplicate Group'),('来源','来源目录 / 源视频'),('景别','景别'),('水平角度','Yaw'),('俯仰','Pitch')]:self.sort_field_combo.addItem(label,value)
        self.sort_field_combo.currentIndexChanged.connect(self.sort_changed);self.sort_dir_combo=QComboBox();self.sort_dir_combo.addItem('优先顺序','优先顺序');self.sort_dir_combo.addItem('反向','反向');self.sort_dir_combo.currentIndexChanged.connect(self.sort_changed);sg.addWidget(QLabel('按'));sg.addWidget(self.sort_field_combo);sg.addWidget(self.sort_dir_combo);order_row.addWidget(sort_box,1)
        extreme_box=QGroupBox('3. 极值检查：在当前筛选结果上取 Top / Bottom');eg=QHBoxLayout(extreme_box);self.rank_basis_combo=QComboBox()
        for label,value in [('质量排序（FIQA→BRISQUE→清晰度）','综合质量'),('人脸识别质量（FIQA）','Face Quality'),('整图质量（BRISQUE）','BRISQUE'),('主脸清晰度','Sharpness'),('主脸像素','Face Pixels')]:self.rank_basis_combo.addItem(label,value)
        self.rank_basis_combo.currentIndexChanged.connect(lambda _=None:self.quick_changed());self.quick_n=QSpinBox();self.quick_n.setRange(1,500);self.quick_n.setValue(10);self.quick_n.setPrefix('N=');self.quick_n.valueChanged.connect(lambda _=None:self.quick_changed());top_view=QPushButton('Top N');top_view.clicked.connect(lambda:self.quick('view_top'));bottom_view=QPushButton('Bottom N');bottom_view.clicked.connect(lambda:self.quick('view_bottom'));clear_top=QPushButton('关闭极值检查');clear_top.clicked.connect(lambda:self.quick(''));eg.addWidget(QLabel('依据'));eg.addWidget(self.rank_basis_combo);eg.addWidget(self.quick_n);eg.addWidget(top_view);eg.addWidget(bottom_view);eg.addWidget(clear_top);order_row.addWidget(extreme_box,2);l.addLayout(order_row)

        tools=QHBoxLayout();tools.addWidget(QLabel('保存视图'));self.saved_view_combo=QComboBox();self.saved_view_combo.addItem('未选择');tools.addWidget(self.saved_view_combo);save_view=QPushButton('保存当前视图');save_view.clicked.connect(self.save_current_view);load_view=QPushButton('载入');load_view.clicked.connect(self.load_selected_view);delete_view=QPushButton('删除');delete_view.clicked.connect(self.delete_selected_view);tools.addWidget(save_view);tools.addWidget(load_view);tools.addWidget(delete_view);tools.addStretch(1);export_view_ai=QPushButton('导出当前视图 AI 包…');export_view_ai.clicked.connect(lambda:self.export_ai_bundle('current_view'));export_all_ai=QPushButton('导出全部 AI 包…');export_all_ai.clicked.connect(lambda:self.export_ai_bundle('dataset'));import_ai=QPushButton('导入 AI 建议…');import_ai.clicked.connect(self.import_ai_patch);tools.addWidget(export_view_ai);tools.addWidget(export_all_ai);tools.addWidget(import_ai);l.addLayout(tools)
        view_head=QHBoxLayout();self.current_view_label=QLabel('当前视图：全部图片\n显示：0 / 0 张');self.current_view_label.setStyleSheet('font-weight:600; padding:7px; color:#1f2937; background:#eef3f8; border:1px solid #cbd5e1; border-radius:4px;');view_head.addWidget(self.current_view_label,1);self.shortcut_hint=QLabel('中键：推荐↔备选 ｜ 右键双击：淘汰');self.shortcut_hint.setStyleSheet('padding:5px 8px;color:#1f2937;background:#ffffff;border:1px solid #d1d5db;');view_head.addWidget(self.shortcut_hint);self.prev=QPushButton('上一页');self.prev.clicked.connect(lambda:self.change(-1));self.page_label=QLabel('第 0/0 页');self.next=QPushButton('下一页');self.next.clicked.connect(lambda:self.change(1));view_head.addWidget(self.prev);view_head.addWidget(self.page_label);view_head.addWidget(self.next);l.addLayout(view_head)
        s=QSplitter(Qt.Horizontal);self.dataset_model=DatasetListModel(self);self.grid=DatasetListView();self.grid.setModel(self.dataset_model);self.grid.clicked.connect(self.details);self.grid.doubleClicked.connect(self.open);self.grid.middleIndexClicked.connect(self.quick_toggle_item);self.grid.rightIndexDoubleClicked.connect(self.quick_reject_item);s.addWidget(self.grid);side=QWidget();sl=QVBoxLayout(side);self.stats=QLabel('目标 / 实际推荐：0 / 0');self.stats.setWordWrap(True);sl.addWidget(self.stats);self.stat_box=QGroupBox('统计（点击分类筛选）');self.stat_layout=QGridLayout(self.stat_box);sl.addWidget(self.stat_box);box=QGroupBox('图片分析数据');bl=QVBoxLayout(box);self.detail=QLabel('点击缩略图查看详情');self.detail.setWordWrap(True);bl.addWidget(self.detail);sl.addWidget(box);man=QGroupBox('人工状态（优先于自动结果）');ml=QGridLayout(man)
        for i,x in enumerate(('推荐','备选','淘汰')):b=QPushButton(x);b.clicked.connect(lambda _,v=x:self.manual(v));ml.addWidget(b,0,i)
        restore=QPushButton('恢复自动');restore.clicked.connect(self.restore);ml.addWidget(restore,1,0,1,3);sl.addWidget(man);ai_box=QGroupBox('AI 审核建议');ail=QVBoxLayout(ai_box);self.ai_label=QLabel('当前图片没有 AI 建议');self.ai_label.setWordWrap(True);ail.addWidget(self.ai_label);aib=QHBoxLayout();accept_ai=QPushButton('接受');accept_ai.clicked.connect(self.accept_ai_suggestion);reject_ai=QPushButton('拒绝');reject_ai.clicked.connect(self.reject_ai_suggestion);clear_ai=QPushButton('清除');clear_ai.clicked.connect(self.clear_ai_suggestion);aib.addWidget(accept_ai);aib.addWidget(reject_ai);aib.addWidget(clear_ai);ail.addLayout(aib);sl.addWidget(ai_box);sl.addStretch(1);s.addWidget(side);s.setSizes([1030,370]);l.addWidget(s,1)
    def choose(self):
        x=QFileDialog.getExistingDirectory(self,'选择训练图片目录',str(self.folder or APP_DIR))
        if x:
            self.folder=Path(x);d=load_data(self.folder);self.target=d.get('target',60) if isinstance(d.get('target',60),int) else 60;self.target_mode=infer_target_mode(self.target,d.get('target_mode'));self.saved_views=saved_views_from_data(self.folder);self.exported_bundle_ids=list(d.get('exported_bundle_ids',[])) if isinstance(d.get('exported_bundle_ids',[]),list) else [];self.pending_composite_outputs={}
            for item in d.get('pending_composite_outputs',[]):
                if isinstance(item,dict) and isinstance(item.get('path'),str) and item.get('status') in ('推荐','淘汰'):self.pending_composite_outputs[key(Path(item['path']))]={'path':item['path'],'status':item['status']}
            for legacy in d.get('pending_composite_recommend_paths',[]):
                if isinstance(legacy,str):self.pending_composite_outputs.setdefault(key(Path(legacy)),{'path':legacy,'status':'推荐'})
            self.pending_last_view=view_spec_from_dict(d.get('last_view')) if isinstance(d.get('last_view'),dict) else None;self.update_saved_view_combo();self.custom.setValue(self.target);self.sync_target_mode_ui();self.folder_label.setText(x);self.start()
    def start(self):
        if not self.folder or self.thread and self.thread.isRunning():return
        self.pick.setEnabled(False);self.rescan.setEnabled(False);self.export.setEnabled(False);self.composite_btn.setEnabled(False);self.auto_crop_btn.setEnabled(False);self.organizer_btn.setEnabled(False);self.dataset_model.clear();self.thread=QThread(self);self.worker=Analyzer(self.folder);self.worker.moveToThread(self.thread);self.thread.started.connect(self.worker.run);self.worker.status.connect(self.progress.setText);self.worker.progress.connect(lambda n,t,name:self.progress.setText(f'分析 {n}/{t}：{name}'));self.worker.finished.connect(self.done);self.worker.failed.connect(lambda e:QMessageBox.critical(self,'分析失败',e));self.worker.finished.connect(self.thread.quit);self.worker.failed.connect(self.thread.quit);self.thread.finished.connect(self.thread_done);self.thread.start()
    def done(self,rs):
        self.records=rs
        if self.pending_composite_outputs:
            found=[]
            for r in rs:
                k=key(r.path);item=self.pending_composite_outputs.get(k)
                if item:r.manual_status=item['status'];r.composite_scan_version=BACKEND.composite_proposal_version;r.composite_proposal=None;found.append(k)
            for k in found:self.pending_composite_outputs.pop(k,None)
        BACKEND.recompute_recommendations(rs,self.target);self.page=0;self.progress.setText(f'刷新完成：新增 {self.worker.added_count} / 删除 {self.worker.deleted_count} / 修改 {self.worker.modified_count} / 未变 {self.worker.unchanged_count}' if self.worker and self.worker.had_v3_cache else f'分析完成：{len(rs)} 张');self.pick.setEnabled(True);self.rescan.setEnabled(True);self.export.setEnabled(True);self.composite_btn.setEnabled(True);self.auto_crop_btn.setEnabled(True);self.organizer_btn.setEnabled(True);self.update_composite_button();self.update_auto_crop_button()
        if self.pending_last_view:
            spec=self.pending_last_view;self.pending_last_view=None;self.apply_view_spec(spec)
        else:
            self.quick_mode='';self.view_combo.setCurrentText('全部');self.refresh()
        self.save()
    def thread_done(self):self.worker=None;self.thread.deleteLater();self.thread=None
    @staticmethod
    def thumb(p):
        r=QImageReader(str(p));r.setAutoTransform(True);z=r.size()
        if z.isValid():z.scale(150,150,Qt.KeepAspectRatio);r.setScaledSize(z)
        i=r.read();return QPixmap.fromImage(i) if not i.isNull() else QPixmap()
    def filters_changed(self,*_):self.page=0;self.refresh();self.save()
    def sort_changed(self,*_):self.page=0;self.refresh();self.save()
    def quick_changed(self):
        if self.quick_mode:self.page=0;self.refresh();self.save()
    def current_view_spec(self,name=''):
        filters={}
        if self.view_combo.currentText()!='全部':filters['status']=self.view_combo.currentText()
        if self.scale_combo.currentText()!='全部':filters['person_scale']=self.scale_combo.currentText()
        if self.yaw_combo.currentText()!='全部':filters['angle_class']=self.yaw_combo.currentText()
        if self.pitch_combo.currentText()!='全部':filters['pitch_class']=self.pitch_combo.currentText()
        if combo_value(self.eligibility_combo)!='全部':filters['eligibility']=combo_value(self.eligibility_combo)
        return ViewSpec(name,filters,combo_value(self.sort_field_combo),combo_value(self.sort_dir_combo),self.best_only.isChecked(),self.quick_mode,self.quick_n.value(),combo_value(self.rank_basis_combo))
    def update_saved_view_combo(self):
        self.saved_view_combo.blockSignals(True);self.saved_view_combo.clear();self.saved_view_combo.addItem('未选择')
        for v in self.saved_views:self.saved_view_combo.addItem(v.name)
        self.saved_view_combo.blockSignals(False)
    def save_current_view(self):
        if not self.folder:return
        name,ok=QInputDialog.getText(self,'保存当前视图','视图名称：')
        name=name.strip()
        if not ok or not name:return
        spec=self.current_view_spec(name);existing=next((i for i,v in enumerate(self.saved_views) if v.name==name),None)
        if existing is None:self.saved_views.append(spec)
        else:self.saved_views[existing]=spec
        self.update_saved_view_combo();self.saved_view_combo.setCurrentText(name);self.save()
    def apply_view_spec(self,spec):
        mapping=((self.view_combo,spec.filters.get('status','全部')),(self.scale_combo,spec.filters.get('person_scale','全部')),(self.yaw_combo,spec.filters.get('angle_class','全部')),(self.pitch_combo,spec.filters.get('pitch_class','全部')),(self.eligibility_combo,spec.filters.get('eligibility','全部')),(self.sort_field_combo,spec.sort_field),(self.sort_dir_combo,spec.sort_direction),(self.rank_basis_combo,spec.ranking_basis))
        for combo,value in mapping:combo.blockSignals(True);set_combo_value(combo,value);combo.blockSignals(False)
        self.best_only.blockSignals(True);self.best_only.setChecked(spec.best_only);self.best_only.blockSignals(False);self.quick_n.blockSignals(True);self.quick_n.setValue(max(1,spec.limit_n));self.quick_n.blockSignals(False);self.quick_mode=spec.quick_mode if spec.quick_mode in ('','view_top','view_bottom') else '';self.page=0;self.refresh();self.save()
    def load_selected_view(self):
        name=self.saved_view_combo.currentText()
        spec=next((v for v in self.saved_views if v.name==name),None)
        if spec:self.apply_view_spec(spec)
    def delete_selected_view(self):
        name=self.saved_view_combo.currentText()
        if name=='未选择':return
        self.saved_views=[v for v in self.saved_views if v.name!=name];self.update_saved_view_combo();self.save()
    def clear_filters(self):
        for combo in (self.view_combo,self.scale_combo,self.yaw_combo,self.pitch_combo,self.eligibility_combo):combo.blockSignals(True);combo.setCurrentIndex(0);combo.blockSignals(False)
        self.best_only.blockSignals(True);self.best_only.setChecked(False);self.best_only.blockSignals(False);self.page=0;self.refresh();self.save()
    def quick(self,mode):self.quick_mode=mode;self.page=0;self.refresh();self.save()
    def quick_key(self,r):
        basis=combo_value(self.rank_basis_combo)
        if basis=='Face Quality':return r.face_quality
        if basis=='BRISQUE':return -r.brisque
        if basis=='Sharpness':return r.blur
        if basis=='Face Pixels':return r.face_px
        return rank(r)
    def set_category_filter(self,kind,value):
        combo={'status':self.view_combo,'scale':self.scale_combo,'yaw':self.yaw_combo,'pitch':self.pitch_combo,'eligibility':self.eligibility_combo}[kind]
        set_combo_value(combo,value);self.page=0;self.refresh()
    def group_rank(self,r):return BACKEND.duplicate_group_rank(self.records,r,False)
    def qualified_group_rank(self,r):return BACKEND.duplicate_group_rank(self.records,r,True)
    def indices(self,with_quick=True):
        spec=self.current_view_spec();base=[i for i,r in enumerate(self.records) if photo_matches_filters(r,spec.filters)]
        if spec.best_only:base=[i for i in base if not self.records[i].duplicate_group or self.qualified_group_rank(self.records[i])[0]==1]
        sort=spec.sort_field;status_order={'推荐':0,'备选':1,'淘汰':2};eligibility_order={'PASS':0,'REVIEW':1,'REJECT':2};scale_order={x:i for i,x in enumerate(SCALES)};yaw_order={x:i for i,x in enumerate(YAWS)};pitch_order={x:i for i,x in enumerate(PITCHES)}
        key_func={'质量排序':lambda r:rank(r),'Face Quality':lambda r:r.face_quality,'BRISQUE':lambda r:r.brisque,'Sharpness':lambda r:r.blur,'Face Pixels':lambda r:r.face_px,'状态':lambda r:status_order.get(r.status,99),'Eligibility':lambda r:eligibility_order.get(r.eligibility,99),'Duplicate Group':lambda r:(r.duplicate_group==0,r.duplicate_group),'来源目录 / 源视频':lambda r:r.source,'景别':lambda r:scale_order.get(r.person_scale,99),'Yaw':lambda r:yaw_order.get(r.angle_class,99),'Pitch':lambda r:pitch_order.get(r.pitch_class,99)}
        if sort in key_func:
            best_reverse=sort in ('质量排序','Face Quality','Sharpness','Face Pixels');reverse=best_reverse
            if spec.sort_direction=='反向':reverse=not reverse
            base.sort(key=lambda i:key_func[sort](self.records[i]),reverse=reverse)
        if with_quick and spec.quick_mode=='view_top':base=sorted(base,key=lambda i:self.quick_key(self.records[i]),reverse=True)[:spec.limit_n]
        if with_quick and spec.quick_mode=='view_bottom':base=sorted(base,key=lambda i:self.quick_key(self.records[i]))[:spec.limit_n]
        return base
    def view_description(self):
        filters=[]
        if self.view_combo.currentText()!='全部':filters.append('状态='+self.view_combo.currentText())
        if combo_value(self.eligibility_combo)!='全部':filters.append('判定='+self.eligibility_combo.currentText())
        if self.scale_combo.currentText()!='全部':filters.append('景别='+self.scale_combo.currentText())
        if self.yaw_combo.currentText()!='全部':filters.append('水平角度='+self.yaw_combo.currentText())
        if self.pitch_combo.currentText()!='全部':filters.append('俯仰='+self.pitch_combo.currentText())
        if self.best_only.isChecked():filters.append('重复组只看最佳')
        filter_text=' / '.join(filters) if filters else '全部图片'
        sort_text='原始顺序' if combo_value(self.sort_field_combo)=='默认顺序' else f'{self.sort_field_combo.currentText()} · {self.sort_dir_combo.currentText()}'
        extreme_text='关闭'
        if self.quick_mode=='view_top':extreme_text=f'Top {self.quick_n.value()} · {self.rank_basis_combo.currentText()}'
        if self.quick_mode=='view_bottom':extreme_text=f'Bottom {self.quick_n.value()} · {self.rank_basis_combo.currentText()}'
        return f'筛选：{filter_text}  ｜  排序：{sort_text}  ｜  极值：{extreme_text}'
    def placeholder(self):
        pix=QPixmap(150,150);pix.fill(QColor('#e8edf2'));return pix
    def cached_thumbnail(self,photo):
        value=self.thumb_memory.get(key(photo.path))
        if value is not None:self.thumb_memory.move_to_end(key(photo.path))
        return value
    def decorated_thumbnail(self,photo,pix):
        if not self.show_face_boxes.isChecked() or not photo.face_detections or pix.isNull():return pix
        out=pix.copy();p=QPainter(out);scale=min(150/max(1,photo.width),150/max(1,photo.height),1.0);draw_w=photo.width*scale;draw_h=photo.height*scale;ox=(150-draw_w)/2;oy=(150-draw_h)/2
        for d in photo.face_detections:
            pen=QPen(QColor('#1b8f3a' if d.is_primary else '#c43a31'));pen.setWidth(3 if d.is_primary else 2);p.setPen(pen);x,y,w,h=d.bbox_xywh;p.drawRect(int(ox+x*scale),int(oy+y*scale),max(1,int(w*scale)),max(1,int(h*scale)))
        p.end();return out
    def start_thumbnails(self,indices):
        missing=[(i,self.records[i]) for i in indices if self.cached_thumbnail(self.records[i]) is None]
        if not missing:return
        self.thumb_generation+=1;token=self.thumb_generation;thread=QThread(self);worker=ThumbnailWorker(token,missing,THUMB_CACHE);thread._thumbnail_worker=worker;worker.moveToThread(thread);thread.started.connect(worker.run);worker.ready.connect(self.thumbnail_ready);worker.finished.connect(thread.quit);thread.finished.connect(worker.deleteLater);thread.finished.connect(lambda t=thread:self.thumbnail_thread_done(t));self.thumb_threads.append(thread);thread.start()
    def thumbnail_thread_done(self,thread):
        if thread in self.thumb_threads:self.thumb_threads.remove(thread)
        thread.deleteLater()
    def thumbnail_ready(self,token,index,image):
        if token!=self.thumb_generation:return
        pix=QPixmap.fromImage(image);self.thumb_memory[key(self.records[index].path)]=pix;self.thumb_memory.move_to_end(key(self.records[index].path))
        while len(self.thumb_memory)>600:self.thumb_memory.popitem(last=False)
        photo=self.records[index]
        self.dataset_model.update_icon(photo.sample_id,index,QIcon(self.decorated_thumbnail(photo,pix)))
    def stat_button(self,text,kind,value,row,column):
        button=QPushButton(text);button.setFlat(True);button.setStyleSheet('text-align:left; color:#175ea8;');button.clicked.connect(lambda _=False,k=kind,v=value:self.set_category_filter(k,v));self.stat_layout.addWidget(button,row,column)
    def refresh_stats(self):
        while self.stat_layout.count():
            child=self.stat_layout.takeAt(0)
            if child.widget():child.widget().deleteLater()
        st=Counter(r.status for r in self.records);sel=[r for r in self.records if r.status=='推荐'];sc=Counter(r.person_scale for r in sel);yw=Counter(r.angle_class for r in sel);pt=Counter(r.pitch_class for r in sel);grp={r.duplicate_group for r in sel if r.duplicate_group};du=sum(r.status!='推荐' and r.eligibility!='REJECT' and r.duplicate_group and (self.qualified_group_rank(r)[0]>1 or r.duplicate_group in grp) for r in self.records);bad=sum(r.eligibility=='REJECT' for r in self.records);review=sum(r.eligibility=='REVIEW' for r in self.records);group_count=len({r.duplicate_group for r in self.records if r.duplicate_group})
        auto_sel=sum(r.auto_status=='推荐' for r in self.records);manual_add=sum(r.manual_status=='推荐' and r.auto_status!='推荐' for r in self.records);self.stats.setText(f'自动目标 / 自动推荐：{self.target} / {auto_sel} · 人工追加：{manual_add} · 总推荐：{len(sel)}\n来源目录/视频：{len({r.source for r in self.records})} · Duplicate Group：{group_count}\n因近重复未推荐：{du} · 需复核：{review} · 硬淘汰：{bad}')
        self.stat_layout.addWidget(QLabel('状态（点击筛选）'),0,0,1,3)
        for col,value in enumerate(('推荐','备选','淘汰')):self.stat_button(f'{value} {st[value]}','status',value,1,col)
        self.stat_layout.addWidget(QLabel('景别（推荐）'),2,0,1,3)
        for n,value in enumerate(SCALES):self.stat_button(f'{value} {sc[value]}','scale',value,3+n//2,n%2)
        self.stat_layout.addWidget(QLabel('水平角度（推荐）'),5,0,1,3)
        for n,value in enumerate(YAWS):self.stat_button(f'{value} {yw[value]}','yaw',value,6+n//2,n%2)
        self.stat_layout.addWidget(QLabel('俯仰（推荐）'),9,0,1,3)
        for n,value in enumerate(PITCHES):self.stat_button(f'{value} {pt[value]}','pitch',value,10+n//2,n%2)
    def refresh(self):
        base=self.indices(False);visible=self.indices(True);old_page=self.page;scroll=self.grid.verticalScrollBar().value();self.page,pages=clamp_page(self.page,len(visible));self.thumb_generation+=1;start=self.page*PAGE;page_indices=visible[start:start+PAGE];rows=[]
        for i in page_indices:
            r=self.records[i];gr,gs=self.group_rank(r);pix=self.cached_thumbnail(r) or self.placeholder();pix=self.decorated_thumbnail(r,pix);reason=r.recommendation_reasons[0] if r.recommendation_reasons else '无';tooltip=f'{r.status} · {r.eligibility} · AI {r.ai_suggestion.decision if r.ai_suggestion else "无"} · 人脸 {r.faces} · {r.person_scale} · {r.angle_class} · eDifFIQA {r.face_quality:.3f} · 组 {gr}/{gs}\n推荐/备选原因：{reason}';rows.append(DatasetViewRow(i,r.sample_id,r.path.name,tooltip,QIcon(pix),QColor(COLORS[r.status])))
        self.dataset_model.set_rows(rows)
        self.page_label.setText(f'第 {self.page+1}/{pages} 页');self.prev.setEnabled(self.page>0);self.next.setEnabled(self.page+1<pages);self.current_view_label.setText(f'当前视图\n{self.view_description()}\n显示：{len(visible)} / {len(base)} 张');self.refresh_stats();self.start_thumbnails(page_indices)
        if self.page==old_page:QTimer.singleShot(0,lambda v=scroll:self.grid.verticalScrollBar().setValue(v))
    def change(self,d):
        n=self.page+d
        if 0<=n<math.ceil(len(self.indices())/PAGE):self.page=n;self.refresh()
    def view_record_index(self,index):
        if index is None or not index.isValid():return None
        sample_id=self.dataset_model.sample_id(index)
        if sample_id:
            for i,r in enumerate(self.records):
                if r.sample_id==sample_id:return i
        record_index=self.dataset_model.record_index(index)
        return record_index if record_index is not None and 0<=record_index<len(self.records) else None
    def record_from_view(self,index):
        i=self.view_record_index(index)
        return self.records[i] if i is not None else None
    def selected(self):
        return self.record_from_view(self.grid.currentIndex())
    def details(self,index):
        r=self.record_from_view(index)
        if r is None:return
        flags='；'.join(finding_text(x) for x in r.review_flags) or '无';rejects='；'.join(finding_text(x) for x in r.hard_rejects) or '无';gr,gs=self.group_rank(r);qr,qs=self.qualified_group_rank(r);dup=f'第 {r.duplicate_group} 组' if r.duplicate_group else '无（独立图片）';primary=next((x for x in r.face_detections if x.is_primary),None);pconf=f'{primary.confidence:.3f}' if primary else '无';status_source='人工' if r.manual_status else '自动';rank_text=qr if qr else '未达推荐门槛';reason_text='；'.join(r.recommendation_reasons) or '无';self.detail.setText(f'文件：{r.path.name}\nSample ID：{r.sample_id}\n\n状态：{r.status}（{status_source}）\nEligibility：{r.eligibility}\n分辨率：{r.width} × {r.height}\n人脸检测数：{r.faces}\n主脸置信度：{pconf}\n主脸占比：{r.face_ratio*100:.1f}%\n主脸实际尺寸：{r.face_px}px\neDifFIQA-T：{r.face_quality:.4f}（高更好）\nBRISQUE：{r.brisque:.2f}（低更好）\nLaplacian 清晰度：{r.blur:.1f}\n平均亮度：{r.brightness:.1f}\nyaw / pitch / roll：{r.yaw:.1f}° / {r.pitch:.1f}° / {r.roll:.1f}°\nYaw 分类：{r.angle_class}\nPitch 分类：{r.pitch_class}\n景别：{r.person_scale}\nDuplicate Group：{dup}\nGroup Size：{gs}\nGroup Rank：{gr} / {gs}\n合格成员 Rank：{rank_text} / {qs}\n\n推荐/备选原因：{reason_text}\n需复核：{flags}\n硬淘汰：{rejects}');self.update_ai_panel(r)
    def update_ai_panel(self,r=None):
        r=r or self.selected()
        if not r or not r.ai_suggestion:self.ai_label.setText('当前图片没有 AI 建议');return
        a=r.ai_suggestion;parts=[f'状态：{a.decision}']
        if a.suggested_eligibility:parts.append(f'建议 Eligibility：{a.suggested_eligibility}')
        if a.suggested_status:parts.append(f'建议状态：{a.suggested_status}')
        if a.flags:parts.append('Flags：'+'、'.join(a.flags))
        if a.note:parts.append('备注：'+a.note)
        if a.request_full_resolution:parts.append('请求：需要原图复核')
        self.ai_label.setText('\n'.join(parts))
    def accept_ai_suggestion(self):
        r=self.selected()
        if not r or not r.ai_suggestion:return
        a=r.ai_suggestion
        if a.suggested_status in ('推荐','备选','淘汰'):r.manual_status=a.suggested_status
        elif a.suggested_eligibility=='REJECT':r.manual_status='淘汰'
        elif a.suggested_eligibility=='REVIEW':r.manual_status='备选'
        a.decision='accepted';self.refresh();self.save();self.update_ai_panel(r)
    def reject_ai_suggestion(self):
        r=self.selected()
        if not r or not r.ai_suggestion:return
        r.ai_suggestion.decision='rejected';self.save();self.update_ai_panel(r)
    def clear_ai_suggestion(self):
        r=self.selected()
        if not r or not r.ai_suggestion:return
        r.ai_suggestion=None;self.save();self.update_ai_panel(r)
    def ai_export_records(self,scope):
        return list(self.records) if scope=='dataset' else [self.records[i] for i in self.indices(True)]
    def export_ai_bundle(self,scope):
        if not self.folder or not self.records:QMessageBox.information(self,'没有数据','请先完成图片分析。');return
        records=self.ai_export_records(scope)
        if not records:QMessageBox.information(self,'当前视图为空','当前视图没有可导出的图片。');return
        out=QFileDialog.getExistingDirectory(self,'选择 AI 审核包保存目录',str(self.folder.parent))
        if not out:return
        include_originals=QMessageBox.question(self,'是否包含原图','是否把当前导出范围的原图一起放进 AI 审核包？\n\n不包含时仍会生成 Contact Sheets、完整指标和统计。',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)==QMessageBox.Yes
        bundle_id='bundle_'+time.strftime('%Y%m%d_%H%M%S',time.gmtime())+'_'+uuid.uuid4().hex[:8];created=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime());dest=Path(out);stage=dest/f'.{bundle_id}.building';zip_path=dest/f'{bundle_id}.zip'
        try:
            if stage.exists():shutil.rmtree(stage)
            stage.mkdir(parents=True);contact=stage/'contact_sheets';dups=contact/'duplicate_groups';manifest=[manifest_entry(r,self.folder) for r in records];flat=[flat_manifest_entry(r,self.folder) for r in records];view_spec=self.current_view_spec('current') if scope=='current_view' else None
            bundle={'schema_version':AI_BUNDLE_SCHEMA,'bundle_id':bundle_id,'created_at':created,'app_version':'0.3-dev','dataset_root_label':self.folder.name,'source_scope':scope,'source_view':asdict(view_spec) if view_spec else None,'sample_count':len(records),'includes_originals':include_originals}
            (stage/'bundle.json').write_text(json.dumps(bundle,ensure_ascii=False,indent=2),encoding='utf-8');(stage/'manifest.json').write_text(json.dumps({'schema_version':AI_BUNDLE_SCHEMA,'bundle_id':bundle_id,'samples':manifest},ensure_ascii=False,indent=2),encoding='utf-8');(stage/'summary.json').write_text(json.dumps(dataset_summary(records,self.view_description() if scope=='current_view' else '全部图片'),ensure_ascii=False,indent=2),encoding='utf-8');(stage/'views.json').write_text(json.dumps({'current':asdict(self.current_view_spec('current')),'saved':[asdict(v) for v in self.saved_views]},ensure_ascii=False,indent=2),encoding='utf-8')
            if flat:
                with (stage/'manifest.csv').open('w',encoding='utf-8-sig',newline='') as fh:
                    writer=csv.DictWriter(fh,fieldnames=list(flat[0].keys()));writer.writeheader();writer.writerows(flat)
            write_contact_sheets(records,contact,'current_view' if scope=='current_view' else 'all')
            for gid in sorted({r.duplicate_group for r in records if r.duplicate_group}):
                members=[r for r in records if r.duplicate_group==gid]
                if len(members)>1:write_contact_sheets(members,dups,f'group_{gid:04d}')
            if include_originals:
                originals=stage/'originals';originals.mkdir()
                for r in records:
                    name=f'{r.sample_id}__{r.path.name}';target=originals/name;n=1
                    while target.exists():target=originals/f'{r.sample_id}_{n}__{r.path.name}';n+=1
                    shutil.copy2(r.path,target)
            if zip_path.exists():zip_path.unlink()
            made=Path(shutil.make_archive(str(zip_path.with_suffix('')),'zip',stage))
            self.exported_bundle_ids.append(bundle_id);self.exported_bundle_ids=self.exported_bundle_ids[-100:];self.save()
            QMessageBox.information(self,'AI 审核包导出完成',f'已导出 {len(records)} 张图片的审核信息。\n\n{made}')
        except Exception as e:QMessageBox.critical(self,'AI 审核包导出失败',str(e))
        finally:
            try:
                if stage.exists():shutil.rmtree(stage)
            except Exception:pass
    def import_ai_patch(self):
        if not self.records:QMessageBox.information(self,'没有数据','请先加载并分析数据集。');return
        filename,_=QFileDialog.getOpenFileName(self,'选择 review_patch.json',str(self.folder or APP_DIR),'JSON (*.json)')
        if not filename:return
        try:
            data=json.loads(Path(filename).read_text(encoding='utf-8'));bundle_id,pending,unknown,stale=prepare_review_patch(data,self.records,Path(filename).stem)
            if bundle_id not in self.exported_bundle_ids:
                ans=QMessageBox.question(self,'外部或历史审核包',f'本地记录中找不到 bundle_id：\n{bundle_id}\n\n如果这是历史导出的审核包，仍可按 sample_id + 内容哈希安全匹配。是否继续？',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)
                if ans!=QMessageBox.Yes:return
            for target,suggestion in pending:target.ai_suggestion=suggestion
            self.save();self.refresh();self.update_ai_panel()
            msg=f'已导入 AI 建议：{len(pending)} 条'
            if unknown:msg+=f'\n未知 sample_id：{len(unknown)} 条（已跳过）'
            if stale:msg+=f'\n内容已变化：{len(stale)} 条（已跳过）'
            QMessageBox.information(self,'AI 建议导入完成',msg)
        except Exception as e:QMessageBox.critical(self,'AI 建议导入失败',str(e))
    def manual(self,v):
        r=self.selected()
        if r:r.manual_status=v;BACKEND.recompute_recommendations(self.records,self.target);self.refresh();self.save()
    def restore(self):
        r=self.selected()
        if r:r.manual_status=None;BACKEND.recompute_recommendations(self.records,self.target);self.refresh();self.save()
    def sync_target_mode_ui(self):
        if self.target_mode=='custom':
            self.custom_mode.setChecked(True);return
        button=self.group.button(int(self.target))
        if button is not None:button.setChecked(True)
        else:self.target_mode='custom';self.custom_mode.setChecked(True)
    def apply_custom_target(self,*_):
        self.run_rec(self.custom.value(),'custom')
    def run_rec(self,n,mode='preset'):
        self.target=max(1,int(n));self.target_mode='custom' if mode=='custom' else 'preset';self.custom.blockSignals(True);self.custom.setValue(self.target);self.custom.blockSignals(False);self.sync_target_mode_ui();BACKEND.recompute_recommendations(self.records,self.target) if self.records else None;self.page=0;self.refresh() if self.records else None;self.save()
    def quick_toggle_item(self,index):
        r=self.record_from_view(index)
        if r is None:return
        if r.status=='推荐':r.manual_status='备选'
        elif r.status=='备选':r.manual_status='推荐'
        else:r.manual_status='备选'
        BACKEND.recompute_recommendations(self.records,self.target);self.refresh();self.save()
    def quick_reject_item(self,index):
        r=self.record_from_view(index)
        if r is None:return
        r.manual_status='淘汰';BACKEND.recompute_recommendations(self.records,self.target);self.refresh();self.save()
    def source_organizer_busy(self):
        return any((
            self.thread and self.thread.isRunning(),
            self.composite_thread and self.composite_thread.isRunning(),
            self.auto_crop_thread and self.auto_crop_thread.isRunning(),
            self.incremental_thread and self.incremental_thread.isRunning(),
            self.organizer_thread and self.organizer_thread.isRunning(),
        ))
    def open_source_organizer(self):
        if not BACKEND.feature_available('source_organizer'):return
        if not self.folder or not self.records:
            QMessageBox.information(self,'没有数据','请先选择并完成一个数据集的分析。');return
        if self.source_organizer_busy():
            QMessageBox.information(self,'后台任务进行中',self._tr_main('请等待当前分析 / 组合图拆分 / 自动裁剪任务完成后再整理源文件。'));return
        try:
            plan=BACKEND.build_source_organizer_plan(self.folder,self.records)
        except Exception as e:
            QMessageBox.warning(self,'暂时不能整理源文件',str(e));return
        if not plan.moves:
            try:
                result=BACKEND.execute_source_organizer(plan)
                self.save()
                self.progress.setText(f'源文件已经是目标结构：无需移动 · 保持 {result.unchanged} · 跳过 {result.skipped}')
            except Exception as e:
                QMessageBox.critical(self,'Source Organizer 失败',str(e))
            return
        counts=plan.counts_by_status()
        box=QMessageBox(self);box.setWindowTitle('确认整理源文件');box.setIcon(QMessageBox.Warning)
        box.setText(f'将移动 {len(plan.moves)} 张图片。')
        box.setInformativeText(
            f"推荐 {counts.get('推荐',0)} · 备选 {counts.get('备选',0)} · 淘汰 {counts.get('淘汰',0)}\n"
            f"保持不动 {plan.unchanged} · 跳过 {plan.skipped}\n\n"
            "文件会按当前最终状态移动到 推荐 / 备选 / 淘汰，并保留原相对来源目录。\n"
            "组合图拆分隔离目录 _CompositeSplit_Originals 不会被触碰；不会修改任何图片像素；不会删除空目录。\n"
            "执行采用 journal + 事务回滚，失败或下次启动会恢复未完成事务。"
        )
        details=[]
        for move in plan.moves[:40]:
            try:
                src=str(move.source.resolve().relative_to(self.folder.resolve()))
                dst=str(move.destination.resolve().relative_to(self.folder.resolve()))
            except Exception:
                src=str(move.source);dst=str(move.destination)
            details.append(f'{src}  →  {dst}')
        if len(plan.moves)>40:details.append(f'…另有 {len(plan.moves)-40} 项')
        box.setDetailedText('\n'.join(details));box.setStandardButtons(QMessageBox.Yes|QMessageBox.Cancel);box.setDefaultButton(QMessageBox.Cancel)
        if box.exec()!=QMessageBox.Yes:return
        self.pick.setEnabled(False);self.rescan.setEnabled(False);self.export.setEnabled(False);self.composite_btn.setEnabled(False);self.auto_crop_btn.setEnabled(False);self.organizer_btn.setEnabled(False)
        self.progress.setText(f'Source Organizer 0/{len(plan.moves)*2}：准备事务')
        self.organizer_thread=QThread(self);self.organizer_worker=SourceOrganizerWorker(plan);self.organizer_worker.moveToThread(self.organizer_thread);self.organizer_thread.started.connect(self.organizer_worker.run);self.organizer_worker.progress.connect(lambda n,t,name:self.progress.setText(f'Source Organizer {n}/{t}：{name}'));self.organizer_worker.finished.connect(self.source_organizer_done);self.organizer_worker.failed.connect(self.source_organizer_failed);self.organizer_worker.finished.connect(self.organizer_thread.quit);self.organizer_worker.failed.connect(self.organizer_thread.quit);self.organizer_thread.finished.connect(self.source_organizer_thread_done);self.organizer_thread.start()
    def source_organizer_done(self,result):
        self.thumb_generation+=1;self.thumb_memory.clear();self.save();self.refresh()
        self.pick.setEnabled(True);self.rescan.setEnabled(True);self.export.setEnabled(True);self.composite_btn.setEnabled(True);self.auto_crop_btn.setEnabled(True);self.organizer_btn.setEnabled(True)
        self.update_composite_button();self.update_auto_crop_button();self.progress.setText(f'Source Organizer 完成：移动 {result.moved} · 保持 {result.unchanged} · 跳过 {result.skipped}；未重新分析图片')
    def source_organizer_failed(self,error):
        self.pick.setEnabled(True);self.rescan.setEnabled(True);self.export.setEnabled(True);self.composite_btn.setEnabled(True);self.auto_crop_btn.setEnabled(True);self.organizer_btn.setEnabled(True)
        self.progress.setText('Source Organizer 失败；已尝试自动回滚');QMessageBox.critical(self,'Source Organizer 失败',error)
    def source_organizer_thread_done(self):
        if self.organizer_worker:self.organizer_worker.deleteLater()
        if self.organizer_thread:self.organizer_thread.deleteLater()
        self.organizer_worker=None;self.organizer_thread=None

    def update_auto_crop_button(self):
        if not hasattr(self,'auto_crop_btn') or not BACKEND.feature_available('auto_crop'):return
        try:
            proposals=BACKEND.auto_crop_review_records(self.records);pending=len(BACKEND.pending_auto_crop(self.records));todo=BACKEND.auto_crop_scan_todo(self.records)
        except Exception:return
        if proposals:self.auto_crop_btn.setText(self._tr_main('自动裁剪 复核… ({total} / 待定 {pending} / 未扫 {todo})').format(total=len(proposals),pending=pending,todo=todo))
        elif todo:self.auto_crop_btn.setText(self._tr_main('自动裁剪 复核…（未扫 {todo}）').format(todo=todo))
        else:self.auto_crop_btn.setText(self._tr_main('自动裁剪 复核…'))
    def open_auto_crop_review(self):
        if not BACKEND.feature_available('auto_crop'):return
        if not self.records:QMessageBox.information(self,self._tr_main('没有数据'),self._tr_main('请先完成图片分析。'));return
        if self.auto_crop_thread and self.auto_crop_thread.isRunning():return
        composite_pending=[r for r in self.records if r.status=='推荐' and r.composite_proposal is not None and r.composite_proposal.decision=='pending']
        if composite_pending:
            QMessageBox.warning(self,self._tr_main('请先完成组合图拆分'),self._tr_main('还有 {count} 张推荐图等待组合图拆分复核。\n\n自动裁剪只处理组合图拆分之后的单主体推荐图。').format(count=len(composite_pending)));return
        todo=BACKEND.auto_crop_scan_todo(self.records)
        if not todo:
            candidates=BACKEND.auto_crop_review_records(self.records)
            if not candidates:QMessageBox.information(self,self._tr_main('没有候选'),self._tr_main('当前推荐图片没有需要自动裁剪复核的候选。'));return
            AutoCropReviewDialog(BACKEND,self.records,self.auto_crop_review_changed,THUMB_CACHE,self).exec();self.update_auto_crop_button();return
        self.auto_crop_btn.setEnabled(False);self.composite_btn.setEnabled(False);self.organizer_btn.setEnabled(False);self.export.setEnabled(False);self.progress.setText(self._tr_main('自动裁剪扫描准备中：{todo} 张；首次使用如未缓存会下载 ISNetIS 模型').format(todo=todo))
        self.auto_crop_thread=QThread(self);self.auto_crop_worker=AutoCropScanWorker(self.records);self.auto_crop_worker.moveToThread(self.auto_crop_thread);self.auto_crop_thread.started.connect(self.auto_crop_worker.run);self.auto_crop_worker.progress.connect(lambda n,t,name:self.progress.setText(self._tr_main('自动裁剪 {current}/{total}：{name}').format(current=n,total=t,name=name)));self.auto_crop_worker.finished.connect(self.auto_crop_scan_done);self.auto_crop_worker.failed.connect(self.auto_crop_scan_failed);self.auto_crop_worker.finished.connect(self.auto_crop_thread.quit);self.auto_crop_worker.failed.connect(self.auto_crop_thread.quit);self.auto_crop_thread.finished.connect(self.auto_crop_thread_done);self.auto_crop_thread.start()
    def auto_crop_scan_done(self,result):
        self.progress.setText(self._tr_main('自动裁剪扫描完成：新扫 {scanned} · 候选 {candidates} · 无需裁 {no_candidate} · 已缓存 {cached}').format(scanned=result.scanned,candidates=result.candidates,no_candidate=result.no_candidate,cached=result.skipped_existing))
        self.auto_crop_btn.setEnabled(True);self.composite_btn.setEnabled(True);self.organizer_btn.setEnabled(True);self.export.setEnabled(True);self.update_auto_crop_button();self.save()
        candidates=BACKEND.auto_crop_review_records(self.records)
        if candidates:AutoCropReviewDialog(BACKEND,self.records,self.auto_crop_review_changed,THUMB_CACHE,self).exec();self.update_auto_crop_button()
        else:QMessageBox.information(self,self._tr_main('没有候选'),self._tr_main('当前推荐图片没有需要自动裁剪复核的候选。'))
    def auto_crop_scan_failed(self,error):
        self.auto_crop_btn.setEnabled(True);self.composite_btn.setEnabled(True);self.organizer_btn.setEnabled(True);self.export.setEnabled(True);self.progress.setText(self._tr_main('自动裁剪扫描失败'));QMessageBox.critical(self,self._tr_main('自动裁剪扫描失败'),error)
    def auto_crop_thread_done(self):
        if self.auto_crop_worker:self.auto_crop_worker.deleteLater()
        if self.auto_crop_thread:self.auto_crop_thread.deleteLater()
        self.auto_crop_worker=None;self.auto_crop_thread=None
    def auto_crop_review_changed(self):
        self.save();self.update_auto_crop_button()

    def update_composite_button(self):
        if not hasattr(self,'composite_btn'):return
        proposals=[r.composite_proposal for r in self.records if r.status=='推荐' and r.composite_proposal is not None]
        pending=sum(p.decision=='pending' for p in proposals)
        self.composite_btn.setText(self._tr_main('组合图拆分 复核… ({total} / 待定 {pending})').format(total=len(proposals),pending=pending) if proposals else self._tr_main('组合图拆分 复核…'))
    def open_composite_review(self):
        if not BACKEND.feature_available('composite'):return
        if not self.records:QMessageBox.information(self,self._tr_main('没有数据'),self._tr_main('请先完成图片分析。'));return
        if self.composite_thread and self.composite_thread.isRunning():return
        todo=sum(r.status=='推荐' and r.composite_scan_version!=BACKEND.composite_proposal_version for r in self.records)
        if not todo:
            candidates=[r for r in self.records if r.status=='推荐' and r.composite_proposal is not None]
            if not candidates:QMessageBox.information(self,self._tr_main('没有候选'),self._tr_main('当前推荐图片中没有检测到需要组合图拆分的图片。'));return
            CompositeSplitReviewDialog(self.records,self.composite_review_changed,self.materialize_composite,self).exec();self.after_composite_review();return
        self.composite_btn.setEnabled(False);self.auto_crop_btn.setEnabled(False);self.organizer_btn.setEnabled(False);self.progress.setText(self._tr_main('组合图拆分扫描准备中：{todo} 张待检查').format(todo=todo))
        self.composite_thread=QThread(self);self.composite_worker=CompositeScanWorker(self.records);self.composite_worker.moveToThread(self.composite_thread);self.composite_thread.started.connect(self.composite_worker.run);self.composite_worker.progress.connect(lambda n,t,name:self.progress.setText(self._tr_main('组合图拆分 {current}/{total}：{name}').format(current=n,total=t,name=name)));self.composite_worker.finished.connect(self.composite_scan_done);self.composite_worker.failed.connect(self.composite_scan_failed);self.composite_worker.finished.connect(self.composite_thread.quit);self.composite_worker.failed.connect(self.composite_thread.quit);self.composite_thread.finished.connect(self.composite_thread_done);self.composite_thread.start()
    def composite_scan_done(self,records):
        self.records=records;count=sum(r.status=='推荐' and r.composite_proposal is not None for r in records);self.progress.setText(self._tr_main('组合图拆分扫描完成：{count} 张推荐候选').format(count=count));self.composite_btn.setEnabled(True);self.auto_crop_btn.setEnabled(True);self.organizer_btn.setEnabled(True);self.update_composite_button();self.save()
        if count:CompositeSplitReviewDialog(self.records,self.composite_review_changed,self.materialize_composite,self).exec();self.after_composite_review()
        else:QMessageBox.information(self,self._tr_main('没有候选'),self._tr_main('当前推荐图片中没有检测到需要组合图拆分的图片。'))
    def composite_scan_failed(self,error):
        self.composite_btn.setEnabled(True);self.auto_crop_btn.setEnabled(True);self.organizer_btn.setEnabled(True);self.progress.setText(self._tr_main('组合图拆分扫描失败'));QMessageBox.critical(self,self._tr_main('组合图拆分扫描失败'),error)
    def composite_thread_done(self):
        if self.composite_worker:self.composite_worker.deleteLater()
        if self.composite_thread:self.composite_thread.deleteLater()
        self.composite_worker=None;self.composite_thread=None
    def materialize_composite(self,r,keep_mask):
        if not self.folder or r not in self.records or r.composite_proposal is None:return False
        source=r.path
        try:
            result=BACKEND.accept_composite(self.folder,source,r.composite_proposal,keep_mask);assigned=[(item.path,item.status) for item in result.outputs]
        except Exception as e:
            QMessageBox.critical(self,self._tr_main('组合图拆分写入失败'),f'{source.name}\n\n{e}')
            return False
        for out,status in assigned:self.pending_composite_outputs[key(out)]={'path':str(out.resolve()),'status':status}
        self.records=[x for x in self.records if x is not r];kept=sum(status=='推荐' for _,status in assigned);rejected=len(assigned)-kept;self.progress.setText(self._tr_main('组合图拆分已落盘：{name} → 推荐 {kept} / 淘汰 {rejected}；原图已隔离').format(name=source.name,kept=kept,rejected=rejected));return True
    def start_incremental_composite_analysis(self):
        if self.incremental_thread and self.incremental_thread.isRunning():return
        items=[]
        for item in self.pending_composite_outputs.values():
            path=Path(item['path'])
            if path.exists():items.append((path,item['status']))
        if not items:self.refresh();self.save();return
        self.refresh();self.save();self.pick.setEnabled(False);self.rescan.setEnabled(False);self.export.setEnabled(False);self.composite_btn.setEnabled(False);self.auto_crop_btn.setEnabled(False);self.organizer_btn.setEnabled(False);self.progress.setText(self._tr_main('分析组合图拆分新生成图片：0/{count}').format(count=len(items)));self.incremental_thread=QThread(self);self.incremental_worker=IncrementalAnalysisWorker(items);self.incremental_worker.moveToThread(self.incremental_thread);self.incremental_thread.started.connect(self.incremental_worker.run);self.incremental_worker.progress.connect(lambda n,t,name:self.progress.setText(self._tr_main('分析组合图拆分新图 {current}/{total}：{name}').format(current=n,total=t,name=name)));self.incremental_worker.finished.connect(self.incremental_composite_done);self.incremental_worker.failed.connect(self.incremental_composite_failed);self.incremental_worker.finished.connect(self.incremental_thread.quit);self.incremental_worker.failed.connect(self.incremental_thread.quit);self.incremental_thread.finished.connect(self.incremental_composite_thread_done);self.incremental_thread.start()
    def incremental_composite_done(self,new_records):
        existing={key(r.path) for r in self.records};added=[]
        for r in new_records:
            if key(r.path) not in existing:self.records.append(r);existing.add(key(r.path));added.append(r)
            self.pending_composite_outputs.pop(key(r.path),None)
        BACKEND.regroup_duplicates(self.records);BACKEND.recompute_recommendations(self.records,self.target);self.refresh();self.save();self.pick.setEnabled(True);self.rescan.setEnabled(True);self.export.setEnabled(True);self.composite_btn.setEnabled(True);self.auto_crop_btn.setEnabled(True);self.organizer_btn.setEnabled(True);self.update_composite_button();self.update_auto_crop_button();self.progress.setText(self._tr_main('组合图拆分新图分析完成：新增 {count} 张（仅分析本轮生成图片）').format(count=len(added)))
    def incremental_composite_failed(self,error):
        self.pick.setEnabled(True);self.rescan.setEnabled(True);self.export.setEnabled(True);self.composite_btn.setEnabled(True);self.auto_crop_btn.setEnabled(True);self.organizer_btn.setEnabled(True);self.progress.setText(self._tr_main('组合图拆分新图增量分析失败；状态已保留，可刷新恢复'));self.save();QMessageBox.critical(self,self._tr_main('组合图拆分新图分析失败'),error)
    def incremental_composite_thread_done(self):
        if self.incremental_worker:self.incremental_worker.deleteLater()
        if self.incremental_thread:self.incremental_thread.deleteLater()
        self.incremental_worker=None;self.incremental_thread=None
    def after_composite_review(self):
        self.update_composite_button();self.start_incremental_composite_analysis()
    def composite_review_changed(self):
        self.save();self.update_composite_button()
    def open_duplicate_review(self):
        if not self.records:QMessageBox.information(self,'没有数据','请先完成图片分析。');return
        DuplicateReviewDialog(BACKEND,self.records,self.duplicate_review_changed,self).exec()
    def duplicate_review_changed(self,regroup=False):
        if regroup:BACKEND.regroup_duplicates(self.records)
        self.page=0;self.refresh();self.save()
    def open(self,index):
        r=self.record_from_view(index)
        if r is None:return
        try:os.startfile(str(r.path))
        except OSError as e:QMessageBox.warning(self,'无法打开图片',str(e))
    def save(self):
        if self.folder and self.records:
            try:save_data(self.folder,self.records,self.target,self.saved_views,self.exported_bundle_ids,self.current_view_spec('last') if self.records else None,list(self.pending_composite_outputs.values()),self.target_mode)
            except Exception:self.progress.setText('缓存保存失败')
    def closeEvent(self,e):self.save();self.sub.save() if self.sub is not None else None;e.accept()
    def exported(self):
        sel=[r for r in self.records if r.status=='推荐']
        if not sel:QMessageBox.information(self,'没有可导出的图片','当前没有推荐图片。');return
        pending=[r for r in sel if r.composite_proposal is not None and r.composite_proposal.decision=='pending']
        if pending:
            QMessageBox.warning(self,self._tr_main('还有组合图拆分待复核'),self._tr_main('推荐图片中还有 {count} 张组合图拆分建议未确认。\n\n请先完成组合图拆分复核，再导出训练图片。').format(count=len(pending)));return
        if BACKEND.feature_available('auto_crop'):
            unscanned=BACKEND.auto_crop_scan_todo(sel)
            if unscanned:
                QMessageBox.warning(self,self._tr_main('还有自动裁剪未扫描'),self._tr_main('推荐图片中还有 {count} 张未完成自动裁剪扫描。\n\n请先完成自动裁剪，再导出训练图片。').format(count=unscanned));return
            auto_pending=BACKEND.pending_auto_crop(sel)
            if auto_pending:
                QMessageBox.warning(self,self._tr_main('还有自动裁剪待复核'),self._tr_main('推荐图片中还有 {count} 张自动裁剪候选未确认。\n\n请接受裁剪或选择保留原图后再导出。').format(count=len(auto_pending)));return
        x=QFileDialog.getExistingDirectory(self,'选择导出目录（只写新文件）')
        if not x:return
        dst=Path(x)
        if self.folder and (dst.resolve()==self.folder.resolve() or self.folder.resolve() in dst.resolve().parents):QMessageBox.warning(self,'请选择新目录','导出目录不能是源目录或其子目录。');return
        try:
            result=BACKEND.export_recommended(self.records,dst)
            QMessageBox.information(self,'导出完成',self._tr_main('已导出 {count} 张当前推荐图片。\n\n组合图拆分已在前置阶段实体化，隔离原图不会进入导出。\n源图片未被修改。').format(count=result.written))
        except Exception as e:QMessageBox.critical(self,'导出失败',str(e))

def self_test():
    """Portable / CI smoke test: load the core models without opening the GUI."""
    from features.auto_crop.service import (
        AutoCropProposal,
        FEATURE_KEY as AUTO_CROP_FEATURE_KEY,
        self_test as auto_crop_backend_self_test,
    )
    from features.source_organizer.service import (
        self_test as source_organizer_backend_self_test,
    )
    from features.text_cleanup.service import (
        self_test as text_cleanup_backend_self_test,
    )
    from features.ranking.analysis import (
        QualityModels,
        phash_int,
        dedupe_face_rows,
        filter_face_rows_by_head,
        consolidate_face_rows,
        new_sample_id,
        pose_smoke_test,
    )
    from infrastructure.filesystem import sha256_file
    if clamp_page(2,250,120)!=(2,3):raise RuntimeError('pagination clamp valid-page self-test failed')
    if clamp_page(2,121,120)!=(1,2):raise RuntimeError('pagination clamp shrink self-test failed')
    if infer_target_mode(60,None)!='preset' or infer_target_mode(61,None)!='custom' or infer_target_mode(60,'custom')!='custom':raise RuntimeError('target mode inference self-test failed')
    required([YUNET,EDIFF,BRISQUE,BRISQUE_RANGE,DDDFA,DDDFA_NORM,POSE])
    qm=QualityModels()
    gradient=np.tile(np.arange(256,dtype=np.uint8),(256,1))
    test_bgr=cv2.merge((gradient,gradient,gradient))
    score=qm.brisque(test_bgr)
    if not math.isfinite(score):raise RuntimeError('BRISQUE self-test returned a non-finite score')
    test_image=Image.fromarray(cv2.cvtColor(test_bgr,cv2.COLOR_BGR2RGB))
    if phash_int(test_image)!=phash_int(test_image.copy()):raise RuntimeError('pHash self-test is not deterministic')
    composite_fake_people=[
        BACKEND.make_composite_detection([10,10,110,230],.95,'person'),
        BACKEND.make_composite_detection([150,12,250,232],.93,'person'),
    ]
    composite_fake_heads=[
        BACKEND.make_composite_detection([35,20,75,65],.9,'head'),
        BACKEND.make_composite_detection([175,22,215,67],.88,'head'),
    ]
    composite_fake=BACKEND.composite_proposal_from_detections((300,260),composite_fake_people,composite_fake_heads)
    if not composite_fake or composite_fake.mode!='split_people' or len(composite_fake.output_boxes)!=2:raise RuntimeError('Composite Split proposal self-test failed')
    with tempfile.TemporaryDirectory() as composite_td:
        root=Path(composite_td);source=root/'source.png';archive=root/BACKEND.composite_archive_dir;archive.mkdir()
        Image.new('RGB',(100,80),(20,30,40)).save(source);Image.new('RGB',(20,20),(1,2,3)).save(archive/'archived.png')
        active={p.name for p in BACKEND.active_image_files(root)}
        if 'archived.png' in active or 'source.png' not in active:raise RuntimeError('Composite archive exclusion self-test failed')
        proposal=BACKEND.make_composite_proposal(mode='split_people',output_boxes=[[0,0,50,80],[50,0,100,80]],decision='pending')
        materialized=BACKEND.accept_composite(root,source,proposal,[True,False]);outputs=[item.path for item in materialized.outputs];archived=materialized.archived_source
        if source.exists() or not archived.exists() or len(outputs)!=2 or any(not p.exists() for p in outputs):raise RuntimeError('Composite materialization self-test failed')
        if [item.status for item in materialized.outputs]!=['推荐','淘汰']:raise RuntimeError('Composite per-output status self-test failed')
        active={p.name for p in BACKEND.active_image_files(root)}
        if archived.name in active or {p.name for p in outputs}-active:raise RuntimeError('Composite materialized active-set self-test failed')
    nested=[np.array([10,10,100,100,*([0]*10),.95],dtype=np.float32),np.array([35,35,25,25,*([0]*10),.90],dtype=np.float32)]
    if len(dedupe_face_rows(nested))!=1:raise RuntimeError('nested face detection dedupe self-test failed')
    fake=[np.array([10,10,20,20,*([0]*10),.9],dtype=np.float32),np.array([200,200,20,20,*([0]*10),.9],dtype=np.float32)]
    if len(filter_face_rows_by_head(fake,(0,0,80,80)))!=1:raise RuntimeError('pose-guided face filtering self-test failed')
    same_head=[np.array([10,10,20,20,*([0]*10),.8],dtype=np.float32),np.array([45,15,18,18,*([0]*10),.9],dtype=np.float32)]
    if len(consolidate_face_rows(same_head,(0,0,100,100)))!=1:raise RuntimeError('same-head face candidates must consolidate to one')
    with tempfile.TemporaryDirectory() as td:
        test_path=Path(td)/'sample.bin';test_path.write_bytes(b'face-lora-selector-v3')
        content_hash=sha256_file(test_path);sid1=new_sample_id();sid2=new_sample_id()
        if len(content_hash)!=64 or sid1==sid2 or not sid1.startswith('img_') or not sid2.startswith('img_'):raise RuntimeError('stable sample_id/content hash self-test failed')
    probe=Photo(Path('probe.jpg'),123,456);probe.sample_id='img_probe';probe.content_sha256='a'*64;probe.face_detections=[FaceDetection('face_1',[1.,2.,30.,40.],.9,.1,30,True)];probe.primary_face_id='face_1';probe.review_flags=[AnalysisFinding('low_face_ratio','primary_face',.01,.018,'test flag')];probe.ai_suggestion=AISuggestion('patch_1','bundle_1','REVIEW','备选',['possible_redundancy'],'compare',True,'pending');derive_eligibility(probe)
    if probe.eligibility!='REVIEW':raise RuntimeError('eligibility REVIEW self-test failed')
    probe.face_quality=.6;probe.brisque=30.;probe.blur=60.
    if not recommendation_qualified(probe):raise RuntimeError('non-blocking REVIEW flag incorrectly blocks recommendation')
    side=Photo(Path('side.jpg'));side.face_quality=.20;side.brisque=30.;side.blur=60.;side.person_scale='近景/头肩';side.angle_class='左侧脸';side.eligibility='REVIEW';side.review_flags=[AnalysisFinding('low_face_quality','ediffiqa',.20,.25,'侧脸 FIQA 偏低')]
    front=Photo(Path('front.jpg'));front.face_quality=.65;front.brisque=30.;front.blur=60.;front.person_scale='近景/头肩';front.angle_class='正脸';front.eligibility='PASS'
    low_front=Photo(Path('low_front.jpg'));low_front.face_quality=.20;low_front.brisque=30.;low_front.blur=60.;low_front.person_scale='近景/头肩';low_front.angle_class='正脸';low_front.eligibility='REVIEW';low_front.review_flags=[AnalysisFinding('low_face_quality','ediffiqa',.20,.25,'正脸 FIQA 偏低')]
    if not recommendation_qualified(side):raise RuntimeError('usable side profile is incorrectly blocked by FIQA')
    if recommendation_qualified(low_front):raise RuntimeError('very low frontal FIQA should remain review-blocking')
    recommendation_summary=BACKEND.recompute_recommendations([front,side],2)
    if recommendation_summary.target!=2 or recommendation_summary.automatic_recommended!=2:raise RuntimeError('application recommendation contract self-test failed')
    if not BACKEND.feature_available('ranking'):raise RuntimeError('mandatory ranking feature registry self-test failed')
    if not BACKEND.feature_available('duplicates'):raise RuntimeError('Duplicate feature registry self-test failed')
    if not BACKEND.feature_available('auto_crop'):raise RuntimeError('自动裁剪 feature registry self-test failed')
    auto_crop_backend_self_test()
    if not BACKEND.feature_available('source_organizer'):raise RuntimeError('Source Organizer feature registry self-test failed')
    source_organizer_backend_self_test()
    if not BACKEND.feature_available('text_cleanup'):raise RuntimeError('Text Cleanup feature registry self-test failed')
    text_cleanup_backend_self_test()
    if side.status!='推荐' or not side.recommendation_reasons:raise RuntimeError('side-profile coverage/reason self-test failed')
    manual_extra=Photo(Path('manual_extra.jpg'));manual_extra.face_quality=.99;manual_extra.brisque=1.;manual_extra.blur=999.;manual_extra.person_scale='近景/头肩';manual_extra.angle_class='正脸';manual_extra.eligibility='PASS'
    baseline=[front,side,manual_extra];BACKEND.recompute_recommendations(baseline,2);before=[r.auto_status for r in baseline]
    manual_extra.manual_status='推荐';side.manual_status='备选';BACKEND.recompute_recommendations(baseline,2);after=[r.auto_status for r in baseline]
    if before!=after or sum(r.auto_status=='推荐' for r in baseline)!=2:raise RuntimeError('manual overlay must not change automatic recommendation baseline')
    if manual_extra.status!='推荐' or side.status!='备选':raise RuntimeError('manual overlay must only affect effective status')
    bad=Photo(Path('bad.jpg'));bad.face_quality=.6;bad.brisque=82.;bad.blur=60.;bad.person_scale='近景/头肩';bad.angle_class='正脸';bad.eligibility='REVIEW'
    BACKEND.recompute_recommendations([bad],1)
    if bad.status!='备选' or not any('BRISQUE' in x for x in bad.recommendation_reasons):raise RuntimeError('backup reason self-test failed')
    probe.duplicate_reviewed=True;restored=photo_from_dict(photo_to_dict(probe),Path('probe.jpg'),123,456)
    if restored.sample_id!=probe.sample_id or not restored.face_detections or not restored.face_detections[0].is_primary:raise RuntimeError('cache v3 round-trip self-test failed')
    if not restored.duplicate_reviewed:raise RuntimeError('duplicate review completion persistence self-test failed')
    if ANALYSIS_VERSION<1:raise RuntimeError('analysis version self-test failed')
    if not restored.ai_suggestion or restored.ai_suggestion.bundle_id!='bundle_1' or restored.ai_suggestion.decision!='pending':raise RuntimeError('AI suggestion round-trip self-test failed')
    entry=manifest_entry(probe,Path('.'));flat=flat_manifest_entry(probe,Path('.'));summary=dataset_summary([probe],'test view')
    if entry['sample_id']!='img_probe' or flat['eligibility']!='REVIEW' or summary['total_samples']!=1:raise RuntimeError('AI bundle serialization self-test failed')
    patch={'schema_version':AI_BUNDLE_SCHEMA,'bundle_id':'bundle_test','suggestions':[{'sample_id':'img_probe','content_sha256':'a'*64,'suggested_eligibility':'REVIEW','suggested_status':'备选','flags':['possible_redundancy'],'note':'test','request_full_resolution':True}]}
    bid,pending,unknown,stale=prepare_review_patch(patch,[probe],'patch_test')
    if bid!='bundle_test' or len(pending)!=1 or unknown or stale or pending[0][1].note!='test':raise RuntimeError('AI review patch validation self-test failed')
    try:prepare_review_patch({'schema_version':AI_BUNDLE_SCHEMA,'bundle_id':'x','suggestions':[{'sample_id':'img_probe'},{'sample_id':'img_probe'}]},[probe])
    except ValueError:pass
    else:raise RuntimeError('duplicate AI patch ID self-test failed')
    view_probe=ViewSpec('review',{'eligibility':'REVIEW'},'Face Quality','优先顺序',True,'view_top',25,'Face Pixels');view_restored=view_spec_from_dict(asdict(view_probe))
    if view_restored!=view_probe:raise RuntimeError('ViewSpec round-trip self-test failed')
    if not photo_matches_filters(probe,{'eligibility':'REVIEW'}) or photo_matches_filters(probe,{'eligibility':'PASS'}):raise RuntimeError('field-driven View filter self-test failed')
    if CACHE.resolve()!=BACKEND.cache_root.resolve():raise RuntimeError('application cache ownership self-test failed')
    legacy_view=view_spec_from_dict({'name':'legacy','filters':{},'sort_mode':'BRISQUE 低 → 高','best_only':False,'quick_mode':'','limit_n':10,'ranking_basis':'综合质量'})
    if legacy_view.sort_field!='BRISQUE' or legacy_view.sort_direction!='优先顺序':raise RuntimeError('legacy ViewSpec migration self-test failed')
    d1=Photo(Path('d1.jpg'));d2=Photo(Path('d2.jpg'));d3=Photo(Path('d3.jpg'))
    d1.sample_id='d1';d2.sample_id='d2';d3.sample_id='d3';d1.phash=d2.phash=d3.phash=12345;d1.face_quality=.9;d2.face_quality=.8;d3.duplicate_ignore=True
    BACKEND.regroup_duplicates([d1,d2,d3],threshold=0,adjacent=0)
    if not d1.duplicate_group or d1.duplicate_group!=d2.duplicate_group or d3.duplicate_group!=0:raise RuntimeError('duplicate exclusion self-test failed')
    gid=d1.duplicate_group
    if BACKEND.duplicate_group_ids([d1,d2,d3])!=(gid,) or BACKEND.duplicate_group_members([d1,d2,d3],gid)[0] is not d1:raise RuntimeError('duplicate group query self-test failed')
    BACKEND.duplicate_keep_best([d1,d2,d3],gid)
    if d1.manual_status!='推荐' or d2.manual_status!='淘汰' or not BACKEND.duplicate_group_reviewed([d1,d2,d3],gid):raise RuntimeError('duplicate keep-best self-test failed')
    BACKEND.duplicate_restore_auto([d1,d2,d3],gid)
    if d1.manual_status is not None or d2.manual_status is not None or d1.duplicate_reviewed or d2.duplicate_reviewed:raise RuntimeError('duplicate restore-auto self-test failed')
    BACKEND.duplicate_apply_checked([d1,d2,d3],gid,{'d2'})
    if d1.manual_status!='淘汰' or d2.manual_status!='推荐':raise RuntimeError('duplicate checked-decision self-test failed')
    if BACKEND.duplicate_set_ignored([d1,d2,d3],{'d2'},True)!=1 or not d2.duplicate_ignore:raise RuntimeError('duplicate ignore mutation self-test failed')
    restored.hard_rejects=[AnalysisFinding('read_error','test',detail='fatal')];derive_eligibility(restored)
    if restored.eligibility!='REJECT':raise RuntimeError('eligibility REJECT self-test failed')
    ok,encoded=cv2.imencode('.jpg',test_bgr)
    if not ok or encoded.size==0:raise RuntimeError('OpenCV image codec self-test failed')
    if not BACKEND.feature_available('text_cleanup'):raise RuntimeError('Text Cleanup feature registry self-test failed')
    BACKEND.text_cleanup_detector_smoke_test()
    with tempfile.TemporaryDirectory() as auto_crop_td:
        root=Path(auto_crop_td);src=root/'source.png';dst=root/'export'
        Image.new('RGB',(100,80),(120,80,40)).save(src)
        crop_photo=Photo(src);crop_photo.manual_status='推荐'
        crop_photo.feature_state[AUTO_CROP_FEATURE_KEY]={
            'version':2,
            'state':'candidate',
            'proposal':AutoCropProposal(
                auto_box=[10,5,90,75],
                box=[10,5,90,75],
                decision='accepted',
                auto_removed_area_ratio=.30,
                removed_area_ratio=.30,
                image_size=[100,80],
            ).to_dict(),
        }
        BACKEND.update_auto_crop_box(crop_photo,[20,10,80,70],(100,80));BACKEND.accept_auto_crop(crop_photo)
        exported=BACKEND.export_recommended([crop_photo],dst)
        if exported.written!=1:raise RuntimeError('自动裁剪 export count self-test failed')
        out=next(dst.iterdir())
        with Image.open(out) as check:
            if check.size!=(60,60):raise RuntimeError(f'自动裁剪 edited export size self-test failed: {check.size}')
        keep=root/'keep.png';Image.new('RGB',(64,48),(1,2,3)).save(keep)
        keep_photo=Photo(keep);keep_photo.manual_status='推荐'
        BACKEND.export_recommended([keep_photo],dst)
        copied=[p for p in dst.iterdir() if p.name.startswith('keep')]
        if len(copied)!=1:
            raise RuntimeError('自动裁剪 Keep Original export self-test failed')
        with Image.open(copied[0]) as check:
            if check.size!=(64,48):raise RuntimeError('Keep Original dimensions changed')
    pose_smoke_test()
    return 0

if __name__=='__main__':
    if '--i18n-self-test' in sys.argv:
        try:
            a=QApplication(sys.argv);a.setApplicationName('LoRA 数据集筛选与字幕清理')
            with tempfile.TemporaryDirectory() as td:
                manager=initialize_i18n(a,settings_path=Path(td)/'ui.ini')
                if not manager.set_language('en_US'):raise RuntimeError(manager.last_error or 'English catalog failed to load')
                if QCoreApplication.translate('MainWindow','LoRA 数据集筛选')!='LoRA Dataset Selector':raise RuntimeError('packaged English catalog translation failed')
                if QCoreApplication.translate('AutoCropReviewDialog','自动裁剪复核')!='Auto Crop Review':raise RuntimeError('packaged Auto Crop catalog translation failed')
                if not manager.set_language('zh_CN'):raise RuntimeError('failed to restore source language')
                if QCoreApplication.translate('AutoCropReviewDialog','自动裁剪复核')!='自动裁剪复核':raise RuntimeError('source language restore failed')
            sys.exit(0)
        except Exception as e:
            print('I18N SELF-TEST FAILED:',e);traceback.print_exc();sys.exit(1)
    if '--self-test' in sys.argv:
        try:sys.exit(self_test())
        except Exception as e:
            print('SELF-TEST FAILED:',e);traceback.print_exc();sys.exit(1)
    a=QApplication(sys.argv);a.setApplicationName('LoRA 数据集筛选与字幕清理');initialize_i18n(a);w=Window();w.show();sys.exit(a.exec())
