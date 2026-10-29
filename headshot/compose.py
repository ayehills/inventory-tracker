#!/usr/bin/env python3
"""Update the business headshot: keep suit/shirt/tie/backdrop from the original,
replace the head with the recent photo (full beard), color-matched to the studio look.

Pipeline
  1. head layer from recent photo: person alpha (u2net_human_seg) cut along the beard's
     bottom contour (so no neck/tank-top), feathered
  2. colour transfer (Lab, Reinhard) using face-skin statistics recent -> base,
     specular (shine) compression on the forehead/nose
  3. affine warp (scale/rotate/translate) so the eyes land where the original eyes were
  4. canvas = synthesized backdrop (quadratic fit of the original gradient) at 2x,
     body = original upscaled 2x, rows below the old jaw only, feathered by its person alpha
  5. composite head on top, soft beard shadow onto the collar, light sharpen + grain
"""
import json, numpy as np, cv2
from PIL import Image, ImageFilter

CFG = dict(
    scale=0.335,       # recent px -> base px
    slim=0.97,         # horizontal factor: undo a little of the close-lens widening
    out_mult=2,        # output = 2x base (1836)
    headroom=120,      # extra canvas rows added at the top
    S=556,             # base row: everything above (outside new head) becomes backdrop
    collar_bottom=712, # base row: bottom of the neck zone (tie knot) for the neck replacement
    eye_dx=0, eye_dy=0,# fine nudge of the head (base px)
    shadow=0.35,
)

L = json.load(open('build/landmarks.json'))
def avg(*p): return np.mean(np.array(p), axis=0)
# base landmarks (average of two consistent detections stored earlier) -------------
b_re, b_le = np.array([377.5, 331.5]), np.array([528.5, 334.0])
b_mouth = np.array([450.5, 485.0]); b_nose = np.array([449.0, 418.5])
# recent landmarks (average of 0.33 and 0.45 scale passes) --------------------------
r_re, r_le = np.array([753.5, 1319.0]), np.array([1218.0, 1319.5])
r_mouth = np.array([982.0, 1813.5]); r_nose = np.array([990.0, 1600.0])

base = np.array(Image.open('assets/base_headshot.jpg').convert('RGB'))
base_a = np.array(Image.open('build/base_rgba.png'))[:, :, 3].astype(np.float32) / 255
rec = np.array(Image.open('assets/recent_full.jpg').convert('RGB'))
rec_rgba = np.array(Image.open('build/recent_rgba.png'))
rec_a = rec_rgba[:, :, 3].astype(np.float32) / 255
rec_fg = rec_rgba[:, :, :3].copy()      # matting-decontaminated foreground colours (no wall bleed at edges)
RH, RW = rec_a.shape; BH, BW = base_a.shape

# ---------------------------------------------------------------- 1. head layer
def beard_contour():
    """Per-column bottom edge of the beard. Hair = near-neutral chroma (or very dark); skin keeps a/b
    high even in shadow. The hair mask is morphologically opened so thin dark strands (the necklace
    cord) cannot drag the scan down. Scan starts below the lip-to-chin skin gap and stops at the first
    long skin run (the neck). Gaps are interpolated; side columns are capped to the chin depth."""
    lab = cv2.cvtColor(rec, cv2.COLOR_RGB2LAB); V = cv2.cvtColor(rec, cv2.COLOR_RGB2HSV)[..., 2]
    hair = (((lab[..., 1] < 137) & (lab[..., 2] < 138)) | (V < 22)).astype(np.uint8)
    hair = cv2.morphologyEx(hair, cv2.MORPH_OPEN, np.ones((21, 21), np.uint8)).astype(bool)
    fg = rec_a > .5
    my = int(r_mouth[1]); em = r_mouth[1] - (r_re[1] + r_le[1]) / 2
    y_start = int(my + 0.53 * em)
    bot = np.full(RW, -1)
    for x in range(RW):
        if not fg[y_start, x]: continue
        col_h = hair[:, x] & fg[:, x]
        y = y_start; run = 0; last = -1
        while y < RH - 1 and fg[y, x]:
            if col_h[y]: last = y; run = 0
            else:
                run += 1
                if run >= 70: break
            y += 1
        if last < 0:                       # no beard below start here: jaw corner is above
            y = y_start
            while y > my and not col_h[y]: y -= 1
            if y > my: last = y
        bot[x] = last
    ok = bot > 0; xs = np.where(ok)[0]; x0, x1 = int(xs.min()), int(xs.max())
    seg = bot[x0:x1 + 1].astype(np.float32); idx = np.arange(len(seg)); okk = seg > 0
    seg = np.interp(idx, idx[okk], seg[okk])
    cx = int(r_nose[0]) - x0; centre = float(np.median(seg[max(0, cx - 120):cx + 120]))
    seg = np.minimum(seg, centre + 40)                                   # sides never deeper than the chin
    k = 31; pad = np.pad(seg, k // 2, mode='edge')
    seg = np.array([np.median(pad[j:j + k]) for j in range(len(seg))], np.float32)
    seg = cv2.GaussianBlur(seg.reshape(1, -1), (0, 0), 7).ravel() - 6   # bias up a touch
    return x0, x1, seg

def head_layer():
    x0, x1, seg = beard_contour()
    ey = (r_re[1] + r_le[1]) / 2
    print(f'beard contour: cols {x0}-{x1}, centre bottom y={seg[len(seg)//2]:.0f} (eye->beard {seg[len(seg)//2]-ey:.0f})')
    cut = np.ones((RH, RW), np.float32)
    yy = np.arange(RH)[:, None]
    # inside the beard span: keep above the contour (feather 14px)
    contour = np.full(RW, np.nan, np.float32); contour[x0:x1 + 1] = seg
    # outside the span (ears / hair sides): cut at the jaw-corner height
    side_y = min(seg[0], seg[-1]) - 30
    contour[:x0] = side_y; contour[x1 + 1:] = side_y
    cut = np.clip((contour[None, :] - yy) / 14.0 + 0.5, 0, 1)
    alpha = rec_a * cut
    # drop any stray alpha far below (shoulders) and far above
    alpha[yy.ravel() > int(seg.max()) + 40, :] = 0
    return defringe(alpha)

def defringe(alpha):
    """Kill wall-coloured pixels the matting let in. The bathroom wall is light AND grey;
    skin is saturated, hair is dark."""
    hsv = cv2.cvtColor(rec, cv2.COLOR_RGB2HSV).astype(np.float32); S, V = hsv[..., 1], hsv[..., 2]
    solid = (alpha > .97).astype(np.uint8)
    inner = cv2.erode(solid, np.ones((41, 41), np.uint8)).astype(bool)
    band = ~inner & (alpha > 0)
    wall = np.clip((85 - S) / 40, 0, 1) * np.clip((V - 95) / 50, 0, 1)
    alpha = np.where(band, alpha * (1 - wall), alpha)
    # and anywhere outside a protected face ellipse (skin shine lives inside it), wall-coloured = wall
    ipd = np.linalg.norm(r_re - r_le); c = (avg(r_re, r_le) + r_mouth) / 2
    xx2, yy2 = np.meshgrid(np.arange(RW), np.arange(RH))
    face = (((xx2 - c[0]) / (0.95 * ipd)) ** 2 + ((yy2 - c[1]) / (1.2 * ipd)) ** 2) <= 1
    wall2 = np.clip((60 - S) / 30, 0, 1) * np.clip((V - 150) / 40, 0, 1)
    alpha = np.where(~face, alpha * (1 - wall2), alpha)
    alpha = cv2.erode(alpha, np.ones((3, 3), np.uint8)); alpha = cv2.GaussianBlur(alpha, (0, 0), 0.9)
    return alpha

# ---------------------------------------------------------------- 2. colour match
def skin_stats(img, alpha, re, le, mouth, nose):
    ipd = np.linalg.norm(re - le); c = (avg(re, le) + mouth) / 2
    H, W = alpha.shape; yy, xx = np.mgrid[0:H, 0:W]
    ell = (((xx - c[0]) / (0.95 * ipd)) ** 2 + ((yy - c[1]) / (1.05 * ipd)) ** 2) <= 1
    hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV); V = hsv[..., 2]; S = hsv[..., 1]
    m = ell & (alpha > .5) & (V > 70) & (V < 235) & (S > 40)
    lab = cv2.cvtColor(img, cv2.COLOR_RGB2LAB).astype(np.float32)
    px = lab[m]; return px.mean(0), px.std(0), m

def colour_match(rgba):
    rgb = rgba[..., :3].astype(np.uint8); a = rgba[..., 3] / 255
    ms, ss, m_r = skin_stats(rec, a, r_re, r_le, r_mouth, r_nose)
    mt, st, m_b = skin_stats(base, base_a, b_re, b_le, b_mouth, b_nose)
    print('skin Lab recent mean', ms.round(1), 'std', ss.round(1)); print('skin Lab base   mean', mt.round(1), 'std', st.round(1))
    mt = mt + np.array([4.0, 0.5, 1.0])              # a touch brighter / warmer than the old shot
    # light professional skin polish: bilateral on skin pixels only, 45% blend (keeps pores, kills harshness)
    labf = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)
    skin_all = (labf[..., 1] > 137) & (labf[..., 2] > 140) & (a > .5)
    skin_all = cv2.GaussianBlur(skin_all.astype(np.float32), (0, 0), 3)[..., None]
    smooth = cv2.bilateralFilter(rgb, 9, 30, 7)
    rgb = (rgb * (1 - 0.45 * skin_all) + smooth * (0.45 * skin_all)).astype(np.uint8)
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
    # specular compression on bright skin before the transfer
    Lc = lab[..., 0]; p = np.percentile(Lc[m_r], 88)
    hi = np.clip((Lc - p) / 25, 0, 1) * m_r.astype(np.float32)
    hi = cv2.GaussianBlur(hi, (0, 0), 2)
    lab[..., 0] = Lc - hi * (Lc - p) * 0.6
    ratio = np.clip(st / ss, [0.75, 0.6, 0.6], [1.15, 1.4, 1.4])
    out = (lab - ms) * ratio + mt
    # keep deep darks (hair/beard) from lifting: blend toward original for very dark pixels
    dark = np.clip((60 - lab[..., 0:1]) / 60, 0, 1)
    out = out * (1 - 0.6 * dark) + lab * (0.6 * dark)
    out = np.clip(out, 0, 255).astype(np.uint8)
    rgb2 = cv2.cvtColor(out, cv2.COLOR_LAB2RGB)
    return np.dstack([rgb2.astype(np.float32), rgba[..., 3]])

# ---------------------------------------------------------------- 3. warp
def warp_head(rgba, M, OW, OH):
    """Premultiplied-alpha warp so zero-alpha (wall) pixels never bleed into the edge.
    Returns (premultiplied rgb, alpha in 0..1)."""
    a = rgba[..., 3:4] / 255.0
    pm = np.dstack([rgba[..., :3] * a, a]).astype(np.float32)
    out = cv2.warpAffine(pm, M, (OW, OH), flags=cv2.INTER_LANCZOS4, borderValue=(0, 0, 0, 0))
    return np.clip(out[..., :3], 0, 255), np.clip(out[..., 3:4], 0, 1)

# ---------------------------------------------------------------- 4. canvas
def backdrop(OW, OH, mult, D):
    coef = np.load('build/bg_coef.npy')
    yy, xx = np.mgrid[0:OH, 0:OW].astype(np.float32)
    X = np.clip(xx / mult / BW, 0, 1); Y = np.clip((yy - D) / mult / BH, 0, 1)
    A = np.stack([np.ones_like(X), X, Y, X * X, Y * Y, X * Y], -1)
    bg = A @ coef
    rng = np.random.default_rng(3); bg += rng.normal(0, 1.2, bg.shape)
    return np.clip(bg, 0, 255)

def old_head_mask():
    """Original head + neck in the base photo (everything above the shirt collar / tie / suit).
    Removed from the body layer and refilled from the recent photo."""
    person = base_a > .5
    b = base.astype(np.int16); V = cv2.cvtColor(base, cv2.COLOR_RGB2HSV)[..., 2]
    blue = (b[..., 2] > b[..., 0] + 25) & (b[..., 2] > 90)
    yy = np.arange(BH)[:, None]
    # cut at the first shirt (blue) row per column: collar wings at the sides, the collar band just
    # above the tie knot in the centre V. Columns beyond the wings fall back to the suit's first dark row.
    y_cut = np.full(BW, 720, np.float32)
    for x in range(BW):
        col = np.where(blue[560:740, x])[0]
        if len(col): y_cut[x] = 560 + col[0]; continue
        if abs(x - 455) <= 70: y_cut[x] = 718; continue           # inside the V: stop at the knot
        col = np.where((V[650:740, x] < 100) & person[650:740, x])[0]
        if len(col): y_cut[x] = 650 + col[0]
    y_cut = cv2.GaussianBlur(y_cut.reshape(1, -1), (0, 0), 1.5).ravel()
    return (person & (yy < y_cut[None, :])).astype(np.float32)

def compose(cfg):
    s, mult, D = cfg['scale'], cfg['out_mult'], cfg['headroom']
    OW, OH = BW * mult, BH * mult + D
    canvas = backdrop(OW, OH, mult, D)
    up = lambda m: cv2.resize(m, (BW * mult, BH * mult), interpolation=cv2.INTER_LINEAR)
    to_canvas = lambda m: np.pad(m, ((D, 0),) + ((0, 0),) * (m.ndim - 1))

    # body layer: original suit/shirt/tie with the old head+neck removed
    body = to_canvas(cv2.resize(base, (BW * mult, BH * mult), interpolation=cv2.INTER_LANCZOS4).astype(np.float32))
    oh = up(old_head_mask())
    ba = to_canvas(up(base_a) * (1 - cv2.GaussianBlur(oh, (0, 0), 0.8)))[..., None]
    # neck-fill safety (canvas rows): never below the tie knot; columns unrestricted —
    # the anatomical limit (head + neck only) is applied in the recent photo's coordinates below
    zone = np.zeros((OH, OW), np.float32); zone[:cfg['collar_bottom'] * mult + D, :] = 1
    zone = cv2.GaussianBlur(zone, (0, 0), 4)[..., None]

    # recent photo clean-up: inpaint the necklace cord out of the neck and lift the neck out of shadow
    x0c, x1c, segc = beard_contour()
    contour = np.full(RW, np.nan, np.float32); contour[x0c:x1c + 1] = segc + 6
    Vr = cv2.cvtColor(rec, cv2.COLOR_RGB2HSV)[..., 2]
    yy = np.arange(RH)[:, None]; xx = np.arange(RW)[None, :]
    lo = np.nan_to_num(contour, nan=1e9)[None, :]; hi = np.nan_to_num(contour, nan=-1e9)[None, :]
    neck = (xx >= 560) & (xx <= 1380) & (yy > lo - 10) & (yy < hi + 300) & (rec_a > .5)
    # the cord is thin and darker than the skin around it (works in the shadowed part of the neck too)
    med = cv2.medianBlur(Vr, 41).astype(np.float32)
    cord = cv2.dilate((neck & (Vr < 0.74 * med)).astype(np.uint8), np.ones((11, 11), np.uint8))
    # anatomical limit for the neck-fill layer: head + neck, stop above the trapezius / tank top
    side_y = min(segc[0], segc[-1]) - 30
    limit = np.where(np.isnan(contour), side_y + 60, contour + 330)
    zone_rec = np.clip((limit[None, :] - yy) / 20.0 + 0.5, 0, 1).astype(np.float32)
    rec_fixed = cv2.inpaint(rec_fg, cord * 255, 7, cv2.INPAINT_TELEA)
    labn = cv2.cvtColor(rec_fixed, cv2.COLOR_RGB2LAB).astype(np.float32)
    lift = cv2.GaussianBlur(neck.astype(np.float32), (0, 0), 12)
    labn[..., 0] = np.clip(labn[..., 0] + 10 * lift, 0, 255)
    rec_fixed = cv2.cvtColor(labn.astype(np.uint8), cv2.COLOR_LAB2RGB)
    print(f'cord/shadow inpaint: {int((cord>0).sum())} px in neck zone')

    # head: colour-match the full person (incl. neck); the beard-bottom cut version goes on top
    full_rgba = colour_match(np.dstack([rec_fixed.astype(np.float32), defringe(rec_a) * zone_rec * 255]))
    cut_alpha = head_layer()
    rgba = np.dstack([full_rgba[..., :3], cut_alpha * 255])
    r_mid = avg(r_re, r_le); b_mid = avg(b_re, b_le)
    ang_r = np.degrees(np.arctan2(r_le[1] - r_re[1], r_le[0] - r_re[0]))
    ang_b = np.degrees(np.arctan2(b_le[1] - b_re[1], b_le[0] - b_re[0]))
    sc = s * mult; sx = cfg['slim']
    M = cv2.getRotationMatrix2D((float(r_mid[0]), float(r_mid[1])), ang_r - ang_b, sc)
    Sq = np.array([[sx, 0, (1 - sx) * r_mid[0]], [0, 1, 0], [0, 0, 1]], np.float64)
    M = (np.vstack([M, [0, 0, 1]]) @ Sq)[:2]
    target = np.array([b_mid[0] + cfg['eye_dx'], b_mid[1] + cfg['eye_dy']]) * mult + np.array([0, D])
    M[:, 2] += target - (M[:, :2] @ r_mid + M[:, 2])
    head_pm, ha = warp_head(rgba, M, OW, OH)
    full_pm, fa = warp_head(full_rgba, M, OW, OH)
    rows = np.where(ha[..., 0].max(1) > .5)[0]; cols = np.where(ha[..., 0].max(0) > .5)[0]
    print(f'head placed: rows {rows.min()}-{rows.max()} cols {cols.min()}-{cols.max()}  (canvas {OW}x{OH}); '
          f'top margin {rows.min()}px, width {cols.max()-cols.min()}px, rotate {ang_r-ang_b:+.1f}deg, scale {sc:.3f}')

    # composite: backdrop -> new person (inside the old-head zone only) -> body -> beard shadow -> head
    canvas = full_pm * zone + canvas * (1 - fa * zone)
    canvas = body * ba + canvas * (1 - ba)
    sh = np.roll(ha[..., 0], 26, axis=0); sh = cv2.GaussianBlur(sh, (0, 0), 14)
    sh = np.clip(sh - ha[..., 0], 0, 1) * cfg['shadow']
    canvas = canvas * (1 - sh[..., None])
    canvas = head_pm + canvas * (1 - ha)

    out = np.clip(canvas, 0, 255).astype(np.uint8)
    img = Image.fromarray(out).filter(ImageFilter.UnsharpMask(radius=1.4, percent=38, threshold=3))
    arr = np.array(img).astype(np.float32)
    rng = np.random.default_rng(5); arr += rng.normal(0, 1.6, arr.shape)
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))

if __name__ == '__main__':
    img = compose(CFG)
    img.save('build/composite_full.png')
    W, H = img.size
    sq = img.crop((0, 0, W, W)); sq.save('headshot-updated-square.png'); sq.save('headshot-updated-square.jpg', quality=95, subsampling=0)
    pw = int(H * 0.8); x0 = (W - pw) // 2
    p45 = img.crop((x0, 0, x0 + pw, H)); p45.save('headshot-updated-4x5.png'); p45.save('headshot-updated-4x5.jpg', quality=95, subsampling=0)
    sq.resize((900, 900), Image.LANCZOS).save('build/_prev_square.png')
    print('saved', sq.size, p45.size)
