import React, { useState } from 'react'
import './theme.css'
import {
  Button, Pill, IconButton, Input, Textarea, SearchInput, Select, Row, Card, Band,
  DashedAdd, Menu, MenuHead, MenuItem, SectionHead, Chip, Tag, Dot, Link, NavLink,
  ModalPanel, Drawer, HeaderRow, Label, Helper, Heading, PageTitle, Spinner, ShowMore,
} from './ui'

// The primitive gallery at /v2/ui — the page the D3 style crawl checks against
// the canonical spec (`v2-testing/round-design/D1-D2.md`). Every primitive in
// every variant and state, in both themes, with the role name and the semantic
// tokens it reads printed under each block. It is deliberately rail-less (like
// ToastLab) so nothing but the primitives is on screen; the theme toggle is the
// app's own — the same `jobnavigator_dark_mode` flag the rail writes.
//
// Adding a primitive to ui.jsx? Add it here in the same pass, or the crawl has
// nothing to measure.

const OPTIONS = [['a', 'Anthropic'], ['b', 'OpenRouter'], ['c', 'Ollama (local)']]

// One documented role. `tokens` is the semantic-token list the primitive reads —
// printed verbatim so the crawl (and a human) can see what a skin would move.
function Role({ name, canonical, tokens, note, children }) {
  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap' }}>
        <Heading size={18}>{name}</Heading>
        {canonical && <Helper size="xs" mono>{canonical}</Helper>}
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'flex-start', gap: 18 }}>{children}</div>
      <Helper size="xs" mono style={{ display: 'block' }}>{tokens}</Helper>
      {note && <Helper size="xs">{note}</Helper>}
    </section>
  )
}

// One sample plus the state it is showing.
function S({ label, children, w }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 5, minWidth: 0, width: w }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, minHeight: 36 }}>{children}</div>
      <Label>{label}</Label>
    </div>
  )
}

export default function UiGallery() {
  const [dark, setDark] = useState(() => { try { return localStorage.getItem('jobnavigator_dark_mode') === 'true' } catch { return false } })
  const toggle = () => setDark((v) => {
    const n = !v
    try { localStorage.setItem('jobnavigator_dark_mode', String(n)) } catch { /* private mode */ }
    return n
  })

  const [text, setText] = useState('Senior Platform Engineer')
  const [area, setArea] = useState('Two lines of body copy so the 19px line-height is visible.\nSecond line.')
  const [q, setQ] = useState('')
  const [q2, setQ2] = useState('')
  const [pick, setPick] = useState('a')
  const [on, setOn] = useState(true)
  const [sel, setSel] = useState(true)
  const [open, setOpen] = useState({ a: true, b: false })
  const [modal, setModal] = useState(false)
  const [drawer, setDrawer] = useState(false)
  const [busy, setBusy] = useState(false)

  return (
    <div className="jn-v2" data-theme={dark ? 'dark' : 'light'}
      style={{ flex: 1, minHeight: '100vh', background: 'var(--bg)', color: 'var(--text)', display: 'flex', flexDirection: 'column' }}>

      <HeaderRow variant="screen" align="flex-end">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 3, minWidth: 0 }}>
          <PageTitle>Primitives</PageTitle>
          <Helper style={{ fontSize: 'var(--t-13)', lineHeight: '20px' }}>
            Every role in <code style={{ fontFamily: 'var(--font-mono)' }}>ui.jsx</code>, every variant and state, both themes. The spec is
            {' '}<code style={{ fontFamily: 'var(--font-mono)' }}>v2-testing/round-design/D1-D2.md</code>.
          </Helper>
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
          <NavLink onClick={() => { window.location.href = '/v2/toasts' }}>Toast lab ›</NavLink>
          <Button variant="secondary" size="sm" onClick={toggle} ariaLabel="Toggle theme">◐ {dark ? 'Dark' : 'Light'}</Button>
        </div>
      </HeaderRow>

      <div className="v2-scroll" style={{ flex: 1, minHeight: 0, overflow: 'auto', padding: '20px 30px 60px', display: 'flex', flexDirection: 'column', gap: 30 }}>

        <Card style={{ padding: '12px 16px' }}>
          <Helper>
            Hover states cannot be forced in a static page — the class that carries each one is named under its block, and the live sample
            shows it on hover. Focus: Tab into a sample; fields turn their border accent (no ring), other controls take the
            <code style={{ fontFamily: 'var(--font-mono)' }}> [tabindex] </code> ring.
          </Helper>
        </Card>

        <Role name="Button" canonical="primary/md · accent · r99 · h36 · 13.5/500 · pad 0 18"
          tokens="--btn-primary-bg/-ink/-disabled-bg/-disabled-ink · --btn-danger-bg/-ink · --btn-secondary-bg/-ink/-border/-disabled-ink/-disabled-border · --btn-ghost-ink · --radius-control · --t-13-5/-13/-12-5 · hover: v2-bdc (secondary), v2-hover-accent (ghost)">
          <S label="primary · md"><Button onClick={() => {}}>Score 12 jobs</Button></S>
          <S label="primary · sm"><Button size="sm" onClick={() => {}}>Save</Button></S>
          <S label="primary · xs"><Button size="xs" onClick={() => {}}>Add</Button></S>
          <S label="primary · disabled"><Button disabled>Save</Button></S>
          <S label="primary · busy"><Button busy>Saving…</Button></S>
          <S label="secondary · md"><Button variant="secondary" onClick={() => {}}>Cancel</Button></S>
          <S label="secondary · sm"><Button variant="secondary" size="sm" onClick={() => {}}>Test</Button></S>
          <S label="secondary · disabled"><Button variant="secondary" disabled>Cancel</Button></S>
          <S label="secondary · busy"><Button variant="secondary" busy>Testing…</Button></S>
          <S label="danger · md"><Button variant="danger" onClick={() => {}}>Delete résumé</Button></S>
          <S label="danger · disabled"><Button variant="danger" disabled>Delete</Button></S>
          <S label="ghost · md"><Button variant="ghost" onClick={() => {}}>Dismiss</Button></S>
          <S label="ghost · disabled"><Button variant="ghost" disabled>Dismiss</Button></S>
          <S label="live busy toggle">
            <Button onClick={() => { setBusy(true); setTimeout(() => setBusy(false), 1600) }} busy={busy}>{busy ? 'Working…' : 'Run 1.6s'}</Button>
          </S>
        </Role>

        <Role name="Pill" canonical="on ? accent-soft/accent : surface/text-2 · 1px · r99 · md h31/12.5 · sm h26/11.5"
          tokens="--pill-bg/-ink/-border/-on-bg/-on-ink/-on-border/-border-hover · --radius-control · --t-12-5/-11-5 · hover: v2-bd">
          <S label="md · off"><Pill onClick={() => {}}>Remote</Pill></S>
          <S label="md · on"><Pill on onClick={() => {}}>Remote</Pill></S>
          <S label="sm · off"><Pill size="sm" onClick={() => {}}>H-1B</Pill></S>
          <S label="sm · on"><Pill size="sm" on onClick={() => {}}>H-1B</Pill></S>
          <S label="md · disabled"><Pill disabled>Locked</Pill></S>
          <S label="live toggle"><Pill on={on} onClick={() => setOn((v) => !v)}>{on ? 'On' : 'Off'}</Pill></S>
        </Role>

        <Role name="IconButton" canonical="26 = muted glyph · r99 · 13px · 36 = bordered ⋯ head button · 15px"
          tokens="--icon-btn-ink · --pill-bg/-ink/-on-bg/-on-ink/-on-border/-border · --radius-control · --t-13/-15 · hover: v2-hover-accent (26), v2-act (36)">
          <S label="26 · rest"><IconButton title="Close" onClick={() => {}}>✕</IconButton></S>
          <S label="26 · disabled"><IconButton title="Close" disabled>✕</IconButton></S>
          <S label="36 · rest"><IconButton size={36} title="More" onClick={() => {}}>⋯</IconButton></S>
          <S label="36 · on"><IconButton size={36} on title="More" onClick={() => {}}>⋯</IconButton></S>
          <S label="36 · disabled"><IconButton size={36} title="More" disabled>⋯</IconButton></S>
        </Role>

        <Role name="Input · Textarea" canonical="h32 (textarea: 32 single-line, rows·19+13) · 1px --input-border · r6 · 12.5 · bg --input-bg · focus = accent border, no ring"
          tokens="--input-bg/-border/-border-focus/-ink/-placeholder · --radius-field · --t-12-5 · --font-body/-mono">
          <S label="rest" w={220}><Input value={text} onChange={setText} ariaLabel="Title" /></S>
          <S label="placeholder" w={220}><Input value="" onChange={() => {}} placeholder="Company name…" ariaLabel="Company" /></S>
          <S label="mono" w={220}><Input value="sk-ant-••••" onChange={() => {}} mono ariaLabel="Key" /></S>
          <S label="disabled" w={220}><Input value="Locked" onChange={() => {}} disabled ariaLabel="Locked" /></S>
          <S label="readOnly" w={220}><Input value="Read only" onChange={() => {}} readOnly ariaLabel="Read only" /></S>
          <S label="textarea · 3 rows" w={300}><Textarea value={area} onChange={setArea} ariaLabel="Notes" /></S>
          <S label="textarea · disabled" w={300}><Textarea value="Locked" onChange={() => {}} disabled rows={2} ariaLabel="Locked notes" /></S>
          <S label="textarea · 1 row (= Input h32)" w={300}><Textarea value="One line" onChange={() => {}} rows={1} ariaLabel="One line" /></S>
        </Role>

        <Role name="SearchInput" canonical="boxed h32 r99 with ⌕ inset · underline h36 on --input-underline"
          tokens="--search-bg/-glyph · --input-border/-border-focus/-ink/-placeholder/-underline · --radius-control · --t-12/-13">
          <S label="boxed · empty" w={240}><SearchInput value={q} onChange={setQ} placeholder="Search name, alias, URL…" /></S>
          <S label="boxed · filled" w={240}><SearchInput value={q2 || 'stripe'} onChange={setQ2} /></S>
          <S label="underline" w={300}><SearchInput variant="underline" value={q} onChange={setQ} placeholder="Search letters, companies…" width="280px" /></S>
        </Role>

        <Role name="Select" canonical="box h32 · 1px --input-border · r6 · 12.5 + ▾, listbox = Menu"
          tokens="--input-border/-border-focus/-ink/-placeholder · --search-bg · --menu-bg/-border/-shadow · --pill-on-bg/-on-ink · --radius-field/-menu · hover: v2-menuitem">
          <S label="rest · picked" w={240}><Select value={pick} options={OPTIONS} onPick={setPick} ariaLabel="Provider" /></S>
          <S label="placeholder" w={240}><Select value="" options={OPTIONS} onPick={() => {}} placeholder="Pick a provider…" ariaLabel="Provider" /></S>
          <S label="empty listbox" w={240}><Select value="" options={[]} onPick={() => {}} emptyText="no models for this provider" ariaLabel="Model" /></S>
          <S label="disabled" w={240}><Select value={pick} options={OPTIONS} onPick={() => {}} disabled ariaLabel="Provider" /></S>
        </Role>

        <Role name="Row" canonical="h46 · r7 · pad 0 10 · selected = --row-selected + 3px mark (flush: r0, full-bleed tables)"
          tokens="--row-hover/-selected/-selected-mark/-line · --radius-row · hover: v2-row">
          <div style={{ width: '100%', display: 'flex', flexDirection: 'column', gap: 2 }}>
            <Row onClick={() => setSel(false)}><span style={{ fontSize: 'var(--t-12-5)' }}>Rest — hover me</span></Row>
            <Row selected={sel} onClick={() => setSel((v) => !v)}><span style={{ fontSize: 'var(--t-12-5)' }}>Selected (click to toggle)</span></Row>
            <Row divider onClick={() => {}}><span style={{ fontSize: 'var(--t-12-5)' }}>With a --row-line divider</span></Row>
            <Row><span style={{ fontSize: 'var(--t-12-5)', color: 'var(--helper-ink)' }}>Inert (no onClick — not a tab stop)</span></Row>
            <Row flush divider onClick={() => {}}><span style={{ fontSize: 'var(--t-12-5)' }}>flush — no radius (full-bleed table row)</span></Row>
          </div>
        </Role>

        <Role name="Card · Band" canonical="Card surface · 1px --card-border · r9 · pad 10 14 · Band = dashed sibling"
          tokens="--card-bg/-border/-border-hover/-bg-hover · --band-border · --radius-card · hover: v2-act">
          <S label="card · static" w={230}><Card style={{ width: '100%' }}><Helper>Static card — no hover.</Helper></Card></S>
          <S label="card · interactive" w={230}><Card interactive onClick={() => {}} style={{ width: '100%' }}><Helper>Hover: accent border + wash.</Helper></Card></S>
          <S label="band" w={230}><Band onClick={() => {}} style={{ width: '100%' }}><Helper>Dashed band.</Helper></Band></S>
          <S label="band · static" w={230}><Band interactive={false} style={{ width: '100%' }}><Helper>Dashed, inert.</Helper></Band></S>
        </Role>

        <Role name="DashedAdd" canonical="accent ink · 1px dashed --dashadd-border · r6 · 11.5 · h28 (big: 32/12/500)"
          tokens="--dashadd-ink/-border/-ink-hover/-border-hover/-bg-hover · --radius-field · --t-11-5/-12 · hover: v2-dashadd">
          <S label="rest" w={200}><DashedAdd onClick={() => {}} style={{ width: '100%' }}>+ Add a bullet</DashedAdd></S>
          <S label="big" w={200}><DashedAdd big onClick={() => {}} style={{ width: '100%' }}>+ Add a section</DashedAdd></S>
          <S label="disabled" w={200}><DashedAdd disabled style={{ width: '100%' }}>+ Add a bullet</DashedAdd></S>
        </Role>

        <Role name="Menu · MenuItem" canonical="menu surface · 1px --menu-border · r10 · --menu-shadow · pad 5 — item text-2 · r6 · 12.5 · pad 7 11"
          tokens="--menu-bg/-border/-shadow/-item-ink/-item-hover/-item-danger-ink/-item-danger-hover/-item-sep · --radius-menu/-field · --t-12-5 · hover: v2-menuitem, v2-hover-bad">
          <S label="menu · rest / danger / disabled" w={250}>
            <Menu ariaLabel="Example" style={{ width: '100%' }}>
              <MenuHead>Actions</MenuHead>
              <MenuItem icon="⧉" onClick={() => {}}>Duplicate</MenuItem>
              <MenuItem icon="↗" hint="⌘O" onClick={() => {}}>Open in a tab</MenuItem>
              <MenuItem icon="✦" disabled>Tailor (needs a job)</MenuItem>
              <MenuItem icon="✕" danger onClick={() => {}}>Delete</MenuItem>
            </Menu>
          </S>
        </Role>

        <Role name="SectionHead" canonical="muted · 12.5 · collapsible, aria-expanded"
          tokens="--section-head-ink · --hover-wash-bg/-ink · --radius-field · --t-12-5 · hover: v2-hover-accent">
          <S label="open" w={220}><SectionHead open={open.a} onToggle={() => setOpen((p) => ({ ...p, a: !p.a }))} count={7}>Experience</SectionHead></S>
          <S label="collapsed" w={220}><SectionHead open={open.b} onToggle={() => setOpen((p) => ({ ...p, b: !p.b }))} count={0}>Publications</SectionHead></S>
          <S label="boxed" w={220}><SectionHead boxed open onToggle={() => {}}>Filters</SectionHead></S>
          <S label="static (no toggle)" w={220}><SectionHead>Read-only head</SectionHead></S>
        </Role>

        <Role name="Chip" canonical="--chip-bg · 1px --chip-border · r99 · 11.5 · h26"
          tokens="--chip-bg/-ink/-border/-bg-hover/-ink-hover/-border-hover/-ring-hover · --radius-control · --t-11-5 · hover: v2-chip">
          <S label="interactive"><Chip onClick={() => {}}>⧉ Copy for a job</Chip></S>
          <S label="static"><Chip>base · 4 versions</Chip></S>
          <S label="disabled"><Chip disabled onClick={() => {}}>⧉ Copy</Chip></S>
        </Role>

        <Role name="Tag · Dot" canonical="Tag r99 · 10/15 · pad 2 8 · .06em uppercase — Dot r99 · 7px"
          tokens="--tag-neutral/-accent/-good/-warn/-bad ×(-bg,-ink) · --dot-neutral/-accent/-good/-warn/-bad · --radius-control · --t-10">
          <S label="tag tones">
            <Tag>neutral</Tag><Tag tone="accent">accent</Tag><Tag tone="good">good</Tag><Tag tone="warn">warn</Tag><Tag tone="bad">bad</Tag>
          </S>
          <S label="dot tones">
            <Dot title="neutral" /><Dot tone="accent" title="accent" /><Dot tone="good" title="good" /><Dot tone="warn" title="warn" /><Dot tone="bad" title="bad" />
          </S>
          <S label="dot · 4 / 7 / 11">
            <Dot size={4} /><Dot size={7} /><Dot size={11} />
          </S>
        </Role>

        <Role name="Link · NavLink" canonical="Link accent · 11.5/500 — NavLink accent · 12, hover washes"
          tokens="--link-ink/-ink-hover · --navlink-ink/-hover-bg/-hover-ink · --t-11-5/-12 · hover: v2-hover-accent-text, v2-navlink">
          <S label="link · button"><Link onClick={() => {}}>Clear all filters</Link></S>
          <S label="link · href"><Link href="https://example.com" target="_blank">Open the posting ↗</Link></S>
          <S label="navlink"><NavLink onClick={() => {}}>‹ All résumés</NavLink></S>
          <S label="navlink · padded"><NavLink pad="7px 8px" onClick={() => {}}>Skills</NavLink></S>
        </Role>

        <Role name="HeaderRow" canonical="modal 16 22 13 · screen 22 30 16 · compact 15 22 12, --head-line beneath"
          tokens="--head-line · --head-line-soft">
          <div style={{ width: '100%', display: 'flex', flexDirection: 'column', gap: 10 }}>
            {['modal', 'screen', 'compact'].map((v) => (
              <Card key={v} style={{ padding: 0, overflow: 'hidden' }}>
                <HeaderRow variant={v}>
                  <Heading size={18}>{v}</Heading>
                  <Helper style={{ marginLeft: 'auto' }}>variant=&quot;{v}&quot;</Helper>
                </HeaderRow>
                <div style={{ padding: '10px 22px' }}><Helper size="xs">body</Helper></div>
              </Card>
            ))}
            <Card style={{ padding: 0, overflow: 'hidden' }}>
              <HeaderRow soft><Heading size={18}>soft rule</Heading><Helper style={{ marginLeft: 'auto' }}>soft</Helper></HeaderRow>
              <div style={{ padding: '10px 22px' }}><Helper size="xs">body</Helper></div>
            </Card>
          </div>
        </Role>

        <Role name="ModalPanel · Drawer" canonical="modal surface · 1px --modal-border · r12 · --modal-shadow on --scrim-bg — drawer 720 wide, --drawer-shadow"
          tokens="--modal-bg/-border/-shadow · --scrim-bg · --drawer-bg/-border/-shadow · --radius-modal"
          note="Both close on Escape (useEscape) and on the scrim; the modal panel is snapped to the pixel grid (useSnapTop).">
          <S label="modal"><Button variant="secondary" size="sm" onClick={() => setModal(true)}>Open modal</Button></S>
          <S label="drawer"><Button variant="secondary" size="sm" onClick={() => setDrawer(true)}>Open drawer</Button></S>
          <div style={{ position: 'relative', width: '100%', height: drawer ? 260 : 0, overflow: 'hidden', transition: 'height .12s' }}>
            {drawer && (
              <Drawer width={420} onClose={() => setDrawer(false)}>
                <HeaderRow>
                  <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 3 }}>
                    <Heading size={18}>Drawer</Heading>
                    <Helper>Anchored to its pane, not the viewport.</Helper>
                  </div>
                  <IconButton title="Close" onClick={() => setDrawer(false)}>✕</IconButton>
                </HeaderRow>
                <div style={{ padding: '12px 22px' }}><Helper>Escape or the scrim closes it.</Helper></div>
              </Drawer>
            )}
          </div>
        </Role>

        <Role name="Label · Helper · Heading · PageTitle" canonical="Label 10 uppercase .13em muted · Helper 11.5/16 muted · Heading serif 18/19/22 · PageTitle serif 30/400"
          tokens="--label-ink · --helper-ink · --heading-ink · --font-display/-body/-mono · --t-10/-11/-10-5/-11-5/-18/-19/-22/-30">
          <S label="label · md" w={160}><Label>Work authorisation</Label></S>
          <S label="label · lg" w={160}><Label size="lg">Sources</Label></S>
          <S label="helper · md" w={220}><Helper>Empty sections are skipped in the PDF.</Helper></S>
          <S label="helper · xs" w={220}><Helper size="xs">last run 14 min ago</Helper></S>
          <S label="helper · mono xs" w={220}><Helper size="xs" mono>content_hash 9f2a…</Helper></S>
          <S label="heading 18" w={230}><Heading size={18}>Delete this résumé?</Heading></S>
          <S label="heading 19" w={230}><Heading size={19}>Tailor for a job</Heading></S>
          <S label="heading 22" w={230}><Heading size={22}>Applications</Heading></S>
          <S label="page title" w="100%"><PageTitle>Cover Letters</PageTitle></S>
        </Role>

        <Role name="Spinner · ShowMore" canonical="Spinner 1.5px --spinner-ink · r99 · 9 / 12 — ShowMore h26 pill pager"
          tokens="--spinner-ink · --pill-border/-ink · --radius-control · --t-11-5 · hover: v2-bdc">
          <S label="spinner 9"><Spinner /></S>
          <S label="spinner 12"><Spinner size={12} /></S>
          <S label="spinner · currentColor" ><span style={{ color: 'var(--dot-bad)', display: 'flex', alignItems: 'center', gap: 7 }}><Spinner size={12} color="currentColor" /><Helper style={{ color: 'inherit' }}>inherits the ink</Helper></span></S>
          <S label="show more" w={240}><ShowMore n={96} onClick={() => {}} style={{ width: '100%' }} /></S>
        </Role>

      </div>

      {modal && (
        <ModalPanel width={440} onClose={() => setModal(false)} labelledBy="gallery-modal-title">
          <HeaderRow>
            <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 3 }}>
              <Heading size={19} id="gallery-modal-title">Modal panel</Heading>
              <Helper>Escape, the scrim, or Cancel.</Helper>
            </div>
            <IconButton title="Close" onClick={() => setModal(false)}>✕</IconButton>
          </HeaderRow>
          <div style={{ padding: '14px 22px', display: 'flex', flexDirection: 'column', gap: 10 }}>
            <Label>Name</Label>
            <Input value={text} onChange={setText} ariaLabel="Name" />
            <Helper size="xs">Fields turn their border accent on focus — no ring.</Helper>
          </div>
          <div style={{ padding: '0 22px 18px', display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
            <Button variant="secondary" size="sm" onClick={() => setModal(false)}>Cancel</Button>
            <Button size="sm" onClick={() => setModal(false)}>Save</Button>
          </div>
        </ModalPanel>
      )}
    </div>
  )
}
