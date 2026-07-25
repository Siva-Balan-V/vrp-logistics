import { useState } from 'react'
import { useAuth } from '../context/AuthContext.jsx'
import { Link, useNavigate } from 'react-router-dom'

export default function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      await login(email, password)
      navigate('/')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      minHeight: '100vh', background: 'var(--bg)',
    }}>
      <div style={{
        background: 'var(--bg-1)', border: '1px solid var(--border)',
        borderRadius: 'var(--radius-lg)', padding: '40px', width: '100%',
        maxWidth: '400px',
      }}>
        <h2 style={{
          fontFamily: 'var(--display)', fontSize: 24, marginBottom: 8,
          textAlign: 'center',
        }}>
          Sign in to <span style={{ color: 'var(--accent)' }}>RouteForge</span>
        </h2>
        <p style={{
          fontFamily: 'var(--mono)', fontSize: 12, color: 'var(--text-2)',
          textAlign: 'center', marginBottom: 24,
        }}>
          Vehicle Route Optimization Platform
        </p>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div>
            <label style={{
              display: 'block', fontFamily: 'var(--mono)', fontSize: 11,
              color: 'var(--text-2)', marginBottom: 6,
            }}>Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              style={{
                width: '100%', padding: '10px 12px', background: 'var(--bg-2)',
                border: '1px solid var(--border)', borderRadius: 'var(--radius)',
                color: 'var(--text)', fontFamily: 'var(--body)', fontSize: 14,
              }}
            />
          </div>

          <div>
            <label style={{
              display: 'block', fontFamily: 'var(--mono)', fontSize: 11,
              color: 'var(--text-2)', marginBottom: 6,
            }}>Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={8}
              style={{
                width: '100%', padding: '10px 12px', background: 'var(--bg-2)',
                border: '1px solid var(--border)', borderRadius: 'var(--radius)',
                color: 'var(--text)', fontFamily: 'var(--body)', fontSize: 14,
              }}
            />
          </div>

          {error && (
            <div style={{
              background: 'var(--red-dim)', border: '1px solid var(--red)',
              borderRadius: 'var(--radius)', padding: '10px 14px',
              fontFamily: 'var(--mono)', fontSize: 12, color: 'var(--red)',
            }}>
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            style={{
              padding: '12px', background: 'var(--accent)', color: '#0a0b0e',
              border: 'none', borderRadius: 'var(--radius)', fontFamily: 'var(--mono)',
              fontSize: 13, fontWeight: 600, cursor: loading ? 'wait' : 'pointer',
              opacity: loading ? 0.7 : 1,
            }}
          >
            {loading ? 'Signing in...' : 'Sign In'}
          </button>
        </form>

        <p style={{
          textAlign: 'center', marginTop: 20, fontFamily: 'var(--mono)',
          fontSize: 12, color: 'var(--text-2)',
        }}>
          Don't have an account?{' '}
          <Link to="/register" style={{ color: 'var(--accent)', textDecoration: 'none' }}>
            Create one
          </Link>
        </p>
      </div>
    </div>
  )
}
