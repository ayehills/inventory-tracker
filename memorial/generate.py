#!/usr/bin/env python3
"""Recreate the burial-announcement flyer in a green+gold theme, two variants:
  deep  = deep-green dominant background + gold
  soft  = golden-hour sky up top fading into green (green as accent, not dominant)
Keeps all original text; swaps in the new cut-out portrait."""
import base64, os

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
    ff("Playfair Display", "PlayfairDisplay.ttf", "400 900", "italic"),
    ff("Cinzel", "Cinzel.ttf", "400 900"),
    ff("EB Garamond", "EBGaramond.ttf", "400 800"),
    ff("EB Garamond", "EBGaramond-Italic.ttf", "400 800", "italic"),
])

IMG = {n: b64(os.path.join(AST, n + ".png")) for n in
       ["portrait", "lily_bl", "lily_br", "cross_bible", "dove1"]}

def img(n): return f"data:image/png;base64,{IMG[n]}"

# ---------------------------------------------------------------- backgrounds
BG_DEEP = """
  radial-gradient(70% 42% at 50% 10%, rgba(240,208,120,.34), rgba(0,0,0,0) 55%),
  radial-gradient(120% 70% at 50% 4%, rgba(255,244,205,.18), rgba(0,0,0,0) 46%),
  linear-gradient(180deg,#134534 0%,#0f3626 34%,#0c2c1e 60%,#0a2418 80%,#071a12 100%)"""

BG_SOFT = """
  radial-gradient(55% 34% at 50% 20%, rgba(255,248,214,.95), rgba(255,226,158,.55) 34%, rgba(255,210,130,0) 62%),
  linear-gradient(180deg,#90b2ce 0%,#b7c6b0 15%,#e6d09a 27%,#d3ad64 36%,#6d8352 43%,#2f5f42 52%,#154630 64%,#0e3524 80%,#08241a 100%)"""

THEMES = {
    "deep": dict(bg=BG_DEEP, sky=False,
                 forever="#f4d98a", inhearts="#efe4c7", para="#e9ddbe",
                 rays=0.10),
    "soft": dict(bg=BG_SOFT, sky=True,
                 forever="#8a1f1f", inhearts="#243a2c", para="#20321f",
                 rays=0.16),
}

GOLD = "linear-gradient(180deg,#fbeeb6 0%,#eccb70 42%,#c99a3a 74%,#f2dc93 100%)"

def sparkle_clouds(op):
    return (f"<svg class='rays' style='opacity:{op}' xmlns='http://www.w3.org/2000/svg'>"
            "<defs><radialGradient id='rg' cx='50%' cy='6%' r='60%'>"
            "<stop offset='0' stop-color='#fff6d0' stop-opacity='.9'/>"
            "<stop offset='1' stop-color='#fff6d0' stop-opacity='0'/></radialGradient>"
            "<filter id='cl'><feTurbulence type='fractalNoise' baseFrequency='0.010' numOctaves='3' seed='7'/>"
            "<feColorMatrix values='0 0 0 0 1  0 0 0 0 .96  0 0 0 0 .82  0 0 0 .7 0'/></filter></defs>"
            "<rect width='100%' height='46%' filter='url(#cl)' opacity='.5'/>"
            "<rect width='100%' height='100%' fill='url(#rg)'/></svg>")

def build(key):
    t = THEMES[key]
    sky_deco = ""
    if t["sky"]:
        sky_deco = sparkle_clouds(0.9)
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
{FACES}
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{background:#06140d}}
#f{{position:relative;width:1080px;height:1620px;overflow:hidden;background:{t['bg']};
  font-family:'EB Garamond',serif}}
.rays{{position:absolute;inset:0;width:100%;height:100%;pointer-events:none}}
.godrays{{position:absolute;inset:0;pointer-events:none;opacity:{t['rays']};
  background:repeating-conic-gradient(from 90deg at 50% -6%, rgba(255,240,200,.0) 0deg, rgba(255,240,200,.55) 2deg, rgba(255,240,200,0) 6deg)}}
.vig{{position:absolute;inset:0;pointer-events:none;
  background:radial-gradient(120% 92% at 50% 42%, rgba(0,0,0,0) 52%, rgba(3,18,11,.5) 84%, rgba(2,12,8,.82) 100%)}}
.frame{{position:absolute;inset:24px;border:2px solid rgba(233,196,106,.55);border-radius:6px;pointer-events:none;
  box-shadow:inset 0 0 50px rgba(0,0,0,.4)}}
.frame:before{{content:'';position:absolute;inset:6px;border:1px solid rgba(233,196,106,.3)}}
.layer{{position:absolute}}
.gold{{background:{GOLD};-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;
  filter:drop-shadow(0 2px 3px rgba(0,0,0,.45))}}

/* portrait */
.portrait{{left:8px;top:78px;width:604px;z-index:5;
  filter:drop-shadow(0 16px 26px rgba(0,0,0,.5));
  -webkit-mask-image:linear-gradient(180deg,#000 82%,transparent 99%);
  mask-image:linear-gradient(180deg,#000 82%,transparent 99%)}}

/* doves */
.dove{{position:absolute;z-index:6;opacity:.95;filter:drop-shadow(0 6px 10px rgba(0,0,0,.35))}}

/* header right */
.forever{{left:560px;top:120px;width:500px;text-align:center;z-index:7;
  font-family:'Great Vibes';font-size:112px;line-height:.8;color:{t['forever']};
  text-shadow:0 2px 10px rgba(0,0,0,.30)}}
.inhearts{{left:560px;top:250px;width:500px;text-align:center;z-index:7;
  font-family:'Playfair Display';font-weight:700;font-style:italic;font-size:44px;letter-spacing:1px;color:{t['inhearts']}}}
.para{{left:588px;top:324px;width:456px;text-align:center;z-index:7;
  font-family:'EB Garamond';font-weight:500;font-size:25px;line-height:1.34;color:{t['para']}}}

/* name block (offset left to clear the seal) */
.late{{left:20px;right:236px;top:600px;text-align:center;z-index:7;
  font-family:'Cinzel';font-weight:700;letter-spacing:10px;font-size:30px}}
.late:before,.late:after{{content:'';display:inline-block;width:54px;height:2px;vertical-align:middle;margin:0 16px;
  background:linear-gradient(90deg,rgba(233,196,106,0),#e9c46a)}}
.late:after{{background:linear-gradient(90deg,#e9c46a,rgba(233,196,106,0))}}
.name{{left:20px;right:236px;top:636px;text-align:center;z-index:7;
  font-family:'Playfair Display';font-weight:900;font-size:76px;line-height:.98;letter-spacing:1px}}
.kwochaa{{left:20px;right:236px;top:726px;text-align:center;z-index:7;
  font-family:'Cinzel';font-weight:700;font-size:28px;letter-spacing:5px}}

/* age seal */
.seal{{right:54px;top:602px;width:168px;height:168px;z-index:8;border-radius:50%;
  display:flex;flex-direction:column;align-items:center;justify-content:center;
  background:radial-gradient(circle at 50% 38%,#12432f,#0a2418 78%);
  box-shadow:0 0 0 4px #0a2418,0 0 0 8px #c99a3a,0 0 0 11px #0a2418,0 8px 22px rgba(0,0,0,.5),
    inset 0 0 22px rgba(0,0,0,.6);border:2px solid #f0d98a}}
.seal .n{{font-family:'Playfair Display';font-weight:900;font-size:72px;line-height:.8;margin-top:6px}}
.seal .y{{font-family:'Cinzel';font-weight:600;font-size:22px;letter-spacing:4px;margin-top:6px;color:#efe4c7}}

/* burial ribbon */
.ribbon{{left:70px;right:70px;top:812px;height:70px;z-index:7;display:flex;align-items:center;justify-content:center;
  background:linear-gradient(180deg,#1a5138,#0c2c1e);border-top:2px solid #e9c46a;border-bottom:2px solid #e9c46a;
  box-shadow:0 6px 18px rgba(0,0,0,.4),inset 0 0 26px rgba(0,0,0,.45)}}
.ribbon:before,.ribbon:after{{content:'';position:absolute;top:8px;width:30px;height:54px;background:#0a2418;z-index:-1}}
.ribbon:before{{left:-30px;clip-path:polygon(0 0,100% 12%,100% 88%,0 100%);border-left:2px solid #c99a3a}}
.ribbon:after{{right:-30px;clip-path:polygon(0 12%,100% 0,100% 100%,0 88%);border-right:2px solid #c99a3a}}
.ribbon span{{font-family:'Cinzel';font-weight:900;font-size:36px;letter-spacing:5px}}

/* schedule */
.sched{{left:78px;right:78px;top:912px;z-index:7}}
.grp{{margin-bottom:22px}}
.dhead{{font-family:'Playfair Display';font-weight:800;font-size:34px;color:#f4d98a;display:flex;align-items:center;
  text-shadow:0 1px 4px rgba(0,0,0,.4)}}
.dot{{width:20px;height:20px;border-radius:50%;margin-right:16px;flex:none;
  background:radial-gradient(circle at 38% 32%,#fbeeb6,#c99a3a);box-shadow:0 0 0 3px rgba(201,154,58,.35)}}
.dline{{height:1px;flex:1;margin-left:18px;background:linear-gradient(90deg,rgba(233,196,106,.5),rgba(233,196,106,0))}}
.row{{display:flex;align-items:flex-start;margin:9px 0 0 36px}}
.chip{{flex:none;min-width:78px;text-align:center;font-family:'EB Garamond';font-weight:700;font-size:23px;
  color:#12251a;background:{GOLD};padding:3px 12px;border-radius:12px;margin-right:18px;margin-top:2px;
  box-shadow:0 3px 8px rgba(0,0,0,.35)}}
.desc{{flex:1;font-family:'EB Garamond';font-weight:500;font-size:25px;line-height:1.32;color:#eadfc0}}

/* decorations */
.lilybl{{left:0px;bottom:22px;width:214px;z-index:8;filter:drop-shadow(0 6px 12px rgba(0,0,0,.4))}}
.crossb{{right:16px;bottom:104px;width:196px;z-index:8;filter:drop-shadow(0 6px 12px rgba(0,0,0,.4))}}

/* bottom ribbon */
.foot{{left:56px;right:56px;bottom:44px;height:60px;z-index:9;display:flex;align-items:center;justify-content:center;
  background:linear-gradient(180deg,#1a5138,#0b2a1c);border-top:2px solid #e9c46a;border-bottom:2px solid #e9c46a;
  box-shadow:0 6px 16px rgba(0,0,0,.45),inset 0 0 22px rgba(0,0,0,.4)}}
.foot span{{font-family:'Cinzel';font-weight:700;font-size:26px;letter-spacing:2px;text-align:center}}
</style></head><body>
<div id="f">
  {sky_deco}
  <div class="godrays"></div>

  <img class="layer dove" src="{img('dove1')}" style="left:16px;top:40px;width:128px;transform:scaleX(-1)"/>
  <img class="layer dove" src="{img('dove1')}" style="right:44px;top:20px;width:92px"/>

  <img class="layer portrait" src="{img('portrait')}"/>

  <div class="layer forever">Forever</div>
  <div class="layer inhearts">in our Hearts</div>
  <div class="layer para">With gratitude to God for a life well spent, the Dimnwaka&rsquo;s Family in Umudimisii, Umuoru Village Uga announce the transition to glory of their husband, father, grand father, brother, uncle, cousin and father-in-law.</div>

  <div class="layer late gold">LATE</div>
  <div class="layer name gold">ENGR. ELIS O. DIM</div>
  <div class="layer kwochaa gold">(KWOCHAA)</div>
  <div class="layer seal"><div class="n gold">86</div><div class="y">YEARS</div></div>

  <div class="layer ribbon"><span class="gold">BURIAL ARRANGEMENTS</span></div>

  <div class="layer sched">
    <div class="grp">
      <div class="dhead"><span class="dot"></span>Thursday, 22nd October, 2026<span class="dline"></span></div>
      <div class="row"><span class="chip">4pm</span><span class="desc">Vigil Mass at his Compound in Umudimisii Umuoru Village Uga Aguata LGA Anambra State.</span></div>
    </div>
    <div class="grp">
      <div class="dhead"><span class="dot"></span>Friday, 23rd October, 2026<span class="dline"></span></div>
      <div class="row"><span class="chip">7am</span><span class="desc">Body leaves Visitation Mortuary Umuchu for lying in state at his Compound in Umudimisii Umuoru Village Uga.</span></div>
      <div class="row"><span class="chip">9am</span><span class="desc">Requiem Mass at St. Paul&rsquo;s Catholic Church Umuoru Village, Uga. Interment/Condolence visits follow thereafter at his Compound.</span></div>
    </div>
    <div class="grp">
      <div class="dhead"><span class="dot"></span>Sunday, 25th October, 2026<span class="dline"></span></div>
      <div class="row"><span class="chip">9am</span><span class="desc">Thanksgiving Mass at St. Paul&rsquo;s Catholic Church, Umuoru Village Uga.</span></div>
    </div>
  </div>

  <img class="layer lilybl" src="{img('lily_bl')}"/>
  <img class="layer crossb" src="{img('cross_bible')}"/>

  <div class="vig"></div>
  <div class="frame"></div>
  <div class="layer foot"><span class="gold">MAY HIS GENTLE SOUL REST IN PERFECT PEACE. AMEN</span></div>
</div>
</body></html>"""

if __name__ == "__main__":
    for key in THEMES:
        html = build(key)
        out = os.path.join(ROOT, "build", f"memorial_{key}.html")
        with open(out, "w") as fh:
            fh.write(html)
        print("wrote", out, len(html), "bytes")
