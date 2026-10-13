#!/usr/bin/env python3
"""Add the 'HOSTED BY / LEGENDARY UNCLE LUKE *' caption to the user's two composites.
Style mirrors the flyer's stacked condensed caps (pink label, white name, gold star).
Rendered at 2x and downsampled to the originals' size so the text is crisp."""
import base64, os, subprocess
from PIL import Image

ROOT = os.path.dirname(os.path.abspath(__file__))
def b64(p):
    with open(os.path.join(ROOT, p), 'rb') as f: return base64.b64encode(f.read()).decode()

STAR = ('<svg viewBox="0 0 24 24"><defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0" stop-color="#fff0b8"/><stop offset=".5" stop-color="#f0c54f"/><stop offset="1" stop-color="#b8842a"/></linearGradient></defs>'
        '<path d="M12 1.8l3 6.7 7.2.7-5.4 4.9 1.6 7.1L12 17.5l-6.4 3.7 1.6-7.1L1.8 9.2 9 8.5z" fill="url(#g)" stroke="#7a5312" stroke-width=".6"/></svg>')

# right-aligned stacks; coordinates in the image's own pixels (720x920)
SPECS = {
    'v1': dict(src='assets/user_v1.png', top=676, right=8,
               lines=[('hosted', 'HOSTED BY'), ('name', 'LEGENDARY'), ('name', 'UNCLE LUKE', True)],
               name_px=17, hosted_px=12),
    'v2': dict(src='assets/user_v2.png', top=826, right=8,
               lines=[('hosted', 'HOSTED BY'), ('name', 'LEGENDARY UNCLE LUKE', True)],
               name_px=13.5, hosted_px=11.5),
}

def render(key, s):
    im = Image.open(os.path.join(ROOT, s['src'])); W, H = im.size
    rows = ''
    for ln in s['lines']:
        cls, txt, star = ln[0], ln[1], (len(ln) > 2)
        rows += f'<div class="{cls}">{txt}{STAR if star else ""}</div>'
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
@font-face{{font-family:'Oswald';src:url(data:font/ttf;base64,{b64('assets/fonts/Oswald.ttf')}) format('truetype');font-weight:200 700}}
*{{margin:0;padding:0;box-sizing:border-box}} body{{background:#000}}
#f{{position:relative;width:{W}px;height:{H}px;overflow:hidden}}
#f>img{{position:absolute;left:0;top:0;width:{W}px;height:{H}px}}
.stack{{position:absolute;top:{s['top']}px;right:{s['right']}px;display:flex;flex-direction:column;align-items:flex-end;gap:3px;font-family:'Oswald'}}
.hosted{{font-weight:600;font-size:{s['hosted_px']}px;letter-spacing:2.5px;color:#ff3d9a;line-height:1;
  text-shadow:0 0 7px rgba(255,61,154,.85),0 1px 2px rgba(0,0,0,.95)}}
.name{{font-weight:700;font-size:{s['name_px']}px;letter-spacing:.6px;color:#fff;line-height:1;display:flex;align-items:center;gap:4px;
  text-shadow:0 1px 2px rgba(0,0,0,.95),0 0 9px rgba(0,0,0,.75)}}
.name svg{{width:{s['name_px']*1.05:.1f}px;height:{s['name_px']*1.05:.1f}px;filter:drop-shadow(0 0 4px rgba(255,215,90,.85))}}
</style></head><body><div id="f"><img src="data:image/png;base64,{b64(s['src'])}"/>
<div class="stack">{rows}</div></div></body></html>"""
    os.makedirs(os.path.join(ROOT, 'build'), exist_ok=True)
    hp = os.path.join(ROOT, 'build', f'cap_{key}.html'); open(hp, 'w').write(html)
    js = f"""const {{ chromium }} = require('playwright');
(async () => {{
  const b = await chromium.launch({{ executablePath:'/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
    args:['--no-sandbox','--force-color-profile=srgb','--font-render-hinting=none'] }});
  const p = await b.newPage({{ viewport:{{width:{W},height:{H}}}, deviceScaleFactor:2 }});
  await p.goto('file://{hp}', {{ waitUntil:'networkidle' }});
  await p.evaluate(async () => {{ await document.fonts.ready; }}); await p.waitForTimeout(250);
  await (await p.$('#f')).screenshot({{ path:'{os.path.join(ROOT, "build", f"cap_{key}_2x.png")}' }}); await b.close();
}})();"""
    jp = os.path.join(ROOT, 'build', f'cap_{key}.js'); open(jp, 'w').write(js)
    subprocess.run(['/opt/node22/bin/node', jp], cwd=ROOT, check=True, env={**os.environ, 'NODE_PATH': '/opt/node22/lib/node_modules'})
    out = Image.open(os.path.join(ROOT, 'build', f'cap_{key}_2x.png')).convert('RGB').resize((W, H), Image.LANCZOS)
    out.save(os.path.join(ROOT, f'larry-dogg-hosted-{key}.png'))
    out.crop((460, s['top'] - 90, W, s['top'] + 110)).resize((520, 400), Image.LANCZOS).save(os.path.join(ROOT, 'build', f'_cap_{key}.png'))
    print(f'{key}: exported larry-dogg-hosted-{key}.png ({W}x{H})')

if __name__ == '__main__':
    for k, s in SPECS.items(): render(k, s)
