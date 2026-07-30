import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import ErrorBoundary from '../ErrorBoundary.jsx'

const GoodChild = () => <div>Working content</div>

const BadChild = () => {
  throw new Error('Test error')
}

beforeEach(() => {
  vi.spyOn(console, 'error').mockImplementation(() => {})
})

describe('ErrorBoundary', () => {
  it('renders children when no error', () => {
    render(
      <ErrorBoundary>
        <GoodChild />
      </ErrorBoundary>
    )
    expect(screen.getByText('Working content')).toBeInTheDocument()
  })

  it('renders fallback UI when child throws', () => {
    render(
      <ErrorBoundary>
        <BadChild />
      </ErrorBoundary>
    )
    expect(screen.getByText('Something went wrong')).toBeInTheDocument()
    expect(screen.getByText('An unexpected error occurred. Please try again.')).toBeInTheDocument()
  })

  it('renders Try Again button on error', () => {
    render(
      <ErrorBoundary>
        <BadChild />
      </ErrorBoundary>
    )
    expect(screen.getByText('Try Again')).toBeInTheDocument()
  })

  it('calls onReset when Try Again is clicked', () => {
    const onReset = vi.fn()
    render(
      <ErrorBoundary onReset={onReset}>
        <BadChild />
      </ErrorBoundary>
    )
    fireEvent.click(screen.getByText('Try Again'))
    expect(onReset).toHaveBeenCalledTimes(1)
  })
})
