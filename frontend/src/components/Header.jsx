import { useState } from 'react'
import { useAuth } from '../context/AuthContext.jsx'
import { useTheme } from '../context/ThemeContext.jsx'

const NAV_LINKS = [
  { href: '/dashboard', label: 'Dashboard' },
  { href: '/history', label: 'History' },
  { href: '/dispatch', label: 'Dispatch' },
  { href: '/drivers', label: 'Drivers' },
  { href: '/notifications', label: 'Notifications' },
  { href: '/billing', label: 'Billing' },
]

export default function Header({ onReset, phase }) {
  const { user, logout } = useAuth()
  const { theme, toggleTheme } = useTheme()
  const [menuOpen, setMenuOpen] = useState(false)

  return (
    <header className="page-header" style={s.header}>
      <div style={s.left}>
        <a href="/" style={s.logo}>
          <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
            <rect x="2" y="2" width="24" height="24" rx="4" fill="var(--accent)" opacity="0.15" />
            <path
              d="M14 4 L4 24 L14 20 L24 24 Z"
              fill="none"
              stroke="var(--accent)"
              strokeWidth="1.5"
              strokeLinejoin="round"
            />
            <circle cx="14" cy="14" r="2.5" fill="var(--accent)" />
          </svg>
          <span style={s.logoText}>
            Route<span style={{ color: 'var(--accent)' }}>Forge</span>
          </span>
        </a>
        <span style={s.badge}>VRP v1.0</span>

        {phase === 'results' && (
          <span style={s.statusBadge}>
            <span style={s.statusDot} />
            SOLUTION READY
          </span>
        )}
        {phase !== 'idle' && (
          <button onClick={onReset} style={s.newJobBtn}>
            New Job
          </button>
        )}

        <nav className="page-nav" style={s.nav}>
          {NAV_LINKS.map((l) => (
            <a key={l.href} href={l.href} style={s.navLink}>
              {l.label}
            </a>
          ))}
          {user?.role === 'admin' && (
            <a href="/api-keys" style={s.navLink}>
              API Keys
            </a>
          )}
          {user?.role === 'admin' && (
            <a
              href="/admin"
              style={{ ...s.navLink, color: 'var(--accent)', borderColor: 'var(--accent)' }}
            >
              Admin
            </a>
          )}
        </nav>

        <button
          className="page-burger"
          onClick={() => setMenuOpen(!menuOpen)}
          style={s.burger}
          aria-label="Toggle navigation menu"
          aria-expanded={menuOpen}
        >
          <span
            style={{
              ...s.burgerLine,
              transform: menuOpen ? 'rotate(45deg) translate(4px, 4px)' : 'none',
            }}
          />
          <span style={{ ...s.burgerLine, opacity: menuOpen ? 0 : 1 }} />
          <span
            style={{
              ...s.burgerLine,
              transform: menuOpen ? 'rotate(-45deg) translate(4px, -4px)' : 'none',
            }}
          />
        </button>
      </div>

      {menuOpen && (
        <div className="page-mobile-menu" style={s.mobileMenu} role="menu">
          {NAV_LINKS.map((l) => (
            <a
              key={l.href}
              href={l.href}
              style={s.mobileLink}
              role="menuitem"
              onClick={() => setMenuOpen(false)}
            >
              {l.label}
            </a>
          ))}
          {user?.role === 'admin' && (
            <a
              href="/api-keys"
              style={s.mobileLink}
              role="menuitem"
              onClick={() => setMenuOpen(false)}
            >
              API Keys
            </a>
          )}
          {user?.role === 'admin' && (
            <a
              href="/admin"
              style={s.mobileLink}
              role="menuitem"
              onClick={() => setMenuOpen(false)}
            >
              Admin
            </a>
          )}
          {phase !== 'idle' && (
            <button
              onClick={() => {
                onReset()
                setMenuOpen(false)
              }}
              style={s.mobileLink}
            >
              New Job
            </button>
          )}
          <a
            href="/docs"
            target="_blank"
            rel="noopener noreferrer"
            style={s.mobileLink}
            onClick={() => setMenuOpen(false)}
          >
            API Docs
          </a>
          <div style={s.mobileUserRow}>
            {user && <span style={s.userEmail}>{user.email}</span>}
            <button
              onClick={() => {
                logout()
                setMenuOpen(false)
              }}
              style={s.mobileLogout}
            >
              Logout
            </button>
            <button
              onClick={() => {
                toggleTheme()
                setMenuOpen(false)
              }}
              style={s.themeBtn}
            >
              {theme === 'dark' ? '☀' : '☾'}
            </button>
          </div>
        </div>
      )}

      <div className="page-header-right" style={s.right}>
        {user && <span style={s.userEmail}>{user.email}</span>}
        {user && (
          <button onClick={logout} style={s.logoutBtn}>
            Logout
          </button>
        )}
        <button
          onClick={toggleTheme}
          title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
          style={s.themeBtn}
        >
          {theme === 'dark' ? '☀' : '☾'}
        </button>
        <a href="/docs" target="_blank" rel="noopener noreferrer" style={s.navLink}>
          API Docs
        </a>
      </div>
    </header>
  )
}

const s = {
  header: {
    height: 64,
    background: 'var(--bg-1)',
    borderBottom: '1px solid var(--border)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '0 24px',
    position: 'sticky',
    top: 0,
    zIndex: 100,
  },
  left: {
    display: 'flex',
    alignItems: 'center',
    gap: 12,
    minWidth: 0,
  },
  logo: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    textDecoration: 'none',
    color: 'inherit',
    flexShrink: 0,
  },
  logoText: {
    fontFamily: 'var(--display)',
    fontWeight: 800,
    fontSize: 18,
    letterSpacing: '-0.03em',
    color: 'var(--text)',
  },
  badge: {
    fontFamily: 'var(--mono)',
    fontSize: 10,
    color: 'var(--text-3)',
    background: 'var(--bg-3)',
    border: '1px solid var(--border)',
    padding: '2px 7px',
    borderRadius: 4,
    flexShrink: 0,
  },
  statusBadge: {
    fontFamily: 'var(--mono)',
    fontSize: 11,
    color: 'var(--green)',
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    flexShrink: 0,
  },
  statusDot: {
    width: 6,
    height: 6,
    borderRadius: '50%',
    background: 'var(--green)',
    display: 'inline-block',
    animation: 'pulse-accent 2s ease infinite',
  },
  newJobBtn: {
    background: 'var(--bg-3)',
    color: 'var(--text-2)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius)',
    padding: '6px 14px',
    fontSize: 12,
    fontWeight: 500,
    flexShrink: 0,
  },
  nav: {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    marginLeft: 16,
  },
  navLink: {
    fontFamily: 'var(--mono)',
    fontSize: 11,
    color: 'var(--text-3)',
    textDecoration: 'none',
    padding: '6px 10px',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius)',
    whiteSpace: 'nowrap',
    minHeight: 32,
    display: 'inline-flex',
    alignItems: 'center',
  },
  right: {
    display: 'flex',
    alignItems: 'center',
    gap: 12,
    flexShrink: 0,
  },
  userEmail: {
    fontFamily: 'var(--mono)',
    fontSize: 11,
    color: 'var(--text-2)',
    maxWidth: 140,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  },
  logoutBtn: {
    background: 'var(--bg-3)',
    color: 'var(--text-2)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius)',
    padding: '6px 14px',
    fontSize: 12,
    minHeight: 32,
  },
  themeBtn: {
    background: 'none',
    color: 'var(--text-3)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius)',
    padding: '6px 10px',
    fontSize: 14,
    minHeight: 32,
    minWidth: 32,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
  burger: {
    flexDirection: 'column',
    justifyContent: 'center',
    gap: 4,
    width: 40,
    height: 40,
    padding: 8,
    background: 'none',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius)',
    cursor: 'pointer',
    flexShrink: 0,
  },
  burgerLine: {
    width: '100%',
    height: 2,
    background: 'var(--text-2)',
    borderRadius: 1,
    transition: 'all 0.2s',
  },
  mobileMenu: {
    width: '100%',
    background: 'var(--bg-1)',
    borderBottom: '1px solid var(--border)',
    padding: '8px 0',
  },
  mobileLink: {
    fontFamily: 'var(--mono)',
    fontSize: 13,
    color: 'var(--text-2)',
    textDecoration: 'none',
    padding: '10px 24px',
    minHeight: 44,
    display: 'flex',
    alignItems: 'center',
    background: 'none',
    border: 'none',
    cursor: 'pointer',
    textAlign: 'left',
    width: '100%',
  },
  mobileUserRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 12,
    padding: '10px 24px',
    borderTop: '1px solid var(--border)',
    marginTop: 4,
    paddingTop: 12,
  },
  mobileLogout: {
    background: 'var(--bg-3)',
    color: 'var(--text-2)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius)',
    padding: '8px 14px',
    fontSize: 12,
    minHeight: 44,
  },
}
