import { useState, useEffect, useCallback } from 'react'
import { useAuth } from '../context/AuthContext.jsx'
import { useTheme } from '../context/ThemeContext.jsx'
import { listApiKeys, createApiKey, revokeApiKey } from '../api.js'
import PageHeader from '../components/PageHeader.jsx'

const PERMISSION_LABELS = {
  optimize: 'Optimize routes',
  read: 'Read routes',
}

export default function ApiKeysPage() {
  const { token, user } = useAuth()
  const { theme, toggleTheme } = useTheme()
  const [keys, setKeys] = useState([])
  const [loading, setLoading] = useState(true)
  const [name, setName] = useState('')
  const [permissions, setPermissions] = useState(['optimize', 'read'])
  const [createdKey, setCreatedKey] = useState(null)
  const [error, setError] = useState(null)

  const fetchKeys = useCallback(async () => {
    try {
      setLoading(true)
      setKeys(await listApiKeys(token))
    } catch {
      setKeys([])
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => {
    fetchKeys()
  }, [fetchKeys])

  const togglePermission = (perm) => {
    setPermissions((prev) =>
      prev.includes(perm) ? prev.filter((p) => p !== perm) : [...prev, perm],
    )
  }

  const handleCreate = async (e) => {
    e.preventDefault()
    setError(null)
    try {
      const created = await createApiKey({ name: name.trim() || 'Default', permissions }, token)
      setCreatedKey(created)
      setName('')
      setPermissions(['optimize', 'read'])
      fetchKeys()
    } catch (err) {
      setError(err.message)
    }
  }

  const handleRevoke = async (keyId) => {
    if (!window.confirm('Revoke this API key? Integrations using it will stop working.')) return
    try {
      await revokeApiKey(keyId, token)
      fetchKeys()
    } catch (err) {
      alert('Failed to revoke key: ' + err.message)
    }
  }

  const copyKey = async () => {
    if (!createdKey?.key) return
    try {
      await navigator.clipboard.writeText(createdKey.key)
      alert('API key copied to clipboard')
    } catch {
      // clipboard unavailable — user can copy manually
    }
  }

  const mono = { fontFamily: 'var(--mono)' }

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)' }}>
      <PageHeader badge="API Keys" />

      <main style={{ maxWidth: 860, margin: '0 auto', padding: '32px 24px' }}>
        <h1
          style={{
            fontFamily: 'var(--display)',
            fontSize: 22,
            fontWeight: 700,
            color: 'var(--text-1)',
            marginBottom: 24,
          }}
        >
          API Keys
        </h1>

        {createdKey && (
          <div
            style={{
              background: 'var(--accent-dim)',
              border: '1px solid var(--accent)',
              borderRadius: 'var(--radius-lg)',
              padding: 20,
              marginBottom: 24,
            }}
          >
            <h2
              style={{
                fontSize: 14,
                fontWeight: 600,
                color: 'var(--accent)',
                fontFamily: 'var(--mono)',
                marginBottom: 8,
              }}
            >
              Key created — copy it now
            </h2>
            <p style={{ fontSize: 12, color: 'var(--text-2)', marginBottom: 12 }}>
              For security, this is the only time the full key is shown. Store it somewhere safe.
            </p>
            <div
              style={{
                display: 'flex',
                gap: 8,
                alignItems: 'center',
                background: 'var(--bg-1)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius)',
                padding: '10px 12px',
              }}
            >
              <code
                style={{
                  flex: 1,
                  fontSize: 12,
                  color: 'var(--text-1)',
                  ...mono,
                  wordBreak: 'break-all',
                }}
              >
                {createdKey.key}
              </code>
              <button
                onClick={copyKey}
                style={{
                  background: 'var(--accent)',
                  color: 'var(--on-accent)',
                  border: 'none',
                  borderRadius: 'var(--radius)',
                  padding: '8px 14px',
                  fontSize: 12,
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                Copy
              </button>
            </div>
            <button
              onClick={() => setCreatedKey(null)}
              style={{
                background: 'none',
                color: 'var(--text-3)',
                border: 'none',
                fontSize: 11,
                cursor: 'pointer',
                marginTop: 10,
              }}
            >
              Dismiss
            </button>
          </div>
        )}

        <div
          style={{
            background: 'var(--bg-1)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-lg)',
            padding: 20,
            marginBottom: 24,
          }}
        >
          <h2 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12, color: 'var(--text-1)' }}>
            Create a new key
          </h2>
          <form
            onSubmit={handleCreate}
            style={{ display: 'flex', flexDirection: 'column', gap: 12 }}
          >
            <input
              type="text"
              placeholder="Name (e.g. Production integration)"
              value={name}
              onChange={(e) => setName(e.target.value)}
              style={{
                background: 'var(--bg-2)',
                color: 'var(--text-1)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius)',
                padding: '9px 12px',
                fontSize: 12,
                ...mono,
              }}
            />
            <div style={{ display: 'flex', gap: 16 }}>
              {Object.entries(PERMISSION_LABELS).map(([perm, label]) => (
                <label
                  key={perm}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                    fontSize: 12,
                    color: 'var(--text-2)',
                    cursor: 'pointer',
                  }}
                >
                  <input
                    type="checkbox"
                    checked={permissions.includes(perm)}
                    onChange={() => togglePermission(perm)}
                  />
                  {label}
                </label>
              ))}
            </div>
            {error && <p style={{ fontSize: 12, color: 'var(--red, #f2614a)' }}>{error}</p>}
            <button
              type="submit"
              style={{
                alignSelf: 'flex-start',
                background: 'var(--accent)',
                color: 'var(--on-accent)',
                border: 'none',
                borderRadius: 'var(--radius)',
                padding: '10px 20px',
                fontSize: 12,
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              Generate API Key
            </button>
          </form>
        </div>

        <h2 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12, color: 'var(--text-1)' }}>
          Active keys
        </h2>

        {loading && <p style={{ color: 'var(--text-2)', fontSize: 12 }}>Loading...</p>}

        {!loading && keys.length === 0 && (
          <p style={{ color: 'var(--text-3)', fontSize: 12 }}>
            No API keys yet. Create one above to enable programmatic access.
          </p>
        )}

        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {keys.map((k) => (
            <div
              key={k.id}
              style={{
                background: 'var(--bg-1)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius-lg)',
                padding: '14px 18px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: 12,
                opacity: k.is_active ? 1 : 0.55,
              }}
            >
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-1)' }}>
                    {k.name}
                  </span>
                  <span
                    style={{
                      fontSize: 10,
                      fontFamily: 'var(--mono)',
                      color: k.is_active ? 'var(--green)' : 'var(--text-3)',
                      background: 'var(--bg-3)',
                      border: '1px solid var(--border)',
                      padding: '1px 6px',
                      borderRadius: 4,
                    }}
                  >
                    {k.is_active ? 'ACTIVE' : 'REVOKED'}
                  </span>
                </div>
                <div style={{ fontSize: 11, fontFamily: 'var(--mono)', color: 'var(--text-2)' }}>
                  {k.prefix}…
                </div>
                <div style={{ fontSize: 11, color: 'var(--text-3)' }}>
                  Permissions: {k.permissions.join(', ')} · Created:{' '}
                  {k.created_at ? new Date(k.created_at).toLocaleDateString() : '—'} · Last used:{' '}
                  {k.last_used_at ? new Date(k.last_used_at).toLocaleDateString() : 'never'}
                </div>
              </div>
              {k.is_active && (
                <button
                  onClick={() => handleRevoke(k.id)}
                  style={{
                    background: 'var(--bg-3)',
                    color: 'var(--red, #f2614a)',
                    border: '1px solid var(--border)',
                    borderRadius: 'var(--radius)',
                    padding: '7px 14px',
                    fontSize: 11,
                    cursor: 'pointer',
                    whiteSpace: 'nowrap',
                  }}
                >
                  Revoke
                </button>
              )}
            </div>
          ))}
        </div>
      </main>
    </div>
  )
}
