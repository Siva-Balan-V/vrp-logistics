import { useState, useEffect, useCallback } from 'react'
import { useAuth } from '../context/AuthContext.jsx'
import { listPlans, getUsage, createRazorpayOrder, verifyRazorpayPayment } from '../api.js'
import PageHeader from '../components/PageHeader.jsx'

export default function BillingPage() {
  const { token, user } = useAuth()
  const [plans, setPlans] = useState([])
  const [usage, setUsage] = useState(null)
  const [loading, setLoading] = useState(true)
  const [paying, setPaying] = useState(null)

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
      setPaying(planId)
      const order = await createRazorpayOrder(planId, token)

      const options = {
        key: import.meta.env.VITE_RAZORPAY_KEY_ID || 'rzp_test_TSsDHsEiWrpwZq',
        amount: order.amount,
        currency: order.currency || 'INR',
        name: 'RouteForge',
        description: `${planId.charAt(0).toUpperCase() + planId.slice(1)} Plan Subscription`,
        order_id: order.razorpay_order_id,
        handler: async (response) => {
          try {
            await verifyRazorpayPayment(
              {
                razorpay_order_id: response.razorpay_order_id,
                razorpay_payment_id: response.razorpay_payment_id,
                razorpay_signature: response.razorpay_signature,
              },
              token,
            )
            await fetchData()
          } catch (e) {
            alert('Payment verification failed: ' + e.message)
          } finally {
            setPaying(null)
          }
        },
        prefill: {
          email: user?.email || '',
        },
        theme: {
          color: '#f5a623',
        },
        modal: {
          ondismiss: () => setPaying(null),
        },
      }

      const rzp = new window.Razorpay(options)
      rzp.on('payment.failed', (response) => {
        alert('Payment failed: ' + (response.error?.description || 'Unknown error'))
        setPaying(null)
      })
      rzp.open()
    } catch (e) {
      alert('Checkout failed: ' + e.message)
      setPaying(null)
    }
  }

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)' }}>
      <PageHeader badge="Billing" />

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
            <div
              style={{
                display: 'flex',
                gap: 24,
                fontFamily: 'var(--mono)',
                fontSize: 12,
                flexWrap: 'wrap',
              }}
            >
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
                  ₹{plan.price_monthly}
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
                    {plan.max_optimizations_per_month === 10000
                      ? 'Unlimited'
                      : plan.max_optimizations_per_month}{' '}
                    optimizations/mo
                  </span>
                  <span style={{ color: 'var(--text-2)' }}>
                    Up to {plan.max_locations_per_job} locations/job
                  </span>
                  <span style={{ color: 'var(--text-2)' }}>
                    {plan.allowed_backends.join(', ')} routing
                  </span>
                  <span style={{ color: plan.export_enabled ? 'var(--green)' : 'var(--text-3)' }}>
                    Export: {plan.export_enabled ? 'Yes' : 'No'}
                  </span>
                  <span style={{ color: plan.priority_support ? 'var(--green)' : 'var(--text-3)' }}>
                    Priority support: {plan.priority_support ? 'Yes' : 'No'}
                  </span>
                  <span style={{ color: 'var(--text-2)' }}>Up to {plan.max_users} users</span>
                </div>
                {plan.id !== 'free' && (
                  <button
                    onClick={() => handleUpgrade(plan.id)}
                    disabled={isCurrent || paying === plan.id}
                    style={{
                      background: isCurrent ? 'var(--bg-3)' : 'var(--accent)',
                      color: isCurrent ? 'var(--text-3)' : 'var(--on-accent)',
                      border: 'none',
                      borderRadius: 'var(--radius)',
                      padding: '10px',
                      fontSize: 12,
                      fontWeight: 600,
                      cursor: isCurrent ? 'default' : 'pointer',
                      marginTop: 'auto',
                    }}
                  >
                    {paying === plan.id
                      ? 'Processing...'
                      : isCurrent
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
      </main>
    </div>
  )
}
