#!/usr/bin/env python3
"""Fit the Larry Dogg flyer to 4x6 and open space right of the title for a headshot.

Pipeline:
  1. mask the title block (LARRY DOGG metallic letters + their dark extrusion, and the
     pink 'AND FRIENDS' script + its shadow)
  2. inpaint a background plate behind the letters
  3. re-composite the letters horizontally condensed (sx) and shifted left (dx), anchored
     at the title's left edge so the left side does not move
  4. extend the canvas to 2:3 by stretching the outer edge bands (no crop, no squash)
  5. upscale to 1200x1800 (4x6 @ 300dpi), light sharpen, export PNG + PDF
"""
import sys, numpy as np, cv2
from PIL import Image, ImageFilter

SRC = 'assets/flyer_src.png'
img = np.array(Image.open(SRC).convert('RGB'))
H, W = img.shape[:2]

def shift_mask(m, dx, dy):
    out = np.zeros_like(m)
    ys, ye = max(0, dy), H + min(0, dy)
    xs, xe = max(0, dx), W + min(0, dx)
    out[ys:ye, xs:xe] = m[ys - dy:ye - dy, xs - dx:xe - dx]
    return out

def title_mask():
    hs = cv2.cvtColor(img, cv2.COLOR_RGB2HSV).astype(np.int16)
    h, s, v = hs[..., 0], hs[..., 1], hs[..., 2]
    gold = ((h >= 8) & (h <= 35) & (s >= 60) & (v >= 120)) | ((s < 70) & (v >= 185))
    band = np.zeros((H, W), bool); band[446:710, 88:606] = True        # LARRY DOGG rows, mic excluded
    gold &= band
    pink = (h >= 150) & (h <= 175) & (s >= 150) & (v >= 140)
    band2 = np.zeros((H, W), bool); band2[690:790, 150:600] = True     # AND FRIENDS
    pink &= band2
    core = gold | pink
    # drop small speckles
    n, lab, stats, _ = cv2.connectedComponentsWithStats(core.astype(np.uint8), 8)
    keep = np.zeros(n, bool); keep[1:] = stats[1:, cv2.CC_STAT_AREA] >= 90
    core = keep[lab]
    # dark extrusion / drop shadow hugs the faces (mostly down-right): grow into dark pixels
    dark = v < 95
    grow = np.zeros_like(core)
    for dx in range(-6, 15):
        for dy in range(-3, 15):
            grow |= shift_mask(core, dx, dy)
    shadow = grow & dark
    full = core | shadow
    full = cv2.morphologyEx(full.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8)).astype(bool)
    full = cv2.dilate(full.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)   # anti-aliased rim
    return full

def make_plate(m):
    """Backdrop behind the letters: quarter-res inpaint (smooth glow, no streaks) + film grain,
    feathered into the original so there is no seam."""
    hole = cv2.dilate(m.astype(np.uint8), np.ones((7, 7), np.uint8)).astype(bool)
    bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    s = 0.25
    small = cv2.resize(bgr, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    hs_ = cv2.dilate(cv2.resize(hole.astype(np.uint8) * 255, None, fx=s, fy=s,
                                interpolation=cv2.INTER_NEAREST), np.ones((3, 3), np.uint8))
    coarse = cv2.inpaint(small, hs_, 7, cv2.INPAINT_TELEA)
    coarse = cv2.GaussianBlur(cv2.resize(coarse, (W, H), interpolation=cv2.INTER_CUBIC), (0, 0), 3.0).astype(np.float32)
    rng = np.random.default_rng(7)
    grain = cv2.GaussianBlur(rng.normal(0, 4.5, (H, W)).astype(np.float32), (0, 0), 0.7)[..., None]
    filled = np.clip(coarse + grain, 0, 255)
    f = cv2.GaussianBlur(hole.astype(np.float32), (0, 0), 1.5)[..., None]
    plate = bgr.astype(np.float32) * (1 - f) + filled * f
    return cv2.cvtColor(plate.astype(np.uint8), cv2.COLOR_BGR2RGB)

def build(sx, dx, name, guide=None):
    m = title_mask()
    ys, xs = np.where(m); x0 = int(xs.min()); print(f'[{name}] title x {x0}-{xs.max()} y {ys.min()}-{ys.max()}')
    # background plate
    plate = make_plate(m)
    # letters layer with soft alpha
    alpha = cv2.GaussianBlur(m.astype(np.float32), (0, 0), 0.9)
    letters = np.dstack([img.astype(np.float32), alpha[..., None] * 255])
    M = np.float32([[sx, 0, x0 - sx * x0 + dx], [0, 1, 0]])          # condense about x0, then shift
    warped = cv2.warpAffine(letters, M, (W, H), flags=cv2.INTER_LANCZOS4, borderValue=(0, 0, 0, 0))
    a = np.clip(warped[..., 3:4] / 255.0, 0, 1)
    out = (warped[..., :3] * a + plate.astype(np.float32) * (1 - a)).astype(np.uint8)
    ys2, xs2 = np.where(a[..., 0] > 0.5); print(f'[{name}] new title right edge x={xs2.max()}')

    # ---- extend to 2:3 (4x6) by stretching the outer edge bands
    TW = int(round(H * 2 / 3)); pad = TW - W; pl = pad // 2; pr = pad - pl
    band = 30
    left = cv2.resize(out[:, :band], (band + pl, H), interpolation=cv2.INTER_CUBIC)
    right = cv2.resize(out[:, W - band:], (band + pr, H), interpolation=cv2.INTER_CUBIC)
    left = cv2.GaussianBlur(left, (0, 0), 1.2); right = cv2.GaussianBlur(right, (0, 0), 1.2)
    ext = np.concatenate([left, out[:, band:W - band], right], axis=1)
    # gentle edge darkening so the new margins read as the venue's dark edges
    xx = np.arange(TW, dtype=np.float32)
    vig = 1 - 0.28 * np.clip(1 - np.minimum(xx, TW - 1 - xx) / 110.0, 0, 1) ** 2
    ext = (ext * vig[None, :, None]).astype(np.uint8)

    # ---- upscale to 4x6 @ 300dpi
    final = Image.fromarray(ext).resize((1200, 1800), Image.LANCZOS).filter(ImageFilter.UnsharpMask(1.1, 55, 3))
    final.save(f'larry-dogg-4x6-{name}.png')
    final.save(f'larry-dogg-4x6-{name}.pdf', 'PDF', resolution=300.0)
    print(f'[{name}] exported 1200x1800')
    # guide preview (not a deliverable): dashed circle where a headshot bubble now fits
    if guide:
        g = np.array(final.copy()); k = 1200 / TW
        cx, cy, r = int((guide[0] + pl) * k), int(guide[1] * k), int(guide[2] * k)
        for t in range(0, 360, 12):
            a0, a1 = np.deg2rad(t), np.deg2rad(t + 6)
            p0 = (int(cx + r * np.cos(a0)), int(cy + r * np.sin(a0))); p1 = (int(cx + r * np.cos(a1)), int(cy + r * np.sin(a1)))
            cv2.line(g, p0, p1, (255, 255, 0), 4)
        Image.fromarray(g).resize((600, 900), Image.LANCZOS).save(f'build/_guide_{name}.png')
    return out

if __name__ == '__main__':
    build(0.97, -8,  'subtle')
    build(0.88, -30, 'open', guide=(604, 700, 110))
