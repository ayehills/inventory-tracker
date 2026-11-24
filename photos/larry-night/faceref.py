#!/usr/bin/env python3
"""Rebuild the out-of-focus head in photo 03 from his own, sharp head in photo 09.

03 and 09 are the same pose moments apart (hand on cheek, same spot, same cap and glasses); in 03
the camera focused on the police car behind him.  Nothing is generated: every detail comes from
his real face in 09, moved onto 03's head position and relit to 03's light.

  1. align    09 -> 03.  Every comparison is made against 03 *as it is blurred*: 09 is blurred
              with 03's defocus disc first, so the sharp face is fitted to what 03 really shows.
              a. similarity (scale, tilt, shift) from the 5 face landmarks, refined by maximising
                 correlation (the landmarks on a blurred face are a few pixels off)
              b. smooth non-rigid demons warp (Gaussian-regularised) for the small differences in
                 head tilt and smile, with no local rippling
  2. light    a smooth per-channel ratio (03 / blurred 09) carries 03's flash level and colour
              onto 09's detail; the glints on his glasses are left out of the ratio.
  3. matte    head + hand only: an ellipse limited by 09's person matte, feathered; the
              background, neck, shirt and arm stay 03's own pixels.
Writes build/faceref_03.npz (ROI box, linear-RGB head, alpha) for enhance.py, which blends it in
after the body deblur and before tone mapping, plus build/_fr_03.png (03 | aligned 09 | result).
Usage: python3 faceref.py   (after analyze.py, before enhance.py)
"""
import os, json, numpy as np, cv2
from PIL import Image

ROOT = os.path.dirname(os.path.abspath(__file__))
A = json.load(open(os.path.join(ROOT, 'build', 'analysis.json')))
LUMA = np.array([.2126, .7152, .0722], np.float32)
DBG = os.path.join(ROOT, 'build')

def lin(x): return np.where(x <= 0.04045, x / 12.92, ((np.maximum(x, 0.04045) + 0.055) / 1.055) ** 2.4).astype(np.float32)
def srgb(x):
    x = np.clip(x, 0, 1); return np.where(x <= 0.0031308, x * 12.92, 1.055 * np.power(np.maximum(x, 0.0031308), 1 / 2.4) - 0.055).astype(np.float32)
def load(k): return np.asarray(Image.open(os.path.join(ROOT, 'originals', A[k]['file'])).convert('RGB'), np.float32) / 255
def disc(r):
    kk = int(np.ceil(r)) * 2 + 1; dy, dx = np.mgrid[:kk, :kk] - kk // 2
    p = np.clip(r + 0.5 - np.hypot(dx, dy), 0, 1); return (p / p.sum()).astype(np.float32)
def blur(a, psf): return cv2.filter2D(a, -1, psf, borderType=cv2.BORDER_REFLECT)
def G(a, s): return cv2.GaussianBlur(a, (0, 0), s)
def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1); return (t * t * (3 - 2 * t)).astype(np.float32)
def save(name, a):
    Image.fromarray((np.clip(a, 0, 1) * 255 + .5).astype(np.uint8)).save(os.path.join(DBG, name))

def localnorm(g, s=12):
    m = G(g, s); sd = np.sqrt(np.maximum(G((g - m) ** 2, s), 1e-6))
    return np.clip(0.5 + 0.18 * (g - m) / (sd + 0.02), 0, 1)

def u8(a): return (np.clip(np.nan_to_num(a), 0, 1) * 255 + .5).astype(np.uint8)

def ncc(a, b, m):
    a = a[m] - a[m].mean(); b = b[m] - b[m].mean(); return float((a * b).sum() / np.sqrt((a * a).sum() * (b * b).sum()))

def rebuild(TGT='03', REF='09', R_DEFOCUS=5.0):
    from scipy.optimize import minimize
    O3, O9 = load(TGT), load(REF); I3, I9 = lin(O3), lin(O9)
    f3, f9 = A[TGT]['face'], A[REF]['face']
    lm3 = np.float32(f3[4:14]).reshape(5, 2); lm9 = np.float32(f9[4:14]).reshape(5, 2)
    M0, _ = cv2.estimateAffinePartial2D(lm9, lm3, method=cv2.LMEDS)
    cx, cy, s = f3[0] + f3[2] / 2, f3[1] + f3[3] / 2, f3[3]
    x0, x1, y0, y1 = int(cx - 1.35 * s), int(cx + 1.35 * s), int(cy - 1.55 * s), int(cy + 1.25 * s)
    h, w = y1 - y0, x1 - x0
    T0 = np.linalg.inv(np.vstack([M0, [0, 0, 1]])) @ np.array([[1, 0, x0], [0, 1, y0], [0, 0, 1]], np.float64)
    gx, gy = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))

    def warp9(T, u=None, src=I9, interp=cv2.INTER_CUBIC):            # ROI pixel -> 09 pixel
        X, Y = (gx, gy) if u is None else (gx + u[..., 0], gy + u[..., 1])
        Z = T[2, 0] * X + T[2, 1] * Y + T[2, 2]
        mx = ((T[0, 0] * X + T[0, 1] * Y + T[0, 2]) / Z).astype(np.float32)
        my = ((T[1, 0] * X + T[1, 1] * Y + T[1, 2]) / Z).astype(np.float32)
        return cv2.remap(src, mx, my, interp, borderMode=cv2.BORDER_REFLECT)

    R3 = I3[y0:y1, x0:x1]
    m3 = np.load(os.path.join(ROOT, 'build', f'mask_{TGT}.npy')).astype(np.float32)[y0:y1, x0:x1]
    m9src = np.load(os.path.join(ROOT, 'build', f'mask_{REF}.npy')).astype(np.float32)
    glint = cv2.dilate((O3[y0:y1, x0:x1].max(-1) >= 190 / 255.).astype(np.uint8),
                       cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (13, 13))) > 0
    hx, hy = cx - x0, cy - y0 - 0.12 * s
    head = ((gx - hx) / (0.62 * s)) ** 2 + ((gy - hy) / (0.92 * s)) ** 2 <= 1
    reg = head & ~glint & (m3 > .5)
    psf = disc(R_DEFOCUS)
    t3 = srgb(R3 @ LUMA)
    blurred = lambda T, u=None: srgb(blur(warp9(T, u, interp=cv2.INTER_LINEAR), psf) @ LUMA)

    # 1a. similarity about the face centre, maximising correlation with 03
    C = np.array([[1, 0, hx], [0, 1, hy], [0, 0, 1]])
    def sim(p):
        sc, rot, tx, ty = p; c, sn = sc * np.cos(np.radians(rot)), sc * np.sin(np.radians(rot))
        return T0 @ C @ np.array([[c, -sn, tx], [sn, c, ty], [0, 0, 1]]) @ np.linalg.inv(C)
    best = min((minimize(lambda p: -ncc(t3, blurred(sim(p)), reg), [1.0, r0, 0, 0], method='Powell',
                         options=dict(xtol=1e-3, ftol=1e-5, maxfev=400)) for r0 in (-4, 0, 4)), key=lambda r: r.fun)
    T = sim(best.x)
    print(f'  similarity: scale x{best.x[0]:.3f} tilt {best.x[1]:+.1f} deg shift ({best.x[2]:+.1f},{best.x[3]:+.1f}) '
          f'-> match {-best.fun:.3f} (landmarks alone {ncc(t3, blurred(T0), reg):.3f})')

    # 1b. demons: smooth non-rigid refinement inside his head and hand
    Mh = ((G(head.astype(np.float32), 8) > .02) & (m3 > .3)).astype(np.float32); Wm = G(Mh, 4)
    u = np.zeros((h, w, 2), np.float32); Fn = localnorm(t3); SD = 5.0
    sup = G(Mh, SD); keep = (sup > .05).astype(np.float32)
    for lv in (4, 2, 1):
        for _ in range(60):
            Ms, Fs = G(localnorm(blurred(T, u)), lv), G(Fn, lv)
            gyF, gxF = np.gradient(Fs); gyM, gxM = np.gradient(Ms)
            gxs, gys, d = (gxF + gxM) / 2, (gyF + gyM) / 2, Ms - Fs
            den = gxs ** 2 + gys ** 2 + 0.005 * d ** 2 + 1e-6
            du = np.clip(np.dstack([-d * gxs / den, -d * gys / den]) * Wm[..., None], -0.5 * lv, 0.5 * lv)
            du = np.dstack([G(du[..., i], 2.0 * lv) for i in range(2)])
            uu = [cv2.remap(u[..., i], gx + du[..., 0], gy + du[..., 1], cv2.INTER_LINEAR,
                            borderMode=cv2.BORDER_REPLICATE) + du[..., i] for i in range(2)]
            u = np.dstack([G(uu[i] * Mh, SD) / (sup + 1e-3) * keep for i in range(2)]).astype(np.float32)
    mag = np.hypot(u[..., 0], u[..., 1])
    print(f'  demons: mean shift {mag[head].mean():.1f}px (max {mag[head].max():.1f}) -> match {ncc(t3, blurred(T, u), reg):.3f}')

    W = np.clip(warp9(T, u, interp=cv2.INTER_LANCZOS4), 0, None)
    m9 = warp9(T, u, src=m9src, interp=cv2.INTER_LINEAR)
    # edge decontamination: 09's street lights glow through the soft edge of its matte (a pale rim
    # on the cap), so the outermost pixels take the colour of the cap / skin just inside the edge
    inner = cv2.erode((m9 > .5).astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))).astype(np.float32)
    Fext = np.dstack([G(W[..., c] * inner, 3) for c in range(3)]) / (G(inner, 3)[..., None] + 1e-6)
    wi = G(inner, 1.2)[..., None]
    W = np.where(G(inner, 3)[..., None] > 1e-3, W * wi + Fext * (1 - wi), W)

    # 2. relight: 03's light and colour, 09's detail (normalised convolution, glints excluded)
    Mrel = (head & ~glint & (m3 > .5) & (m9 > .5)).astype(np.float32); sL = 12
    bW = blur(W, psf); sup = G(Mrel, sL)
    Lg = R3[Mrel > 0].mean(0) / bW[Mrel > 0].mean(0)
    L = np.dstack([G(Mrel * R3[..., c], sL) / np.maximum(G(Mrel * bW[..., c], sL), 1e-7) for c in range(3)])
    L = np.where(sup[..., None] > .05, L, Lg)
    L = np.clip(L, Lg / 3, Lg * 3)
    L = np.dstack([G(L[..., c], 3) for c in range(3)])
    face = W * L
    print(f'  relight: 09 -> 03 average ratio R {Lg[0]:.2f} G {Lg[1]:.2f} B {Lg[2]:.2f}')

    # 3. matte: head + the hand on his cheek, limited to 09's person matte, feathered
    ex, ey, ax, ay = hx + 0.10 * s, hy + 0.08 * s, 0.80 * s, 1.00 * s
    E = (((gx - ex) / ax) ** 2 + ((gy - ey) / ay) ** 2 <= 1).astype(np.float32)
    person = cv2.erode((m9 > .5).astype(np.uint8), np.ones((3, 3), np.uint8)).astype(np.float32)
    alpha = np.clip(G(E, 7) * G(person, 1.2), 0, 1)

    np.savez_compressed(os.path.join(ROOT, 'build', f'faceref_{TGT}.npz'), roi=np.array([x0, y0, x1, y1]),
                        face=face.astype(np.float16), alpha=alpha.astype(np.float16))
    k = 0.05 / np.median(R3[head] @ LUMA)                                # debug view, brightened
    comp = face * alpha[..., None] + R3 * (1 - alpha[..., None])
    save(f'_fr_{TGT}.png', np.concatenate([srgb(R3 * k), srgb(W * k * Lg.mean()), srgb(comp * k)], 1))
    return (x0, y0, x1, y1)

if __name__ == '__main__':
    print('faceref 03 <- 09'); print('  roi', rebuild())
