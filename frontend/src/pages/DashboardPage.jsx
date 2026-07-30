import { useState, useEffect, useCallback } from 'react'
import { useAuth } from '../context/AuthContext.jsx'
import { useTheme } from '../context/ThemeContext.jsx'
import { getDashboard } from '../api.js'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  LineChart, Line, CartesianGrid, Legend,
} from 'recharts'

export default function DashboardPage() {
  const { token, user, logout } = useAuth()
  const { theme, toggleTheme } = useTheme()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [days, setDays] = useState(30)

  const fetchData = useCallback(async () => {
    try {
      setLoading(true)
      const d = await getDashboard(token, days)
      setData(d)
    } catch {
      setData(null)
    } finally {
      setLoading(false)
    }
  }, [token, days])

  useEffect(() => { fetchData() }, [fetchData])

  const MetricCard = ({ label, value, sub }) => (
    <div style={{
      background: 'var(--bg-1)', border: '1px solid var(--border)',
      borderRadius: 'var(--radius-lg)', padding: '20px 24px', flex: 1, minWidth: 160,
    }}>
      <div style={{ fontSize: 11, fontFamily: 'var(--mono)', color: 'var(--text-3)', marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 28, fontWeight: 700, color: 'var(--text-1)', fontFamily: 'var(--display)' }}>{value}</div>
      {sub && <div style={{ fontSize: 11, color: 'var(--text-2)', marginTop: 4 }}>{sub}</div>}
    </div>
  )

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
          }}>Dashboard</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <a href="/history" style={{
            fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text-3)',
            textDecoration: 'none', padding: '5px 10px',
            border: '1px solid var(--border)', borderRadius: 'var(--radius)'
          }}>History</a>
          <a href="/" style={{
            fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--accent)',
            textDecoration: 'none', padding: '5px 10px',
            border: '1px solid var(--accent)', borderRadius: 'var(--radius)',
          }}>← Optimize</a>
          {user && (
            <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text-2)' }}>
              {user.email}
            </span>
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

      <main style={{ maxWidth: 1100, margin: '0 auto', padding: '32px 24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
          <h1 style={{ fontFamily: 'var(--display)', fontSize: 22, fontWeight: 700, color: 'var(--text-1)' }}>
            Analytics Dashboard
          </h1>
          <select value={days} onChange={(e) => setDays(Number(e.target.value))} style={{
            background: 'var(--bg-2)', color: 'var(--text-1)',
            border: '1px solid var(--border)', borderRadius: 'var(--radius)',
            padding: '6px 12px', fontSize: 12, fontFamily: 'var(--mono)',
          }}>
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
            <option value={365}>Last year</option>
          </select>
        </div>

        {loading && <p style={{ color: 'var(--text-2)' }}>Loading...</p>}

        {!loading && data && (
          <>
            <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginBottom: 32 }}>
              <MetricCard label="Total Jobs" value={data.total_jobs} sub={`${data.success_rate}% success rate`} />
              <MetricCard label="Avg Distance" value={`${data.avg_distance_km} km`} sub="Per job" />
              <MetricCard label="Avg Solver Time" value={`${data.avg_solver_time_s}s`} sub="Per job" />
              <MetricCard label="Avg Vehicles" value={data.avg_vehicles_used} sub="Per job" />
              <MetricCard label="Locations Served" value={data.total_locations_served} sub="All time" />
            </div>

            {data.daily_trend.length > 0 && (
              <div style={{
                background: 'var(--bg-1)', border: '1px solid var(--border)',
                borderRadius: 'var(--radius-lg)', padding: 24, marginBottom: 24,
              }}>
                <h2 style={{ fontSize: 14, fontWeight: 600, marginBottom: 16, color: 'var(--text-1)', fontFamily: 'var(--mono)' }}>
                  Daily Job Volume
                </h2>
                <ResponsiveContainer width="100%" height={250}>
                  <BarChart data={data.daily_trend}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                    <XAxis dataKey="date" tick={{ fontSize: 10, fill: 'var(--text-3)' }} />
                    <YAxis tick={{ fontSize: 10, fill: 'var(--text-3)' }} />
                    <Tooltip />
                    <Bar dataKey="jobs" fill="var(--accent)" radius={[4, 4, 0, 0]} name="Jobs" />
                  </BarChart>
                </ResponsiveContainer>

                <h2 style={{ fontSize: 14, fontWeight: 600, marginTop: 24, marginBottom: 16, color: 'var(--text-1)', fontFamily: 'var(--mono)' }}>
                  Daily Distance Trend
                </h2>
                <ResponsiveContainer width="100%" height={250}>
                  <LineChart data={data.daily_trend}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                    <XAxis dataKey="date" tick={{ fontSize: 10, fill: 'var(--text-3)' }} />
                    <YAxis tick={{ fontSize: 10, fill: 'var(--text-3)' }} />
                    <Tooltip />
                    <Legend />
                    <Line type="monotone" dataKey="distance_km" stroke="#f5a623" name="Distance (km)" strokeWidth={2} dot={false} />
                    <Line type="monotone" dataKey="locations" stroke="var(--accent)" name="Locations" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}

            {data.recent_jobs.length > 0 && (
              <div style={{
                background: 'var(--bg-1)', border: '1px solid var(--border)',
                borderRadius: 'var(--radius-lg)', padding: 24,
              }}>
                <h2 style={{ fontSize: 14, fontWeight: 600, marginBottom: 16, color: 'var(--text-1)', fontFamily: 'var(--mono)' }}>
                  Recent Jobs
                </h2>
                {data.recent_jobs.map((j) => (
                  <div key={j.job_id} style={{
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    padding: '8px 0', borderBottom: '1px solid var(--border)', fontSize: 12,
                  }}>
                    <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text-2)' }}>
                      {j.job_id.slice(0, 8)}
                    </span>
                    <span style={{ color: j.status === 'success' ? 'var(--green)' : 'var(--text-3)' }}>
                      {j.status}
                    </span>
                    <span style={{ color: 'var(--text-1)' }}>{j.total_locations} locs</span>
                    <span style={{ color: 'var(--text-2)' }}>
                      {j.total_distance_km != null ? `${j.total_distance_km.toFixed(1)} km` : '—'}
                    </span>
                    <a href={`/?job=${j.job_id}`} style={{ color: 'var(--accent)', textDecoration: 'none' }}>View</a>
                  </div>
                ))}
              </div>
            )}
          </>
        )}

        {!loading && !data && (
          <p style={{ color: 'var(--text-2)', fontFamily: 'var(--mono)', fontSize: 13 }}>
            No data available. Run some optimizations to populate the dashboard.
          </p>
        )}
      </main>
    </div>
  )
}
