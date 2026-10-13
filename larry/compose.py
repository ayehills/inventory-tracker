#!/usr/bin/env python3
"""Place the 'Hosted by' headshot bubble on the 4x6 'open' flyer.
Renders an HTML overlay (gold ring, pink stage glow, caption band) at 2x and
downsamples to the 1200x1800 deliverable."""
import base64, os, subprocess
from PIL import Image

ROOT = os.path.dirname(os.path.abspath(__file__))
def b64(p):
    with open(os.path.join(ROOT, p), 'rb') as f: return base64.b64encode(f.read()).decode()

BASE = 'larry-dogg-4x6-open.png'          # 1200x1800
CX, CY, R = 1000, 985, 147                 # bubble centre / radius in base px
RING = 9

html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
@font-face{{font-family:'Oswald';src:url(data:font/ttf;base64,{b64('assets/fonts/Oswald.ttf')}) format('truetype');font-weight:200 700}}
@font-face{{font-family:'Barlow Condensed';src:url(data:font/ttf;base64,{b64('assets/fonts/BarlowCondensed-SemiBold.ttf')}) format('truetype');font-weight:600}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#000}}
#f{{position:relative;width:1200px;height:1800px;overflow:hidden}}
#f>img.base{{position:absolute;left:0;top:0;width:1200px;height:1800px}}
.ring{{position:absolute;left:{CX-R-RING}px;top:{CY-R-RING}px;width:{2*(R+RING)}px;height:{2*(R+RING)}px;border-radius:50%;
  padding:{RING}px;
  background:conic-gradient(from 210deg,#8a5a12,#f7e3a1 12%,#c9962e 26%,#fff3c4 40%,#b8842a 54%,#f3d27a 68%,#9c6f1c 82%,#f7e3a1 94%,#8a5a12);
  box-shadow:0 0 0 1.5px rgba(60,35,5,.9),0 0 38px rgba(255,45,140,.62),0 0 90px rgba(255,45,140,.28),0 16px 30px rgba(0,0,0,.65)}}
.bubble{{position:relative;width:{2*R}px;height:{2*R}px;border-radius:50%;overflow:hidden;
  background:radial-gradient(circle at 50% 34%,#8d1a55 0%,#4a0f34 46%,#1c0616 78%,#0d030a 100%);
  box-shadow:inset 0 0 0 2px rgba(0,0,0,.65),inset 0 0 46px rgba(0,0,0,.55)}}
.bubble img.hs{{position:absolute;left:-47px;top:-4px;width:389px;
  filter:drop-shadow(0 0 18px rgba(255,60,150,.35))}}
.band{{position:absolute;left:0;right:0;bottom:0;height:100px;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;
  padding-bottom:27px;background:linear-gradient(180deg,rgba(8,2,6,0) 0%,rgba(8,2,6,.70) 36%,rgba(8,2,6,.94) 100%)}}
.hosted{{font-family:'Barlow Condensed';font-weight:600;font-size:15px;letter-spacing:3.5px;color:#ff3d9a;line-height:1;margin-bottom:5px;
  text-shadow:0 0 8px rgba(255,61,154,.75),0 1px 2px rgba(0,0,0,.8)}}
.name{{font-family:'Oswald';font-weight:700;font-size:16px;letter-spacing:1px;color:#fff;line-height:1;display:flex;align-items:center;gap:5px;
  text-shadow:0 1px 2px rgba(0,0,0,.9),0 0 10px rgba(0,0,0,.6)}}
.name svg{{width:17px;height:17px;filter:drop-shadow(0 0 4px rgba(255,215,90,.8))}}
</style></head><body><div id="f">
<img class="base" src="data:image/png;base64,{b64(BASE)}"/>
<div class="ring"><div class="bubble">
  <img class="hs" src="data:image/png;base64,{b64('assets/headshot_cut.png')}"/>
  <div class="band">
    <div class="hosted">HOSTED BY</div>
    <div class="name">LEGENDARY UNCLE LUKE
      <svg viewBox="0 0 24 24"><defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="#fff0b8"/><stop offset=".5" stop-color="#f0c54f"/><stop offset="1" stop-color="#b8842a"/></linearGradient></defs>
        <path d="M12 1.8l3 6.7 7.2.7-5.4 4.9 1.6 7.1L12 17.5l-6.4 3.7 1.6-7.1L1.8 9.2 9 8.5z" fill="url(#g)" stroke="#7a5312" stroke-width=".6"/></svg>
    </div>
  </div>
</div></div>
</div></body></html>"""
os.makedirs(os.path.join(ROOT, 'build'), exist_ok=True)
with open(os.path.join(ROOT, 'build', 'hosted.html'), 'w') as f: f.write(html)

JS = r"""
const { chromium } = require('playwright'); const path = require('path');
(async () => {
  const b = await chromium.launch({ executablePath:'/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
    args:['--no-sandbox','--force-color-profile=srgb','--font-render-hinting=none'] });
  const p = await b.newPage({ viewport:{width:1200,height:1800}, deviceScaleFactor:2 });
  await p.goto('file://' + path.resolve('build/hosted.html'), { waitUntil:'networkidle' });
  await p.evaluate(async () => { await document.fonts.ready; }); await p.waitForTimeout(300);
  await (await p.$('#f')).screenshot({ path:'build/hosted_2x.png' }); await b.close(); console.log('rendered build/hosted_2x.png');
})();"""
with open(os.path.join(ROOT, 'build', 'render_hosted.js'), 'w') as f: f.write(JS)
subprocess.run(['/opt/node22/bin/node', 'build/render_hosted.js'], cwd=ROOT, check=True,
               env={**os.environ, 'NODE_PATH': '/opt/node22/lib/node_modules'})

im = Image.open(os.path.join(ROOT, 'build', 'hosted_2x.png')).convert('RGB').resize((1200, 1800), Image.LANCZOS)
im.save(os.path.join(ROOT, 'larry-dogg-4x6-hosted.png'))
im.save(os.path.join(ROOT, 'larry-dogg-4x6-hosted.pdf'), 'PDF', resolution=300.0)
im.crop((640, 760, 1200, 1230)).resize((840, 705), Image.LANCZOS).save(os.path.join(ROOT, 'build', '_bubble.png'))
print('exported larry-dogg-4x6-hosted.png/.pdf')
