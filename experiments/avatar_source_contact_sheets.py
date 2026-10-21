"""Generate contact sheets (6 frames: 0/20/40/60/80/100%) for top candidates
+ compute final 0-100 scores and grades. No images enter model context."""
import cv2, numpy as np, json, os

OUT = "D:/CongThang_AI_Avatar/avatar_source_audit"
os.makedirs(OUT, exist_ok=True)
cv = json.load(open("C:/CongThang_AI_Avatar/avatar_source_audit_cv.json"))

# candidates to sheet (name -> (path, rank_label, is_video))
SHEETS = [
 ("rank00_close_up_CURRENT_proxy","C:/CongThang_AI_Avatar/AI_avatar/data/avatars/close_up/full_imgs",True),
 ("rank01_test17_8_close_up","C:/CongThang/AI_avatar/test17_8/Close Up.mp4",False),
 ("rank02_uploads_4k_30_7","C:/CongThang_AI_Avatar/AI_avatar/data/avatars/.uploads/musetalk_8960_6881921.mp4",False),
 ("rank03_test17_8_full_body","C:/CongThang/AI_avatar/test17_8/Full Body (2).mp4",False),
 ("rank04_master_plus_body_closeup","C:/CongThang/AI_avatar/experiments/master_plus/inputs/body_closeup.mp4",False),
 ("rank05_uploads_4k_HEARING1","C:/CongThang/AI_avatar/Hearing-1.mp4",False),
]
TILE_W = 480

def frames_from_dir(d, n=6):
    fs=sorted([os.path.join(d,f) for f in os.listdir(d) if f.lower().endswith((".png",".jpg",".jpeg"))])
    if not fs: return []
    idx=[int(i*(len(fs)-1)/max(n-1,1)) for i in range(n)]
    return [cv2.imread(fs[i]) for i in idx if fs[i]]

def frames_from_video(p, n=6):
    c=cv2.VideoCapture(p)
    if not c.isOpened(): return []
    fc=int(c.get(cv2.CAP_PROP_FRAME_COUNT))
    pts=[int(i*(fc-1)/max(n-1,1)) for i in range(n)]
    out=[]
    for fr in pts:
        c.set(cv2.CAP_PROP_POS_FRAMES,fr); ok,img=c.read()
        if ok and img is not None: out.append(img)
    c.release(); return out

for label,p,is_dir in SHEETS:
    frames = frames_from_dir(p,6) if is_dir else frames_from_video(p,6)
    if not frames:
        print("NO FRAMES",label); continue
    tiles=[]
    for im in frames:
        h,w=im.shape[:2]
        nw=TILE_W; nh=max(1,int(h*nw/w))
        tiles.append(cv2.resize(im,(nw,nh)))
    # pad to uniform height
    H=max(t.shape[0] for t in tiles)
    row=[]
    for t in tiles:
        if t.shape[0]<H:
            pad=np.zeros((H-t.shape[0],t.shape[1],3),np.uint8); t=np.vstack([t,pad])
        row.append(t)
    sheet=np.hstack(row)
    fn=os.path.join(OUT, label+".jpg")
    cv2.imwrite(fn, sheet, [cv2.IMWRITE_JPEG_QUALITY,88])
    print("wrote",fn, sheet.shape, flush=True)

# ---- scoring ----
def clamp(x,a,b): return max(a,min(b,x))
scores={}
for k,r in cv.items():
    if "error" in r: continue
    faceH=r.get("est_face_h_at_1080p_out") or 0
    sharp=r.get("median_face_sharpness",0)
    front=r.get("frontal_ratio",0)
    mouth=r.get("mouth_in_frame_ratio",0)
    chin=r.get("median_chin_ratio",0)
    motion=r.get("median_motion",0) or 0
    flick=r.get("luma_flicker",0) or 0
    mvar=r.get("mouth_var_mean",0) or 0
    # critical failures
    fail=None
    if sharp<40: fail="face_region_blurry"
    if mouth<1.0: fail="mouth_obstructed_or_cropped"
    if chin<1.0: fail="chin_jaw_cropped"
    if r.get("width",0)<720 or r.get("height",0)<1280:
        if not (r.get("width",0)>=1280): pass  # halfbody 1280x720 landscape flagged below
    s_face = clamp(faceH/400.0,0,1)*25
    s_sharp= clamp(sharp/300.0,0,1)*20
    s_pose = front*10
    s_mouth= mouth*10
    s_chin = clamp(chin/1.0,0,1)*10
    s_neut= clamp(1-mvar/120.0,0,1)*8
    s_light= clamp(1-flick/3.0,0,1)*5
    s_blur = clamp(1-motion/15.0,0,1)*5
    s_geom = clamp(1-motion/15.0,0,1)*4
    s_nat  = 3 if 1.5<=motion<=4.5 else (2 if motion<1.5 else (1 if motion<=8 else 0))
    total=round(s_face+s_sharp+s_pose+s_mouth+s_chin+s_neut+s_light+s_blur+s_geom+s_nat,1)
    # orientation penalty (landscape halfbody)
    if r.get("width",0)>r.get("height",0): total-=8; fail=(fail or "")+"/landscape_orientation"
    if r.get("duration",0) and r["duration"]<10: total-=5; fail=(fail or "")+"/very_short"
    if fail and not fail.startswith("/"): total=min(total,40)  # critical blur/crop caps score
    grade=("A+" if total>=85 else "A" if total>=72 else "B" if total>=58 else "C" if total>=45 else "D")
    scores[k]={"faceH_out":faceH,"sharp":sharp,"frontal":front,"mouth":mouth,"chin":chin,
               "motion":motion,"flicker":flick,"mvar":mvar,
               "sub":{"face":round(s_face,1),"sharp":round(s_sharp,1),"pose":s_pose,"mouth":s_mouth,
                      "chin":round(s_chin,1),"neutral":round(s_neut,1),"light":round(s_light,1),
                      "blur":round(s_blur,1),"geom":round(s_geom,1),"nat":s_nat},
               "score":round(total,1),"grade":grade,"fail":fail or None,
               "path":r.get("path"),
               "res":f"{r.get('width')}x{r.get('height')}",
               "fps":r.get("fps"),"dur":r.get("duration")}
json.dump(scores, open("C:/CongThang_AI_Avatar/avatar_source_audit_scores.json","w"), indent=2)
print("\n=== SCORED ===")
for k,v in sorted(scores.items(), key=lambda kv:-kv[1]["score"]):
    print(f"{v['grade']:2} {v['score']:5} {k:30} faceH={v['faceH_out']:3} sharp={v['sharp']:6} {v['res']:10} {v.get('fail') or ''}")