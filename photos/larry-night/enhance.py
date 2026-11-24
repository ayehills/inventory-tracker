#!/usr/bin/env python3
"""Camera-Raw-style enhancement of the night flash photos: clarity, HDR tone mapping, subject focus.

The face is never reshaped, smoothed or synthesized: it gets global tone and colour, plus
deconvolution sharpening (clarity), with gentler local-contrast boost than the rest of the frame.

Per photo:
  1. clean-up    chroma noise reduction everywhere; JPEG-block / noise smoothing only in the dark
                 *background* (never on the subject), so lifting the shadows stays clean.
  2. exposure    gain from the measured face luminance (partial correction, capped), then a
                 soft subject +EV / background -EV and a vignette centred on the subject.
  3. HDR         Durand-style local tone mapping in log2 luminance with guided filters:
                 base (compressed -> shadows up, highlights down) + mid (clarity) + fine (texture).
  4. display     hue-preserving highlight roll-off, sRGB, black/white points, gentle S-curve.
  5. colour      vibrance in Lab, skin hues and the face protected.
  6. sharpen     Richardson-Lucy deconvolution + unsharp mask on lightness, edge-masked, with an
                 anti-halo clamp to the local min/max.
Usage: python3 enhance.py [keys e.g. 01,03] [--preview]
"""
import sys, os, json, glob, numpy as np, cv2
from PIL import Image
from skimage.restoration import richardson_lucy, denoise_tv_chambolle

ROOT = os.path.dirname(os.path.abspath(__file__))
A = json.load(open(os.path.join(ROOT, 'build', 'analysis.json')))

DEFAULT = dict(
    face_L=42.0, gain_lo=0.40, gain_hi=4.50,          # face lands at L*~42 (his true flash-lit tone, a touch brighter)
    subj_ev=0.15, bg_ev=-0.20, vignette_ev=-0.40,
    base_r=48, base_eps=0.20, mid_r=6, mid_eps=0.02,
    compress=0.74,                                     # pivot = the face itself (face-anchored HDR)
    k_mid=1.50, k_fine=1.25, k_mid_face=1.15, k_fine_face=1.10,
    bg_smooth=1.0,
    black=0.012, white=0.985, s_curve=0.14,
    vib=0.32,
    deconv_sigma=1.0, deconv_iter=8, deconv_amt=0.85,
    usm_r=1.1, usm_amt=0.55, halo=0.02,
)
PER = {
    # focus missed the subject (background is sharp): disc-PSF deblur on him only, radius chosen
    # below the point where deconvolution starts ringing (>=6 px draws false lines on the face)
    '03': dict(pre_deblur=4.75, usm_amt=0.65),
}

def lin(x): return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4).astype(np.float32)
def srgb(x):
    x = np.clip(x, 0, 1); return np.where(x <= 0.0031308, 12.92 * x, 1.055 * np.power(x, 1 / 2.4) - 0.055).astype(np.float32)
LUMA = np.array([0.2126, 0.7152, 0.0722], np.float32)
def box(x, r): return cv2.blur(x, (2 * r + 1, 2 * r + 1), borderType=cv2.BORDER_REFLECT)
def gf(I, p, r, eps):
    mI, mp = box(I, r), box(p, r)
    a = (box(I * p, r) - mI * mp) / (box(I * I, r) - mI * mI + eps); b = mp - a * mI
    return box(a, r) * I + box(b, r)
def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1); return (t * t * (3 - 2 * t)).astype(np.float32)

def rl_masked(d, psf, iters, valid):
    """Richardson-Lucy that ignores unreliable (clipped) pixels in the data term, so a blown
    highlight may be brighter than 1 in the estimate instead of ringing (Whyte et al. 2014)."""
    d = d.astype(np.float32); M = valid.astype(np.float32)
    conv = lambda a, k: cv2.filter2D(a, -1, k, borderType=cv2.BORDER_REFLECT)   # psf is symmetric
    norm = conv(M, psf); u = d.copy()
    for _ in range(iters):
        u *= np.where(norm > 1e-3, conv(M * d / np.maximum(conv(u, psf), 1e-6), psf) / np.maximum(norm, 1e-3), 1)
    return np.where(valid, u, np.maximum(u, d))

def enhance(key, P, preview=False):
    a = A[key]
    img8 = np.array(Image.open(os.path.join(ROOT, 'originals', a['file'])).convert('RGB'))
    H, W = img8.shape[:2]
    m = np.load(os.path.join(ROOT, 'build', f'mask_{key}.npy')).astype(np.float32)
    S = cv2.GaussianBlur(m, (0, 0), 18)                                      # soft subject
    x, y, w, h = a['face'][:4]
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    F = (((xx - (x + w / 2)) / (0.62 * w)) ** 2 + ((yy - (y + h / 2)) / (0.62 * h)) ** 2 <= 1).astype(np.float32)
    F = cv2.GaussianBlur(F, (0, 0), 0.12 * w)                                # soft face ellipse

    rgb = img8.astype(np.float32) / 255
    if P.get('pre_deblur'):                                                   # 0. defocus deblur (linear light)
        r = P['pre_deblur']; kk = int(np.ceil(r)) * 2 + 1; dy, dx = np.mgrid[:kk, :kk] - kk // 2
        psf = np.clip(r + 0.5 - np.hypot(dx, dy), 0, 1); psf = (psf / psf.sum()).astype(np.float64)
        ys, xs = np.where(m > .3); pad = 60
        y0, y1, x0, x1 = max(0, ys.min() - pad), min(H, ys.max() + pad), max(0, xs.min() - pad), min(W, xs.max() + pad)
        Lin = lin(rgb[y0:y1, x0:x1]); out = np.empty_like(Lin)
        # blown highlights (tail lights) and the glints on his glasses (bright, compressed by the
        # camera's highlight shoulder, and not blurred like the face) are left out of the fit and
        # keep their original pixels; fitting them would draw a dark ring around each one
        mx8 = img8[y0:y1, x0:x1].max(-1)
        clipped = (mx8 >= 240) | ((mx8 >= 190) & (F[y0:y1, x0:x1] > 0.02))
        clipped = cv2.dilate(clipped.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
        for c in range(3):
            out[..., c] = rl_masked(np.clip(Lin[..., c], 1e-5, 1), psf.astype(np.float32), 25, ~clipped)
        out = denoise_tv_chambolle(np.clip(out, 0, 1), weight=0.004, channel_axis=-1).astype(np.float32)
        wsub = cv2.GaussianBlur(m, (0, 0), 12)[y0:y1, x0:x1, None]
        rgb[y0:y1, x0:x1] = srgb(out * wsub + Lin * (1 - wsub))
    rgb_orig = rgb.copy()

    # 1. clean-up ------------------------------------------------------------------------
    ycc = cv2.cvtColor(rgb, cv2.COLOR_RGB2YCrCb); Y = ycc[..., 0]
    wbg = (1 - S) * smoothstep(0.40, 0.04, Y) * P['bg_smooth']                 # dark background only
    Y = Y * (1 - wbg) + gf(Y, Y, 4, 2.5e-4) * wbg
    wc = (0.55 + 0.45 * smoothstep(0.45, 0.05, ycc[..., 0])) * (1 - 0.6 * F)
    for c in (1, 2):
        ycc[..., c] = ycc[..., c] * (1 - wc) + gf(ycc[..., 0], ycc[..., c], 6, 1e-3) * wc
    ycc[..., 0] = Y
    rgb = np.clip(cv2.cvtColor(ycc, cv2.COLOR_YCrCb2RGB), 0, 1)

    def render(g):
        # high-gain factor: 0 up to x1.8, 1 from x4 — a heavily lifted dark JPEG exposes compression blocks
        hg = float(np.clip((g - 1.8) / 2.2, 0, 1))
        src = rgb
        if hg > 0:                                                            # JPEG deblock on the face only:
            ycc_ = cv2.cvtColor(rgb, cv2.COLOR_RGB2YCrCb); Y_ = ycc_[..., 0]  # edge-preserving below ~1.1% steps,
            wdb = np.clip(F * 1.6, 0, 1) * hg * 0.75                          # so features and wrinkles are kept
            ycc_[..., 0] = Y_ * (1 - wdb) + gf(Y_, Y_, 2, 1.2e-4) * wdb
            src = np.clip(cv2.cvtColor(ycc_, cv2.COLOR_YCrCb2RGB), 0, 1)
        # 2. exposure -------------------------------------------------------------------------
        E = lin(src) * g
        my, mx_ = np.argwhere(m > .5).mean(0)
        d = np.sqrt(((xx - mx_) / (0.80 * W)) ** 2 + ((yy - my) / (0.80 * H)) ** 2)
        ev = P['subj_ev'] * S + P['bg_ev'] * (1 - S) + P['vignette_ev'] * smoothstep(0.35, 1.15, d) * (1 - S)
        E *= (2 ** ev)[..., None]

        # 3. HDR local tone mapping ---------------------------------------------------------------
        eps0 = 2.0 ** -13
        L = E @ LUMA; lL = np.log2(L + eps0)
        base = gf(lL, lL, P['base_r'], P['base_eps'])
        mb = gf(lL, lL, P['mid_r'], P['mid_eps'])
        mid, fine = mb - base, lL - mb
        pv = np.log2(g * a['face_median'] * 2 ** P['subj_ev'])          # face-anchored pivot
        base_c = pv + (base - pv) * P['compress']
        kmf = 1 + (P['k_mid_face'] - 1) * (1 - 0.5 * hg); kff = 1 + (P['k_fine_face'] - 1) * (1 - hg)
        kmid = P['k_mid'] * (1 - F) + kmf * F
        kfine = P['k_fine'] * (1 - F) + kff * F
        lit = smoothstep(np.log2(0.0025), np.log2(0.02), base)                    # 0 in deep, noisy darks
        kfine = 1 + (kfine - 1) * lit * (0.35 + 0.65 * S)
        kmid = 1 + (kmid - 1) * (0.55 + 0.45 * lit)
        out = base_c + kmid * mid + kfine * fine
        E = E * ((2.0 ** out) / (L + eps0))[..., None]

        # 4. display ---------------------------------------------------------------------------
        mx = E.max(2, keepdims=True); knee = 0.80
        m2 = np.where(mx > knee, knee + (1 - knee) * (1 - np.exp(-(mx - knee) / (1 - knee))), mx)
        E = E * (m2 / np.maximum(mx, 1e-6))
        D = srgb(E)
        Ld = D @ LUMA
        lo, hi = min(float(np.percentile(Ld, 0.15)), 0.06), 1.0          # black point only; white fixed so exposure stays exposure
        D = (D - lo) / max(hi - lo, 1e-3) * (P['white'] - P['black']) + P['black']
        D = np.clip(D, 0, 1)
        D = D * (1 - P['s_curve']) + D * D * (3 - 2 * D) * P['s_curve']
        D = D * (0.72 + 0.28 * smoothstep(0.02, 0.30, D))                 # toe: rich blacks; faces (>0.3) untouched

        # 5. vibrance (skin + face protected) ---------------------------------------------------------
        lab = cv2.cvtColor(D.astype(np.float32), cv2.COLOR_RGB2Lab)
        A_, B_ = lab[..., 1], lab[..., 2]
        C = np.hypot(A_, B_); hue = np.degrees(np.arctan2(B_, A_))
        skin = smoothstep(8, 25, hue) * (1 - smoothstep(60, 80, hue)) * (1 - smoothstep(30, 55, C))
        protect = np.maximum(F, skin * S)
        boost = 1 + P['vib'] * (1 - np.clip(C / 60, 0, 1)) * (1 - 0.85 * protect) * smoothstep(4.0, 14.0, C)
        boost *= 0.35 + 0.65 * smoothstep(4.0, 16.0, lab[..., 0])          # near-blacks stay neutral (no casts)
        # dark neutrals keep their colour: a black shirt stays black, not navy
        lab_o = cv2.cvtColor(rgb_orig, cv2.COLOR_RGB2Lab); Co = np.hypot(lab_o[..., 1], lab_o[..., 2])
        wn = (1 - smoothstep(4.0, 8.0, Co)) * (1 - smoothstep(30.0, 45.0, lab[..., 0])) * (1 - F)
        boost *= 1 - 0.45 * wn
        lab[..., 1] *= boost; lab[..., 2] *= boost

        # 6. sharpening on lightness ---------------------------------------------------------------
        Lc = lab[..., 0] / 100.0
        s = P['deconv_sigma']; k = int(np.ceil(3 * s)) * 2 + 1
        g1 = cv2.getGaussianKernel(k, s); psf = (g1 @ g1.T).astype(np.float32)
        rl = richardson_lucy(np.clip(Lc, 1e-4, 1).astype(np.float64), psf.astype(np.float64),
                             num_iter=P['deconv_iter'], clip=False).astype(np.float32)
        gx = cv2.Sobel(cv2.GaussianBlur(Lc, (0, 0), 1.0), cv2.CV_32F, 1, 0)
        gy = cv2.Sobel(cv2.GaussianBlur(Lc, (0, 0), 1.0), cv2.CV_32F, 0, 1)
        gm = np.hypot(gx, gy); gm = gm / (np.percentile(gm, 98) + 1e-6)
        edge = smoothstep(0.06, 0.30, gm) * (0.45 + 0.55 * S)                     # subject gets full sharpening
        edge *= 1 - 0.55 * hg * F                                                 # don't re-crisp lifted JPEG blocks
        Ls = Lc + (rl - Lc) * P['deconv_amt'] * edge
        Ls = Ls + P['usm_amt'] * (Ls - cv2.GaussianBlur(Ls, (0, 0), P['usm_r'])) * edge
        k3 = np.ones((3, 3), np.uint8)
        Ls = np.clip(Ls, cv2.erode(Lc, k3) - P['halo'], cv2.dilate(Lc, k3) + P['halo'])
        lab[..., 0] = np.clip(Ls, 0, 1) * 100

        # 7. face colour lock: brighter and clearer, but the original skin colour (chromaticity) ---------
        ratio =np.clip((lab[..., 0] + 4) / (lab_o[..., 0] + 4), 0.7, 1.8)
        for c in (1, 2):
            lab[..., c] = lab[..., c] * (1 - F) + lab_o[..., c] * ratio * F
        return np.clip(cv2.cvtColor(lab, cv2.COLOR_Lab2RGB), 0, 1)

    # solve the exposure so the face core lands at P['face_L'] (secant on log gain, 3 passes max)
    x, y, w, h = a['face'][:4]; cx, cy = int(x + w / 2), int(y + h * 0.55)
    core = (slice(cy - int(h / 5), cy + int(h / 5)), slice(cx - int(w / 4), cx + int(w / 4)))
    def face_L(D): return float(np.median(cv2.cvtColor(D[core].astype(np.float32), cv2.COLOR_RGB2Lab)[..., 0]))
    Lo = face_L(rgb_orig)
    g = float(np.clip(0.07 / a['face_median'], P['gain_lo'], P['gain_hi']))
    for it in range(4):
        D = render(g); Lf = face_L(D)
        if abs(Lf - P['face_L']) < 1.0 or it == 3: break
        Yt, Yc = ((P['face_L'] + 16) / 116) ** 3, ((Lf + 16) / 116) ** 3
        g = float(np.clip(g * (Yt / Yc) ** 1.1, P['gain_lo'], P['gain_hi']))
    print(f'{key}: face L* {Lo:.1f} -> {Lf:.1f}  gain x{g:.2f} ({np.log2(g):+.2f} EV, {it + 1} pass)')

    out8 = (D * 255 + 0.5).astype(np.uint8)
    name = a['file'].replace('.jpg', '_enhanced.jpg')
    if not preview:
        Image.fromarray(out8).save(os.path.join(ROOT, 'enhanced', name), quality=95, subsampling=0)
    Image.fromarray(out8).save(os.path.join(ROOT, 'build', f'out_{key}.png'))
    print(f'    -> {name}')
    return out8

if __name__ == '__main__':
    keys = sorted(A) if len(sys.argv) < 2 or sys.argv[1].startswith('--') else sys.argv[1].split(',')
    for k in keys:
        enhance(k, {**DEFAULT, **PER.get(k, {})}, preview='--preview' in sys.argv)
