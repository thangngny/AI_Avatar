# TEMPORARY diagnostic — NOT production. Raw MuseTalk 256 mouth vs final composite.
# Measures whether paste-back/resize/encode loses mouth articulation detail
# (high-frequency energy, edge density). Compare on a speaking frame.
import os,sys,pickle,glob
os.environ.setdefault("CUDA_VISIBLE_DEVICES","1")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, cv2, torch
from avatars.musetalk.utils.utils import load_all_model
from avatars.musetalk.myutil import get_image_blending
from avatars.musetalk.whisper.audio2feature import Audio2Feature
from utils.device import initialize_device
import soundfile as sf, subprocess, tempfile

device=initialize_device()
torch.backends.cudnn.benchmark=True
AV="fullbody_30_7_25fps"; ROOT=os.path.dirname(os.path.abspath(__file__))
vae,unet,pe=load_all_model()
pe=pe.half().to(device); vae.vae=vae.vae.half().to(device); unet.model=unet.model.half().to(device)
ap=Audio2Feature(model_path=os.path.join(ROOT,"models","whisper"),device=device)
# master wav from sweep_ctx
wav=r"D:\CongThang_AI_Avatar\sweep_ctx\master_artic.wav"
w,sr=sf.read(wav,dtype="float32"); w=w.mean(axis=1) if w.ndim>1 else w
feat=ap.audio2feat(w)
# avatar
frames=sorted(glob.glob(f"data/avatars/{AV}/full_imgs/*"))
frame_list=[cv2.resize(cv2.imread(f),(1080,1920)) for f in frames]  # downscaled
coords=pickle.load(open(f"data/avatars/{AV}/coords.pkl","rb"))
coords=[ [int(round(v*0.5)) for v in c] for c in coords ]
mask_coords=pickle.load(open(f"data/avatars/{AV}/mask_coords.pkl","rb"))
mask_coords=[[int(round(v*0.5)) for v in c] for c in mask_coords]
masks=[cv2.resize(cv2.imread(m,0),(540//2,540//2)) for m in sorted(glob.glob(f"data/avatars/{AV}/mask/*"))] if False else None
# load masks at scaled size
ms=[]
for m in sorted(glob.glob(f"data/avatars/{AV}/mask/*")):
    im=cv2.imread(m)  # 3-channel BGR (get_image_blending does cvtColor BGR2GRAY)
    ms.append(cv2.resize(im,(im.shape[1]//2,im.shape[0]//2)))
lat=torch.load(f"data/avatars/{AV}/latents.pt", map_location="cpu")
# pick a speaking frame ~ middle
i=200
center=(i-3)*2
win=np.stack([feat[max(0,min(feat.shape[0]-1,center+j))] for j in range(10)],0).reshape(-1,384)
audio=torch.from_numpy(win).to(device).half().unsqueeze(0)  # [1,50,384]
audio=pe(audio)
latb=torch.cat([lat[i%len(lat)]]).to(device).half()  # [1,8,32,32]
with torch.no_grad():
    pred=vae.decode_latents(unet.model(latb,torch.zeros(1,device=device,dtype=torch.long),encoder_hidden_states=audio,return_dict=False)[0])
raw256=pred[0]  # 256x256 uint8 BGR
# paste back
bbox=coords[i%len(coords)]
x1,y1,x2,y2=bbox
ori=frame_list[i%len(frame_list)].copy()
res=cv2.resize(raw256,(x2-x1,y2-y1))
mc=mask_coords[i%len(mask_coords)]
msk=ms[i%len(ms)]
comp=get_image_blending(ori,res,(x1,y1,x2,y2),msk,mc)
# crop mouth region from composite (the paste bbox)
mouth_comp=comp[y1:y2,x1:x2]
# metrics: Laplacian variance (HF energy) + edge density
def hf(img):
    g=cv2.cvtColor(img,cv2.COLOR_BGR2GRAY) if img.ndim==3 else img
    return float(cv2.Laplacian(g,cv2.CV_64F).var())
def edge(img):
    g=cv2.cvtColor(img,cv2.COLOR_BGR2GRAY) if img.ndim==3 else img
    return float(np.mean(cv2.Canny(g,80,180)))
raw_up=cv2.resize(raw256,(x2-x1,y2-y1))  # raw at composite scale
out=r"D:\CongThang_AI_Avatar\sweep_ctx\raw_vs_comp"
os.makedirs(out,exist_ok=True)
cv2.imwrite(f"{out}/raw256_frame{i}.png",raw256)
cv2.imwrite(f"{out}/raw_upscaled_frame{i}.png",raw_up)
cv2.imwrite(f"{out}/composite_mouth_frame{i}.png",mouth_comp)
cv2.imwrite(f"{out}/composite_full_frame{i}.png",comp)
print(f"frame {i}: bbox={bbox} mouth_size={x2-x1}x{y2-y1}")
print(f"  RAW 256     : HF(LaplacianVar)={hf(raw256):.1f} edge={edge(raw256):.1f}")
print(f"  RAW upscaled: HF={hf(raw_up):.1f} edge={edge(raw_up):.1f}")
print(f"  COMPOSITE mouth: HF={hf(mouth_comp):.1f} edge={edge(mouth_comp):.1f}")
print(f"  ratio composite/raw_upscaled HF = {hf(mouth_comp)/hf(raw_up):.2f}")
print(f"  saved: {out}/{{raw256,raw_upscaled,composite_mouth,composite_full}}_frame{i}.png")