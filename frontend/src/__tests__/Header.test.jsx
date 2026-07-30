import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import Header from '../components/Header.jsx'
import { AuthProvider } from '../context/AuthContext.jsx'

function renderWithProviders(ui) {
  return render(<AuthProvider>{ui}</AuthProvider>)
}

describe('Header', () => {
  it('renders the app name', () => {
    renderWithProviders(<Header onReset={() => {}} phase="idle" />)
    expect(screen.getByText('Route')).toBeInTheDocument()
  })

  it('renders VRP version badge', () => {
    renderWithProviders(<Header onReset={() => {}} phase="idle" />)
    expect(screen.getByText('VRP v1.0')).toBeInTheDocument()
  })

  it('renders API Docs link', () => {
    renderWithProviders(<Header onReset={() => {}} phase="idle" />)
    const link = screen.getByText('API Docs')
    expect(link).toBeInTheDocument()
    expect(link.closest('a')).toHaveAttribute('href', '/docs')
  })

  it('shows SOLUTION READY when phase is results', () => {
    renderWithProviders(<Header onReset={() => {}} phase="results" />)
    expect(screen.getByText('SOLUTION READY')).toBeInTheDocument()
  })

  it('does not show SOLUTION READY when phase is idle', () => {
    renderWithProviders(<Header onReset={() => {}} phase="idle" />)
    expect(screen.queryByText('SOLUTION READY')).not.toBeInTheDocument()
  })

  it('shows New Job button when phase is not idle', () => {
    renderWithProviders(<Header onReset={() => {}} phase="results" />)
    expect(screen.getByText('← New Job')).toBeInTheDocument()
  })

  it('does not show New Job button when phase is idle', () => {
    renderWithProviders(<Header onReset={() => {}} phase="idle" />)
    expect(screen.queryByText('← New Job')).not.toBeInTheDocument()
  })

  it('calls onReset when New Job is clicked', () => {
    const onReset = vi.fn()
    renderWithProviders(<Header onReset={onReset} phase="results" />)
    fireEvent.click(screen.getByText('← New Job'))
    expect(onReset).toHaveBeenCalledTimes(1)
  })
})
