export default function Header({ onReset, phase }) {
  return (
    <header style={{
      height: 64, background: 'var(--bg-1)',
      borderBottom: '1px solid var(--border)',
      display: 'flex', alignItems: 'center',
      justifyContent: 'space-between', padding: '0 24px',
      position: 'sticky', top: 0, zIndex: 100,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
          <rect x="2" y="2" width="24" height="24" rx="4" fill="var(--accent)" opacity="0.15"/>
          <path d="M14 4 L4 24 L14 20 L24 24 Z" fill="none" stroke="var(--accent)" strokeWidth="1.5" strokeLinejoin="round"/>
          <circle cx="14" cy="14" r="2.5" fill="var(--accent)"/>
        </svg>
        <span style={{ fontFamily: 'var(--display)', fontWeight: 800, fontSize: 18, letterSpacing: '-0.03em' }}>
          Route<span style={{ color: 'var(--accent)' }}>Forge</span>
        </span>
        <span style={{
          fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--text-3)',
          background: 'var(--bg-3)', border: '1px solid var(--border)',
          padding: '2px 7px', borderRadius: 4, marginLeft: 4
        }}>VRP v1.0</span>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
        {phase === 'results' && (
          <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--green)',
            display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--green)',
              display: 'inline-block', animation: 'pulse-accent 2s ease infinite' }}/>
            SOLUTION READY
          </span>
        )}
        {phase !== 'idle' && (
          <button onClick={onReset} style={{
            background: 'var(--bg-3)', color: 'var(--text-2)',
            border: '1px solid var(--border)', borderRadius: 'var(--radius)',
            padding: '6px 14px', fontSize: 12, fontWeight: 500
          }}>← New Job</button>
        )}
        <a href="/docs" target="_blank" rel="noopener noreferrer" style={{
          fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text-3)',
          textDecoration: 'none', padding: '5px 10px',
          border: '1px solid var(--border)', borderRadius: 'var(--radius)'
        }}>API Docs</a>
      </div>
    </header>
  )
}
