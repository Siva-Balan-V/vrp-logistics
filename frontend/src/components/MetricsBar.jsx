export default function MetricsBar({ result }) {
  const pct = result.total_locations > 0
    ? Math.round((result.assigned_count / result.total_locations) * 100)
    : 0

  const metrics = [
    { label: 'Vehicles Used', value: result.vehicles_used, sub: `of ${result.vehicles?.length ?? '?'} available`, color: 'var(--accent)' },
    { label: 'Locations Served', value: `${result.assigned_count}/${result.total_locations}`, sub: `${pct}% coverage`, color: 'var(--green)' },
    { label: 'Unassigned', value: result.unassigned_count, sub: 'constraint violations', color: result.unassigned_count > 0 ? 'var(--red)' : 'var(--text-3)' },
    { label: 'Total Distance', value: `${result.total_distance_km.toFixed(1)} km`, sub: 'all routes combined', color: 'var(--blue)' },
    { label: 'Solver Time', value: `${result.solver_time_seconds.toFixed(2)} s`, sub: 'OR-Tools GLSS', color: 'var(--text-2)' },
    { label: 'Matrix Source', value: result.matrix_source.toUpperCase(), sub: 'distance backend', color: 'var(--text-2)' },
  ]

  return (
    <div style={{
      background: 'var(--bg-1)', borderBottom: '1px solid var(--border)',
      display: 'flex', alignItems: 'stretch',
      overflowX: 'auto', height: 56,
    }}>
      {metrics.map((m, i) => (
        <div key={i} style={{
          display: 'flex', alignItems: 'center', gap: 12,
          padding: '0 20px', borderRight: '1px solid var(--border)',
          flex: '0 0 auto', minWidth: 140,
        }}>
          <div>
            <div style={{ fontFamily: 'var(--mono)', fontSize: 15, fontWeight: 500, color: m.color, lineHeight: 1 }}>
              {m.value}
            </div>
            <div style={{ fontSize: 10, color: 'var(--text-3)', fontFamily: 'var(--mono)', marginTop: 2 }}>
              {m.label}
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}
