"""Pixel diff between two shots stages. Run inside the backend container:
python /tmp/v2t/shotdiff.py D0 D4a [--threshold 0]
Writes /tmp/v2t/shots/diff_<a>_<b>/<name>.png (changed pixels in red over the new shot) and prints a table.
"""
import sys, os, json
from PIL import Image, ImageChops
a, b = sys.argv[1], sys.argv[2]
thr = int(sys.argv[sys.argv.index('--threshold') + 1]) if '--threshold' in sys.argv else 0
# data masks: regions whose content is time-dependent data, not design (route substring + width → boxes)
MASKS = {('v2_stats', 1440): [(930, 450, 1410, 750), (236, 760, 1410, 900)], ('v2_stats', 1024): [(690, 540, 1000, 700), (236, 700, 1000, 720)], ('v2_toasts', 1440): [(1240, 48, 1320, 70)], ('v2_toasts', 1024): [(824, 48, 900, 70)]}
def mask_for(name):
    w = 1440 if '__1440' in name else 1024
    return [b for (sub, ww), boxes in MASKS.items() if sub in name and ww == w for b in boxes]
A, B = f'/tmp/v2t/shots/{a}', f'/tmp/v2t/shots/{b}'; OUT = f'/tmp/v2t/shots/diff_{a}_{b}'; os.makedirs(OUT, exist_ok=True)
rows = []
for name in sorted(os.listdir(A)):
    if not name.endswith('.png'): continue
    if not os.path.exists(f'{B}/{name}'): rows.append((name, 'missing in ' + b, 0)); continue
    ia, ib = Image.open(f'{A}/{name}').convert('RGB'), Image.open(f'{B}/{name}').convert('RGB')
    if ia.size != ib.size: rows.append((name, f'size {ia.size} → {ib.size}', -1)); continue
    d = ImageChops.difference(ia, ib).convert('L').point(lambda p: 255 if p > thr else 0)
    for (x0, y0, x1, y1) in mask_for(name): d.paste(0, (x0, y0, x1, y1))
    n = sum(1 for p in d.getdata() if p)
    if n:
        over = ib.copy(); red = Image.new('RGB', ib.size, (220, 40, 40)); over.paste(red, mask=d); over.save(f'{OUT}/{name}')
        bbox = d.getbbox()
    rows.append((name, f'bbox {bbox}' if n else '', n))
json.dump(rows, open(f'{OUT}/summary.json', 'w'))
changed = [r for r in rows if r[2]]
print(f'{len(rows)} shots compared, {len(changed)} changed')
for name, note, n in changed: print(f'  {n:>7}  {name}  {note}')
