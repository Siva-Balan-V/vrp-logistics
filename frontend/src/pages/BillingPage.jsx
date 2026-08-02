import { useState, useEffect, useCallback } from 'react'
import { useAuth } from '../context/AuthContext.jsx'
import { useTheme } from '../context/ThemeContext.jsx'
import { listPlans, getUsage, createCheckoutSession, createPortalSession } from '../api.js'

export default function BillingPage() {
  const { token, user, logout } = useAuth()
  const { theme, toggleTheme } = useTheme()
  const [plans, setPlans] = useState([])
  const [usage, setUsage] = useState(null)
  const [loading, setLoading] = useState(true)

  const fetchData = useCallback(async () => {
    try {
      setLoading(true)
      const [p, u] = await Promise.all([listPlans(token), getUsage(token)])
      setPlans(p.plans || [])
      setUsage(u)
    } catch {
      // failed to load plans/usage — leave panels empty
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  const handleUpgrade = async (planId) => {
    try {
      const session = await createCheckoutSession(planId, token)
      if (session?.url) window.location.href = session.url
    } catch (e) {
      alert('Checkout failed: ' + e.message)
    }
  }

  const handlePortal = async () => {
    try {
      const res = await createPortalSession(token)
      if (res?.url) window.location.href = res.url
    } catch (e) {
      alert('Portal failed: ' + e.message)
    }
  }

  const inputStyle = {
    background: 'var(--bg-2)',
    color: 'var(--text-1)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius)',
    padding: '7px 10px',
    fontSize: 12,
    fontFamily: 'var(--mono)',
  }

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)' }}>
      <header
        style={{
          height: 64,
          background: 'var(--bg-1)',
          borderBottom: '1px solid var(--border)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 24px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span
            style={{
              fontFamily: 'var(--display)',
              fontWeight: 800,
              fontSize: 18,
              letterSpacing: '-0.03em',
            }}
          >
            Route<span style={{ color: 'var(--accent)' }}>Forge</span>
          </span>
          <span
            style={{
              fontFamily: 'var(--mono)',
              fontSize: 10,
              color: 'var(--text-3)',
              background: 'var(--bg-3)',
              border: '1px solid var(--border)',
              padding: '2px 7px',
              borderRadius: 4,
            }}
          >
            Billing
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <a
            href="/dashboard"
            style={{
              fontFamily: 'var(--mono)',
              fontSize: 11,
              color: 'var(--text-3)',
              textDecoration: 'none',
              padding: '5px 10px',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius)',
            }}
          >
            Dashboard
          </a>
          <a
            href="/"
            style={{
              fontFamily: 'var(--mono)',
              fontSize: 11,
              color: 'var(--accent)',
              textDecoration: 'none',
            }}
          >
            ← Optimize
          </a>
          {user && (
            <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text-2)' }}>
              {user.email}
            </span>
          )}
          <button
            onClick={toggleTheme}
            style={{
              background: 'none',
              color: 'var(--text-3)',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius)',
              padding: '5px 10px',
              fontSize: 14,
            }}
          >
            {theme === 'dark' ? '☀' : '☾'}
          </button>
        </div>
      </header>

      <main style={{ maxWidth: 960, margin: '0 auto', padding: '32px 24px' }}>
        <h1
          style={{
            fontFamily: 'var(--display)',
            fontSize: 22,
            fontWeight: 700,
            color: 'var(--text-1)',
            marginBottom: 24,
          }}
        >
          Subscription & Billing
        </h1>

        {loading && <p style={{ color: 'var(--text-2)' }}>Loading...</p>}

        {usage && (
          <div
            style={{
              background: 'var(--bg-1)',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius-lg)',
              padding: 20,
              marginBottom: 24,
            }}
          >
            <h2
              style={{
                fontSize: 14,
                fontWeight: 600,
                marginBottom: 12,
                color: 'var(--text-1)',
                fontFamily: 'var(--mono)',
              }}
            >
              Current Plan:{' '}
              <span style={{ textTransform: 'capitalize', color: 'var(--accent)' }}>
                {usage.plan}
              </span>
            </h2>
            <div style={{ display: 'flex', gap: 24, fontFamily: 'var(--mono)', fontSize: 12 }}>
              <div>
                <span style={{ color: 'var(--text-3)' }}>Optimizations this month: </span>
                <span style={{ color: 'var(--text-1)' }}>
                  {usage.monthly_optimizations_used} / {usage.monthly_optimizations_limit}
                </span>
              </div>
              <div>
                <span style={{ color: 'var(--text-3)' }}>Max locations/job: </span>
                <span style={{ color: 'var(--text-1)' }}>{usage.max_locations_per_job}</span>
              </div>
              <div>
                <span style={{ color: 'var(--text-3)' }}>Export: </span>
                <span style={{ color: usage.export_enabled ? 'var(--green)' : 'var(--text-3)' }}>
                  {usage.export_enabled ? 'Enabled' : 'Not available'}
                </span>
              </div>
            </div>
          </div>
        )}

        <div
          style={{
            display: 'grid',
            gap: 16,
            gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
          }}
        >
          {plans.map((plan) => {
            const isCurrent = usage?.plan === plan.id
            return (
              <div
                key={plan.id}
                style={{
                  background: isCurrent ? 'var(--accent-dim)' : 'var(--bg-1)',
                  border: `1px solid ${isCurrent ? 'var(--accent)' : 'var(--border)'}`,
                  borderRadius: 'var(--radius-lg)',
                  padding: 24,
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 12,
                }}
              >
                <h3
                  style={{
                    fontSize: 16,
                    fontWeight: 700,
                    color: 'var(--text-1)',
                    fontFamily: 'var(--display)',
                  }}
                >
                  {plan.name}
                </h3>
                <div
                  style={{
                    fontSize: 28,
                    fontWeight: 700,
                    color: 'var(--accent)',
                    fontFamily: 'var(--display)',
                  }}
                >
                  ${(plan.price_monthly / 100).toFixed(0)}
                  <span style={{ fontSize: 12, color: 'var(--text-3)', fontWeight: 400 }}>/mo</span>
                </div>
                <div
                  style={{
                    fontFamily: 'var(--mono)',
                    fontSize: 11,
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 6,
                  }}
                >
                  <span style={{ color: 'var(--text-2)' }}>
                    📊{' '}
                    {plan.max_optimizations_per_month === 10000
                      ? 'Unlimited'
                      : plan.max_optimizations_per_month}{' '}
                    optimizations/mo
                  </span>
                  <span style={{ color: 'var(--text-2)' }}>
                    📍 Up to {plan.max_locations_per_job} locations/job
                  </span>
                  <span style={{ color: 'var(--text-2)' }}>
                    🗺 {plan.allowed_backends.join(', ')} routing
                  </span>
                  <span style={{ color: plan.export_enabled ? 'var(--green)' : 'var(--text-3)' }}>
                    📤 Export: {plan.export_enabled ? 'Yes' : 'No'}
                  </span>
                  <span style={{ color: plan.priority_support ? 'var(--green)' : 'var(--text-3)' }}>
                    🎧 Priority support: {plan.priority_support ? 'Yes' : 'No'}
                  </span>
                  <span style={{ color: 'var(--text-2)' }}>👥 Up to {plan.max_users} users</span>
                </div>
                {plan.id !== 'free' && (
                  <button
                    onClick={() => handleUpgrade(plan.id)}
                    disabled={isCurrent}
                    style={{
                      background: isCurrent ? 'var(--bg-3)' : 'var(--accent)',
                      color: isCurrent ? 'var(--text-3)' : '#000',
                      border: 'none',
                      borderRadius: 'var(--radius)',
                      padding: '10px',
                      fontSize: 12,
                      fontWeight: 600,
                      cursor: isCurrent ? 'default' : 'pointer',
                      marginTop: 'auto',
                    }}
                  >
                    {isCurrent
                      ? 'Current Plan'
                      : plan.id === 'pro'
                        ? 'Upgrade to Pro'
                        : 'Contact Sales'}
                  </button>
                )}
              </div>
            )
          })}
        </div>

        {usage && usage.plan !== 'free' && (
          <div style={{ marginTop: 24, textAlign: 'center' }}>
            <button
              onClick={handlePortal}
              style={{
                background: 'var(--bg-3)',
                color: 'var(--text-1)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius)',
                padding: '10px 24px',
                fontSize: 12,
                cursor: 'pointer',
              }}
            >
              Manage Subscription via Stripe →
            </button>
          </div>
        )}
      </main>
    </div>
  )
}
