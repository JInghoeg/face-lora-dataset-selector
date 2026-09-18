"""本地 LoRA 数据集筛选与批量字幕清理。"""
from __future__ import annotations
import hashlib, json, math, os, pickle, shutil, sys, tempfile, traceback, urllib.request
from collections import Counter, defaultdict, OrderedDict
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

try:
    import cv2, mediapipe as mp, numpy as np, onnxruntime as ort
    from PIL import Image
    from rapidocr_onnxruntime.ch_ppocr_det.text_detect import TextDetector
    from PySide6.QtCore import QObject, QThread, Qt, Signal, QSize, QTimer
    from PySide6.QtGui import QColor, QIcon, QImage, QImageReader, QPainter, QPen, QPixmap
    from PySide6.QtWidgets import QApplication, QButtonGroup, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPushButton, QProgressBar, QSpinBox, QSplitter, QTabWidget, QVBoxLayout, QWidget
    from mediapipe.tasks import python
    from mediapipe.tasks.python.vision.pose_landmarker import PoseLandmarker, PoseLandmarkerOptions
    from mediapipe.tasks.python.vision.core.vision_task_running_mode import VisionTaskRunningMode
except ImportError as exc:
    msg=f"缺少依赖：{exc}\n请先双击运行 安装.bat，或在本目录运行：python -m pip install -r requirements.txt"
    print(msg)
    if getattr(sys,'frozen',False):
        try:Path(sys.executable).with_name('startup-error.txt').write_text(msg,encoding='utf-8')
        except Exception:pass
    sys.exit(1)

APP_DIR=Path(__file__).resolve().parent; MODELS=APP_DIR/'models'; CACHE=APP_DIR/'cache'
THUMB_CACHE=CACHE/'thumbnails'
POSE=MODELS/'pose_landmarker_lite.task'; YUNET=MODELS/'yunet_2023mar.onnx'; EDIFF=MODELS/'ediffiqa_t.onnx'; BRISQUE=MODELS/'brisque_model_live.yml'; BRISQUE_RANGE=MODELS/'brisque_range_live.yml'; DDDFA=MODELS/'mb1_120x120.onnx'; DDDFA_NORM=MODELS/'param_mean_std_62d_120x120.pkl'; TEXT=MODELS/'ppocrv5_mobile_det'/'inference.onnx'; MIGAN=MODELS/'migan_pipeline_v2.onnx'
POSE_URL='https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task'
MIGAN_URL='https://huggingface.co/andraniksargsyan/migan/resolve/1538c135034b8cfe7a8472f34d09c8a5a45b17a7/migan_pipeline_v2.onnx?download=true'
MIGAN_SHA256='6f1f3530a1a2324b19752018ce756088b07973cda8d7d890034ace5c8a48c40b'
MIGAN_SIZE=28079181
EXT={'.jpg','.jpeg','.png','.webp','.bmp','.tif','.tiff'}; PAGE=120; COLORS={'推荐':'#d9f4df','备选':'#fff2bf','淘汰':'#ffd9d9'}; SCALES=('近景/头肩','半身','大半身','全身'); YAWS=('正脸','左3/4','右3/4','左侧脸','右侧脸'); PITCHES=('正常','仰头','低头')

@dataclass
class Photo:
    path:Path; file_size:int=0; mtime_ns:int=0; width:int=0; height:int=0; faces:int=0; face_ratio:float=0.; face_px:int=0; blur:float=0.; brightness:float=0.; face_quality:float=0.; brisque:float=0.; yaw:float=0.; pitch:float=0.; roll:float=0.; angle_class:str='未检测'; pitch_class:str='未检测'; person_scale:str='未检测身体'; phash:int=0; duplicate_group:int=0; reasons:list[str]=field(default_factory=list); auto_status:str='备选'; manual_status:Optional[str]=None
    @property
    def status(self): return self.manual_status or self.auto_status
    @property
    def source(self): return self.path.stem.split('_frame_',1)[0] if '_frame_' in self.path.stem else str(self.path.parent.resolve())
@dataclass
class TextPhoto:
    path:Path; file_size:int; mtime_ns:int; boxes:list=field(default_factory=list); selected:list=field(default_factory=list); manual:list=field(default_factory=list); scores:list=field(default_factory=list); suggested:list=field(default_factory=list); width:int=0; height:int=0

def key(path): return str(path.resolve()).casefold()

def phash_int(image):
    """64-bit perceptual hash compatible with the previous ImageHash-style pHash."""
    gray=image.convert('L').resize((32,32),Image.Resampling.LANCZOS)
    low=cv2.dct(np.asarray(gray,dtype=np.float32))[:8,:8]
    bits=(low>np.median(low)).reshape(-1)
    value=0
    for bit in bits:value=(value<<1)|int(bit)
    return value
def cache_path(folder): return CACHE/(hashlib.sha256(key(folder).encode()).hexdigest()[:24]+'.json')
def load_data(folder):
    try:
        data=json.loads(cache_path(folder).read_text(encoding='utf-8')); return data if data.get('version',data.get('schema_version')) in (1,2) else {}
    except Exception:return {}
def load_cached(folder):
    d=load_data(folder);return {x['path'].casefold():x for x in d.get('records',[])} if d.get('version',d.get('schema_version'))==2 else {}
def manual_states(folder):
    return {x['path'].casefold():x.get('manual_status') for x in load_data(folder).get('records',[]) if x.get('manual_status')}
def photo_to_dict(p):
    d=asdict(p); d['path']=str(p.path.resolve()); return d
def photo_from_dict(d,path,size,mtime):
    p=Photo(path,size,mtime)
    for name in p.__dataclass_fields__:
        if name not in ('path','file_size','mtime_ns','reasons') and name in d:setattr(p,name,d[name])
    p.reasons=list(d.get('reasons',[])); return p
def save_data(folder,records,target):
    CACHE.mkdir(exist_ok=True); dest=cache_path(folder); tmp=dest.with_suffix('.tmp'); tmp.write_text(json.dumps({'version':2,'folder':str(folder.resolve()),'target':target,'records':[photo_to_dict(x) for x in records]},ensure_ascii=False,separators=(',',':')),encoding='utf-8'); tmp.replace(dest)
def ensure_pose():
    if not POSE.exists():
        POSE.parent.mkdir(exist_ok=True); urllib.request.urlretrieve(POSE_URL,POSE)
    run=Path(tempfile.gettempdir())/'face_lora_selector'/POSE.name; run.parent.mkdir(exist_ok=True)
    if not run.exists() or run.stat().st_size!=POSE.stat().st_size:shutil.copy2(POSE,run)
    return run

def ensure_migan():
    """首次使用时从上游下载 MI-GAN，并在落盘前校验大小与 SHA-256。"""
    if MIGAN.exists() and MIGAN.stat().st_size==MIGAN_SIZE:
        return MIGAN
    MIGAN.parent.mkdir(parents=True,exist_ok=True)
    tmp=MIGAN.with_suffix(MIGAN.suffix+'.part')
    try:
        if tmp.exists():tmp.unlink()
        req=urllib.request.Request(MIGAN_URL,headers={'User-Agent':'Face-LoRA-Dataset-Selector/0.1'})
        h=hashlib.sha256();size=0
        with urllib.request.urlopen(req,timeout=60) as src,tmp.open('wb') as dst:
            while True:
                chunk=src.read(1024*1024)
                if not chunk:break
                dst.write(chunk);h.update(chunk);size+=len(chunk)
        if size!=MIGAN_SIZE or h.hexdigest().lower()!=MIGAN_SHA256:
            raise RuntimeError(f'MI-GAN 下载校验失败：{size} bytes / {h.hexdigest()}')
        tmp.replace(MIGAN)
    except Exception:
        try:
            if tmp.exists():tmp.unlink()
        except Exception:pass
        raise
    return MIGAN
def native_model(path):
    """OpenCV Windows 原生层不能稳定打开中文路径，给它 ASCII 运行时副本。"""
    run=Path(tempfile.gettempdir())/'face_lora_selector'/path.name;run.parent.mkdir(exist_ok=True)
    if not run.exists() or run.stat().st_size!=path.stat().st_size:shutil.copy2(path,run)
    return run
def required(paths):
    missing=[str(x) for x in paths if not x.exists()]
    if missing:raise RuntimeError('缺少模型文件：\n'+'\n'.join(missing))
def yaw_class(y): return '正脸' if abs(y)<15 else ('左' if y>0 else '右')+('3/4' if abs(y)<45 else '侧脸')
def pitch_class(p): return '仰头' if p>=22 else ('低头' if p<=-12 else '正常')
def person_scale(points):
    if not points:return '近景/头肩'
    good=lambda ids:any(0<=points[i].x<=1 and 0<=points[i].y<=1 and getattr(points[i],'visibility',0)>=.45 for i in ids)
    return '全身' if good((27,28)) else '大半身' if good((25,26)) else '半身' if good((23,24)) else '近景/头肩'

class QualityModels:
    pts=np.array([[38.2946,51.6963],[73.5318,51.5014],[56.0252,71.7366],[41.5493,92.3655],[70.7299,92.2041]],np.float32)
    def __init__(self):
        required([YUNET,EDIFF,BRISQUE,BRISQUE_RANGE,DDDFA,DDDFA_NORM]); self.yunet_path=native_model(YUNET);self.brisque_model=native_model(BRISQUE);self.brisque_range=native_model(BRISQUE_RANGE);self.det=cv2.FaceDetectorYN.create(str(self.yunet_path),'',(320,320),.7,.3,5000); self.fq=ort.InferenceSession(str(EDIFF),providers=['CPUExecutionProvider']); self.fqin=self.fq.get_inputs()[0].name; self.pose=ort.InferenceSession(str(DDDFA),providers=['CPUExecutionProvider']); self.posein=self.pose.get_inputs()[0].name
        with DDDFA_NORM.open('rb') as f:n=pickle.load(f)
        self.mean=n['mean'].astype(np.float32); self.std=n['std'].astype(np.float32)
    def faces(self,img):self.det.setInputSize((img.shape[1],img.shape[0])); return self.det.detect(img)[1]
    @staticmethod
    def crop(img,roi):
        sx,sy,ex,ey=map(lambda x:int(round(x)),roi); out=np.zeros((max(1,ey-sy),max(1,ex-sx),3),np.uint8); h,w=img.shape[:2];x0,x1=max(0,sx),min(w,ex);y0,y1=max(0,sy),min(h,ey)
        if x1>x0 and y1>y0:out[y0-sy:y1-sy,x0-sx:x1-sx]=img[y0:y1,x0:x1]
        return out
    def quality(self,img,face):
        m,_=cv2.estimateAffinePartial2D(face[4:14].reshape(5,2).astype(np.float32),self.pts,method=cv2.LMEDS)
        if m is None:return 0.
        rgb=cv2.cvtColor(cv2.warpAffine(img,m,(112,112)),cv2.COLOR_BGR2RGB).astype(np.float32); x=np.transpose((rgb/255-.5)/.5,(2,0,1))[None].astype(np.float32);return float(np.squeeze(self.fq.run(None,{self.fqin:x})[0]))
    def brisque(self,img):
        r=cv2.quality.QualityBRISQUE_compute(img,str(self.brisque_model),str(self.brisque_range));return float(r[0] if isinstance(r,tuple) else r[0])
    def head(self,img,f):
        x,y,w,h=map(float,f[:4]); old=(w+h)/2; cx=x+w/2;cy=y+h/2+old*.14;s=int(old*1.58); c=cv2.resize(self.crop(img,(cx-s/2,cy-s/2,cx+s/2,cy+s/2)),(120,120)).astype(np.float32); out=self.pose.run(None,{self.posein:((c-127.5)/128).transpose(2,0,1)[None]})[0][0]*self.std+self.mean; r=out[:12].reshape(3,4)[:,:3];r1=r[0]/np.linalg.norm(r[0]);r2=r[1]/np.linalg.norm(r[1]);r=np.stack((r1,r2,np.cross(r1,r2))); yaw=math.degrees(math.asin(np.clip(r[2,0],-1,1)));cs=max(1e-6,math.cos(math.radians(yaw)));return yaw,math.degrees(math.atan2(r[2,1]/cs,r[2,2]/cs)),math.degrees(math.atan2(r[1,0]/cs,r[0,0]/cs))

class Analyzer(QObject):
    status=Signal(str); progress=Signal(int,int,str); finished=Signal(object); failed=Signal(str)
    def __init__(self,folder):super().__init__();self.folder=folder
    def run(self):
        try:
            files=sorted((x for x in self.folder.rglob('*') if x.is_file() and x.suffix.lower() in EXT),key=lambda x:str(x).lower())
            if not files:raise RuntimeError('没有找到图片。')
            old=load_cached(self.folder);manual=manual_states(self.folder); result=[]; todo=[]
            for i,path in enumerate(files):
                stat=path.stat(); cache=old.get(key(path))
                if cache and cache.get('file_size')==stat.st_size and cache.get('mtime_ns')==stat.st_mtime_ns:result.append(photo_from_dict(cache,path,stat.st_size,stat.st_mtime_ns))
                else:result.append(None);todo.append((i,path,stat.st_size,stat.st_mtime_ns))
            if todo:
                self.status.emit(f'分析 {len(todo)} 张变化图片；其余恢复缓存…');qm=QualityModels();opt=PoseLandmarkerOptions(base_options=python.BaseOptions(model_asset_path=str(ensure_pose())),running_mode=VisionTaskRunningMode.IMAGE,num_poses=1,min_pose_detection_confidence=.5,min_pose_presence_confidence=.5)
                with PoseLandmarker.create_from_options(opt) as pl:
                    for n,(i,p,s,m) in enumerate(todo,1):result[i]=self.one(p,qm,pl,s,m);self.progress.emit(n,len(todo),p.name)
            rec=[x for x in result if x]
            for r in rec:r.manual_status=manual.get(key(r.path),r.manual_status)
            self.groups(rec);self.base(rec);self.finished.emit(rec)
        except Exception:self.failed.emit(traceback.format_exc())
    @staticmethod
    def one(path,qm,pl,size,mtime):
        r=Photo(path,size,mtime)
        try:
            with Image.open(path) as im:im=im.convert('RGB');r.width,r.height=im.size;r.phash=phash_int(im);rgb=np.asarray(im)
            bgr=cv2.cvtColor(rgb,cv2.COLOR_RGB2BGR);gray=cv2.cvtColor(bgr,cv2.COLOR_BGR2GRAY);r.brightness=float(gray.mean()); fs=qm.faces(bgr);r.faces=0 if fs is None else len(fs);po=pl.detect(mp.Image(image_format=mp.ImageFormat.SRGB,data=rgb));r.person_scale=person_scale(po.pose_landmarks[0] if po.pose_landmarks else None)
            if r.faces==1:
                f=fs[0];x,y,w,h=map(float,f[:4]);l,t=max(0,int(x)),max(0,int(y));rr,bb=min(r.width,int(x+w)),min(r.height,int(y+h));r.face_ratio=w*h/max(1,r.width*r.height);r.face_px=int(min(w,h));crop=gray[t:bb,l:rr];r.blur=float(cv2.Laplacian(crop,cv2.CV_64F).var()) if crop.size else 0.;r.face_quality=qm.quality(bgr,f);r.brisque=qm.brisque(bgr);r.yaw,r.pitch,r.roll=qm.head(bgr,f);r.angle_class=yaw_class(r.yaw);r.pitch_class=pitch_class(r.pitch)
            else:r.blur=float(cv2.Laplacian(gray,cv2.CV_64F).var());r.brisque=qm.brisque(bgr)
            dark,bright=float((gray<20).mean()),float((gray>235).mean())
            if r.faces==0:r.reasons.append('YuNet 未检测到人脸')
            elif r.faces>1:r.reasons.append(f'YuNet 检测到 {r.faces} 张人脸')
            if r.width<512 or r.height<512:r.reasons.append('图片分辨率低于 512px')
            if r.faces==1 and r.face_px<120:r.reasons.append('人脸实际像素过小')
            if r.faces==1 and r.face_ratio<.018:r.reasons.append('脸部占画面比例过低')
            if r.faces==1 and r.blur<25:r.reasons.append('人脸严重模糊')
            if r.faces==1 and r.face_quality<.25:r.reasons.append('eDifFIQA 人脸质量过低')
            if r.brisque>80:r.reasons.append('BRISQUE 整图质量过低')
            if r.brightness<28 or r.brightness>228 or dark>.55 or bright>.55:r.reasons.append('严重欠曝或过曝')
        except Exception as e:r.reasons.append(f'无法读取或分析图片：{e}')
        return r
    @staticmethod
    def groups(rs,threshold=8,adjacent=16):
        """以组内质量最佳图为锚点分组，避免 A≈B≈C 的无限传递合并。"""
        for r in rs:r.duplicate_group=0
        remaining=set(i for i,r in enumerate(rs) if r.phash)
        group_no=1
        while remaining:
            anchor=max(remaining,key=lambda i:rank(rs[i]));remaining.remove(anchor);members=[anchor]
            for candidate in list(remaining):
                a,b=rs[anchor],rs[candidate];distance=bin(a.phash^b.phash).count('1')
                same_source=a.source==b.source
                # 连续帧只能在同源、同景别、姿态相近时放宽；每张都直接比较锚点。
                close=distance<=threshold or (same_source and distance<=adjacent and a.person_scale==b.person_scale and abs(a.yaw-b.yaw)<=25 and abs(a.pitch-b.pitch)<=25)
                if close:members.append(candidate);remaining.remove(candidate)
            if len(members)>1:
                for i in members:rs[i].duplicate_group=group_no
                group_no+=1
    @staticmethod
    def base(rs):
        for r in rs:
            if r.manual_status is None:r.auto_status='淘汰' if r.reasons else '备选'

def rank(r):return(r.face_quality,-r.brisque,r.blur)
def recommendation_qualified(r):
    """自动推荐的最低质量门槛；未通过者仍是备选，不会被强行补位。"""
    return not r.reasons and r.face_quality>=.45 and r.brisque<=70 and r.blur>=40
def group_entries(rs,group,qualified=False):
    entries=[r for r in rs if r.duplicate_group==group]
    if qualified:
        good=[r for r in entries if recommendation_qualified(r)]
        entries=good or entries
    return sorted(entries,key=rank,reverse=True)
def group_best(rs):
    """质量门槛后的唯一组代表；同组其余图保持备选，绝不参与后续桶补位。"""
    result=[];seen=set()
    for r in sorted(rs,key=rank,reverse=True):
        if r.duplicate_group and r.duplicate_group in seen:continue
        result.append(r)
        if r.duplicate_group:seen.add(r.duplicate_group)
    return result
def alloc(total,names,weights):
    if not names:return {x:0 for x in names}
    w=sum(weights[x] for x in names);raw={x:total*weights[x]/w for x in names};out={x:int(raw[x]) for x in names}
    for x in sorted(names,key=lambda a:raw[a]-out[a],reverse=True)[:total-sum(out.values())]:out[x]+=1
    return out
def recommend(rs,target):
    for r in rs:
        if r.manual_status is None:r.auto_status='淘汰' if r.reasons else '备选'
    fixed=[r for r in rs if r.manual_status=='推荐'];remain=max(0,target-len(fixed))
    # 质量门槛 -> 每个 duplicate group 的最佳代表 -> 景别 × Yaw 分桶。
    pool=group_best([r for r in rs if recommendation_qualified(r) and r.manual_status is None]);b=defaultdict(list);sc=defaultdict(list)
    for r in pool:b[r.person_scale,r.angle_class].append(r);sc[r.person_scale].append(r)
    for x in list(b.values())+list(sc.values()):x.sort(key=rank,reverse=True)
    sq=alloc(remain,[x for x in SCALES if sc[x]],{'近景/头肩':.35,'半身':.3,'大半身':.2,'全身':.15});used={r.duplicate_group for r in fixed if r.duplicate_group};chosen=[];ids=set();got=Counter()
    def take(xs,n):
        for r in xs:
            if len(chosen)>=remain or n<=0:return
            if id(r) in ids or (r.duplicate_group and r.duplicate_group in used):continue
            chosen.append(r);ids.add(id(r));got[r.person_scale]+=1;n-=1
            if r.duplicate_group:used.add(r.duplicate_group)
    for s in [x for x in SCALES if sc[x]]:
        yn=[x for x in YAWS if b[s,x]]
        for y,n in alloc(sq[s],yn,{'正脸':.35,'左3/4':.2,'右3/4':.2,'左侧脸':.125,'右侧脸':.125}).items():take(b[s,y],n)
        take(sc[s],max(0,sq[s]-got[s]))
    # 仅在现有合格组代表内、按景别完成度补位；不放宽质量或重复组约束。
    while len(chosen)<remain:
        progress=False
        for s in sorted(sq,key=lambda x:got[x]/max(1,sq[x])):
            n=len(chosen);take(sc[s],1);progress|=len(chosen)>n
        if not progress:break
    for r in chosen:r.auto_status='推荐'

def det_config():return {'model_path':str(TEXT),'limit_side_len':960,'limit_type':'min','mean':[.485,.456,.406],'std':[.229,.224,.225],'thresh':.3,'box_thresh':.6,'max_candidates':1000,'unclip_ratio':1.5,'use_dilation':False,'score_mode':'fast','use_cuda':False,'use_dml':False,'intra_op_num_threads':-1,'inter_op_num_threads':-1}
class TextScan(QObject):
    progress=Signal(int,int,str);finished=Signal(object);failed=Signal(str)
    def __init__(self,folder,cached):super().__init__();self.folder=folder;self.cached=cached
    @staticmethod
    def detected(det, image):
        """使用 RapidOCR 自带 DB 后处理，同时取回检测置信度。"""
        shape=image.shape[:2];det.preprocess_op=det.get_preprocess(max(shape));x=det.preprocess_op(image)
        if x is None:return [],[]
        boxes,scores=det.postprocess_op(det.infer(x)[0],shape);boxes=det.filter_tag_det_res(boxes,shape)
        boxes=np.asarray(boxes).astype(int).tolist() if len(boxes) else []
        scores=[float(v) for v in np.asarray(scores).reshape(-1)]
        return boxes,(scores if len(scores)==len(boxes) else [1.0]*len(boxes))
    @staticmethod
    def source_name(path): return path.stem.split('_frame_',1)[0] if '_frame_' in path.stem else str(path.parent.resolve())
    @staticmethod
    def suggest(records,targets=None):
        """保留全部文字框；只把典型字幕/overlay 结构默认选入修复。"""
        repeats=defaultdict(int)
        for r in (targets or records):
            try:
                im=cv2.imdecode(np.fromfile(str(r.path),np.uint8),cv2.IMREAD_GRAYSCALE);h,w=im.shape[:2]
                for b in r.boxes:
                    a=np.asarray(b); repeats[(TextScan.source_name(r.path),round(float(a[:,0].mean())/w,1),round(float(a[:,1].mean())/h,1))]+=1
            except Exception:pass
        for r in records:
            try:
                im=cv2.imdecode(np.fromfile(str(r.path),np.uint8),cv2.IMREAD_GRAYSCALE);h,w=im.shape[:2]
                values=[]
                for b in r.boxes:
                    a=np.asarray(b);bw=max(1,a[:,0].max()-a[:,0].min());bh=max(1,a[:,1].max()-a[:,1].min());cx=float(a[:,0].mean())/w;cy=float(a[:,1].mean())/h
                    edge=cy<.18 or cy>.70; line=bw/w>=.12 and bw/bh>=1.35; repeated=repeats[(TextScan.source_name(r.path),round(cx,1),round(cy,1))]>=2
                    values.append(bool((edge and line) or (repeated and edge and bw/w>=.06)))
                r.suggested=values;r.selected=list(values);r.manual=[False]*len(values)
            except Exception:r.suggested=[False]*len(r.boxes);r.selected=[False]*len(r.boxes);r.manual=[False]*len(r.boxes)
    def run(self):
        try:
            fs=sorted((x for x in self.folder.rglob('*') if x.is_file() and x.suffix.lower() in EXT),key=lambda x:str(x).lower());det=None;out=[];fresh=[]
            for i,p in enumerate(fs,1):
                st=p.stat();old=self.cached.get(key(p))
                if old and old.get('file_size')==st.st_size and old.get('mtime_ns')==st.st_mtime_ns:
                    boxes=list(old.get('boxes',[]));selected=list(old.get('selected',[]));manual=list(old.get('manual',[False]*len(boxes)));scores=list(old.get('scores',[1.0]*len(boxes)));suggested=list(old.get('suggested',selected));selected=(selected+[False]*len(boxes))[:len(boxes)];manual=(manual+[False]*len(boxes))[:len(boxes)];scores=(scores+[1.0]*len(boxes))[:len(boxes)];suggested=(suggested+[False]*len(boxes))[:len(boxes)];out.append(TextPhoto(p,st.st_size,st.st_mtime_ns,boxes,selected,manual,scores,suggested,int(old.get('width',0)),int(old.get('height',0))))
                else:
                    required([TEXT]);det=det or TextDetector(det_config());im=cv2.imdecode(np.fromfile(str(p),np.uint8),cv2.IMREAD_COLOR);boxes,scores=([],[]) if im is None else self.detected(det,im);h,w=im.shape[:2] if im is not None else (0,0);r=TextPhoto(p,st.st_size,st.st_mtime_ns,boxes,[False]*len(boxes),[False]*len(boxes),scores,[],w,h);out.append(r);fresh.append(r)
                self.progress.emit(i,len(fs),p.name)
            if fresh:self.suggest(out,fresh)
            self.finished.emit(out)
        except Exception:self.failed.emit(traceback.format_exc())

class ImagePreview(QLabel):
    drawn=Signal(object)
    def __init__(self):super().__init__('选择缩略图查看文字框');self.setMinimumSize(520,400);self.setAlignment(Qt.AlignCenter);self.setStyleSheet('background:#222;color:#ddd');self.img=None;self.boxes=[];self.selected=[];self.manual=[];self.add=False;self.start=None;self.now=None
    def set_data(self,img,boxes,selected,manual=None):self.img=img;self.boxes=boxes;self.selected=selected;self.manual=manual or [False]*len(boxes);self.start=self.now=None;self.update()
    def scale(self):
        if self.img is None:return 1,0,0
        h,w=self.img.shape[:2];s=min(self.width()/w,self.height()/h);return s,(self.width()-w*s)/2,(self.height()-h*s)/2
    def paintEvent(self,e):
        super().paintEvent(e)
        if self.img is None:return
        h,w=self.img.shape[:2];rgb=cv2.cvtColor(self.img,cv2.COLOR_BGR2RGB);pix=QPixmap.fromImage(QImage(rgb.data,w,h,rgb.strides[0],QImage.Format_RGB888).copy());s,ox,oy=self.scale();p=QPainter(self);p.drawPixmap(int(ox),int(oy),int(w*s),int(h*s),pix)
        for b,on,manual in zip(self.boxes,self.selected,self.manual):
            a=np.asarray(b);p.setPen(QPen(QColor('#32e675' if on else ('#ffb000' if manual else '#999')),2));p.drawRect(int(ox+a[:,0].min()*s),int(oy+a[:,1].min()*s),int((a[:,0].max()-a[:,0].min())*s),int((a[:,1].max()-a[:,1].min())*s))
        if self.start and self.now:p.setPen(QPen(QColor('#3da5ff'),2));p.drawRect(int(self.start[0]),int(self.start[1]),int(self.now[0]-self.start[0]),int(self.now[1]-self.start[1]))
        p.end()
    def mousePressEvent(self,e):
        if self.add and self.img is not None:self.start=self.now=(e.position().x(),e.position().y());self.update()
    def mouseMoveEvent(self,e):
        if self.start:self.now=(e.position().x(),e.position().y());self.update()
    def mouseReleaseEvent(self,e):
        if not self.start or not self.img:return
        x0,y0=map(min,zip(self.start,self.now));x1,y1=map(max,zip(self.start,self.now));s,ox,oy=self.scale();self.start=self.now=None
        if x1-x0>8 and y1-y0>8:self.drawn.emit([[int((x0-ox)/s),int((y0-oy)/s)],[int((x1-ox)/s),int((y0-oy)/s)],[int((x1-ox)/s),int((y1-oy)/s)],[int((x0-ox)/s),int((y1-oy)/s)]])
        self.update()

class MIRepair:
    """官方 MI-GAN ONNX pipeline；每个连通字幕区域独立取上下文后修复。"""
    def __init__(self): self.session=ort.InferenceSession(str(ensure_migan()),providers=['CPUExecutionProvider'])
    def run(self,image,mask):
        joined=cv2.dilate(mask,cv2.getStructuringElement(cv2.MORPH_RECT,(25,13)))
        contours,_=cv2.findContours(joined,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE);result=image.copy();h,w=mask.shape
        for c in contours:
            x,y,bw,bh=cv2.boundingRect(c);pad=max(48,int(max(bw,bh)*.55));x0=max(0,x-pad);y0=max(0,y-pad);x1=min(w,x+bw+pad);y1=min(h,y+bh+pad)
            local_mask=mask[y0:y1,x0:x1]
            if not np.any(local_mask):continue
            rgb=cv2.cvtColor(image[y0:y1,x0:x1],cv2.COLOR_BGR2RGB);known=255-local_mask
            feeds={'image':np.ascontiguousarray(rgb.transpose(2,0,1)[None]),'mask':np.ascontiguousarray(known[None,None])}
            out=self.session.run(None,feeds)[0][0]
            if out.shape[0]==3:out=out.transpose(1,2,0)
            fixed=cv2.cvtColor(out,cv2.COLOR_RGB2BGR);area=result[y0:y1,x0:x1];area[local_mask>0]=fixed[local_mask>0]
        return result

class SubtitleTab(QWidget):
    PAGE_SIZE=80
    def __init__(self):
        super().__init__();self.folder=None;self.output=None;self.records=[];self.current=-1;self.thread=None;self.worker=None;self.page=0;self.visible=[];self.thumb_memory=OrderedDict();self.thumb_threads=[];self.thumb_token=0;self.item_by_record={};self.repair_model=None;self.save_timer=QTimer(self);self.save_timer.setSingleShot(True);self.save_timer.timeout.connect(self.save);self.ui();self.restore()
    def ui(self):
        l=QVBoxLayout(self);p=QGridLayout();self.input=QLabel('未选择输入目录');self.output_label=QLabel('未选择输出目录');a=QPushButton('选择输入目录');b=QPushButton('选择输出目录');a.clicked.connect(self.pick_input);b.clicked.connect(self.pick_output);p.addWidget(a,0,0);p.addWidget(self.input,0,1);p.addWidget(b,1,0);p.addWidget(self.output_label,1,1);l.addLayout(p)
        c=QHBoxLayout();self.scan=QPushButton('扫描文字');self.scan.clicked.connect(self.start_scan);self.add=QPushButton('添加区域：关');self.add.setCheckable(True);self.add.toggled.connect(lambda x:(self.preview.__setattr__('add',x),self.add.setText('添加区域：开' if x else '添加区域：关')));dele=QPushButton('删除选中区域');dele.clicked.connect(self.delete);self.method=QComboBox();self.method.addItems(['AI 修复（MI-GAN）','快速修复（TELEA）','Navier-Stokes']);self.expand=QSpinBox();self.expand.setRange(0,40);self.expand.setValue(5);self.expand.setPrefix('Mask 扩张 ');self.radius=QSpinBox();self.radius.setRange(1,30);self.radius.setValue(4);self.radius.setPrefix('修复半径 ');pre=QPushButton('预览修复');pre.clicked.connect(self.preview_repair);batch=QPushButton('批量处理到新目录');batch.clicked.connect(self.batch)
        for x in (self.scan,self.add,dele,QLabel('方式'),self.method,self.expand,self.radius,pre,batch):c.addWidget(x)
        l.addLayout(c)
        f=QHBoxLayout();self.view=QComboBox();self.view.addItems(['全部图片','仅显示需要修复','仅显示有文字','仅显示人工修改']);self.view.currentTextChanged.connect(self.filter_changed);all_s=QPushButton('全选建议修复');all_s.clicked.connect(self.select_suggested);none=QPushButton('取消当前页全部');none.clicked.connect(self.clear_page);self.min_height=QSpinBox();self.min_height.setRange(2,80);self.min_height.setValue(6);self.min_height.setPrefix('最小高 ');self.min_area=QSpinBox();self.min_area.setRange(4,5000);self.min_area.setValue(36);self.min_area.setPrefix('最小面积 ');self.min_conf=QDoubleSpinBox();self.min_conf.setRange(0,.99);self.min_conf.setSingleStep(.05);self.min_conf.setValue(.0);self.min_conf.setPrefix('最低置信度 ')
        for x in (QLabel('查看'),self.view,all_s,none,self.min_height,self.min_area,self.min_conf):f.addWidget(x)
        for x in (self.min_height,self.min_area,self.min_conf):x.valueChanged.connect(self.filter_changed)
        f.addStretch(1);self.summary=QLabel('检测到文字：0 · 建议修复：0 · 人工修改：0');f.addWidget(self.summary);l.addLayout(f);self.bar=QProgressBar();l.addWidget(self.bar)
        s=QSplitter(Qt.Horizontal);self.list=QListWidget();self.list.setViewMode(QListWidget.IconMode);self.list.setResizeMode(QListWidget.Adjust);self.list.setMovement(QListWidget.Static);self.list.setIconSize(QSize(110,110));self.list.setGridSize(QSize(135,150));self.list.itemClicked.connect(self.show);s.addWidget(self.list);r=QWidget();rl=QVBoxLayout(r);self.preview=ImagePreview();self.preview.drawn.connect(self.new_box);rl.addWidget(self.preview,1);rl.addWidget(QLabel('灰色＝检测到文字；绿色＝建议/已选修复；橙色＝人工修改。勾选仅控制修复。'));self.boxes=QListWidget();self.boxes.itemChanged.connect(self.checked);rl.addWidget(self.boxes);nav=QHBoxLayout();self.prev_image=QPushButton('上一张');self.prev_image.clicked.connect(lambda:self.move_image(-1));self.next_image=QPushButton('下一张');self.next_image.clicked.connect(lambda:self.move_image(1));nav.addWidget(self.prev_image);nav.addWidget(self.next_image);rl.addLayout(nav);s.addWidget(r);s.setSizes([500,800]);l.addWidget(s,1);pg=QHBoxLayout();self.prev_page=QPushButton('上一页');self.prev_page.clicked.connect(lambda:self.change_page(-1));self.page_label=QLabel('第 0/0 页');self.next_page=QPushButton('下一页');self.next_page.clicked.connect(lambda:self.change_page(1));pg.addStretch(1);pg.addWidget(self.prev_page);pg.addWidget(self.page_label);pg.addWidget(self.next_page);pg.addStretch(1);l.addLayout(pg)
    def pick_input(self):
        x=QFileDialog.getExistingDirectory(self,'选择待去字幕图片目录',str(self.folder or APP_DIR))
        if x:self.folder=Path(x);self.input.setText(x);self.schedule_save()
    def pick_output(self):
        x=QFileDialog.getExistingDirectory(self,'选择输出目录（只写新文件）',str(self.output or APP_DIR))
        if x:self.output=Path(x);self.output_label.setText(x);self.schedule_save()
    def state_records(self):
        try:
            d=json.loads((CACHE/'subtitle_cleaner.json').read_text(encoding='utf-8'));return {x['path'].casefold():x for x in d.get('records',[])} if self.folder and d.get('folder','').casefold()==key(self.folder) else {}
        except Exception:return {}
    def start_scan(self):
        if not self.folder or self.thread and self.thread.isRunning():return
        self.scan.setEnabled(False);self.bar.setRange(0,0);self.thread=QThread(self);self.worker=TextScan(self.folder,self.state_records());self.worker.moveToThread(self.thread);self.thread.started.connect(self.worker.run);self.worker.progress.connect(self.scan_progress);self.worker.finished.connect(self.scanned);self.worker.failed.connect(lambda e:QMessageBox.critical(self,'扫描失败',e));self.worker.finished.connect(self.thread.quit);self.worker.failed.connect(self.thread.quit);self.thread.finished.connect(self.done);self.thread.start()
    def scan_progress(self,n,t,name):self.bar.setRange(0,t);self.bar.setValue(n);self.bar.setFormat(f'扫描文字 {n}/{t}: {name}')
    def scanned(self,rs):self.records=rs;self.current=-1;self.page=0;self.refresh();self.schedule_save();self.bar.setFormat(f'扫描完成：{len(rs)} 张')
    def done(self):self.scan.setEnabled(True);self.worker=None;self.thread.deleteLater();self.thread=None
    def eligible(self,r):
        h,w=self.current_size(r);return [i for i,b in enumerate(r.boxes) if max(1,np.ptp(np.asarray(b)[:,1]))>=max(self.min_height.value(),h*.004) and abs(cv2.contourArea(np.asarray(b,np.float32)))>=max(self.min_area.value(),h*w*.00001) and (r.scores[i] if i<len(r.scores) else 1)>=self.min_conf.value()]
    def current_size(self,r):
        if r.height and r.width:return r.height,r.width
        if self.current>=0 and self.records[self.current] is r and self.preview.img is not None:r.height,r.width=self.preview.img.shape[:2];return r.height,r.width
        # 旧缓存缺少尺寸时只补读一次，随后保存在 JSON；正常勾选不会再读原图。
        im=cv2.imdecode(np.fromfile(str(r.path),np.uint8),cv2.IMREAD_GRAYSCALE)
        r.height,r.width=im.shape[:2] if im is not None else (1,1);return r.height,r.width
    def filtered(self):
        mode=self.view.currentText();out=[]
        for i,r in enumerate(self.records):
            good=self.eligible(r)
            if mode=='仅显示需要修复' and not any(r.selected[j] for j in good):continue
            if mode=='仅显示有文字' and not good:continue
            if mode=='仅显示人工修改' and not any(r.manual):continue
            out.append(i)
        return out
    def status_text(self,r):
        good=self.eligible(r);return f'{r.path.name}\n检测 {len(good)} · 建议 {sum(r.selected[i] for i in good)}'+(' · 人工' if any(r.manual) else '')
    def placeholder(self):
        p=QPixmap(110,110);p.fill(QColor('#e8edf2'));return p
    def refresh(self,preserve=True):
        old=self.current;scroll=self.list.verticalScrollBar().value();self.visible=self.filtered();pages=max(1,math.ceil(len(self.visible)/self.PAGE_SIZE));self.page=min(self.page,pages-1);shown=self.visible[self.page*self.PAGE_SIZE:(self.page+1)*self.PAGE_SIZE];self.thumb_token+=1;token=self.thumb_token;self.list.clear();self.item_by_record={}
        for i in shown:
            it=QListWidgetItem(QIcon(self.placeholder()),self.status_text(self.records[i]));it.setData(Qt.UserRole,i);self.list.addItem(it);self.item_by_record[i]=it
        self.page_label.setText(f'第 {self.page+1}/{pages} 页 · 显示 {len(shown)} / {len(self.visible)} 张');self.prev_page.setEnabled(self.page>0);self.next_page.setEnabled(self.page+1<pages);self.update_summary();self.start_thumbnails(token,shown)
        if preserve and old in self.item_by_record:self.list.setCurrentItem(self.item_by_record[old]);QTimer.singleShot(0,lambda:self.list.verticalScrollBar().setValue(scroll))
    def filter_changed(self,*_):self.page=0;self.refresh(False)
    def change_page(self,d):self.page=max(0,self.page+d);self.refresh(False)
    def start_thumbnails(self,token,indices):
        miss=[]
        for i in indices:
            v=self.thumb_memory.get(key(self.records[i].path))
            if v is not None:self.thumb_memory.move_to_end(key(self.records[i].path));self.thumbnail_ready(token,i,v)
            else:miss.append((i,self.records[i]))
        if not miss:return
        thread=QThread(self);worker=ThumbnailWorker(token,miss);thread._subtitle_worker=worker;worker.moveToThread(thread);thread.started.connect(worker.run);worker.ready.connect(self.thumbnail_ready);worker.finished.connect(thread.quit);thread.finished.connect(worker.deleteLater);thread.finished.connect(lambda t=thread:self.thumb_done(t));self.thumb_threads.append(thread);thread.start()
    def thumb_done(self,t):
        if t in self.thumb_threads:self.thumb_threads.remove(t)
        t.deleteLater()
    def thumbnail_ready(self,token,index,image):
        k=key(self.records[index].path);self.thumb_memory[k]=image;self.thumb_memory.move_to_end(k)
        while len(self.thumb_memory)>600:self.thumb_memory.popitem(last=False)
        if token==self.thumb_token and index in self.item_by_record:self.item_by_record[index].setIcon(QIcon(QPixmap.fromImage(image)))
    def show(self,item):
        self.current=item.data(Qt.UserRole);r=self.records[self.current];im=cv2.imdecode(np.fromfile(str(r.path),np.uint8),cv2.IMREAD_COLOR);self.preview.set_data(im,r.boxes,r.selected,r.manual);self.refresh_boxes()
    def move_image(self,d):
        if not self.visible:return
        try:p=self.visible.index(self.current)
        except ValueError:p=-1
        i=self.visible[max(0,min(len(self.visible)-1,p+d))]
        if i not in self.item_by_record:self.page=self.visible.index(i)//self.PAGE_SIZE;self.refresh(False)
        self.list.setCurrentItem(self.item_by_record[i]);self.show(self.item_by_record[i])
    def refresh_boxes(self):
        self.boxes.blockSignals(True);self.boxes.clear()
        if self.current>=0:
            r=self.records[self.current]
            for i,b in enumerate(r.boxes):
                a=np.asarray(b);state='建议修复' if (i<len(r.suggested) and r.suggested[i]) else '检测到文字';state+='（人工）' if r.manual[i] else ''
                it=QListWidgetItem(f'{state} · 区域 {i+1}: {a[:,0].min()},{a[:,1].min()} - {a[:,0].max()},{a[:,1].max()}');it.setData(Qt.UserRole,i);it.setFlags(it.flags()|Qt.ItemIsUserCheckable);it.setCheckState(Qt.Checked if r.selected[i] else Qt.Unchecked);self.boxes.addItem(it)
        self.boxes.blockSignals(False)
    def update_item(self,index):
        if index in self.item_by_record:self.item_by_record[index].setText(self.status_text(self.records[index]))
    def checked(self,it):
        if self.current<0:return
        r=self.records[self.current];i=it.data(Qt.UserRole);r.selected[i]=it.checkState()==Qt.Checked;r.manual[i]=True;self.preview.set_data(self.preview.img,r.boxes,r.selected,r.manual);self.update_item(self.current);self.update_summary();self.schedule_save()
    def new_box(self,b):
        if self.current<0:return
        r=self.records[self.current];r.boxes.append(b);r.suggested.append(False);r.selected.append(True);r.manual.append(True);r.scores.append(1.0);self.preview.set_data(self.preview.img,r.boxes,r.selected,r.manual);self.refresh_boxes();self.update_item(self.current);self.update_summary();self.schedule_save()
    def delete(self):
        if self.current<0:return
        r=self.records[self.current]
        for i in sorted((x.data(Qt.UserRole) for x in self.boxes.selectedItems()),reverse=True):
            for x in (r.boxes,r.selected,r.manual,r.scores,r.suggested):del x[i]
        self.preview.set_data(self.preview.img,r.boxes,r.selected,r.manual);self.refresh_boxes();self.update_item(self.current);self.update_summary();self.schedule_save()
    def select_suggested(self):
        for i in self.visible[self.page*self.PAGE_SIZE:(self.page+1)*self.PAGE_SIZE]:
            r=self.records[i]
            for j,v in enumerate(r.suggested):
                if v:r.selected[j]=True;r.manual[j]=True
            self.update_item(i)
        if self.current>=0:self.preview.set_data(self.preview.img,self.records[self.current].boxes,self.records[self.current].selected,self.records[self.current].manual);self.refresh_boxes()
        self.update_summary();self.schedule_save()
    def clear_page(self):
        for i in self.visible[self.page*self.PAGE_SIZE:(self.page+1)*self.PAGE_SIZE]:
            r=self.records[i];r.selected=[False]*len(r.selected);r.manual=[True]*len(r.manual);self.update_item(i)
        if self.current>=0:self.preview.set_data(self.preview.img,self.records[self.current].boxes,self.records[self.current].selected,self.records[self.current].manual);self.refresh_boxes()
        self.update_summary();self.schedule_save()
    def update_summary(self):
        detected=sum(len(self.eligible(r)) for r in self.records);selected=sum(sum(r.selected[i] for i in self.eligible(r)) for r in self.records);manual=sum(any(r.manual) for r in self.records);self.summary.setText(f'检测到文字：{detected} · 建议修复：{selected} · 人工修改：{manual}')
    def mask(self,r,im):
        m=np.zeros(im.shape[:2],np.uint8)
        for b,on in zip(r.boxes,r.selected):
            if on:cv2.fillPoly(m,[np.asarray(b,np.int32)],255)
        e=self.expand.value();return cv2.dilate(m,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(e*2+1,e*2+1))) if e else m
    def repaired_image(self,r,im):
        m=self.mask(r,im)
        if not np.any(m):return im.copy()
        if self.method.currentText()=='AI 修复（MI-GAN）':
            self.repair_model=self.repair_model or MIRepair();return self.repair_model.run(im,m)
        return cv2.inpaint(im,m,self.radius.value(),cv2.INPAINT_TELEA if self.method.currentText()=='快速修复（TELEA）' else cv2.INPAINT_NS)
    def repaired(self,r):
        im=cv2.imdecode(np.fromfile(str(r.path),np.uint8),cv2.IMREAD_COLOR);return None if im is None else self.repaired_image(r,im)
    def preview_repair(self):
        if self.current>=0:
            try:
                if self.method.currentText()=='AI 修复（MI-GAN）' and not MIGAN.exists():
                    QMessageBox.information(self,'首次使用 MI-GAN','首次使用会自动从上游下载约 28 MB 的 MI-GAN 模型。下载完成后会自动校验文件。')
                im=self.repaired(self.records[self.current]);self.preview.set_data(im,[],[],[])
            except Exception as e:QMessageBox.critical(self,'预览修复失败',str(e))
    def batch(self):
        if not self.folder or not self.output or not self.records:QMessageBox.information(self,'缺少内容','请先选择输入、输出目录并扫描文字。');return
        if self.output.resolve()==self.folder.resolve() or self.folder.resolve() in self.output.resolve().parents:QMessageBox.warning(self,'输出目录无效','输出目录必须是源目录以外的新目录。');return
        try:
            self.output.mkdir(parents=True,exist_ok=True)
            for i,r in enumerate(self.records,1):
                dst=self.output/r.path.relative_to(self.folder);dst.parent.mkdir(parents=True,exist_ok=True);im=self.repaired(r) if any(r.selected) else cv2.imdecode(np.fromfile(str(r.path),np.uint8),cv2.IMREAD_COLOR)
                if im is not None:ok,x=cv2.imencode('.webp' if r.path.suffix.lower()=='.webp' else r.path.suffix,im);x.tofile(str(dst)) if ok else None
                self.bar.setRange(0,len(self.records));self.bar.setValue(i);self.bar.setFormat(f'批量处理 {i}/{len(self.records)}');QApplication.processEvents()
            QMessageBox.information(self,'批量处理完成',f'已写入新目录：\n{self.output}\n\n源图片未被修改。')
        except Exception as e:QMessageBox.critical(self,'批量处理失败',str(e))
    def restore(self):
        try:
            d=json.loads((CACHE/'subtitle_cleaner.json').read_text(encoding='utf-8'));f=d.get('folder');o=d.get('output');self.folder=Path(f) if f and Path(f).exists() else None;self.output=Path(o) if o else None;self.input.setText(f or '未选择输入目录');self.output_label.setText(o or '未选择输出目录');self.method.setCurrentText(d.get('method','AI 修复（MI-GAN）'));self.expand.setValue(int(d.get('expand',5)));self.radius.setValue(int(d.get('radius',4)));q=d.get('filters',{});self.min_height.setValue(int(q.get('min_height',6)));self.min_area.setValue(int(q.get('min_area',36)));self.min_conf.setValue(float(q.get('min_conf',0)))
            restored=[]
            for x in d.get('records',[]):
                p=Path(x.get('path',''))
                if not p.exists():continue
                st=p.stat()
                if st.st_size!=x.get('file_size') or st.st_mtime_ns!=x.get('mtime_ns'):continue
                boxes=list(x.get('boxes',[]));sel=(list(x.get('selected',[]))+[False]*len(boxes))[:len(boxes)];man=(list(x.get('manual',[]))+[False]*len(boxes))[:len(boxes)];scores=(list(x.get('scores',[]))+[1.0]*len(boxes))[:len(boxes)];sug=(list(x.get('suggested',sel))+[False]*len(boxes))[:len(boxes)]
                restored.append(TextPhoto(p,st.st_size,st.st_mtime_ns,boxes,sel,man,scores,sug,int(x.get('width',0)),int(x.get('height',0))))
            if restored:self.records=restored;self.refresh(False)
        except Exception:pass
    def schedule_save(self):self.save_timer.start(450)
    def save(self):
        try:CACHE.mkdir(exist_ok=True);(CACHE/'subtitle_cleaner.json').write_text(json.dumps({'version':2,'folder':key(self.folder) if self.folder else '','output':str(self.output) if self.output else '','method':self.method.currentText(),'expand':self.expand.value(),'radius':self.radius.value(),'filters':{'min_height':self.min_height.value(),'min_area':self.min_area.value(),'min_conf':self.min_conf.value()},'records':[{'path':key(r.path),'file_size':r.file_size,'mtime_ns':r.mtime_ns,'boxes':r.boxes,'selected':r.selected,'manual':r.manual,'scores':r.scores,'suggested':r.suggested,'width':r.width,'height':r.height} for r in self.records]},ensure_ascii=False,separators=(',',':')),encoding='utf-8')
        except Exception:pass

class ThumbnailWorker(QObject):
    ready=Signal(int,int,object)
    finished=Signal(int)
    def __init__(self,token,items):super().__init__();self.token=token;self.items=items
    @staticmethod
    def disk_path(photo):
        digest=hashlib.sha256(f'{key(photo.path)}:{photo.file_size}:{photo.mtime_ns}'.encode()).hexdigest()
        return THUMB_CACHE/f'{digest}.jpg'
    def run(self):
        try:
            THUMB_CACHE.mkdir(parents=True,exist_ok=True)
            for index,photo in self.items:
                cache=self.disk_path(photo)
                try:
                    with Image.open(cache if cache.exists() else photo.path) as image:
                        image=image.convert('RGB');image.thumbnail((150,150),Image.Resampling.LANCZOS)
                        canvas=Image.new('RGB',(150,150),(30,30,30));canvas.paste(image,((150-image.width)//2,(150-image.height)//2))
                        if not cache.exists():canvas.save(cache,'JPEG',quality=85,optimize=True)
                        data=canvas.tobytes();qimage=QImage(data,150,150,150*3,QImage.Format_RGB888).copy()
                        self.ready.emit(self.token,index,qimage)
                except Exception:pass
        finally:self.finished.emit(self.token)

class Window(QMainWindow):
    def __init__(self):super().__init__();self.records=[];self.folder=None;self.thread=None;self.worker=None;self.page=0;self.target=60;self.quick_mode='';self.thumb_memory=OrderedDict();self.thumb_generation=0;self.thumb_threads=[];self.visible_item_map={};self.setWindowTitle('LoRA 数据集筛选与字幕清理');self.resize(1400,880);self.ui()
    def ui(self):
        tabs=QTabWidget();self.setCentralWidget(tabs);w=QWidget();tabs.addTab(w,'LoRA 数据集筛选');self.sub=SubtitleTab();tabs.addTab(self.sub,'批量去字幕 / 水印');l=QVBoxLayout(w);t=QHBoxLayout();self.pick=QPushButton('选择图片文件夹');self.pick.clicked.connect(self.choose);self.rescan=QPushButton('重新分析当前文件夹');self.rescan.clicked.connect(self.start);self.rescan.setEnabled(False);self.folder_label=QLabel('尚未选择文件夹');self.progress=QLabel('准备就绪');t.addWidget(self.pick);t.addWidget(self.rescan);t.addWidget(self.folder_label,1);t.addWidget(self.progress);l.addLayout(t);c=QHBoxLayout();c.addWidget(QLabel('自动推荐数量：'));self.group=QButtonGroup(self)
        for n in (40,50,60,70,80):b=QPushButton(str(n));b.setCheckable(True);b.setChecked(n==60);b.clicked.connect(lambda _,x=n:self.run_rec(x));self.group.addButton(b,n);c.addWidget(b)
        self.custom=QSpinBox();self.custom.setRange(1,3000);self.custom.setValue(60);self.custom.setPrefix('自定义 ');ap=QPushButton('应用');ap.clicked.connect(lambda:self.run_rec(self.custom.value()));self.export=QPushButton('导出推荐图片…');self.export.clicked.connect(self.exported);self.export.setEnabled(False);c.addWidget(self.custom);c.addWidget(ap)
        self.view_combo=QComboBox();self.view_combo.addItems(['全部','推荐','备选','淘汰']);self.view_combo.currentTextChanged.connect(self.filters_changed);c.addWidget(QLabel('状态'));c.addWidget(self.view_combo)
        self.scale_combo=QComboBox();self.scale_combo.addItems(['全部',*SCALES]);self.scale_combo.currentTextChanged.connect(self.filters_changed);c.addWidget(QLabel('景别'));c.addWidget(self.scale_combo)
        self.yaw_combo=QComboBox();self.yaw_combo.addItems(['全部',*YAWS]);self.yaw_combo.currentTextChanged.connect(self.filters_changed);c.addWidget(QLabel('Yaw'));c.addWidget(self.yaw_combo)
        self.pitch_combo=QComboBox();self.pitch_combo.addItems(['全部',*PITCHES]);self.pitch_combo.currentTextChanged.connect(self.filters_changed);c.addWidget(QLabel('Pitch'));c.addWidget(self.pitch_combo)
        clear_filters=QPushButton('清除全部筛选');clear_filters.clicked.connect(self.clear_filters);c.addWidget(clear_filters)
        self.sort_combo=QComboBox();self.sort_combo.addItems(['默认顺序','Face Quality 高 → 低','Face Quality 低 → 高','BRISQUE 低 → 高','BRISQUE 高 → 低','Sharpness 高 → 低','Sharpness 低 → 高','状态','Duplicate Group','来源目录 / 源视频','景别','Yaw','Pitch']);self.sort_combo.currentTextChanged.connect(self.sort_changed);c.addWidget(QLabel('排序'));c.addWidget(self.sort_combo)
        self.best_only=QCheckBox('仅显示每个 Duplicate Group 的最佳图');self.best_only.toggled.connect(self.filters_changed);c.addWidget(self.best_only)
        top_view=QPushButton('本视图质量 Top 10');top_view.clicked.connect(lambda:self.quick('view_top'));bottom_view=QPushButton('本视图质量 Bottom 10');bottom_view.clicked.connect(lambda:self.quick('view_bottom'));clear_top=QPushButton('清除 Top/Bottom');clear_top.clicked.connect(lambda:self.quick(''));c.addWidget(top_view);c.addWidget(bottom_view);c.addWidget(clear_top);c.addStretch(1);c.addWidget(self.export);l.addLayout(c)
        self.current_view_label=QLabel('当前视图：全部图片\n显示：0 / 0 张');self.current_view_label.setStyleSheet('font-weight:600; padding:4px; background:#eef3f8;');l.addWidget(self.current_view_label)
        s=QSplitter(Qt.Horizontal);self.grid=QListWidget();self.grid.setViewMode(QListWidget.IconMode);self.grid.setResizeMode(QListWidget.Adjust);self.grid.setMovement(QListWidget.Static);self.grid.setIconSize(QSize(150,150));self.grid.setGridSize(QSize(174,205));self.grid.itemClicked.connect(self.details);self.grid.itemDoubleClicked.connect(self.open);s.addWidget(self.grid);side=QWidget();sl=QVBoxLayout(side);self.stats=QLabel('目标 / 实际推荐：0 / 0');self.stats.setWordWrap(True);sl.addWidget(self.stats);self.stat_box=QGroupBox('统计（点击分类筛选）');self.stat_layout=QGridLayout(self.stat_box);sl.addWidget(self.stat_box);box=QGroupBox('图片分析数据');bl=QVBoxLayout(box);self.detail=QLabel('点击缩略图查看详情');self.detail.setWordWrap(True);bl.addWidget(self.detail);sl.addWidget(box);man=QGroupBox('人工状态（优先于自动结果）');ml=QGridLayout(man)
        for i,x in enumerate(('推荐','备选','淘汰')):b=QPushButton(x);b.clicked.connect(lambda _,v=x:self.manual(v));ml.addWidget(b,0,i)
        restore=QPushButton('恢复自动');restore.clicked.connect(self.restore);ml.addWidget(restore,1,0,1,3);sl.addWidget(man);sl.addStretch(1);s.addWidget(side);s.setSizes([1030,370]);l.addWidget(s,1);p=QHBoxLayout();self.prev=QPushButton('上一页');self.prev.clicked.connect(lambda:self.change(-1));self.page_label=QLabel('第 0/0 页');self.next=QPushButton('下一页');self.next.clicked.connect(lambda:self.change(1));p.addStretch(1);p.addWidget(self.prev);p.addWidget(self.page_label);p.addWidget(self.next);p.addStretch(1);l.addLayout(p)
    def choose(self):
        x=QFileDialog.getExistingDirectory(self,'选择训练图片目录',str(self.folder or APP_DIR))
        if x:self.folder=Path(x);d=load_data(self.folder);self.target=d.get('target',60) if isinstance(d.get('target',60),int) else 60;self.custom.setValue(self.target);self.folder_label.setText(x);self.start()
    def start(self):
        if not self.folder or self.thread and self.thread.isRunning():return
        self.pick.setEnabled(False);self.rescan.setEnabled(False);self.export.setEnabled(False);self.grid.clear();self.thread=QThread(self);self.worker=Analyzer(self.folder);self.worker.moveToThread(self.thread);self.thread.started.connect(self.worker.run);self.worker.status.connect(self.progress.setText);self.worker.progress.connect(lambda n,t,name:self.progress.setText(f'分析 {n}/{t}：{name}'));self.worker.finished.connect(self.done);self.worker.failed.connect(lambda e:QMessageBox.critical(self,'分析失败',e));self.worker.finished.connect(self.thread.quit);self.worker.failed.connect(self.thread.quit);self.thread.finished.connect(self.thread_done);self.thread.start()
    def done(self,rs):self.records=rs;self.target=self.custom.value();recommend(rs,self.target);self.quick_mode='';self.view_combo.setCurrentText('推荐');self.page=0;self.progress.setText(f'分析完成：{len(rs)} 张');self.pick.setEnabled(True);self.rescan.setEnabled(True);self.export.setEnabled(True);self.refresh();self.save()
    def thread_done(self):self.worker=None;self.thread.deleteLater();self.thread=None
    @staticmethod
    def thumb(p):
        r=QImageReader(str(p));r.setAutoTransform(True);z=r.size()
        if z.isValid():z.scale(150,150,Qt.KeepAspectRatio);r.setScaledSize(z)
        i=r.read();return QPixmap.fromImage(i) if not i.isNull() else QPixmap()
    def filters_changed(self,*_):self.quick_mode='';self.page=0;self.refresh()
    def sort_changed(self,*_):self.refresh()
    def clear_filters(self):
        for combo in (self.view_combo,self.scale_combo,self.yaw_combo,self.pitch_combo):combo.blockSignals(True);combo.setCurrentIndex(0);combo.blockSignals(False)
        self.best_only.blockSignals(True);self.best_only.setChecked(False);self.best_only.blockSignals(False);self.quick_mode='';self.page=0;self.refresh()
    def quick(self,mode):self.quick_mode=mode;self.page=0;self.refresh()
    def set_category_filter(self,kind,value):
        combo={'status':self.view_combo,'scale':self.scale_combo,'yaw':self.yaw_combo,'pitch':self.pitch_combo}[kind]
        combo.setCurrentText(value);self.quick_mode='';self.page=0;self.refresh()
    def group_rank(self,r):
        if not r.duplicate_group:return 1,1
        entries=group_entries(self.records,r.duplicate_group);return entries.index(r)+1,len(entries)
    def qualified_group_rank(self,r):
        if not r.duplicate_group:return 1,1
        entries=group_entries(self.records,r.duplicate_group,True)
        return (entries.index(r)+1,len(entries)) if r in entries else (0,len(entries))
    def indices(self,with_quick=True):
        base=[i for i,r in enumerate(self.records) if (self.view_combo.currentText()=='全部' or r.status==self.view_combo.currentText()) and (self.scale_combo.currentText()=='全部' or r.person_scale==self.scale_combo.currentText()) and (self.yaw_combo.currentText()=='全部' or r.angle_class==self.yaw_combo.currentText()) and (self.pitch_combo.currentText()=='全部' or r.pitch_class==self.pitch_combo.currentText())]
        if self.best_only.isChecked():base=[i for i in base if not self.records[i].duplicate_group or self.qualified_group_rank(self.records[i])[0]==1]
        sort=self.sort_combo.currentText()
        key_func={'Face Quality 高 → 低':lambda r:r.face_quality,'Face Quality 低 → 高':lambda r:r.face_quality,'BRISQUE 低 → 高':lambda r:r.brisque,'BRISQUE 高 → 低':lambda r:r.brisque,'Sharpness 高 → 低':lambda r:r.blur,'Sharpness 低 → 高':lambda r:r.blur,'状态':lambda r:r.status,'Duplicate Group':lambda r:(r.duplicate_group==0,r.duplicate_group),'来源目录 / 源视频':lambda r:r.source,'景别':lambda r:r.person_scale,'Yaw':lambda r:r.angle_class,'Pitch':lambda r:r.pitch_class}
        reverse=sort in ('Face Quality 高 → 低','BRISQUE 高 → 低','Sharpness 高 → 低')
        if sort in key_func:base.sort(key=lambda i:key_func[sort](self.records[i]),reverse=reverse)
        if with_quick and self.quick_mode=='view_top':base=sorted(base,key=lambda i:rank(self.records[i]),reverse=True)[:10]
        if with_quick and self.quick_mode=='view_bottom':base=sorted(base,key=lambda i:rank(self.records[i]))[:10]
        return base
    def view_description(self):
        parts=[]
        if self.view_combo.currentText()!='全部':parts.append(self.view_combo.currentText())
        if self.scale_combo.currentText()!='全部':parts.append('景别：'+self.scale_combo.currentText())
        if self.yaw_combo.currentText()!='全部':parts.append('Yaw：'+self.yaw_combo.currentText())
        if self.pitch_combo.currentText()!='全部':parts.append('Pitch：'+self.pitch_combo.currentText())
        if self.best_only.isChecked():parts.append('每组最佳图')
        if self.quick_mode=='view_top':parts.append('Top 10')
        if self.quick_mode=='view_bottom':parts.append('Bottom 10')
        return ' > '.join(parts) if parts else '全部图片'
    def placeholder(self):
        pix=QPixmap(150,150);pix.fill(QColor('#e8edf2'));return pix
    def cached_thumbnail(self,photo):
        value=self.thumb_memory.get(key(photo.path))
        if value is not None:self.thumb_memory.move_to_end(key(photo.path))
        return value
    def start_thumbnails(self,indices):
        missing=[(i,self.records[i]) for i in indices if self.cached_thumbnail(self.records[i]) is None]
        if not missing:return
        self.thumb_generation+=1;token=self.thumb_generation;thread=QThread(self);worker=ThumbnailWorker(token,missing);thread._thumbnail_worker=worker;worker.moveToThread(thread);thread.started.connect(worker.run);worker.ready.connect(self.thumbnail_ready);worker.finished.connect(thread.quit);thread.finished.connect(worker.deleteLater);thread.finished.connect(lambda t=thread:self.thumbnail_thread_done(t));self.thumb_threads.append(thread);thread.start()
    def thumbnail_thread_done(self,thread):
        if thread in self.thumb_threads:self.thumb_threads.remove(thread)
        thread.deleteLater()
    def thumbnail_ready(self,token,index,image):
        if token!=self.thumb_generation:return
        pix=QPixmap.fromImage(image);self.thumb_memory[key(self.records[index].path)]=pix;self.thumb_memory.move_to_end(key(self.records[index].path))
        while len(self.thumb_memory)>600:self.thumb_memory.popitem(last=False)
        item=self.visible_item_map.get(index)
        if item is not None:item.setIcon(QIcon(pix))
    def stat_button(self,text,kind,value,row,column):
        button=QPushButton(text);button.setFlat(True);button.setStyleSheet('text-align:left; color:#175ea8;');button.clicked.connect(lambda _=False,k=kind,v=value:self.set_category_filter(k,v));self.stat_layout.addWidget(button,row,column)
    def refresh_stats(self):
        while self.stat_layout.count():
            child=self.stat_layout.takeAt(0)
            if child.widget():child.widget().deleteLater()
        st=Counter(r.status for r in self.records);sel=[r for r in self.records if r.status=='推荐'];sc=Counter(r.person_scale for r in sel);yw=Counter(r.angle_class for r in sel);pt=Counter(r.pitch_class for r in sel);grp={r.duplicate_group for r in sel if r.duplicate_group};du=sum(r.status!='推荐' and not r.reasons and r.duplicate_group and (self.qualified_group_rank(r)[0]>1 or r.duplicate_group in grp) for r in self.records);bad=sum(bool(r.reasons) for r in self.records);group_count=len({r.duplicate_group for r in self.records if r.duplicate_group})
        self.stats.setText(f'目标 / 实际推荐：{self.target} / {len(sel)}\n来源目录/视频：{len({r.source for r in self.records})} · Duplicate Group：{group_count}\n因近重复未推荐：{du} · 因质量问题淘汰：{bad}')
        self.stat_layout.addWidget(QLabel('状态（点击筛选）'),0,0,1,3)
        for col,value in enumerate(('推荐','备选','淘汰')):self.stat_button(f'{value} {st[value]}','status',value,1,col)
        self.stat_layout.addWidget(QLabel('景别（推荐）'),2,0,1,3)
        for n,value in enumerate(SCALES):self.stat_button(f'{value} {sc[value]}','scale',value,3+n//2,n%2)
        self.stat_layout.addWidget(QLabel('Yaw（推荐）'),5,0,1,3)
        for n,value in enumerate(YAWS):self.stat_button(f'{value} {yw[value]}','yaw',value,6+n//2,n%2)
        self.stat_layout.addWidget(QLabel('Pitch（推荐）'),9,0,1,3)
        for n,value in enumerate(PITCHES):self.stat_button(f'{value} {pt[value]}','pitch',value,10+n//2,n%2)
    def refresh(self):
        base=self.indices(False);visible=self.indices(True);self.grid.clear();self.visible_item_map={};self.thumb_generation+=1;start=self.page*PAGE;page_indices=visible[start:start+PAGE]
        for i in page_indices:
            r=self.records[i];gr,gs=self.group_rank(r);pix=self.cached_thumbnail(r) or self.placeholder();it=QListWidgetItem(QIcon(pix),r.path.name);it.setData(Qt.UserRole,i);it.setToolTip(f'{r.status} · {r.person_scale} · {r.angle_class} · eDifFIQA {r.face_quality:.3f} · 组 {gr}/{gs}');it.setBackground(QColor(COLORS[r.status]));self.grid.addItem(it);self.visible_item_map[i]=it
        pages=max(1,math.ceil(len(visible)/PAGE));self.page=min(self.page,pages-1);self.page_label.setText(f'第 {self.page+1}/{pages} 页');self.prev.setEnabled(self.page>0);self.next.setEnabled(self.page+1<pages);self.current_view_label.setText(f'当前视图：{self.view_description()}\n显示：{len(visible)} / {len(base)} 张');self.refresh_stats();self.start_thumbnails(page_indices)
    def change(self,d):
        n=self.page+d
        if 0<=n<math.ceil(len(self.indices())/PAGE):self.page=n;self.refresh()
    def selected(self):
        x=self.grid.currentItem();return self.records[x.data(Qt.UserRole)] if x else None
    def details(self,it):
        r=self.records[it.data(Qt.UserRole)];reasons='；'.join(r.reasons) or '无（符合基础训练门槛）';gr,gs=self.group_rank(r);qr,qs=self.qualified_group_rank(r);dup=f'第 {r.duplicate_group} 组' if r.duplicate_group else '无（独立图片）';self.detail.setText(f'文件：{r.path.name}\n\n状态：{r.status}（{"人工" if r.manual_status else "自动"}）\n分辨率：{r.width} × {r.height}\n人脸数：{r.faces}\n脸部占比：{r.face_ratio*100:.1f}%\n人脸实际尺寸：{r.face_px}px\neDifFIQA-T：{r.face_quality:.4f}（高更好）\nBRISQUE：{r.brisque:.2f}（低更好）\nLaplacian 清晰度：{r.blur:.1f}\n平均亮度：{r.brightness:.1f}\nyaw / pitch / roll：{r.yaw:.1f}° / {r.pitch:.1f}° / {r.roll:.1f}°\nYaw 分类：{r.angle_class}\nPitch 分类：{r.pitch_class}\n景别：{r.person_scale}\nDuplicate Group：{dup}\nGroup Size：{gs}\nGroup Rank：{gr} / {gs}\n合格成员 Rank：{qr if qr else "未达推荐门槛"} / {qs}\n\n淘汰原因：{reasons}')
    def manual(self,v):
        r=self.selected()
        if r:r.manual_status=v;self.refresh();self.save()
    def restore(self):
        r=self.selected()
        if r:r.manual_status=None;recommend(self.records,self.target);self.refresh();self.save()
    def run_rec(self,n):self.target=n;self.custom.setValue(n);recommend(self.records,n) if self.records else None;self.quick_mode='';self.view_combo.setCurrentText('推荐');self.refresh() if self.records else None;self.save()
    def open(self,it):
        try:os.startfile(str(self.records[it.data(Qt.UserRole)].path))
        except OSError as e:QMessageBox.warning(self,'无法打开图片',str(e))
    def save(self):
        if self.folder and self.records:
            try:save_data(self.folder,self.records,self.target)
            except Exception:self.progress.setText('缓存保存失败')
    def closeEvent(self,e):self.save();self.sub.save();e.accept()
    def exported(self):
        sel=[r for r in self.records if r.status=='推荐']
        if not sel:QMessageBox.information(self,'没有可导出的图片','当前没有推荐图片。');return
        x=QFileDialog.getExistingDirectory(self,'选择导出目录（只复制）')
        if not x:return
        dst=Path(x)
        if self.folder and (dst.resolve()==self.folder.resolve() or self.folder.resolve() in dst.resolve().parents):QMessageBox.warning(self,'请选择新目录','导出目录不能是源目录或其子目录。');return
        try:
            n=0
            for r in sel:
                out=dst/r.path.name;i=1
                while out.exists():out=dst/f'{r.path.stem}_{i}{r.path.suffix}';i+=1
                shutil.copy2(r.path,out);n+=1
            QMessageBox.information(self,'导出完成',f'已复制 {n} 张推荐图片。\n源图片未被修改。')
        except Exception as e:QMessageBox.critical(self,'导出失败',str(e))

def self_test():
    """Portable / CI smoke test: load the core models without opening the GUI."""
    required([YUNET,EDIFF,BRISQUE,BRISQUE_RANGE,DDDFA,DDDFA_NORM,POSE,TEXT])
    QualityModels()
    TextDetector(det_config())
    options=PoseLandmarkerOptions(
        base_options=python.BaseOptions(model_asset_path=str(ensure_pose())),
        running_mode=VisionTaskRunningMode.IMAGE,
        num_poses=1,
        min_pose_detection_confidence=.5,
        min_pose_presence_confidence=.5,
    )
    landmarker=PoseLandmarker.create_from_options(options)
    landmarker.close()
    return 0

if __name__=='__main__':
    if '--self-test' in sys.argv:
        try:sys.exit(self_test())
        except Exception as e:
            print('SELF-TEST FAILED:',e);traceback.print_exc();sys.exit(1)
    a=QApplication(sys.argv);a.setApplicationName('LoRA 数据集筛选与字幕清理');w=Window();w.show();sys.exit(a.exec())
