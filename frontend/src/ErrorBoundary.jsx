import { Component } from 'react'

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false }
  }

  static getDerivedStateFromError() {
    return { hasError: true }
  }

  componentDidCatch(error, errorInfo) {
    console.error('ErrorBoundary caught:', error, errorInfo)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          display: 'flex', flexDirection: 'column', alignItems: 'center',
          justifyContent: 'center', gap: 16, padding: 40, minHeight: '100vh',
          background: 'var(--bg)', color: 'var(--text)',
        }}>
          <h2 style={{ fontFamily: 'var(--display)', fontSize: 24 }}>
            Something went wrong
          </h2>
          <p style={{ color: 'var(--text-2)', fontFamily: 'var(--mono)', fontSize: 13 }}>
            An unexpected error occurred. Please try again.
          </p>
          <button
            onClick={() => {
              this.setState({ hasError: false })
              this.props.onReset?.()
            }}
            style={{
              marginTop: 8, padding: '10px 24px', borderRadius: 'var(--radius)',
              background: 'var(--accent)', color: '#0a0b0e', fontWeight: 600,
              fontFamily: 'var(--mono)', fontSize: 13, cursor: 'pointer',
            }}
          >
            Try Again
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
