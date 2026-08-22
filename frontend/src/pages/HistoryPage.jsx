import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'
import { useTheme } from '../context/ThemeContext.jsx'
import { listJobs } from '../api.js'
import PageHeader from '../components/PageHeader.jsx'

export default function HistoryPage() {
  const { token, user, logout } = useAuth()
  const { theme, toggleTheme } = useTheme()
  const navigate = useNavigate()
  const [jobs, setJobs] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetchJobs = useCallback(async () => {
    try {
      setLoading(true)
      const data = await listJobs(token)
      setJobs(data.jobs || [])
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => {
    fetchJobs()
  }, [fetchJobs])

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)' }}>
      <PageHeader badge="History" />

      <main style={{ maxWidth: 960, margin: '0 auto', padding: '32px 24px' }}>
        <h1
          style={{
            fontFamily: 'var(--display)',
            fontSize: 22,
            fontWeight: 700,
            marginBottom: 24,
            color: 'var(--text-1)',
          }}
        >
          Optimization History
        </h1>

        {loading && <p style={{ color: 'var(--text-2)' }}>Loading...</p>}
        {error && <p style={{ color: 'var(--red)' }}>{error}</p>}

        {!loading && !error && jobs.length === 0 && (
          <p style={{ color: 'var(--text-2)', fontFamily: 'var(--mono)', fontSize: 13 }}>
            No optimization jobs yet. Run an optimization to see it here.
          </p>
        )}

        {!loading && jobs.length > 0 && (
          <div
            style={{
              background: 'var(--bg-1)',
              borderRadius: 'var(--radius-lg)',
              border: '1px solid var(--border)',
              overflow: 'hidden',
            }}
          >
            <table
              style={{
                width: '100%',
                borderCollapse: 'collapse',
                fontSize: 12,
                fontFamily: 'var(--mono)',
              }}
            >
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border)', background: 'var(--bg-2)' }}>
                  <th style={{ padding: '10px 14px', textAlign: 'left', color: 'var(--text-3)' }}>
                    Date
                  </th>
                  <th style={{ padding: '10px 14px', textAlign: 'left', color: 'var(--text-3)' }}>
                    Job ID
                  </th>
                  <th style={{ padding: '10px 14px', textAlign: 'left', color: 'var(--text-3)' }}>
                    Status
                  </th>
                  <th style={{ padding: '10px 14px', textAlign: 'right', color: 'var(--text-3)' }}>
                    Locs
                  </th>
                  <th style={{ padding: '10px 14px', textAlign: 'right', color: 'var(--text-3)' }}>
                    Vehicles
                  </th>
                  <th style={{ padding: '10px 14px', textAlign: 'right', color: 'var(--text-3)' }}>
                    Distance
                  </th>
                  <th style={{ padding: '10px 14px', textAlign: 'right', color: 'var(--text-3)' }}>
                    Solver
                  </th>
                  <th style={{ padding: '10px 14px', textAlign: 'center', color: 'var(--text-3)' }}>
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody>
                {jobs.map((job) => (
                  <tr key={job.job_id} style={{ borderBottom: '1px solid var(--border)' }}>
                    <td style={{ padding: '10px 14px', color: 'var(--text-2)' }}>
                      {job.created_at ? new Date(job.created_at).toLocaleDateString() : '—'}
                    </td>
                    <td style={{ padding: '10px 14px', color: 'var(--text-2)', fontSize: 11 }}>
                      {job.job_id.slice(0, 8)}...
                    </td>
                    <td style={{ padding: '10px 14px' }}>
                      <span
                        style={{
                          color: job.status === 'success' ? 'var(--green)' : 'var(--text-3)',
                        }}
                      >
                        {job.status}
                      </span>
                    </td>
                    <td
                      style={{ padding: '10px 14px', textAlign: 'right', color: 'var(--text-1)' }}
                    >
                      {job.total_locations ?? '—'}
                      {job.unassigned_count > 0 && (
                        <span style={{ color: 'var(--red)', marginLeft: 4 }}>
                          ({job.unassigned_count} un)
                        </span>
                      )}
                    </td>
                    <td
                      style={{ padding: '10px 14px', textAlign: 'right', color: 'var(--text-1)' }}
                    >
                      {job.vehicles_used ?? '—'}
                    </td>
                    <td
                      style={{ padding: '10px 14px', textAlign: 'right', color: 'var(--text-1)' }}
                    >
                      {job.total_distance_km != null
                        ? `${job.total_distance_km.toFixed(1)} km`
                        : '—'}
                    </td>
                    <td
                      style={{ padding: '10px 14px', textAlign: 'right', color: 'var(--text-2)' }}
                    >
                      {job.solver_time_seconds != null
                        ? `${job.solver_time_seconds.toFixed(2)}s`
                        : '—'}
                    </td>
                    <td style={{ padding: '10px 14px', textAlign: 'center' }}>
                      <button
                        onClick={() => navigate(`/?job=${job.job_id}`)}
                        style={{
                          background: 'var(--bg-3)',
                          color: 'var(--accent)',
                          border: '1px solid var(--border)',
                          borderRadius: 'var(--radius)',
                          padding: '4px 10px',
                          fontSize: 11,
                          cursor: 'pointer',
                        }}
                      >
                        View
                      </button>
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
