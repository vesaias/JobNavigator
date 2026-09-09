// The primitives' `busy` state: Tag and GlyphBadge.
//
// The contract is "same box, same ink, the CONTENT is the spinner": a badge that
// starts working must not change size, tone or position, because it sits inline
// in a row of text (the Feed's report band, a résumé tab). So the assertions are
// about what happens to the CHILDREN and what does not happen to the box.
//
// These render for real (@testing-library/react) rather than testing a pure
// helper, because the swap lives in the component's own JSX.
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { GlyphBadge, Tag } from '../ui'

// the spinner draws as a bordered span with the .v2-spin class (arc) or the
// .v2-march band (blocks); either way it is aria-hidden, so query by class
const spinners = (el) => el.querySelectorAll('.v2-spin, .v2-march')

describe('Tag · busy', () => {
  it('replaces the label with a spinner', () => {
    const { container, rerender } = render(<Tag tone="ai">✦ Tailored</Tag>)
    expect(container.textContent).toContain('Tailored')
    expect(spinners(container)).toHaveLength(0)

    rerender(<Tag tone="ai" busy>✦ Tailored</Tag>)
    expect(container.textContent).not.toContain('Tailored')
    expect(spinners(container)).toHaveLength(1)
  })
  it('keeps its ground and its box', () => {
    const { container } = render(<Tag tone="ai" busy>✦ Tailored</Tag>)
    const tag = container.firstChild
    expect(tag.style.background).toBe('var(--tag-ai-bg)')
    expect(tag.style.color).toBe('var(--tag-ai-ink)')
    expect(tag.style.padding).toBe('2px 8px')
  })
  it('reports itself busy to assistive tech', () => {
    const { container } = render(<Tag busy>x</Tag>)
    expect(container.firstChild.getAttribute('aria-busy')).toBe('true')
    render(<Tag>x</Tag>)
    expect(screen.getByText('x').getAttribute('aria-busy')).toBe(null)
  })
})

describe('GlyphBadge · busy', () => {
  it('replaces the glyph with a spinner and keeps the ground/ink', () => {
    const { container, rerender } = render(<GlyphBadge size={22} tone="ai">✦</GlyphBadge>)
    expect(container.textContent).toBe('✦')

    rerender(<GlyphBadge size={22} tone="ai" busy>✦</GlyphBadge>)
    const badge = container.firstChild
    expect(container.textContent).toBe('')
    expect(spinners(container)).toHaveLength(1)
    expect(badge.style.background).toBe('var(--ai)')
    expect(badge.style.color).toBe('var(--ai-ink)')
  })
  it('does not move the box', () => {
    const { container: rest } = render(<GlyphBadge size={22}>✓</GlyphBadge>)
    const { container: busy } = render(<GlyphBadge size={22} busy>✓</GlyphBadge>)
    for (const k of ['width', 'height', 'borderRadius', 'fontSize']) {
      expect(busy.firstChild.style[k]).toBe(rest.firstChild.style[k])
    }
  })
  it('stays clickable-or-not as its own props say, and reports aria-busy', () => {
    const { container } = render(<GlyphBadge size={22} busy title="Tailoring…">✦</GlyphBadge>)
    expect(container.firstChild.getAttribute('aria-busy')).toBe('true')
    expect(container.firstChild.getAttribute('role')).toBe(null)   // no onClick, no button role
  })
})
