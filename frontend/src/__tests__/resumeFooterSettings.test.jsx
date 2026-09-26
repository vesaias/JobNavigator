import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { PERSONA_SECTIONS, SECTION_ORDER, SectionEditor } from '../screens/ResumeSections'

describe('résumé footer settings', () => {
  it('shows Settings only in résumé editor and saves the footer switch', () => {
    expect(SECTION_ORDER.at(-1)).toBe('Settings')
    expect(PERSONA_SECTIONS).not.toContain('Settings')
    const setField = vi.fn()
    render(<SectionEditor name="Settings" data={{}} setField={setField} />)
    fireEvent.click(screen.getByRole('checkbox', { name: /Show footer/ }))
    expect(setField).toHaveBeenCalledWith('footer_enabled', false)
  })
})
