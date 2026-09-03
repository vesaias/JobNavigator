"""Diff two stylecrawl stages: python /tmp/v2t/stylediff.py D0 D4a [--out /tmp/v2t/shots/stylediff_D0_D4a.md]"""
import sys, json, collections
a, b = sys.argv[1], sys.argv[2]
out = sys.argv[sys.argv.index('--out') + 1] if '--out' in sys.argv else f'/tmp/v2t/shots/stylediff_{a}_{b}.md'
A = json.load(open(f'/tmp/v2t/shots/{a}/styles.json')); B = json.load(open(f'/tmp/v2t/shots/{b}/styles.json'))
changed = []; missing = [k for k in A if k not in B]; added = [k for k in B if k not in A]
for k in A:
    if k not in B: continue
    for state in ('rest', 'hover'):
        x, y = A[k].get(state), B[k].get(state)
        if not x or not y: continue
        d = {p: (x[p], y[p]) for p in x if x.get(p) != y.get(p)}
        if d: changed.append((k, state, d))
by_change = collections.Counter()
for k, state, d in changed:
    for p, (o, n) in d.items(): by_change[(state, p, o, n)] += 1
with open(out, 'w', encoding='utf-8') as f:
    f.write(f'# style diff {a} → {b}\n\n{len(A)} baseline elements · {len(changed)} changed tuples · {len(missing)} missing · {len(added)} added\n\n## Changes grouped (state · prop · old → new · count)\n')
    for (state, p, o, n), c in by_change.most_common(): f.write(f'- {c:>4} · {state} · {p}: `{o}` → `{n}`\n')
    f.write('\n## Changed elements\n')
    for k, state, d in changed: f.write(f'- `{k}` · {state} · ' + '; '.join(f'{p} {o} → {n}' for p, (o, n) in d.items()) + '\n')
    f.write('\n## Missing in ' + b + '\n' + '\n'.join(f'- `{k}`' for k in missing[:300]) + '\n\n## Added in ' + b + '\n' + '\n'.join(f'- `{k}`' for k in added[:300]) + '\n')
print(f'{len(changed)} changed, {len(missing)} missing, {len(added)} added → {out}')
