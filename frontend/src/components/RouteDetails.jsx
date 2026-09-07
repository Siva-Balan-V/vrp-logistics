import { useState, useEffect, useRef } from 'react'
import { vehicleColor, fetchDirections } from '../api.js'
import { useAuth } from '../context/AuthContext.jsx'

const ORS_MANEUVERS = {
  0: '↱',
  1: '↳',
  2: '⇠',
  3: '⇢',
  4: '↰',
  5: '↲',
  6: '↑',
  7: '⟳',
  8: '↺',
  9: '⊢',
  10: '⇇',
  11: '◎',
  12: '↗',
}

export function maneuverIcon(maneuver) {
  if (typeof maneuver === 'number') return ORS_MANEUVERS[maneuver] || '→'
  const m = String(maneuver || '').toLowerCase()
  if (m === 'depart') return '↗'
  if (m === 'arrive') return '◎'
  if (m === 'roundabout') return '⟳'
  if (m.includes('u-turn') || m.includes('uturn')) return '⇇'
  if (m.includes('left')) return '←'
  if (m.includes('right')) return '→'
  if (m.includes('straight') || m === 'continue') return '↑'
  if (m === 'end of road') return '⊢'
  return '→'
}

function fmtDistance(meters) {
  const m = Number(meters) || 0
  if (m < 1000) return `${Math.round(m)} m`
  return `${(m / 1000).toFixed(2)} km`
}

function fmtDuration(seconds) {
  const s = Number(seconds) || 0
  const min = Math.floor(s / 60)
  const sec = Math.round(s % 60)
  if (min >= 60) return `${Math.floor(min / 60)}h ${String(min % 60).padStart(2, '0')}m`
  return `${min}:${String(sec).padStart(2, '0')}`
}

export default function RouteDetails({
  result,
  selectedVehicle,
  onSelectVehicle,
  directions,
  onDirectionsChange,
  onFocusStep,
}) {
  const { token } = useAuth()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const fetchedRef = useRef(new Set())

  const activeIndex = Math.max(
    0,
    result.vehicles.findIndex((v) => v.vehicle_id === selectedVehicle),
  )
  const activeVehicle = result.vehicles[activeIndex]

  useEffect(() => {
    if (fetchedRef.current.has(activeIndex)) return
    let cancelled = false
    fetchedRef.current.add(activeIndex)
    setLoading(true)
    setError(null)
    fetchDirections(result.job_id, activeIndex, token)
      .then((data) => {
        if (cancelled) return
        onDirectionsChange({ routeIndex: activeIndex, ...data })
      })
      .catch((err) => {
        if (cancelled) return
        fetchedRef.current.delete(activeIndex)
        setError(err.message || 'Failed to load directions')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [activeIndex, result.job_id, token, onDirectionsChange])

  const totalMeters = (directions?.steps || []).reduce((s, st) => s + (st.distance_m || 0), 0)
  const totalSeconds = (directions?.steps || []).reduce((s, st) => s + (st.duration_s || 0), 0)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* Vehicle tabs */}
      <div
        role="tablist"
        aria-label="Vehicles"
        style={{ display: 'flex', gap: 6, overflowX: 'auto', flexShrink: 0 }}
      >
        {result.vehicles.map((v, i) => {
          const color = vehicleColor(i)
          const isActive = v.vehicle_id === activeVehicle.vehicle_id
          return (
            <button
              key={v.vehicle_id}
              role="tab"
              aria-selected={isActive}
              onClick={() => onSelectVehicle(v.vehicle_id)}
              style={{
                padding: '6px 10px',
                fontSize: 10,
                fontFamily: 'var(--mono)',
                background: isActive ? color : 'var(--bg-2)',
                color: isActive ? '#111' : 'var(--text-2)',
                border: `1px solid ${isActive ? color : 'var(--border)'}`,
                borderRadius: 'var(--radius)',
                cursor: 'pointer',
                whiteSpace: 'nowrap',
                transition: 'all 0.15s',
              }}
            >
              V{v.vehicle_id} · {v.route.length - 2} stops
            </button>
          )
        })}
      </div>

      {loading && (
        <div style={{ padding: '24px 0', textAlign: 'center', color: 'var(--text-3)' }}>
          Loading directions…
        </div>
      )}

      {error && (
        <div
          style={{
            background: 'var(--red-dim)',
            border: '1px solid var(--red)',
            borderRadius: 'var(--radius)',
            padding: '10px 14px',
            fontSize: 11,
            color: 'var(--red)',
            fontFamily: 'var(--mono)',
          }}
        >
          ⚠ {error}
        </div>
      )}

      {!loading && !error && directions && directions.routeIndex === activeIndex && (
        <>
          {/* Summary strip */}
          <div
            style={{
              display: 'flex',
              gap: 8,
              flexWrap: 'wrap',
              alignItems: 'center',
              padding: '10px 12px',
              background: 'var(--bg-2)',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius)',
            }}
          >
            <span
              style={{
                fontSize: 9,
                fontFamily: 'var(--mono)',
                textTransform: 'uppercase',
                letterSpacing: '0.06em',
                color: 'var(--text-3)',
              }}
            >
              {directions.source}
            </span>
            <Dot />
            <Metric label="Distance" value={fmtDistance(totalMeters)} />
            <Dot />
            <Metric label="ETA" value={fmtDuration(totalSeconds)} />
            <Dot />
            <Metric label="Steps" value={directions.steps.length} />
          </div>

          {/* Maneuver list */}
          <div
            role="list"
            aria-label="Turn-by-turn instructions"
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: 2,
              fontSize: 10,
              fontFamily: 'var(--mono)',
            }}
          >
            {directions.steps.map((step, i) => (
              <button
                key={i}
                role="listitem"
                onClick={() => onFocusStep({ lat: step.lat, lon: step.lon })}
                title="Focus map on this step"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  padding: '8px 10px',
                  textAlign: 'left',
                  background: 'transparent',
                  border: '1px solid var(--border)',
                  borderRadius: 'var(--radius)',
                  cursor: 'pointer',
                  color: 'var(--text)',
                  transition: 'background 0.15s',
                }}
                onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--bg-2)')}
                onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
              >
                <span
                  style={{
                    width: 26,
                    height: 26,
                    flexShrink: 0,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    background: 'var(--bg-3)',
                    borderRadius: '50%',
                    fontSize: 13,
                    color: 'var(--accent)',
                  }}
                >
                  {maneuverIcon(step.maneuver)}
                </span>
                <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {step.instruction || `Step ${i + 1}`}
                </span>
                <span style={{ color: 'var(--text-3)', flexShrink: 0 }}>
                  {fmtDistance(step.distance_m)}
                </span>
                <span style={{ color: 'var(--text-3)', flexShrink: 0, minWidth: 34 }}>
                  {fmtDuration(step.duration_s)}
                </span>
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  )
}

function Dot() {
  return <span style={{ color: 'var(--text-3)', fontSize: 8 }}>•</span>
}

function Metric({ label, value }) {
  return (
    <span style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
      <span style={{ color: 'var(--text)', fontSize: 11, fontWeight: 600 }}>{value}</span>
      <span style={{ color: 'var(--text-3)', fontSize: 9, textTransform: 'uppercase' }}>
        {label}
      </span>
    </span>
  )
}
