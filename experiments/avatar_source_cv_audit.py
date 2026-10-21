"""Best raw avatar-source audit. CV measurement only (no model image reads).
Outputs numeric JSON per candidate. Does NOT modify any source."""
import cv2, numpy as np, json, os, sys, math

HAAR = os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml")
HAAR_ALT = os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_alt2.xml")
HAAR_PROFILE = os.path.join(cv2.data.haarcascades, "haarcascade_profileface.xml")
EYE = os.path.join(cv2.data.haarcascades, "haarcascade_eye.xml")
face_cascade = cv2.CascadeClassifier(HAAR_ALT)
face_def = cv2.CascadeClassifier(HAAR)
eye_cascade = cv2.CascadeClassifier(EYE)
profile_cascade = cv2.CascadeClassifier(HAAR_PROFILE)

def detect_face(gray):
    for c in (face_cascade, face_def):
        f = c.detectMultiScale(gray, scaleFactor=1.15, minNeighbors=5, minSize=(60,60), flags=cv2.CASCADE_SCALE_IMAGE)
        if len(f):
            # largest
            f = sorted(f, key=lambda b: b[2]*b[3], reverse=True)[0]
            return f
    # try profile
    p = profile_cascade.detectMultiScale(gray, scaleFactor=1.15, minNeighbors=5, minSize=(60,60))
    if len(p):
        return sorted(p, key=lambda b: b[2]*b[3], reverse=True)[0]
    return None

def laplacian_var(img):
    return float(cv2.Laplacian(img, cv2.CV_64F).var())

def analyze_video(path, n=6):
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        return {"error": "cannot open", "path": path}
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)); H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS); fc = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    dur = fc/fps if fps else 0
    pts = [int(i*fc/max(n,1)) for i in range(n)]
    if fc>0 and pts and pts[-1]>=fc: pts[-1]=fc-1
    results=[]
    prev_gray=None
    for fr in pts:
        cap.set(cv2.CAP_PROP_POS_FRAMES, fr)
        ok,img = cap.read()
        if not ok or img is None:
            continue
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        g = detect_face(gray)
        r = {"frame": fr}
        if g is not None:
            x,y,w,h = g
            # face crop with margin for sharpness
            m = int(h*0.15)
            x0=max(0,x-m); y0=max(0,y-m); x1=min(W,x+w+m); y1=min(H,y+h+m)
            face_crop = gray[y0:y1, x0:x1]
            sharp = laplacian_var(face_crop) if face_crop.size else 0
            # eyes within upper face
            eye_region = gray[y:y+int(h*0.55), x:x+w]
            eyes = eye_cascade.detectMultiScale(eye_region, scaleFactor=1.1, minNeighbors=6, minSize=(int(w*0.08),int(w*0.08))) if eye_region.size else []
            eyes = sorted(eyes, key=lambda b:b[2]*b[3], reverse=True)[:2]
            eyes_x = [ex for (ex,ey,ew,eh) in eyes]
            # Robust pose: face aspect ratio w/h. Frontal human face ~0.74-0.82.
            # Strong profile shrinks w/h toward ~0.5; tilted/up-down distorts too.
            aspect = w/float(h)
            # yaw from aspect: map 0.78->0deg, 0.55->45deg, 0.4->70deg
            yaw_aspect = max(0.0, (0.78-aspect)/0.28)*70.0
            # eye-based cross-check (only if 2 eyes & gap plausible)
            yaw_eye = None
            if len(eyes)>=2:
                ex1,ex2 = sorted(eyes_x)
                gap = (ex2-ex1)/float(w)
                if 0.25 < gap < 0.7:
                    mid_eye=(ex1+ex2)/2.0
                    off=(x+w/2.0 - mid_eye)/float(w)
                    yaw_eye=abs(off)*60.0
            pose = {"eyes":len(eyes), "aspect":round(aspect,3), "est_yaw_deg":round(yaw_aspect,1),
                    "yaw_eye": (round(yaw_eye,1) if yaw_eye is not None else None)}
            # mouth region = lower third of face
            mouth_y0 = y+int(h*0.62); mouth_y1 = y+int(h*0.92)
            mouth_x0 = x+int(w*0.18); mouth_x1 = x+int(w*0.82)
            mouth_in_frame = (mouth_y1 < H) and (mouth_y0 < mouth_y1)
            mouth_crop = gray[mouth_y0:mouth_y1, mouth_x0:mouth_x1] if mouth_in_frame else None
            mouth_var = float(cv2.Laplacian(mouth_crop, cv2.CV_64F).var()) if mouth_crop is not None and mouth_crop.size else 0
            # chin/jaw: space below face within frame
            space_below = H - (y+h)
            chin_ratio = space_below / float(h)  # >= ~0.1 good
            # motion (frame diff)
            motion = 0.0
            if prev_gray is not None:
                motion = float(np.mean(cv2.absdiff(gray, prev_gray)))
            r.update({"face":[int(x),int(y),int(w),int(h)],
                      "face_h_px":int(h), "face_h_ratio":round(h/float(H),4),
                      "face_w_ratio":round(w/float(W),4),
                      "sharpness":round(sharp,1),
                      "pose":pose,
                      "mouth_in_frame":bool(mouth_in_frame),
                      "mouth_sharp":round(mouth_var,1),
                      "space_below_px":int(space_below), "chin_ratio":round(chin_ratio,3),
                      "frame_motion":round(motion,2)})
        else:
            r.update({"face":None})
        # lighting
        r["luma_mean"]=round(float(np.mean(gray)),1)
        r["luma_std"]=round(float(np.std(gray)),1)
        # global sharpness
        r["frame_sharp"]=round(laplacian_var(gray),1)
        results.append(r)
        prev_gray = gray
    cap.release()
    # aggregate
    faces = [r for r in results if r.get("face")]
    agg = {"path":path.replace("C:/","C:/").replace("D:/","D:/"),
           "width":W,"height":H,"fps":round(fps,3),"frame_count":fc,"duration":round(dur,2),
           "samples":len(results),"faces_detected":len(faces)}
    if faces:
        hs=[r["face_h_px"] for r in faces]
        hrs=[r["face_h_ratio"] for r in faces]
        sh=[r["sharpness"] for r in faces]
        yaws=[r["pose"]["est_yaw_deg"] for r in faces]
        mouth_in=sum(1 for r in faces if r["mouth_in_frame"])
        chins=[r["chin_ratio"] for r in faces]
        motions=[r["frame_motion"] for r in faces if "frame_motion" in r]
        lums=[r["luma_mean"] for r in faces]
        # mouth openness proxy: variance of mouth region brightness across samples (talking -> more)
        mouthvars=[r.get("mouth_sharp",0) for r in faces]
        agg.update({
          "median_face_h_px":int(np.median(hs)),
          "median_face_h_ratio":round(float(np.median(hrs)),4),
          "est_face_h_at_1080p_out":int(round(np.median(hrs)*1920)),
          "median_face_sharpness":round(float(np.median(sh)),1),
          "median_yaw_deg":round(float(np.median(yaws)),1),
          "frontal_ratio":round(sum(1 for y in yaws if y<18)/float(len(yaws)),3),
          "mouth_in_frame_ratio":round(mouth_in/float(len(faces)),3),
          "median_chin_ratio":round(float(np.median(chins)),3),
          "median_motion":round(float(np.median(motions)) if motions else 0,2),
          "luma_mean":round(float(np.mean(lums)),1),
          "luma_flicker":round(float(np.std(lums)),1),
          "mouth_var_mean":round(float(np.mean(mouthvars)),1),
        })
    return agg

CANDIDATES = [
 ("uploads_4k_30_7_fullbody","C:/CongThang_AI_Avatar/AI_avatar/data/avatars/.uploads/musetalk_8960_6881921.mp4"),
 ("test17_8_close_up","C:/CongThang/AI_avatar/test17_8/Close Up.mp4"),
 ("test17_8_full_body","C:/CongThang/AI_avatar/test17_8/Full Body (2).mp4"),
 ("Hearing_1","C:/CongThang/AI_avatar/Hearing-1.mp4"),
 ("record_av","C:/CongThang/AI_avatar/record_av.mp4"),
 ("master_plus_body_closeup","C:/CongThang/AI_avatar/experiments/master_plus/inputs/body_closeup.mp4"),
 ("master_plus_body_fullbody","C:/CongThang/AI_avatar/experiments/master_plus/inputs/body_fullbody.mp4"),
 ("master_plus_body_halfbody","C:/CongThang/AI_avatar/experiments/master_plus/inputs/body_halfbody.mp4"),
]

out={}
for name,p in CANDIDATES:
    print("analyzing",name,p,flush=True)
    r=analyze_video(p)
    r["name"]=name
    out[name]=r

# close_up prepared frames proxy
print("analyzing close_up prepared frames proxy",flush=True)
import glob
cu_dir="C:/CongThang_AI_Avatar/AI_avatar/data/avatars/close_up/full_imgs"
fs=sorted(glob.glob(os.path.join(cu_dir,"*")))
if not fs:
    fs=sorted([os.path.join(cu_dir,f) for f in os.listdir(cu_dir)])
sub=fs[::max(1,len(fs)//6)][:6]
imgs=[cv2.imread(f) for f in sub]
imgs=[im for im in imgs if im is not None]
H=imgs[0].shape[0] if imgs else 0; W=imgs[0].shape[1] if imgs else 0
faces=[]
for im in imgs:
    g=cv2.cvtColor(im,cv2.COLOR_BGR2GRAY)
    d=detect_face(g)
    if d is not None:
        x,y,w,h=d
        sharp=laplacian_var(g[max(0,y-int(h*0.15)):y+h+int(h*0.15), max(0,x-int(w*0.15)):x+w+int(w*0.15)])
        eyes=eye_cascade.detectMultiScale(g[y:y+int(h*0.55),x:x+w],scaleFactor=1.1,minNeighbors=6,minSize=(int(w*0.08),int(w*0.08)))
        aspect=w/float(h)
        yaw=max(0.0,(0.78-aspect)/0.28)*70.0
        space_below=H-(y+h)
        faces.append({"h":h,"hr":h/float(H),"sharp":float(sharp),"yaw":float(yaw),
                      "mouth_in": (y+int(h*0.92))<H, "chin": (H-(y+h))/float(h)})
if faces:
    out["close_up_PROXY_prepared"]={
      "name":"close_up_PROXY_prepared",
      "path":"C:/CongThang_AI_Avatar/AI_avatar/data/avatars/close_up/full_imgs (proxy; original missing)",
      "width":W,"height":H,"frame_count":len(fs),
      "is_prepared_frame_proxy":True,
      "median_face_h_px":int(np.median([f["h"] for f in faces])),
      "median_face_h_ratio":round(float(np.median([f["hr"] for f in faces])),4),
      "est_face_h_at_1080p_out":int(round(float(np.median([f["hr"] for f in faces]))*1920)),
      "median_face_sharpness":round(float(np.median([f["sharp"] for f in faces])),1),
      "median_yaw_deg":round(float(np.median([f["yaw"] for f in faces])),1),
      "frontal_ratio":round(sum(1 for f in faces if f["yaw"]<18)/float(len(faces)),3),
      "mouth_in_frame_ratio":round(sum(1 for f in faces if f["mouth_in"])/float(len(faces)),3),
      "median_chin_ratio":round(float(np.median([f["chin"] for f in faces])),3),
      "n_samples":len(imgs),"faces_detected":len(faces)}

json.dump(out, open("C:/CongThang_AI_Avatar/avatar_source_audit_cv.json","w"), indent=2)
print("WROTE JSON",flush=True)
print(json.dumps(out,indent=1)[:4000])