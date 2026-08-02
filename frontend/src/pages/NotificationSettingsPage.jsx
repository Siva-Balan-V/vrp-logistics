import { useState, useEffect, useCallback } from 'react'
import { useAuth } from '../context/AuthContext.jsx'
import { useTheme } from '../context/ThemeContext.jsx'
import {
  getNotificationConfig,
  updateNotificationConfig,
  listNotificationLogs,
  triggerNotification,
  listDrivers,
} from '../api.js'

const TRIGGER_OPTIONS = [
  { value: 'out_for_delivery', label: 'Out for Delivery' },
  { value: 'arrived', label: 'Delivered' },
  { value: 'delayed', label: 'Delayed' },
]

export default function NotificationSettingsPage() {
  const { token, user, logout } = useAuth()
  const { theme, toggleTheme } = useTheme()
  const [cfg, setCfg] = useState(null)
  const [logs, setLogs] = useState([])
  const [drivers, setDrivers] = useState([])
  const [saving, setSaving] = useState(false)

  const [smsEnabled, setSmsEnabled] = useState(false)
  const [emailEnabled, setEmailEnabled] = useState(false)
  const [twilioSid, setTwilioSid] = useState('')
  const [twilioToken, setTwilioToken] = useState('')
  const [twilioFrom, setTwilioFrom] = useState('')
  const [smtpHost, setSmtpHost] = useState('')
  const [smtpPort, setSmtpPort] = useState('587')
  const [smtpUser, setSmtpUser] = useState('')
  const [smtpPass, setSmtpPass] = useState('')
  const [smtpFrom, setSmtpFrom] = useState('')
  const [triggers, setTriggers] = useState([])

  const [testDriverId, setTestDriverId] = useState('')
  const [testTrigger, setTestTrigger] = useState('out_for_delivery')
  const [testPhone, setTestPhone] = useState('')
  const [testEmail, setTestEmail] = useState('')
  const [testResult, setTestResult] = useState('')

  const fetchCfg = useCallback(async () => {
    try {
      const c = await getNotificationConfig(token)
      if (c) {
        setCfg(c)
        setSmsEnabled(c.sms_enabled || false)
        setEmailEnabled(c.email_enabled || false)
        setTwilioSid(c.twilio_account_sid || '')
        setTwilioFrom(c.twilio_from_number || '')
        setSmtpHost(c.smtp_host || '')
        setSmtpPort(String(c.smtp_port || 587))
        setSmtpUser(c.smtp_user || '')
        setSmtpFrom(c.smtp_from_email || '')
        setTriggers(c.triggers || [])
      }
    } catch {
      // failed to load config — keep defaults
    }
  }, [token])

  const fetchLogs = useCallback(async () => {
    try {
      setLogs(await listNotificationLogs(20, token))
    } catch {
      // failed to load logs — leave table empty
    }
  }, [token])

  const fetchDrivers = useCallback(async () => {
    try {
      setDrivers(await listDrivers(token))
    } catch {
      // failed to load drivers — test dropdown stays empty
    }
  }, [token])

  useEffect(() => {
    fetchCfg()
  }, [fetchCfg])
  useEffect(() => {
    fetchLogs()
  }, [fetchLogs])
  useEffect(() => {
    fetchDrivers()
  }, [fetchDrivers])

  const handleSave = async () => {
    setSaving(true)
    try {
      const body = {
        sms_enabled: smsEnabled,
        email_enabled: emailEnabled,
        twilio_account_sid: twilioSid || null,
        twilio_auth_token: twilioToken || null,
        twilio_from_number: twilioFrom || null,
        smtp_host: smtpHost || null,
        smtp_port: smtpPort ? parseInt(smtpPort) : null,
        smtp_user: smtpUser || null,
        smtp_password: smtpPass || null,
        smtp_from_email: smtpFrom || null,
        triggers,
      }
      const updated = await updateNotificationConfig(body, token)
      setCfg(updated)
      setTwilioToken('')
      setSmtpPass('')
    } catch (e) {
      alert('Save failed: ' + e.message)
    } finally {
      setSaving(false)
    }
  }

  const handleTest = async () => {
    if (!testDriverId) {
      alert('Select a driver')
      return
    }
    setTestResult('Sending...')
    try {
      const res = await triggerNotification(
        {
          driver_id: testDriverId,
          trigger: testTrigger,
          customer_phone: testPhone || null,
          customer_email: testEmail || null,
        },
        token,
      )
      setTestResult(`Sent: ${JSON.stringify(res.sent)}`)
      await fetchLogs()
    } catch (e) {
      setTestResult('Failed: ' + e.message)
    }
  }

  const toggleTrigger = (val) => {
    setTriggers((prev) => (prev.includes(val) ? prev.filter((t) => t !== val) : [...prev, val]))
  }

  const inputStyle = {
    background: 'var(--bg-2)',
    color: 'var(--text-1)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius)',
    padding: '7px 10px',
    fontSize: 12,
    fontFamily: 'var(--mono)',
    width: '100%',
  }
  const labelStyle = {
    fontSize: 11,
    fontFamily: 'var(--mono)',
    color: 'var(--text-3)',
    display: 'block',
    marginBottom: 3,
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
            Notifications
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
            href="/drivers"
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
            Drivers
          </a>
          {user && (
            <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text-2)' }}>
              {user.email}
            </span>
          )}
          {user && (
            <button
              onClick={logout}
              style={{
                background: 'var(--bg-3)',
                color: 'var(--text-2)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius)',
                padding: '6px 14px',
                fontSize: 12,
              }}
            >
              Logout
            </button>
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
          Notification Settings
        </h1>

        <div style={{ display: 'grid', gap: 24, gridTemplateColumns: '1fr 1fr' }}>
          {/* SMS Config */}
          <div
            style={{
              background: 'var(--bg-1)',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius-lg)',
              padding: 20,
            }}
          >
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: 12,
              }}
            >
              <h2
                style={{
                  fontSize: 14,
                  fontWeight: 600,
                  color: 'var(--text-1)',
                  fontFamily: 'var(--mono)',
                }}
              >
                SMS (Twilio)
              </h2>
              <label
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                  fontSize: 11,
                  color: 'var(--text-2)',
                }}
              >
                <input
                  type="checkbox"
                  checked={smsEnabled}
                  onChange={(e) => setSmsEnabled(e.target.checked)}
                />
                Enabled
              </label>
            </div>
            <div style={{ display: 'grid', gap: 10 }}>
              <div>
                <label style={labelStyle}>Account SID</label>
                <input
                  style={inputStyle}
                  value={twilioSid}
                  onChange={(e) => setTwilioSid(e.target.value)}
                  placeholder="AC..."
                />
              </div>
              <div>
                <label style={labelStyle}>Auth Token</label>
                <input
                  style={inputStyle}
                  type="password"
                  value={twilioToken}
                  onChange={(e) => setTwilioToken(e.target.value)}
                  placeholder={cfg ? '••••••••' : ''}
                />
              </div>
              <div>
                <label style={labelStyle}>From Number</label>
                <input
                  style={inputStyle}
                  value={twilioFrom}
                  onChange={(e) => setTwilioFrom(e.target.value)}
                  placeholder="+1234567890"
                />
              </div>
            </div>
          </div>

          {/* Email Config */}
          <div
            style={{
              background: 'var(--bg-1)',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius-lg)',
              padding: 20,
            }}
          >
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: 12,
              }}
            >
              <h2
                style={{
                  fontSize: 14,
                  fontWeight: 600,
                  color: 'var(--text-1)',
                  fontFamily: 'var(--mono)',
                }}
              >
                Email (SMTP)
              </h2>
              <label
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                  fontSize: 11,
                  color: 'var(--text-2)',
                }}
              >
                <input
                  type="checkbox"
                  checked={emailEnabled}
                  onChange={(e) => setEmailEnabled(e.target.checked)}
                />
                Enabled
              </label>
            </div>
            <div style={{ display: 'grid', gap: 10, gridTemplateColumns: '2fr 1fr' }}>
              <div>
                <label style={labelStyle}>Host</label>
                <input
                  style={inputStyle}
                  value={smtpHost}
                  onChange={(e) => setSmtpHost(e.target.value)}
                  placeholder="smtp.sendgrid.net"
                />
              </div>
              <div>
                <label style={labelStyle}>Port</label>
                <input
                  style={inputStyle}
                  value={smtpPort}
                  onChange={(e) => setSmtpPort(e.target.value)}
                  placeholder="587"
                />
              </div>
            </div>
            <div style={{ display: 'grid', gap: 10, marginTop: 10 }}>
              <div>
                <label style={labelStyle}>Username</label>
                <input
                  style={inputStyle}
                  value={smtpUser}
                  onChange={(e) => setSmtpUser(e.target.value)}
                  placeholder="apikey"
                />
              </div>
              <div>
                <label style={labelStyle}>Password</label>
                <input
                  style={inputStyle}
                  type="password"
                  value={smtpPass}
                  onChange={(e) => setSmtpPass(e.target.value)}
                  placeholder={cfg ? '••••••••' : ''}
                />
              </div>
              <div>
                <label style={labelStyle}>From Email</label>
                <input
                  style={inputStyle}
                  value={smtpFrom}
                  onChange={(e) => setSmtpFrom(e.target.value)}
                  placeholder="notifications@routeforge.com"
                />
              </div>
            </div>
          </div>
        </div>

        {/* Triggers */}
        <div
          style={{
            background: 'var(--bg-1)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-lg)',
            padding: 20,
            marginTop: 24,
          }}
        >
          <h2
            style={{
              fontSize: 14,
              fontWeight: 600,
              color: 'var(--text-1)',
              fontFamily: 'var(--mono)',
              marginBottom: 12,
            }}
          >
            Notification Triggers
          </h2>
          <div style={{ display: 'flex', gap: 16 }}>
            {TRIGGER_OPTIONS.map((opt) => (
              <label
                key={opt.value}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                  fontSize: 12,
                  color: 'var(--text-2)',
                }}
              >
                <input
                  type="checkbox"
                  checked={triggers.includes(opt.value)}
                  onChange={() => toggleTrigger(opt.value)}
                />
                {opt.label}
              </label>
            ))}
          </div>
        </div>

        {/* Save */}
        <button
          onClick={handleSave}
          disabled={saving}
          style={{
            background: 'var(--accent)',
            color: '#000',
            fontWeight: 600,
            border: 'none',
            borderRadius: 'var(--radius)',
            padding: '10px 24px',
            fontSize: 13,
            cursor: 'pointer',
            marginTop: 24,
          }}
        >
          {saving ? 'Saving...' : 'Save Settings'}
        </button>

        {/* Test Panel */}
        <div
          style={{
            background: 'var(--bg-1)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-lg)',
            padding: 20,
            marginTop: 32,
          }}
        >
          <h2
            style={{
              fontSize: 14,
              fontWeight: 600,
              color: 'var(--text-1)',
              fontFamily: 'var(--mono)',
              marginBottom: 12,
            }}
          >
            Test Notification
          </h2>
          <div style={{ display: 'flex', gap: 12, alignItems: 'end', flexWrap: 'wrap' }}>
            <div>
              <label style={labelStyle}>Driver</label>
              <select
                value={testDriverId}
                onChange={(e) => setTestDriverId(e.target.value)}
                style={inputStyle}
              >
                <option value="">Select driver...</option>
                {drivers.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label style={labelStyle}>Trigger</label>
              <select
                value={testTrigger}
                onChange={(e) => setTestTrigger(e.target.value)}
                style={inputStyle}
              >
                {TRIGGER_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label style={labelStyle}>Phone</label>
              <input
                style={{ ...inputStyle, width: 160 }}
                value={testPhone}
                onChange={(e) => setTestPhone(e.target.value)}
                placeholder="+1234567890"
              />
            </div>
            <div>
              <label style={labelStyle}>Email</label>
              <input
                style={{ ...inputStyle, width: 200 }}
                value={testEmail}
                onChange={(e) => setTestEmail(e.target.value)}
                placeholder="customer@example.com"
              />
            </div>
            <button
              onClick={handleTest}
              style={{
                background: 'var(--bg-3)',
                color: 'var(--text-1)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius)',
                padding: '7px 16px',
                fontSize: 12,
                cursor: 'pointer',
              }}
            >
              Send Test
            </button>
          </div>
          {testResult && (
            <p
              style={{
                fontFamily: 'var(--mono)',
                fontSize: 11,
                color: 'var(--text-2)',
                marginTop: 8,
              }}
            >
              {testResult}
            </p>
          )}
        </div>

        {/* Logs */}
        <div style={{ marginTop: 24 }}>
          <h2
            style={{
              fontSize: 14,
              fontWeight: 600,
              color: 'var(--text-1)',
              fontFamily: 'var(--mono)',
              marginBottom: 12,
            }}
          >
            Recent Notifications
          </h2>
          {logs.length === 0 && (
            <p style={{ color: 'var(--text-2)', fontFamily: 'var(--mono)', fontSize: 11 }}>
              No notifications sent yet.
            </p>
          )}
          {logs.length > 0 && (
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
                  fontSize: 11,
                  fontFamily: 'var(--mono)',
                }}
              >
                <thead>
                  <tr
                    style={{ borderBottom: '1px solid var(--border)', background: 'var(--bg-2)' }}
                  >
                    <th style={{ padding: '8px 12px', textAlign: 'left', color: 'var(--text-3)' }}>
                      Channel
                    </th>
                    <th style={{ padding: '8px 12px', textAlign: 'left', color: 'var(--text-3)' }}>
                      Recipient
                    </th>
                    <th style={{ padding: '8px 12px', textAlign: 'left', color: 'var(--text-3)' }}>
                      Trigger
                    </th>
                    <th style={{ padding: '8px 12px', textAlign: 'left', color: 'var(--text-3)' }}>
                      Status
                    </th>
                    <th style={{ padding: '8px 12px', textAlign: 'left', color: 'var(--text-3)' }}>
                      Time
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {logs.map((l) => (
                    <tr key={l.id} style={{ borderBottom: '1px solid var(--border)' }}>
                      <td style={{ padding: '8px 12px', color: 'var(--text-1)' }}>{l.channel}</td>
                      <td style={{ padding: '8px 12px', color: 'var(--text-2)' }}>{l.recipient}</td>
                      <td style={{ padding: '8px 12px', color: 'var(--text-2)' }}>{l.trigger}</td>
                      <td
                        style={{
                          padding: '8px 12px',
                          color: l.status === 'sent' ? 'var(--green)' : 'var(--red)',
                        }}
                      >
                        {l.status}
                      </td>
                      <td style={{ padding: '8px 12px', color: 'var(--text-3)' }}>
                        {l.created_at ? new Date(l.created_at).toLocaleString() : ''}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
