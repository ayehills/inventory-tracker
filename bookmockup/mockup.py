#!/usr/bin/env python3
"""Photoreal hardcover mockup of the 'Dope to Jokes' cover on black (Blender/Cycles via bpy).

Model
  case  : one extruded profile (back board -> rounded spine -> front board with hinge groove),
          solidified to board thickness, bevelled, UV-mapped to a single cover-wrap texture
          [back | spine | front] so the print runs continuously across the spine.
  pages : inset text block (3 mm squares) with procedural page-edge striping + a headband.
  stage : black glossy floor, black world, softbox key + fill + rim/top strip lights.

Usage: python3 mockup.py preview|final
"""
import sys, math, json, os
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import bpy, bmesh
from mathutils import Vector

ROOT = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(ROOT, '..', 'flyer', 'assets', 'fonts')
P = lambda *a: os.path.join(ROOT, *a)

# ---------------------------------------------------------------- geometry (metres)
COVER_W, COVER_H = 1122, 1402
H = 0.254                              # 10 in
W = H * COVER_W / COVER_H              # front board width keeps the cover's exact aspect
T = 0.028                              # overall thickness (boards included)
TB = 0.0028                            # board thickness
SAG = 0.0035                           # spine bulge
GROOVE = (0.0045, 0.0115, 0.0009)      # hinge groove start, end, depth (front + back)
SQUARE = 0.003                         # board overhang beyond the text block
ROT_DEG = 33.0                         # book turned so the spine faces the camera-left

def profile():
    """Outer cross-section from back fore-edge -> spine -> front fore-edge (x along width, y thickness)."""
    g0, g1, gd = GROOVE
    def board(sign, forward):
        # flat board with a cosine hinge groove; extra column after the groove keeps the face flat-shaded
        xs = [W, g1 + 0.0002, g1] + list(np.linspace(g1, g0, 12)[1:-1]) + [g0, 0.0]
        pts = []
        for x in xs:
            d = 0.0
            if g0 < x < g1:
                t = (x - g0) / (g1 - g0); d = gd * 0.5 * (1 - math.cos(2 * math.pi * t))
            pts.append((x, sign * (T / 2 - d)))
        return pts if forward else pts[::-1]
    back = board(+1, True)                               # W -> 0 at +T/2
    c = T / 2; R = (c * c + SAG * SAG) / (2 * SAG); cx = R - SAG
    a0 = math.asin(c / R)
    spine = [(cx - R * math.cos(a), R * math.sin(a)) for a in np.linspace(a0, -a0, 41)]
    front = board(-1, False)                             # 0 -> W at -T/2
    pts = back + spine[1:-1] + front
    pts = [(x - W / 2, y) for x, y in pts]               # centre the book on x
    seg = [math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    s = np.concatenate([[0], np.cumsum(seg)])
    nb, ns = len(back), len(spine) - 2
    L_back, L_spine, L_front = s[nb - 1], s[nb + ns] - s[nb - 1], s[-1] - s[nb + ns]
    return pts, s, dict(back=L_back, spine=L_spine, front=L_front, total=s[-1])

# ---------------------------------------------------------------- textures
def gold_texture(size):
    src = np.array(Image.open(P('assets', 'cover_src.jpg')).convert('RGB'))
    x, y, w, h = 792, 96, 60, 120                        # clean foil patch measured on the cover
    tile = Image.fromarray(src[y:y + h, x:x + w]).resize((w * 2, h * 2), Image.LANCZOS)
    tw, th = tile.size; out = Image.new('RGB', size); rng = np.random.default_rng(11)
    for yy in range(0, size[1], th):
        for xx in range(0, size[0], tw):
            t = tile
            if rng.random() > .5: t = t.transpose(Image.FLIP_LEFT_RIGHT)
            if rng.random() > .5: t = t.transpose(Image.FLIP_TOP_BOTTOM)
            out.paste(t, (xx, yy))
    return out

def spine_texture(ws, hp):
    """Spine art, designed horizontally (x = top->bottom of the book) then turned clockwise so it reads
    top-to-bottom with letter tops toward the front cover (US convention)."""
    bg = np.full((ws, hp, 3), (9, 8, 7), np.float32)
    bg += np.random.default_rng(3).normal(0, 2.2, bg.shape)
    canvas = Image.fromarray(np.clip(bg, 0, 255).astype(np.uint8))
    gold = gold_texture((hp, ws))
    gmask = Image.new('L', (hp, ws), 0); wmask = Image.new('L', (hp, ws), 0)
    dg, dw = ImageDraw.Draw(gmask), ImageDraw.Draw(wmask)
    anton = lambda s: ImageFont.truetype(os.path.join(FONTS, 'Anton-Regular.ttf'), s)
    def oswald(s):
        f = ImageFont.truetype(os.path.join(FONTS, 'Oswald.ttf'), s)
        try: f.set_variation_by_axes([600])
        except Exception: pass
        return f
    # size the title so its cap height is ~50% of the spine width
    ft = anton(100); cap = ft.getbbox('D')[3] - ft.getbbox('D')[1]
    ts = int(100 * 0.50 * ws / cap); f_big, f_to = anton(ts), anton(int(ts * 0.62))
    fa = oswald(int(ts * 0.42))
    parts = [('DOPE', f_big, 'g'), ('TO', f_to, 'w'), ('JOKES', f_big, 'g')]
    gap = int(ts * 0.22)
    def width(t, f, track=0): return f.getlength(t) + track * (len(t) - 1)
    title_w = sum(width(t, f) for t, f, _ in parts) + gap * 2
    author, track = 'LARRY DOGG GORDON', int(ts * 0.06)
    auth_w = width(author, fa, track)
    def draw_centered(d, x, text, f, track=0):
        bb = f.getbbox('H'); y = (ws - (bb[3] + bb[1])) / 2
        for ch in text:
            d.text((x, y), ch, font=f, fill=255); x += f.getlength(ch) + track
        return x
    x = hp * 0.085
    for t, f, col in parts:
        x = draw_centered(dg if col == 'g' else dw, x, t, f) + gap
    xa = hp * 0.915 - auth_w
    draw_centered(dw, xa, author, fa, track)
    # gold rules + stars near both ends, echoing the cover
    for x0 in (hp * 0.035, hp * 0.965):
        for dx in (-ws * 0.05, ws * 0.05):
            dg.rectangle([x0 + dx - 2, ws * 0.12, x0 + dx + 2, ws * 0.88], fill=255)
    def star(d, cx, cy, r):
        pts = []
        for k in range(10):
            a = -math.pi / 2 + k * math.pi / 5; rr = r if k % 2 == 0 else r * 0.42
            pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
        d.polygon(pts, fill=255)
    star(dg, hp * 0.062, ws / 2, ws * 0.13); star(dg, hp * 0.938, ws / 2, ws * 0.13)
    gm = gmask.filter(ImageFilter.GaussianBlur(0.6)); wm = wmask.filter(ImageFilter.GaussianBlur(0.6))
    canvas = Image.composite(gold, canvas, gm)
    canvas = Image.composite(Image.new('RGB', canvas.size, (236, 230, 220)), canvas, wm)
    print(f'spine art: title {title_w:.0f}px + author {auth_w:.0f}px on {hp}px spine (ws={ws})')
    return canvas.rotate(-90, expand=True)              # clockwise: left (book top) -> top

def build_textures(L):
    hp = COVER_H * 2
    ppm = (COVER_W * 2) / L['front']
    wb, ws, wf = round(L['back'] * ppm), round(L['spine'] * ppm), COVER_W * 2
    front = Image.open(P('assets', 'cover_src.jpg')).convert('RGB').resize((wf, hp), Image.LANCZOS)
    front = front.filter(ImageFilter.UnsharpMask(1.2, 45, 2))
    bg = np.full((hp, wb, 3), (9, 8, 7), np.float32) + np.random.default_rng(5).normal(0, 2.2, (hp, wb, 3))
    back = Image.fromarray(np.clip(bg, 0, 255).astype(np.uint8))
    spine = spine_texture(ws, hp)
    wrap = Image.new('RGB', (wb + ws + wf, hp)); wrap.paste(back, (0, 0)); wrap.paste(spine, (wb, 0)); wrap.paste(front, (wb + ws, 0))
    wrap.save(P('build', 'wrap.png'))
    a = np.array(wrap).astype(np.int16)
    gm = (a[..., 0] > 120) & (a[..., 1] > 85) & (a[..., 2] < 120) & (a[..., 0] - a[..., 2] > 70)
    Image.fromarray((gm * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.0)).save(P('build', 'goldmask.png'))
    wrap.crop((wb - 40, 0, wb + ws + 260, hp)).resize(((ws + 300) // 2, hp // 2)).save(P('build', '_spine_check.png'))
    print(f'wrap {wrap.size}  back {wb}  spine {ws}  front {wf}')

# ---------------------------------------------------------------- blender helpers
def new_material(name):
    m = bpy.data.materials.new(name)
    if m.node_tree is None:
        m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes): nt.nodes.remove(n)
    out = nt.nodes.new('ShaderNodeOutputMaterial'); bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    return m, nt, bsdf

def link_obj(obj):
    bpy.context.scene.collection.objects.link(obj); return obj

def finish_mesh(obj, sharp_deg=20.0):
    """Apply modifiers through the depsgraph, then smooth with sharp edges by angle."""
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(obj.evaluated_get(dg))
    mats = [s.material for s in obj.material_slots]
    obj.modifiers.clear(); obj.data = me
    me.materials.clear()
    for m in mats: me.materials.append(m)
    me.shade_smooth(); me.set_sharp_from_angle(angle=math.radians(sharp_deg))

def look_at(obj, target):
    d = Vector(target) - obj.location
    obj.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()

# ---------------------------------------------------------------- materials
def mat_cover():
    m, nt, bsdf = new_material('CoverPrint'); N, Lk = nt.nodes, nt.links
    tex = N.new('ShaderNodeTexImage'); tex.image = bpy.data.images.load(P('build', 'wrap.png')); tex.interpolation = 'Cubic'
    Lk.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
    mk = N.new('ShaderNodeTexImage'); mk.image = bpy.data.images.load(P('build', 'goldmask.png'))
    mk.image.colorspace_settings.name = 'Non-Color'
    # soft-touch matte laminate overall (keeps the blacks deep), spot gloss on the gold type
    def by_mask(lo, hi, sock):
        mr = N.new('ShaderNodeMapRange'); mr.inputs['To Min'].default_value = lo; mr.inputs['To Max'].default_value = hi
        Lk.new(mk.outputs['Color'], mr.inputs['Value']); Lk.new(mr.outputs['Result'], bsdf.inputs[sock])
    by_mask(0.74, 0.42, 'Roughness')
    by_mask(0.10, 0.30, 'Specular IOR Level')
    by_mask(0.00, 0.12, 'Coat Weight')
    bsdf.inputs['Coat Roughness'].default_value = 0.18
    # micro paper / laminate grain
    tc = N.new('ShaderNodeTexCoord'); nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 2600.0
    nz.inputs['Detail'].default_value = 4.0
    Lk.new(tc.outputs['Object'], nz.inputs['Vector'])
    bump = N.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = 0.06; bump.inputs['Distance'].default_value = 0.0002
    Lk.new(nz.outputs['Fac'], bump.inputs['Height']); Lk.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    return m

def mat_flat(name, rgb, rough):
    m, nt, bsdf = new_material(name)
    bsdf.inputs['Base Color'].default_value = (*rgb, 1); bsdf.inputs['Roughness'].default_value = rough
    return m

def mat_pages():
    m, nt, bsdf = new_material('Pages'); N, Lk = nt.nodes, nt.links
    tc = N.new('ShaderNodeTexCoord')
    wave = N.new('ShaderNodeTexWave'); wave.wave_type = 'BANDS'; wave.bands_direction = 'Y'
    wave.inputs['Scale'].default_value = 1250.0; wave.inputs['Distortion'].default_value = 3.0
    wave.inputs['Detail'].default_value = 2.0
    Lk.new(tc.outputs['Object'], wave.inputs['Vector'])
    ramp = N.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = (0.70, 0.67, 0.62, 1); ramp.color_ramp.elements[1].color = (0.90, 0.88, 0.84, 1)
    Lk.new(wave.outputs['Fac'], ramp.inputs['Fac']); Lk.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 0.85
    bump = N.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = 0.25; bump.inputs['Distance'].default_value = 0.0001
    Lk.new(wave.outputs['Fac'], bump.inputs['Height']); Lk.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    return m

def mat_headband():
    m, nt, bsdf = new_material('Headband'); N, Lk = nt.nodes, nt.links
    tc = N.new('ShaderNodeTexCoord'); wave = N.new('ShaderNodeTexWave'); wave.bands_direction = 'Y'
    wave.inputs['Scale'].default_value = 180.0
    Lk.new(tc.outputs['Object'], wave.inputs['Vector'])
    ramp = N.new('ShaderNodeValToRGB'); ramp.color_ramp.interpolation = 'CONSTANT'
    ramp.color_ramp.elements[0].color = (0.02, 0.018, 0.015, 1); ramp.color_ramp.elements[1].position = 0.5
    ramp.color_ramp.elements[1].color = (0.62, 0.42, 0.12, 1)
    Lk.new(wave.outputs['Fac'], ramp.inputs['Fac']); Lk.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 0.45; bsdf.inputs['Sheen Weight'].default_value = 0.6
    return m

# ---------------------------------------------------------------- scene
def build_scene(pts, s, L):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    book = bpy.data.objects.new('Book', None); link_obj(book)

    # case
    bm = bmesh.new(); uvl = bm.loops.layers.uv.new('UVMap')
    vb = [bm.verts.new((x, y, 0.0)) for x, y in pts]; vt = [bm.verts.new((x, y, H)) for x, y in pts]
    u = s / s[-1]
    for i in range(len(pts) - 1):
        f = bm.faces.new((vb[i], vb[i + 1], vt[i + 1], vt[i]))
        for lp, uv in zip(f.loops, [(u[i], 0), (u[i + 1], 0), (u[i + 1], 1), (u[i], 1)]): lp[uvl].uv = uv
    me = bpy.data.meshes.new('case'); bm.to_mesh(me); bm.free()
    case = link_obj(bpy.data.objects.new('Case', me))
    for m in (mat_cover(), mat_flat('Endpaper', (0.012, 0.011, 0.010), 0.6), mat_flat('BoardEdge', (0.010, 0.009, 0.008), 0.45)):
        me.materials.append(m)
    sol = case.modifiers.new('solid', 'SOLIDIFY'); sol.thickness = TB; sol.offset = -1.0
    sol.use_even_offset = True; sol.use_rim = True; sol.material_offset = 1; sol.material_offset_rim = 2
    bev = case.modifiers.new('bevel', 'BEVEL'); bev.width = 0.00045; bev.segments = 4
    bev.limit_method = 'ANGLE'; bev.angle_limit = math.radians(30)
    finish_mesh(case)

    # text block
    x0, x1 = -W / 2 + 0.0025, W / 2 - SQUARE
    y0 = T / 2 - TB - 0.0002
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x = x0 + (v.co.x + .5) * (x1 - x0); v.co.y = v.co.y * 2 * y0; v.co.z = SQUARE + (v.co.z + .5) * (H - 2 * SQUARE)
    me = bpy.data.meshes.new('pages'); bm.to_mesh(me); bm.free()
    pages = link_obj(bpy.data.objects.new('Pages', me)); me.materials.append(mat_pages())
    bev = pages.modifiers.new('bevel', 'BEVEL'); bev.width = 0.0007; bev.segments = 3
    finish_mesh(pages, 30)

    # headbands (top + bottom)
    hb_mat = mat_headband(); book_parts = []
    for zc in (H - SQUARE + 0.0007, SQUARE - 0.0007):
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, segments=20, radius1=0.0011, radius2=0.0011, depth=2 * y0 - 0.001)
        bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=__import__('mathutils').Matrix.Rotation(math.radians(90), 3, 'X'))
        bmesh.ops.translate(bm, verts=bm.verts, vec=(x0 + 0.0012, 0, zc))
        me = bpy.data.meshes.new('hb'); bm.to_mesh(me); bm.free()
        hb = link_obj(bpy.data.objects.new('Headband', me)); me.materials.append(hb_mat); me.shade_smooth()
        hb.parent = book; book_parts.append(hb)
    for o in (case, pages): o.parent = book
    book_parts += [case, pages]
    only_book = bpy.data.collections.new('BookOnly')        # light-linking receivers: rims/fill skip the floor
    for o in book_parts: only_book.objects.link(o)
    book.rotation_euler = (0, 0, math.radians(ROT_DEG))

    # floor
    bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=4.0)
    me = bpy.data.meshes.new('floor'); bm.to_mesh(me); bm.free()
    floor = link_obj(bpy.data.objects.new('Floor', me))
    fm, nt, bsdf = new_material('Floor')
    bsdf.inputs['Base Color'].default_value = (0.004, 0.004, 0.004, 1); bsdf.inputs['Roughness'].default_value = 0.16
    bsdf.inputs['Specular IOR Level'].default_value = 0.45
    me.materials.append(fm)

    # world: black
    wd = bpy.data.worlds.new('World'); sc.world = wd
    if wd.node_tree is None: wd.use_nodes = True
    bg = wd.node_tree.nodes.get('Background')
    if bg: bg.inputs['Color'].default_value = (0, 0, 0, 1); bg.inputs['Strength'].default_value = 0.0

    # camera
    target = (0.0, 0.0, 0.112)
    cd = bpy.data.cameras.new('Cam'); cd.lens = 96; cd.sensor_width = 36; cd.sensor_fit = 'AUTO'
    cam = link_obj(bpy.data.objects.new('Cam', cd)); cam.location = (0.02, -1.07, 0.35); look_at(cam, target)
    sc.camera = cam

    # lights
    def area(name, loc, size, energy, aim, color=(1, 1, 1), book_only=False):
        ld = bpy.data.lights.new(name, 'AREA'); ld.shape = 'RECTANGLE'; ld.size, ld.size_y = size
        ld.energy = energy; ld.color = color
        o = link_obj(bpy.data.objects.new(name, ld)); o.location = loc; look_at(o, aim)
        if book_only: o.light_linking.receiver_collection = only_book
        return o
    # key: front-left, high; lights cover (~53 deg incidence) and spine evenly, far from the cover's mirror angle
    area('Key',   (-0.30, -1.25, 0.78), (0.9, 0.9), 52, (0.0, 0.0, 0.13), (1.0, 0.975, 0.94))
    # small fill high front-right, kept ~45 deg off the mirror angle so the laminate doesn't wash out
    area('Fill',  ( 0.95, -1.10, 0.95), (0.5, 0.5),  12, (0.0, 0.0, 0.13), (0.96, 0.98, 1.0), True)
    area('Rim',   ( 0.55,  0.60, 0.45), (0.12, 1.1), 60, (0.0, 0.0, 0.13), (1.0, 0.92, 0.80), True)
    area('RimL',  (-0.65,  0.45, 0.40), (0.12, 1.1), 30, (-0.05, 0.0, 0.13), (1.0, 0.95, 0.88), True)
    area('Top',   ( 0.00,  0.25, 0.75), (0.7, 0.25), 40, (0.0, 0.0, 0.254), (1, 1, 1), True)
    # spine light: square to the rotated spine, grazes the cover (no effect there), book-only
    area('Spine', (-0.84, -0.55, 0.35), (0.45, 0.8), 16, (-0.088, -0.057, 0.13), (1.0, 0.97, 0.93), True)

def render(quality):
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'
    if quality == 'final':
        sc.render.resolution_x, sc.render.resolution_y = 2400, 3000; sc.cycles.samples = 160
        sc.cycles.adaptive_threshold = 0.008
    else:
        sc.render.resolution_x, sc.render.resolution_y = 600, 750; sc.cycles.samples = 48
        sc.cycles.adaptive_threshold = 0.03
    sc.render.resolution_percentage = 100; sc.cycles.use_adaptive_sampling = True
    sc.cycles.use_denoising = True
    try: sc.cycles.denoiser = 'OPENIMAGEDENOISE'
    except Exception: pass
    sc.cycles.max_bounces = 8; sc.cycles.glossy_bounces = 4
    vts = [i.identifier for i in sc.view_settings.bl_rna.properties['view_transform'].enum_items]
    sc.view_settings.view_transform = 'Khronos PBR Neutral' if 'Khronos PBR Neutral' in vts else 'Standard'
    sc.view_settings.look = 'None'; sc.view_settings.exposure = 0.0
    print('view transform:', sc.view_settings.view_transform)
    # render unclipped scene-linear HDR; tone-mapped below so bright gold keeps its hue
    sc.render.image_settings.file_format = 'OPEN_EXR'; sc.render.image_settings.color_depth = '32'
    sc.render.filepath = P('build', f'render_{quality}.exr')
    bpy.ops.render.render(write_still=True)
    print('rendered', sc.render.filepath)
    tonemap(sc.render.filepath, P('build', f'render_{quality}.png'))

def tonemap(exr_path, png_path, ev=0.0, knee=0.80):
    """Hue-preserving highlight roll-off: compress the max channel with a soft shoulder and scale
    R,G,B by the same factor, so over-bright gold stays gold instead of drifting to lemon yellow."""
    img = bpy.data.images.load(exr_path); w, h = img.size
    px = np.empty(w * h * 4, np.float32); img.pixels.foreach_get(px)
    rgb = px.reshape(h, w, 4)[::-1, :, :3] * (2.0 ** ev)
    m = rgb.max(axis=2, keepdims=True)
    over = np.maximum(m - knee, 0)
    m2 = np.where(m > knee, knee + (1 - knee) * (1 - np.exp(-over / (1 - knee))), m)
    rgb = rgb * np.where(m > 1e-6, m2 / np.maximum(m, 1e-6), 1.0)
    rgb = np.clip(rgb, 0, 1)
    srgb = np.where(rgb <= 0.0031308, 12.92 * rgb, 1.055 * np.power(rgb, 1 / 2.4) - 0.055)
    Image.fromarray(np.clip(srgb * 255 + 0.5, 0, 255).astype(np.uint8)).save(png_path)
    print('tone-mapped ->', png_path, f'(max linear {float(m.max()):.2f})')

if __name__ == '__main__':
    q = sys.argv[1] if len(sys.argv) > 1 else 'preview'
    pts, s, L = profile()
    print('book W x H x T (mm): %.1f x %.1f x %.1f   arcs back %.1f spine %.1f front %.1f mm' %
          (W * 1e3, H * 1e3, T * 1e3, L['back'] * 1e3, L['spine'] * 1e3, L['front'] * 1e3))
    build_textures(L)
    build_scene(pts, s, L)
    render(q)
