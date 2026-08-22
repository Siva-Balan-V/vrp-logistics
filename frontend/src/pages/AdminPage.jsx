import { useState, useEffect, useCallback } from 'react'
import { useAuth } from '../context/AuthContext.jsx'
import { useTheme } from '../context/ThemeContext.jsx'
import { listAdminCompanies, getAdminCompany, updateCompanyPlan } from '../api.js'
import PageHeader from '../components/PageHeader.jsx'

export default function AdminPage() {
  const { token, user, logout } = useAuth()
  const { theme, toggleTheme } = useTheme()
  const [companies, setCompanies] = useState([])
  const [selected, setSelected] = useState(null)
  const [loading, setLoading] = useState(true)

  const fetchCompanies = useCallback(async () => {
    try {
      setLoading(true)
      setCompanies(await listAdminCompanies(token))
    } catch {
      // failed to load companies — leave list empty
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => {
    fetchCompanies()
  }, [fetchCompanies])

  const viewCompany = async (id) => {
    try {
      const detail = await getAdminCompany(id, token)
      setSelected(detail)
    } catch {
      // failed to load company detail — keep previous selection
    }
  }

  const changePlan = async (companyId, plan) => {
    try {
      await updateCompanyPlan(companyId, plan, token)
      await viewCompany(companyId)
      await fetchCompanies()
    } catch (e) {
      alert('Failed: ' + e.message)
    }
  }

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)' }}>
      <PageHeader badge="Admin" />

      <main
        style={{
          maxWidth: 1200,
          margin: '0 auto',
          padding: '32px 24px',
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: 24,
        }}
      >
        <div>
          <h1
            style={{
              fontFamily: 'var(--display)',
              fontSize: 22,
              fontWeight: 700,
              color: 'var(--text-1)',
              marginBottom: 16,
            }}
          >
            Companies
          </h1>
          {loading && <p style={{ color: 'var(--text-2)', fontSize: 12 }}>Loading...</p>}
          {!loading && (
            <div
              style={{
                background: 'var(--bg-1)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius-lg)',
                overflow: 'hidden',
              }}
            >
              <table
                style={{
                  width: '100%',
                  borderCollapse: 'collapse',
                  fontSize: 11,
                  fontFamily: 'var(--mono)',
                }}
              >
                <thead>
                  <tr
                    style={{ borderBottom: '1px solid var(--border)', background: 'var(--bg-2)' }}
                  >
                    <th style={{ padding: '8px 10px', textAlign: 'left', color: 'var(--text-3)' }}>
                      Name
                    </th>
                    <th style={{ padding: '8px 10px', textAlign: 'left', color: 'var(--text-3)' }}>
                      Plan
                    </th>
                    <th style={{ padding: '8px 10px', textAlign: 'right', color: 'var(--text-3)' }}>
                      Users
                    </th>
                    <th style={{ padding: '8px 10px', textAlign: 'right', color: 'var(--text-3)' }}>
                      Opts
                    </th>
                    <th
                      style={{ padding: '8px 10px', textAlign: 'center', color: 'var(--text-3)' }}
                    ></th>
                  </tr>
                </thead>
                <tbody>
                  {companies.map((c) => (
                    <tr
                      key={c.id}
                      style={{ borderBottom: '1px solid var(--border)', cursor: 'pointer' }}
                      onClick={() => viewCompany(c.id)}
                    >
                      <td style={{ padding: '8px 10px', color: 'var(--text-1)', fontWeight: 500 }}>
                        {c.name}
                      </td>
                      <td style={{ padding: '8px 10px' }}>
                        <span
                          style={{
                            background:
                              c.plan === 'enterprise'
                                ? 'var(--accent-dim)'
                                : c.plan === 'pro'
                                  ? 'var(--bg-3)'
                                  : 'var(--bg-2)',
                            color: c.plan === 'enterprise' ? 'var(--accent)' : 'var(--text-2)',
                            padding: '2px 6px',
                            borderRadius: 3,
                            fontSize: 10,
                          }}
                        >
                          {c.plan}
                        </span>
                      </td>
                      <td
                        style={{ padding: '8px 10px', textAlign: 'right', color: 'var(--text-2)' }}
                      >
                        {c.users}
                      </td>
                      <td
                        style={{ padding: '8px 10px', textAlign: 'right', color: 'var(--text-2)' }}
                      >
                        {c.optimizations}
                      </td>
                      <td
                        style={{ padding: '8px 10px', textAlign: 'center', color: 'var(--text-3)' }}
                      >
                        →
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div>
          <h1
            style={{
              fontFamily: 'var(--display)',
              fontSize: 22,
              fontWeight: 700,
              color: 'var(--text-1)',
              marginBottom: 16,
            }}
          >
            Company Detail
          </h1>
          {selected ? (
            <div
              style={{
                background: 'var(--bg-1)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius-lg)',
                padding: 20,
              }}
            >
              <h2
                style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-1)', marginBottom: 8 }}
              >
                {selected.name}
              </h2>
              <div
                style={{
                  fontFamily: 'var(--mono)',
                  fontSize: 11,
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 6,
                  marginBottom: 16,
                }}
              >
                <span style={{ color: 'var(--text-2)' }}>
                  Plan:{' '}
                  <strong style={{ color: 'var(--accent)', textTransform: 'capitalize' }}>
                    {selected.plan}
                  </strong>
                </span>
                <span style={{ color: 'var(--text-3)' }}>
                  Stripe ID: {selected.stripe_customer_id || '—'}
                </span>
                <span style={{ color: 'var(--text-3)' }}>
                  Total optimizations: {selected.total_optimizations}
                </span>
              </div>

              <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
                {['free', 'pro', 'enterprise'].map((p) => (
                  <button
                    key={p}
                    onClick={() => changePlan(selected.id, p)}
                    disabled={selected.plan === p}
                    style={{
                      background: selected.plan === p ? 'var(--bg-3)' : 'var(--bg-2)',
                      color: selected.plan === p ? 'var(--text-3)' : 'var(--text-1)',
                      border: `1px solid ${selected.plan === p ? 'var(--border)' : 'var(--accent)'}`,
                      borderRadius: 'var(--radius)',
                      padding: '6px 12px',
                      fontSize: 11,
                      cursor: 'pointer',
                      textTransform: 'capitalize',
                    }}
                  >
                    {p}
                  </button>
                ))}
              </div>

              <h3
                style={{
                  fontSize: 12,
                  fontWeight: 600,
                  color: 'var(--text-1)',
                  fontFamily: 'var(--mono)',
                  marginBottom: 8,
                }}
              >
                Users ({selected.users.length})
              </h3>
              <div style={{ fontFamily: 'var(--mono)', fontSize: 11 }}>
                {selected.users.map((u) => (
                  <div
                    key={u.id}
                    style={{
                      padding: '6px 0',
                      borderBottom: '1px solid var(--border)',
                      display: 'flex',
                      gap: 8,
                      color: 'var(--text-2)',
                    }}
                  >
                    <span>{u.email}</span>
                    <span style={{ color: 'var(--text-3)', marginLeft: 'auto' }}>{u.role}</span>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <p style={{ color: 'var(--text-2)', fontFamily: 'var(--mono)', fontSize: 12 }}>
              Select a company to view details.
            </p>
          )}
        </div>
      </main>
    </div>
  )
}
