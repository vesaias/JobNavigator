"""Tiny case runner for the v2 e2e suite.

A case is a function registered with @case('name'). It receives a Ctx and calls
ctx.check(label, cond, detail) as many times as it likes. A case passes when it
raises nothing and every check is true; one failing case never aborts the run.

    from _suite import case, Skip
    @case('smoke')
    def _(c):
        c.check('heading', ok, detail)
"""
import sys, time, traceback

_CASES = []


class Skip(Exception):
    """Raise (or use ctx.skip) to report SKIP instead of PASS/FAIL."""


def case(name):
    def deco(fn):
        _CASES.append((name, fn))
        return fn
    return deco


class Ctx:
    def __init__(self, name):
        self.name = name
        self.checks = []          # (label, ok, detail)
        self.notes = []

    def check(self, label, cond, detail=''):
        ok = bool(cond)
        d = str(detail)
        if len(d) > 400:
            d = d[:400] + '…'
        self.checks.append((label, ok, d))
        print(f"    {'ok  ' if ok else 'FAIL'} {label}" + (f"  — {d}" if d else ''), flush=True)
        return ok

    def eq(self, label, got, want):
        return self.check(label, got == want, f'got {got!r} want {want!r}')

    def note(self, msg):
        self.notes.append(str(msg))
        print(f"    ..   {msg}", flush=True)

    def skip(self, reason):
        raise Skip(reason)

    @property
    def failed(self):
        return [c for c in self.checks if not c[1]]


LIVE_HINT = 'needs JN_E2E_LIVE=1'


def run(filter_=None):
    cases = [(n, f) for n, f in _CASES if not filter_ or filter_.lower() in n.lower()]
    if not cases:
        print(f'E2E: no case matches {filter_!r}. Known: {", ".join(n for n, _ in _CASES)}')
        return 2
    t0 = time.time()
    results = []          # (name, status, seconds, summary)
    for name, fn in cases:
        print(f'\n── {name} ' + '─' * max(0, 60 - len(name)), flush=True)
        c = Ctx(name)
        t = time.time()
        status, summary = 'PASS', ''
        try:
            fn(c)
            bad = c.failed
            if bad:
                status = 'FAIL'
                summary = '; '.join(f'{l}' for l, _, _ in bad[:3]) + (f' (+{len(bad) - 3})' if len(bad) > 3 else '')
        except Skip as e:
            status, summary = 'SKIP', str(e)
        except Exception as e:                          # noqa: BLE001 - one case never aborts the run
            status = 'FAIL'
            summary = f'{type(e).__name__}: {e}'.replace('\n', ' ')[:200]
            traceback.print_exc(limit=6)
        el = time.time() - t
        n_ok = sum(1 for _, ok, _ in c.checks if ok)
        results.append((name, status, el, len(c.checks), n_ok, summary))
        print(f'   → {status} ({n_ok}/{len(c.checks)} checks, {el:.1f}s)' + (f' — {summary}' if summary else ''), flush=True)

    total = time.time() - t0
    w = max([len(r[0]) for r in results] + [4])
    print('\n' + '=' * (w + 46))
    print(f'{"case".ljust(w)}  status  checks   time  detail')
    print('-' * (w + 46))
    for name, status, el, n, n_ok, summary in results:
        print(f'{name.ljust(w)}  {status:<6}  {n_ok:>2}/{n:<3}  {el:5.1f}s  {summary[:60]}')
    print('=' * (w + 46))
    p = sum(1 for r in results if r[1] == 'PASS')
    f = sum(1 for r in results if r[1] == 'FAIL')
    s = sum(1 for r in results if r[1] == 'SKIP')
    print(f'E2E: {len(results)} cases · {p} passed · {f} failed · {s} skipped · {total:.0f}s')
    return 1 if f else 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    return run(argv[0] if argv else None)
