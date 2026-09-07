import { useState, useEffect, useCallback, useMemo } from 'react'
import { useAuth } from '../context/AuthContext.jsx'
import { listDrivers } from '../api.js'
import useWebSocket from '../hooks/useWebSocket.js'
import PageHeader from '../components/PageHeader.jsx'
import DispatchMap, { isOffline } from '../components/DispatchMap.jsx'

const STATUS_COLORS = {
  offline: 'var(--text-3)',
  active: 'var(--green)',
  on_route: 'var(--accent)',
}

function etaCaption(driver) {
  const eta = driver?.eta
  if (!eta || eta.total_remaining_time_min == null) return 'no ETA yet'
  const first = eta.remaining_stops?.[0]
  const base = `${Math.round(eta.total_remaining_time_min)} min`
  if (!first || first.delta_min == null) return `ETA ${base}`
  if (first.delta_min > 1) return `ETA ${base} (+${Math.round(first.delta_min)})`
  if (first.delta_min < -1) return `ETA ${base} (${Math.round(first.delta_min)})`
  return `ETA ${base}`
}

export default function DispatchPage() {
  const { token, user } = useAuth()
  const companyId = user?.company_id
  const [drivers, setDrivers] = useState({})
  const [loading, setLoading] = useState(true)
  const [now, setNow] = useState(Date.now())

  // Baseline fleet snapshot (last known positions, ETA, status)
  const fetchFleet = useCallback(async () => {
    try {
      const list = (await listDrivers(token)) || []
      const map = {}
      list.forEach((d) => {
        map[d.id] = { ...d }
      })
      setDrivers(map)
    } catch {
      // fleet list unavailable — live updates still stream in
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => {
    fetchFleet()
  }, [fetchFleet])

  // Refresh "offline" flags over time
  useEffect(() => {
    const tick = setInterval(() => setNow(Date.now()), 30000)
    return () => clearInterval(tick)
  }, [])

  const onWsMessage = useCallback((data) => {
    if (!data || data.type !== 'driver.update') return
    setDrivers((prev) => {
      const current = prev[data.driver_id]
      const moved = !current || current.current_lat !== data.lat || current.current_lon !== data.lon
      return {
        ...prev,
        [data.driver_id]: {
          ...(current || {}),
          id: data.driver_id,
          company_id: data.company_id,
          name: data.name ?? current?.name,
          status: data.status ?? current?.status,
          current_lat: data.lat,
          current_lon: data.lon,
          last_ping_at: data.last_ping_at,
          eta: data.eta,
          moving: moved,
        },
      }
    })
  }, [])

  const wsPath = companyId ? `/api/v1/ws/drivers/${companyId}` : null
  useWebSocket(wsPath, companyId ? token : null, onWsMessage)

  const driverList = useMemo(() => {
    return Object.values(drivers).sort((a, b) => (a.name || '').localeCompare(b.name || ''))
  }, [drivers])

  const onlineCount = driverList.filter((d) => !isOffline(d.last_ping_at, now)).length

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)' }}>
      <PageHeader badge="Dispatch" />

      <main style={{ maxWidth: 1280, margin: '0 auto', padding: '32px 24px' }}>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: 24,
          }}
        >
          <h1
            style={{
              fontFamily: 'var(--display)',
              fontSize: 22,
              fontWeight: 700,
              color: 'var(--text-1)',
            }}
          >
            Real-time Fleet
          </h1>
          <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text-3)' }}>
            {onlineCount} / {driverList.length} online
          </span>
        </div>

        {loading && <p style={{ color: 'var(--text-2)' }}>Loading fleet...</p>}

        {!loading && driverList.length === 0 && (
          <p style={{ color: 'var(--text-2)', fontFamily: 'var(--mono)', fontSize: 13 }}>
            No drivers yet. Add one on the Drivers page to see it live here.
          </p>
        )}

        {!loading && driverList.length > 0 && (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'minmax(260px, 340px) 1fr',
              gap: 20,
              height: '72vh',
            }}
          >
            {/* Fleet roster */}
            <div
              style={{
                background: 'var(--bg-1)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius-lg)',
                overflowY: 'auto',
              }}
            >
              {driverList.map((d) => {
                const offline = isOffline(d.last_ping_at, now)
                return (
                  <div
                    key={d.id}
                    style={{
                      padding: '14px 16px',
                      borderBottom: '1px solid var(--border)',
                      fontFamily: 'var(--mono)',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <div
                        style={{
                          width: 8,
                          height: 8,
                          borderRadius: '50%',
                          background: offline
                            ? 'var(--text-3)'
                            : STATUS_COLORS[d.status] || 'var(--green)',
                        }}
                      />
                      <span style={{ fontWeight: 600, fontSize: 13, color: 'var(--text-1)' }}>
                        {d.name}
                      </span>
                      {offline && (
                        <span
                          style={{
                            marginLeft: 'auto',
                            fontSize: 10,
                            color: 'var(--red)',
                            border: '1px solid var(--red)',
                            borderRadius: 'var(--radius)',
                            padding: '1px 6px',
                          }}
                        >
                          OFFLINE
                        </span>
                      )}
                    </div>
                    <div
                      style={{
                        fontSize: 11,
                        color: 'var(--text-3)',
                        marginTop: 6,
                        lineHeight: 1.6,
                      }}
                    >
                      <div>
                        {etaCaption(d)}
                        {d.eta?.total_remaining_distance_km != null && (
                          <span> · {d.eta.total_remaining_distance_km.toFixed(1)} km</span>
                        )}
                      </div>
                      <div>
                        Ping:{' '}
                        {d.last_ping_at ? (
                          <span style={{ color: offline ? 'var(--red)' : 'var(--text-2)' }}>
                            {new Date(d.last_ping_at).toLocaleTimeString()}
                          </span>
                        ) : (
                          'never'
                        )}
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>

            {/* Live fleet map */}
            <div
              style={{
                background: 'var(--bg-1)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius-lg)',
                overflow: 'hidden',
              }}
            >
              <DispatchMap drivers={driverList} now={now} />
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
