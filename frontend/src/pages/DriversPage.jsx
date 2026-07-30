import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'
import { useTheme } from '../context/ThemeContext.jsx'
import { listDrivers, createDriver } from '../api.js'

const STATUS_COLORS = {
  offline: 'var(--text-3)',
  active: 'var(--green)',
  on_route: 'var(--accent)',
}

export default function DriversPage() {
  const { token, user, logout } = useAuth()
  const { theme, toggleTheme } = useTheme()
  const navigate = useNavigate()
  const [drivers, setDrivers] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [name, setName] = useState('')
  const [phone, setPhone] = useState('')

  const fetch = useCallback(async () => {
    try {
      setLoading(true)
      setDrivers((await listDrivers(token)) || [])
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => { fetch() }, [fetch])

  const handleCreate = async () => {
    if (!name.trim() || !phone.trim()) return
    try {
      await createDriver(name.trim(), phone.trim(), token)
      setName('')
      setPhone('')
      setShowForm(false)
      await fetch()
    } catch {}
  }

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)' }}>
      <header style={{
        height: 64, background: 'var(--bg-1)',
        borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center',
        justifyContent: 'space-between', padding: '0 24px',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontFamily: 'var(--display)', fontWeight: 800, fontSize: 18, letterSpacing: '-0.03em' }}>
            Route<span style={{ color: 'var(--accent)' }}>Forge</span>
          </span>
          <span style={{
            fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--text-3)',
            background: 'var(--bg-3)', border: '1px solid var(--border)',
            padding: '2px 7px', borderRadius: 4,
          }}>Drivers</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <a href="/dashboard" style={{
            fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text-3)',
            textDecoration: 'none', padding: '5px 10px',
            border: '1px solid var(--border)', borderRadius: 'var(--radius)'
          }}>Dashboard</a>
          <a href="/" style={{
            fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--accent)',
            textDecoration: 'none', padding: '5px 10px',
            border: '1px solid var(--accent)', borderRadius: 'var(--radius)',
          }}>← Optimize</a>
          {user && (
            <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text-2)' }}>{user.email}</span>
          )}
          {user && (
            <button onClick={logout} style={{
              background: 'var(--bg-3)', color: 'var(--text-2)',
              border: '1px solid var(--border)', borderRadius: 'var(--radius)',
              padding: '6px 14px', fontSize: 12,
            }}>Logout</button>
          )}
          <button onClick={toggleTheme} style={{
            background: 'none', color: 'var(--text-3)',
            border: '1px solid var(--border)', borderRadius: 'var(--radius)',
            padding: '5px 10px', fontSize: 14,
          }}>
            {theme === 'dark' ? '☀' : '☾'}
          </button>
        </div>
      </header>

      <main style={{ maxWidth: 960, margin: '0 auto', padding: '32px 24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
          <h1 style={{ fontFamily: 'var(--display)', fontSize: 22, fontWeight: 700, color: 'var(--text-1)' }}>
            Drivers
          </h1>
          <button onClick={() => setShowForm(!showForm)} style={{
            background: 'var(--accent)', color: '#000', fontWeight: 600,
            border: 'none', borderRadius: 'var(--radius)',
            padding: '8px 16px', fontSize: 12, cursor: 'pointer',
          }}>
            {showForm ? 'Cancel' : '+ Add Driver'}
          </button>
        </div>

        {showForm && (
          <div style={{
            background: 'var(--bg-1)', border: '1px solid var(--border)',
            borderRadius: 'var(--radius-lg)', padding: '20px 24px', marginBottom: 24,
            display: 'flex', gap: 12, alignItems: 'end',
          }}>
            <div>
              <label style={{ fontSize: 11, fontFamily: 'var(--mono)', color: 'var(--text-3)', display: 'block', marginBottom: 4 }}>Name</label>
              <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Driver name" style={{
                background: 'var(--bg-2)', color: 'var(--text-1)',
                border: '1px solid var(--border)', borderRadius: 'var(--radius)',
                padding: '8px 12px', fontSize: 13, width: 200,
              }} />
            </div>
            <div>
              <label style={{ fontSize: 11, fontFamily: 'var(--mono)', color: 'var(--text-3)', display: 'block', marginBottom: 4 }}>Phone</label>
              <input value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+1234567890" style={{
                background: 'var(--bg-2)', color: 'var(--text-1)',
                border: '1px solid var(--border)', borderRadius: 'var(--radius)',
                padding: '8px 12px', fontSize: 13, width: 180,
              }} />
            </div>
            <button onClick={handleCreate} style={{
              background: 'var(--accent)', color: '#000', fontWeight: 600,
              border: 'none', borderRadius: 'var(--radius)',
              padding: '8px 20px', fontSize: 12, cursor: 'pointer',
            }}>Save</button>
          </div>
        )}

        {loading && <p style={{ color: 'var(--text-2)' }}>Loading...</p>}

        {!loading && drivers.length === 0 && (
          <p style={{ color: 'var(--text-2)', fontFamily: 'var(--mono)', fontSize: 13 }}>
            No drivers yet. Add one to get started.
          </p>
        )}

        {!loading && drivers.length > 0 && (
          <div style={{
            background: 'var(--bg-1)', borderRadius: 'var(--radius-lg)',
            border: '1px solid var(--border)', overflow: 'hidden',
          }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, fontFamily: 'var(--mono)' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border)', background: 'var(--bg-2)' }}>
                  <th style={{ padding: '10px 14px', textAlign: 'left', color: 'var(--text-3)' }}>Status</th>
                  <th style={{ padding: '10px 14px', textAlign: 'left', color: 'var(--text-3)' }}>Name</th>
                  <th style={{ padding: '10px 14px', textAlign: 'left', color: 'var(--text-3)' }}>Phone</th>
                  <th style={{ padding: '10px 14px', textAlign: 'right', color: 'var(--text-3)' }}>Last Ping</th>
                  <th style={{ padding: '10px 14px', textAlign: 'center', color: 'var(--text-3)' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {drivers.map((d) => (
                  <tr key={d.id} style={{ borderBottom: '1px solid var(--border)' }}>
                    <td style={{ padding: '10px 14px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <div style={{
                          width: 8, height: 8, borderRadius: '50%',
                          background: STATUS_COLORS[d.status] || 'var(--text-3)',
                        }} />
                        <span style={{ color: 'var(--text-1)' }}>{d.status}</span>
                      </div>
                    </td>
                    <td style={{ padding: '10px 14px', color: 'var(--text-1)', fontWeight: 500 }}>{d.name}</td>
                    <td style={{ padding: '10px 14px', color: 'var(--text-2)' }}>{d.phone}</td>
                    <td style={{ padding: '10px 14px', textAlign: 'right', color: 'var(--text-2)' }}>
                      {d.last_ping_at ? new Date(d.last_ping_at).toLocaleString() : '—'}
                    </td>
                    <td style={{ padding: '10px 14px', textAlign: 'center' }}>
                      <button onClick={() => navigate(`/drivers/${d.id}`)} style={{
                        background: 'var(--bg-3)', color: 'var(--accent)',
                        border: '1px solid var(--border)', borderRadius: 'var(--radius)',
                        padding: '4px 10px', fontSize: 11, cursor: 'pointer',
                      }}>View</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </div>
  )
}
