import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { axe, toHaveNoViolations } from 'jest-axe'
import Header from '../components/Header.jsx'
import UploadPanel from '../components/UploadPanel.jsx'
import { AuthProvider } from '../context/AuthContext.jsx'
import { ThemeProvider } from '../context/ThemeContext.jsx'

expect.extend(toHaveNoViolations)

function renderHeader(phase = 'results') {
  return render(
    <ThemeProvider>
      <AuthProvider>
        <Header onReset={() => {}} phase={phase} />
      </AuthProvider>
    </ThemeProvider>,
  )
}

describe('accessibility smoke tests (jest-axe)', () => {
  it('Header has no axe violations', async () => {
    const { container } = renderHeader('results')
    expect(await axe(container)).toHaveNoViolations()
  })

  it('UploadPanel generate mode has no axe violations', async () => {
    const { container } = render(<UploadPanel phase="idle" error={null} onSubmit={() => {}} />)
    expect(await axe(container)).toHaveNoViolations()
  })

  it('UploadPanel upload mode has a keyboard-reachable dropzone and no axe violations', async () => {
    const { container } = render(<UploadPanel phase="idle" error={null} onSubmit={() => {}} />)
    fireEvent.click(screen.getByRole('tab', { name: /upload json/i }))
    const dropzone = screen.getByRole('button', { name: /upload json file/i })
    expect(dropzone).toHaveAttribute('tabindex', '0')
    expect(await axe(container)).toHaveNoViolations()
  })

  it('UploadPanel paste mode has no axe violations', async () => {
    const { container } = render(<UploadPanel phase="idle" error={null} onSubmit={() => {}} />)
    fireEvent.click(screen.getByRole('tab', { name: /paste json/i }))
    expect(await axe(container)).toHaveNoViolations()
  })
})

describe('keyboard tab navigation', () => {
  it('arrow keys move between UploadPanel mode tabs', () => {
    vi.spyOn(HTMLButtonElement.prototype, 'focus')
    render(<UploadPanel phase="idle" error={null} onSubmit={() => {}} />)
    const generate = screen.getByRole('tab', { name: /generate/i })
    generate.focus()
    const tablist = generate.closest('[role="tablist"]')
    fireEvent.keyDown(tablist, { key: 'ArrowRight' })
    expect(screen.getByRole('tab', { name: /upload json/i })).toHaveAttribute(
      'aria-selected',
      'true',
    )
    fireEvent.keyDown(tablist, { key: 'ArrowRight' })
    expect(screen.getByRole('tab', { name: /paste json/i })).toHaveAttribute(
      'aria-selected',
      'true',
    )
    fireEvent.keyDown(tablist, { key: 'ArrowLeft' })
    expect(screen.getByRole('tab', { name: /upload json/i })).toHaveAttribute(
      'aria-selected',
      'true',
    )
    fireEvent.keyDown(tablist, { key: 'Home' })
    expect(screen.getByRole('tab', { name: /generate/i })).toHaveAttribute('aria-selected', 'true')
    fireEvent.keyDown(tablist, { key: 'End' })
    expect(screen.getByRole('tab', { name: /paste json/i })).toHaveAttribute(
      'aria-selected',
      'true',
    )
  })

  it('activating a tab shows the matching tabpanel', () => {
    render(<UploadPanel phase="idle" error={null} onSubmit={() => {}} />)
    fireEvent.click(screen.getByRole('tab', { name: /paste json/i }))
    const activePanel = screen.getByRole('tabpanel')
    expect(activePanel).toHaveAttribute('id', 'mode-panel-paste')
  })
})
