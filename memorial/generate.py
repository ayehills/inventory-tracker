#!/usr/bin/env python3
"""Faithful recreation of the burial-announcement flyer, re-themed green + gold.
Layout coordinates mirror the original 720x1080 flyer scaled 1.5x -> 1080x1620.
Variants:  deep = deep-green card + teal-graded sky (green-forward)
           soft = cream card, green only as accent (golden sky kept airy)"""
import base64, os, math

ROOT = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(ROOT, "assets", "fonts")
AST = os.path.join(ROOT, "assets")

def b64(p):
    with open(p, "rb") as f:
        return base64.b64encode(f.read()).decode()

def ff(fam, fn, wt="400", st="normal"):
    return (f"@font-face{{font-family:'{fam}';src:url(data:font/ttf;base64,{b64(os.path.join(FONTS,fn))}) "
            f"format('truetype');font-weight:{wt};font-style:{st};font-display:block;}}")

FACES = "".join([
    ff("Great Vibes", "GreatVibes-Regular.ttf"),
    ff("Playfair Display", "PlayfairDisplay.ttf", "400 900"),
    ff("Gelasio", "Gelasio.ttf", "400 700"),
    ff("Gelasio", "Gelasio-Italic.ttf", "400 700", "italic"),
])

IMG = {n: b64(os.path.join(AST, n + ".png")) for n in
       ["portrait", "sky", "bouquet", "bouquet2", "cross_scene", "dove1"]}
def img(n): return f"data:image/png;base64,{IMG[n]}"

GOLD_GRAD = "linear-gradient(180deg,#fbe9b0 0%,#e9c86a 40%,#c39a35 72%,#f3dc92 100%)"

# ------------------------------------------------------------------ SVG bits
GOLD_DEFS = """<defs>
  <linearGradient id="gv" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#fbeab2"/><stop offset=".45" stop-color="#e4c063"/><stop offset="1" stop-color="#9c741f"/></linearGradient>
  <linearGradient id="gh" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="#c79b38"/><stop offset=".3" stop-color="#fbe8ad"/><stop offset=".55" stop-color="#e2bd5f"/><stop offset=".8" stop-color="#fbe8ad"/><stop offset="1" stop-color="#c79b38"/></linearGradient>
  <linearGradient id="grn" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#1f6a48"/><stop offset=".5" stop-color="#0f4630"/><stop offset="1" stop-color="#0a3122"/></linearGradient>
</defs>"""

def wreath_svg():
    cx, cy, R = 100, 106, 74
    def p(a): t = math.radians(a); return (cx + R*math.cos(t), cy + R*math.sin(t))
    leaves = []
    for a in range(98, 226, 11):
        x, y = p(a); tang = a + 90
        for off in (-34, 34):
            leaves.append(f'<path d="M0,0 Q13,-7 27,0 Q13,7 0,0" fill="url(#gv)" stroke="#7d5c16" stroke-width=".7" '
                          f'transform="translate({x:.1f},{y:.1f}) rotate({tang+off})"/>')
    x0, y0 = p(96); x1, y1 = p(228)
    stem = f'<path d="M{x0:.1f},{y0:.1f} A{R},{R} 0 0 1 {x1:.1f},{y1:.1f}" fill="none" stroke="#b8902e" stroke-width="3.2"/>'
    branch = stem + "".join(leaves)
    return (f'<svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">{GOLD_DEFS}'
            f'<g>{branch}</g><g transform="translate(200,0) scale(-1,1)">{branch}</g></svg>')

def ribbon_svg(fill_id, stroke, tail):
    """Folded ribbon banner. fill_id: gradient id for band; stroke: outline; tail: tail fill."""
    return (f'<svg viewBox="0 0 1000 110" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="none">{GOLD_DEFS}'
            f'<polygon points="2,24 78,24 78,98 2,98 26,61" fill="{tail}" stroke="{stroke}" stroke-width="2.5"/>'
            f'<polygon points="998,24 922,24 922,98 998,98 974,61" fill="{tail}" stroke="{stroke}" stroke-width="2.5"/>'
            f'<polygon points="62,98 78,110 78,98" fill="#000" opacity=".55"/>'
            f'<polygon points="938,98 922,110 922,98" fill="#000" opacity=".55"/>'
            f'<rect x="62" y="6" width="876" height="92" rx="4" fill="url(#{fill_id})" stroke="{stroke}" stroke-width="3"/>'
            f'<rect x="70" y="14" width="860" height="76" rx="2" fill="none" stroke="{stroke}" stroke-width="1.2" opacity=".75"/>'
            f'</svg>')

FLOURISH = """<svg viewBox="0 0 300 30" xmlns="http://www.w3.org/2000/svg">""" + GOLD_DEFS + """
  <path d="M8,15 C60,15 90,6 130,15" fill="none" stroke="url(#gh)" stroke-width="2.4" stroke-linecap="round"/>
  <path d="M292,15 C240,15 210,6 170,15" fill="none" stroke="url(#gh)" stroke-width="2.4" stroke-linecap="round"/>
  <path d="M118,15 c10,-9 18,-9 26,0 c-8,9 -16,9 -26,0z" fill="url(#gv)" stroke="#8a6a1c" stroke-width=".6"/>
  <path d="M156,15 c10,-9 18,-9 26,0 c-8,9 -16,9 -26,0z" fill="url(#gv)" stroke="#8a6a1c" stroke-width=".6"/>
  <path d="M143,15 l7,-8 l7,8 l-7,8z" fill="url(#gv)" stroke="#8a6a1c" stroke-width=".6"/>
  <path d="M8,15 c-4,-6 2,-12 8,-8 c4,3 2,8 -4,8" fill="none" stroke="url(#gh)" stroke-width="1.6"/>
  <path d="M292,15 c4,-6 -2,-12 -8,-8 c-4,3 -2,8 4,8" fill="none" stroke="url(#gh)" stroke-width="1.6"/>
</svg>"""

CORNER = """<svg viewBox="0 0 60 60" xmlns="http://www.w3.org/2000/svg">""" + GOLD_DEFS + """
  <path d="M2,58 L2,14 Q2,2 14,2 L58,2" fill="none" stroke="url(#gv)" stroke-width="3"/>
  <path d="M10,50 L10,20 Q10,10 20,10 L50,10" fill="none" stroke="url(#gv)" stroke-width="1.3" opacity=".8"/>
  <path d="M6,6 c8,0 10,8 4,12 c-6,-4 -4,-12 -4,-12z" fill="url(#gv)"/>
</svg>"""

SMALL_FLOURISH = """<svg viewBox="0 0 90 24" xmlns="http://www.w3.org/2000/svg">
  <path d="M4,12 C24,12 32,4 46,12 C60,20 68,12 86,12" fill="none" stroke="#0d3d2a" stroke-width="2" stroke-linecap="round"/>
  <path d="M40,12 l6,-6 l6,6 l-6,6z" fill="#0d3d2a"/>
</svg>"""

# ------------------------------------------------------------------ themes
THEMES = {
  "soft": dict(
     card="linear-gradient(180deg,#f7f0dc 0%,#f1e7cf 55%,#ebdfc2 100%)",
     card_grain=.10, skytint="none",
     head="#0d4a33", body="#1d1d1d", divider="rgba(13,74,51,.75)",
     bullet="radial-gradient(circle at 40% 35%,#2d8a5f,#0d4a33 70%)", bullet_ring="#d9b755",
     chip_txt="#0d4a33", foot_txt="#0b3a28",
     ribbon_txt="#fdf6e1", seal_num="#0d4a33", seal_yrs="#0d4a33"),
  "deep": dict(
     card="linear-gradient(180deg,#134734 0%,#0e3a29 40%,#0b2f21 75%,#092619 100%)",
     card_grain=.16, skytint="linear-gradient(180deg,rgba(9,66,50,.16),rgba(9,66,50,.36))",
     head="#f3d27a", body="#f1e8d2", divider="rgba(233,196,106,.55)",
     bullet="radial-gradient(circle at 40% 35%,#fbe9b0,#c39a35 70%)", bullet_ring="#0d4a33",
     chip_txt="#0d4a33", foot_txt="#0b3a28",
     ribbon_txt="#fdf6e1", seal_num="#0d4a33", seal_yrs="#0d4a33"),
}

def build(key):
    t = THEMES[key]
    sky_tint = "" if t["skytint"] == "none" else f'<div class="skytint" style="background:{t["skytint"]}"></div>'
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
{FACES}
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{background:#08110c}}
#f{{position:relative;width:1080px;height:1620px;overflow:hidden;background:#cfd9e0;font-family:'Gelasio',serif}}
.abs{{position:absolute}}

/* ---------- backgrounds ---------- */
.sky{{left:-18px;top:-10px;width:1116px;z-index:1}}
.skytint{{position:absolute;left:0;top:0;width:1080px;height:920px;z-index:2;mix-blend-mode:multiply}}
.card{{left:0;right:0;top:806px;bottom:0;z-index:3;background:{t['card']};
  -webkit-mask-image:linear-gradient(180deg,transparent 0,#000 70px);mask-image:linear-gradient(180deg,transparent 0,#000 70px)}}
.cardfade{{display:none}}
.grain{{position:absolute;inset:0;z-index:3;opacity:{t['card_grain']};mix-blend-mode:multiply;pointer-events:none}}
.sunglow{{right:-60px;top:980px;width:560px;height:560px;z-index:4;border-radius:50%;
  background:radial-gradient(circle,rgba(255,196,110,.55) 0%,rgba(255,170,80,.28) 32%,rgba(255,160,70,0) 66%)}}

/* frame */
.frame{{inset:18px;z-index:12;border:2.5px solid #d9b755;border-radius:3px;pointer-events:none;
  box-shadow:0 0 0 1px rgba(120,86,20,.35)}}
.frame:before{{content:'';position:absolute;inset:6px;border:1px solid rgba(217,183,85,.75)}}
.corner{{width:64px;height:64px;z-index:13;pointer-events:none}}

/* ---------- photo & florals ---------- */
.portrait{{left:-4px;top:58px;width:708px;z-index:5;
  filter:drop-shadow(0 0 22px rgba(255,244,214,.55)) drop-shadow(0 14px 22px rgba(0,0,0,.28));
  -webkit-mask-image:linear-gradient(180deg,#000 68%,rgba(0,0,0,.6) 84%,transparent 100%),linear-gradient(90deg,#000 86%,transparent 100%);
  -webkit-mask-composite:source-in;mask-composite:intersect;
  mask-image:linear-gradient(180deg,#000 68%,rgba(0,0,0,.6) 84%,transparent 100%),linear-gradient(90deg,#000 86%,transparent 100%)}}
.bouquet{{left:-14px;top:596px;width:392px;z-index:7;filter:drop-shadow(0 8px 14px rgba(0,0,0,.35))}}
.bouquet2{{left:-8px;bottom:18px;width:118px;z-index:9;filter:drop-shadow(0 6px 10px rgba(0,0,0,.35))}}
.dove{{right:48px;top:26px;width:92px;z-index:14;filter:drop-shadow(0 6px 10px rgba(0,0,0,.3))}}
.scene{{right:18px;top:956px;width:316px;z-index:6;opacity:.97}}

/* ---------- top-right text ---------- */
.forever{{left:580px;top:70px;width:480px;text-align:center;z-index:9;font-family:'Great Vibes';font-size:112px;line-height:1;
  color:#07301f;text-shadow:0 0 14px rgba(255,248,224,.85),0 0 4px rgba(255,248,224,.6),0 4px 8px rgba(0,0,0,.4)}}
.inhearts{{left:580px;top:188px;width:480px;text-align:center;z-index:9;font-family:'Gelasio';font-weight:700;font-size:44px;letter-spacing:2.5px;
  color:#07301f;text-shadow:0 0 12px rgba(255,248,224,.85),0 0 3px rgba(255,248,224,.6),0 3px 6px rgba(0,0,0,.35)}}
.flourish{{left:680px;top:246px;width:280px;z-index:9}}
.para{{left:586px;top:282px;width:468px;text-align:center;z-index:9;font-family:'Gelasio';font-size:23.5px;line-height:1.27;color:#1c1c1c}}

.late{{left:556px;top:528px;width:504px;text-align:center;z-index:9;font-family:'Gelasio';font-weight:700;font-size:26px;letter-spacing:6px;color:#8a1f1f;
  text-shadow:0 1px 2px rgba(255,248,224,.6)}}
.late:before,.late:after{{content:'';display:inline-block;width:60px;height:2px;vertical-align:middle;margin:0 14px;background:#8a1f1f}}
.name{{left:530px;top:558px;width:546px;text-align:center;z-index:9;font-family:'Gelasio';font-weight:700;font-size:82px;line-height:.9;letter-spacing:0;white-space:nowrap;
  color:#07251a}}
.name-ext{{z-index:8;color:#f6e2a2;
  text-shadow:1.4px 0 0 #f6e2a2,-1.4px 0 0 #f6e2a2,0 1.4px 0 #f6e2a2,0 -1.4px 0 #f6e2a2,
    1px 1px 0 #f6e2a2,-1px 1px 0 #f6e2a2,1px -1px 0 #f6e2a2,-1px -1px 0 #f6e2a2,
    0 0 8px rgba(255,255,255,.55),0 5px 12px rgba(0,0,0,.42),0 1px 2px rgba(0,0,0,.35)}}
.kwochaa{{left:556px;top:712px;width:504px;text-align:center;z-index:9;font-family:'Gelasio';font-weight:700;font-size:31px;letter-spacing:.5px;color:#07251a;
  text-shadow:0 2px 4px rgba(0,0,0,.25)}}

/* seal */
.seal{{left:800px;top:746px;width:150px;height:150px;z-index:11}}
.seal .glow{{position:absolute;inset:10px;border-radius:50%;background:radial-gradient(circle,rgba(255,250,232,.92),rgba(255,250,232,.6) 55%,rgba(255,250,232,0) 72%)}}
.seal svg{{position:absolute;inset:0;width:100%;height:100%}}
.seal .num{{position:absolute;left:0;right:0;top:34px;text-align:center;font-family:'Playfair Display';font-weight:900;font-size:60px;line-height:1;color:{t['seal_num']}}}
.seal .yrs{{position:absolute;left:0;right:0;top:96px;text-align:center;font-family:'Gelasio';font-weight:700;font-size:20px;color:{t['seal_yrs']}}}

/* ribbons */
.ribbon{{left:112px;top:876px;width:864px;height:96px;z-index:10}}
.ribbon svg{{position:absolute;inset:0;width:100%;height:100%;filter:drop-shadow(0 6px 10px rgba(0,0,0,.4))}}
.ribbon span{{position:absolute;left:0;right:0;top:25px;text-align:center;font-family:'Gelasio';font-weight:700;font-size:38px;letter-spacing:2px;
  color:{t['ribbon_txt']};text-shadow:0 2px 4px rgba(0,0,0,.55)}}
.foot{{left:66px;top:1518px;width:948px;height:66px;z-index:11}}
.foot svg.rb{{position:absolute;inset:0;width:100%;height:100%;filter:drop-shadow(0 5px 9px rgba(0,0,0,.4))}}
.foot span{{position:absolute;left:0;right:0;top:17px;text-align:center;font-family:'Gelasio';font-weight:700;font-size:24px;letter-spacing:.3px;color:{t['foot_txt']}}}
.foot .fl{{position:absolute;top:18px;width:78px;height:24px}}

/* ---------- schedule ---------- */
.sched{{left:86px;top:972px;width:756px;z-index:8;font-family:'Gelasio'}}
.dh{{display:flex;align-items:center;font-weight:700;font-size:32px;color:{t['head']};line-height:1.1}}
.dot{{width:22px;height:22px;border-radius:50%;flex:none;margin-right:14px;background:{t['bullet']};
  box-shadow:0 0 0 3px {t['bullet_ring']},0 2px 4px rgba(0,0,0,.35)}}
.row{{display:flex;align-items:flex-start;margin:7px 0 0 40px}}
.chip{{flex:none;font-weight:700;font-size:23px;color:{t['chip_txt']};background:{GOLD_GRAD};padding:2px 11px 3px;border-radius:8px;
  margin-right:14px;margin-top:2px;box-shadow:0 2px 5px rgba(0,0,0,.35),inset 0 0 0 1px rgba(255,255,255,.35)}}
.desc{{flex:1;font-size:22.5px;line-height:1.22;color:{t['body']}}}
.div{{border-top:2.5px dashed {t['divider']};margin:10px 0 11px 0}}
</style></head><body>
<div id="f">
  <img class="abs sky" src="{img('sky')}"/>
  {sky_tint}
  <div class="abs card"></div>
  <div class="abs cardfade"></div>
  <svg class="grain" xmlns="http://www.w3.org/2000/svg"><filter id="gr"><feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="2" stitchTiles="stitch"/><feColorMatrix values="0 0 0 0 .45 0 0 0 0 .38 0 0 0 0 .25 0 0 0 1 0"/></filter><rect width="100%" height="100%" filter="url(#gr)"/></svg>
  <div class="abs sunglow"></div>

  <img class="abs portrait" src="{img('portrait')}"/>
  <img class="abs bouquet" src="{img('bouquet')}"/>
  <img class="abs dove" src="{img('dove1')}"/>
  <img class="abs scene" src="{img('cross_scene')}"/>

  <div class="abs forever">Forever</div>
  <div class="abs inhearts">IN OUR HEARTS</div>
  <div class="abs flourish">{FLOURISH}</div>
  <div class="abs para">With gratitude to God for a life well spent, the Dimnwaka Family in Umudimisii, Umuoru Village Uga announce the transition to glory of their husband, father, grand father, brother, uncle, cousin and father&#8209;in&#8209;law.</div>

  <div class="abs late">LATE</div>
  <div class="abs name name-ext">ENGR. ELIS<br/>O. DIM</div>
  <div class="abs name">ENGR. ELIS<br/>O. DIM</div>
  <div class="abs kwochaa">(KWOCHAA)</div>

  <div class="abs seal"><div class="glow"></div>{wreath_svg()}<div class="num">86</div><div class="yrs">Years</div></div>

  <div class="abs ribbon">{ribbon_svg('grn','#e6c25a','#0a2e20')}<span>BURIAL ARRANGEMENTS</span></div>

  <div class="abs sched">
    <div class="dh"><span class="dot"></span>Thursday, 22nd October, 2026</div>
    <div class="row"><span class="chip">4pm:</span><span class="desc">Vigil Mass at his Compound in Umudimisii<br/>Umuoru Village Uga Aguata LGA Anambra State.</span></div>
    <div class="div"></div>
    <div class="dh"><span class="dot"></span>Friday, 23rd October, 2026</div>
    <div class="row"><span class="chip">7am:</span><span class="desc">Body leaves Visitation Mortuary Umuchu for<br/>lying in state at his Compound in Umudimisii<br/>Umuoru Village Uga.</span></div>
    <div class="row"><span class="chip">9am:</span><span class="desc">Requiem Mass at St. Paul&rsquo;s Catholic Church<br/>Umuoru Village, Uga.<br/>Interment/Condolence visits follow thereafter<br/>at his Compound.</span></div>
    <div class="div"></div>
    <div class="dh"><span class="dot"></span>Sunday, 25th October, 2026</div>
    <div class="row"><span class="chip">9am:</span><span class="desc">Thanksgiving Mass at St. Paul&rsquo;s Catholic Church,<br/>Umuoru Village Uga.</span></div>
    <div class="div"></div>
  </div>

  <img class="abs bouquet2" src="{img('bouquet2')}"/>
  <div class="abs foot">{ribbon_svg('gh','#8a6a1c','#b8892a').replace('<svg ','<svg class="rb" ')}
    <div class="fl" style="left:30px">{SMALL_FLOURISH}</div><div class="fl" style="right:30px;transform:scaleX(-1)">{SMALL_FLOURISH}</div>
    <span>MAY HIS GENTLE SOUL REST IN PERFECT PEACE. AMEN</span></div>

  <div class="abs frame"></div>
  <div class="abs corner" style="left:24px;top:24px">{CORNER}</div>
  <div class="abs corner" style="right:24px;top:24px;transform:scaleX(-1)">{CORNER}</div>
  <div class="abs corner" style="left:24px;bottom:24px;transform:scaleY(-1)">{CORNER}</div>
  <div class="abs corner" style="right:24px;bottom:24px;transform:scale(-1,-1)">{CORNER}</div>
</div>
</body></html>"""

if __name__ == "__main__":
    for key in THEMES:
        html = build(key)
        out = os.path.join(ROOT, "build", f"memorial_{key}.html")
        with open(out, "w") as fh:
            fh.write(html)
        print("wrote", out, len(html), "bytes")
