#!/usr/bin/env python3
"""Step 1 of 2: measure each original before enhance.py runs.

Writes build/analysis.json (face box, face/subject/background luminance, noise, clipping) and
build/mask_XX.npy (person mask: the figure under the detected face, not bystanders).

Models:
  models/yunet.onnx   OpenCV Zoo face_detection_yunet_2023mar.onnx
                      https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet
  u2net_human_seg     downloaded by rembg on first use
Usage: python3 analyze.py   (then python3 enhance.py)
"""
import os, glob, json, numpy as np, cv2
from PIL import Image
from rembg import remove, new_session
from skimage.restoration import estimate_sigma

ROOT = os.path.dirname(os.path.abspath(__file__))
os.makedirs(os.path.join(ROOT, 'build'), exist_ok=True)
sess = new_session('u2net_human_seg')
def lin(x): return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)

info = {}
for f in sorted(glob.glob(os.path.join(ROOT, 'originals', '*.jpg'))):
    key = os.path.basename(f)[:2]
    img = np.array(Image.open(f).convert('RGB')); H, W = img.shape[:2]
    m = np.array(remove(Image.fromarray(img), session=sess, only_mask=True, post_process_mask=True)).astype(np.float32) / 255
    bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR); face = None
    for thr in (0.6, 0.4, 0.25):                                   # relax until his face is found
        det = cv2.FaceDetectorYN.create(os.path.join(ROOT, 'models', 'yunet.onnx'), '', (W, H), thr, 0.3, 5000)
        det.setInputSize((W, H))
        _, fs = det.detect(bgr)
        if fs is not None and len(fs):
            fs = sorted(fs, key=lambda r: -r[2] * r[3]); face = [float(v) for v in fs[0][:15]]; break
    # keep only the person under the face (drops bystanders the segmenter also picked up)
    n, lab, st, cen = cv2.connectedComponentsWithStats((m > .5).astype(np.uint8), 8)
    if n > 1:
        keep = 0
        if face:
            fx, fy = int(face[0] + face[2] / 2), int(face[1] + face[3] / 2)
            keep = lab[min(H - 1, fy + int(face[3])), fx] or lab[fy, fx]
        if not keep: keep = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
        m = m * (lab == keep)
    np.save(os.path.join(ROOT, 'build', f'mask_{key}.npy'), m.astype(np.float16))
    Y = cv2.cvtColor(img, cv2.COLOR_RGB2YCrCb)[..., 0]
    sig = float(estimate_sigma(Y.astype(np.float64), channel_axis=None))
    L = lin(img.astype(np.float32) / 255) @ np.array([.2126, .7152, .0722], np.float32)
    subj = L[m > .5]; bg = L[m < .1]; fmed = None
    if face:
        x, y, w, h = [int(v) for v in face[:4]]
        fmed = float(np.median(L[max(0, y):y + h, max(0, x):x + w]))
    info[key] = dict(file=os.path.basename(f), face=face, noise_sigma=sig, subj_median=float(np.median(subj)),
                     face_median=fmed, bg_p50=float(np.median(bg)), bg_p99=float(np.percentile(bg, 99)),
                     clip_pct=float((img.max(2) >= 250).mean() * 100), subj_area=float((m > .5).mean()))
    print(f"{key}: face={'%.2f@(%d,%d,%dx%d)' % (face[14], face[0], face[1], face[2], face[3]) if face else 'NONE':26s} "
          f"noise={sig:4.2f} face_med={fmed if fmed is None else round(fmed, 3)} subj_med={np.median(subj):.3f} "
          f"bg_med={np.median(bg):.4f} clip={info[key]['clip_pct']:.2f}% subj_area={info[key]['subj_area'] * 100:.1f}%")
json.dump(info, open(os.path.join(ROOT, 'build', 'analysis.json'), 'w'), indent=1)
