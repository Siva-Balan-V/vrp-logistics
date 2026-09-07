import { useState, useEffect, useCallback, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'
import { useTheme } from '../context/ThemeContext.jsx'
import { getDriver, getDriverEta, listJobs, assignDriverRoute } from '../api.js'
import PageHeader from '../components/PageHeader.jsx'
import L from 'leaflet'

const STATUS_COLORS = {
  offline: 'var(--text-3)',
  active: 'var(--green)',
  on_route: 'var(--accent)',
}

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;')
}

export default function DriverDetailPage() {
  const { id } = useParams()
  const { token, user, logout } = useAuth()
  const { theme, toggleTheme } = useTheme()
  const navigate = useNavigate()
  const mapRef = useRef(null)
  const mapInstanceRef = useRef(null)
  const [driver, setDriver] = useState(null)
  const [jobs, setJobs] = useState([])
  const [loading, setLoading] = useState(true)
  const [assignJobId, setAssignJobId] = useState('')
  const [assignVehicleId, setAssignVehicleId] = useState('')
  const [eta, setEta] = useState(null)
  const etaInterval = useRef(null)
  const idRef = useRef(id)

  const fetchDriver = useCallback(async () => {
    try {
      setLoading(true)
      const d = await getDriver(id, token)
      if (idRef.current === id) setDriver(d)
    } finally {
      if (idRef.current === id) setLoading(false)
    }
  }, [id, token])

  useEffect(() => {
    idRef.current = id
    setDriver(null)
    setEta(null)
    fetchDriver()
  }, [id, fetchDriver])

  const fetchJobs = useCallback(async () => {
    try {
      const data = await listJobs(token, 20)
      setJobs(data.jobs || [])
    } catch {
      // failed to load jobs — assignment dropdown stays empty
    }
  }, [token])

  useEffect(() => {
    fetchJobs()
  }, [fetchJobs])

  const fetchEta = useCallback(async () => {
    if (!driver?.current_lat || !driver?.assigned_route) return
    try {
      const etaData = await getDriverEta(id, token)
      if (idRef.current === id) setEta(etaData)
    } catch {
      // keep last known ETA if refresh fails
    }
  }, [id, token, driver?.current_lat, driver?.assigned_route])

  useEffect(() => {
    if (etaInterval.current) {
      clearInterval(etaInterval.current)
      etaInterval.current = null
    }
    if (driver?.current_lat && driver?.assigned_route) {
      fetchEta()
      etaInterval.current = setInterval(fetchEta, 15000)
    }
    return () => {
      if (etaInterval.current) {
        clearInterval(etaInterval.current)
        etaInterval.current = null
      }
    }
  }, [driver?.current_lat, driver?.assigned_route, fetchEta])

  useEffect(() => {
    if (!mapRef.current || mapInstanceRef.current || !driver?.current_lat) return
    mapInstanceRef.current = L.map(mapRef.current, {
      center: [driver.current_lat, driver.current_lon],
      zoom: 13,
      zoomControl: true,
    })
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap contributors',
      maxZoom: 19,
    }).addTo(mapInstanceRef.current)
    const marker = L.circleMarker([driver.current_lat, driver.current_lon], {
      radius: 8,
      color: '#f5a623',
      fillColor: '#f5a623',
      fillOpacity: 0.8,
      weight: 2,
    }).addTo(mapInstanceRef.current)
    marker.bindTooltip(
      `<strong>${escapeHtml(driver.name)}</strong><br/>${escapeHtml(driver.status)}`,
    )
    requestAnimationFrame(() => mapInstanceRef.current?.invalidateSize())
    return () => {
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove()
        mapInstanceRef.current = null
      }
    }
  }, [driver])

  const handleAssign = async () => {
    if (!assignJobId || !assignVehicleId) return
    try {
      const updated = await assignDriverRoute(id, assignJobId, parseInt(assignVehicleId), token)
      setDriver(updated)
      setAssignJobId('')
      setAssignVehicleId('')
    } catch {
      // assignment failed — keep form values for retry
    }
  }

  const route = driver?.assigned_route
  const waypoints =
    route?.route?.waypoints ||
    route?.route?.route_labels?.map((_, i) => ({
      id: route.route[i],
      label: route.route_labels[i],
    })) ||
    []

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)' }}>
      <PageHeader badge="Driver" />

      <main style={{ maxWidth: 960, margin: '0 auto', padding: '32px 24px' }}>
        {loading && <p style={{ color: 'var(--text-2)' }}>Loading...</p>}

        {!loading && driver && (
          <div style={{ display: 'flex', gap: 24, flexDirection: 'column' }}>
            <div
              style={{
                background: 'var(--bg-1)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius-lg)',
                padding: 24,
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'start',
              }}
            >
              <div>
                <h1
                  style={{
                    fontFamily: 'var(--display)',
                    fontSize: 22,
                    fontWeight: 700,
                    color: 'var(--text-1)',
                    marginBottom: 8,
                  }}
                >
                  {driver.name}
                </h1>
                <div style={{ display: 'flex', gap: 16, fontFamily: 'var(--mono)', fontSize: 12 }}>
                  <span style={{ color: 'var(--text-2)' }}>📞 {driver.phone}</span>
                  <span
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 4,
                      color: 'var(--text-2)',
                    }}
                  >
                    <span
                      style={{
                        width: 8,
                        height: 8,
                        borderRadius: '50%',
                        background: STATUS_COLORS[driver.status] || 'var(--text-3)',
                      }}
                    />
                    {driver.status}
                  </span>
                  <span style={{ color: 'var(--text-2)' }}>
                    Last ping:{' '}
                    {driver.last_ping_at ? new Date(driver.last_ping_at).toLocaleString() : 'never'}
                  </span>
                </div>
              </div>
              {driver.current_lat && (
                <div
                  style={{
                    color: 'var(--text-3)',
                    fontFamily: 'var(--mono)',
                    fontSize: 11,
                    textAlign: 'right',
                  }}
                >
                  {driver.current_lat.toFixed(5)}, {driver.current_lon.toFixed(5)}
                </div>
              )}
            </div>

            {driver.current_lat && (
              <div
                style={{
                  background: 'var(--bg-1)',
                  border: '1px solid var(--border)',
                  borderRadius: 'var(--radius-lg)',
                  overflow: 'hidden',
                  height: 300,
                }}
              >
                <div ref={mapRef} style={{ width: '100%', height: '100%' }} />
              </div>
            )}

            {/* Live ETA */}
            {eta && eta.remaining_stops?.length > 0 && (
              <div
                style={{
                  background: 'var(--bg-1)',
                  border: '1px solid var(--border)',
                  borderRadius: 'var(--radius-lg)',
                  padding: 24,
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
                  Live ETA{' '}
                  {eta.total_remaining_time_min > 0 && (
                    <span style={{ fontSize: 11, color: 'var(--text-3)', fontWeight: 400 }}>
                      — {eta.total_remaining_distance_km.toFixed(1)} km remaining
                    </span>
                  )}
                </h2>
                <div style={{ fontFamily: 'var(--mono)', fontSize: 11 }}>
                  {eta.remaining_stops.map((s) => (
                    <div
                      key={s.stop_index}
                      style={{
                        padding: '6px 0',
                        borderBottom: '1px solid var(--border)',
                        display: 'flex',
                        gap: 8,
                        alignItems: 'center',
                      }}
                    >
                      <span style={{ color: 'var(--text-3)', minWidth: 20 }}>#{s.stop_index}</span>
                      <span style={{ color: 'var(--text-1)', flex: 1 }}>
                        {s.label || `Stop ${s.id}`}
                      </span>
                      <span
                        style={{
                          color: s.delta_min > 5 ? 'var(--red)' : 'var(--text-2)',
                          textAlign: 'right',
                        }}
                      >
                        {s.live_eta_min.toFixed(0)} min
                        {s.delta_min != null && s.delta_min > 1 && (
                          <span style={{ color: 'var(--text-3)', marginLeft: 4 }}>
                            (+{s.delta_min.toFixed(0)})
                          </span>
                        )}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Assign Route */}
            <div
              style={{
                background: 'var(--bg-1)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius-lg)',
                padding: 24,
              }}
            >
              <h2
                style={{
                  fontSize: 14,
                  fontWeight: 600,
                  marginBottom: 16,
                  color: 'var(--text-1)',
                  fontFamily: 'var(--mono)',
                }}
              >
                {route ? 'Assigned Route' : 'Assign a Route'}
              </h2>

              {route ? (
                <div>
                  <div
                    style={{
                      display: 'flex',
                      gap: 16,
                      fontFamily: 'var(--mono)',
                      fontSize: 12,
                      marginBottom: 16,
                    }}
                  >
                    <span style={{ color: 'var(--text-2)' }}>
                      📏 {route.distance_km.toFixed(1)} km
                    </span>
                    <span style={{ color: 'var(--text-2)' }}>
                      ⏱ {route.time_minutes.toFixed(0)} min
                    </span>
                    <span style={{ color: 'var(--text-2)' }}>📦 {route.packages} packages</span>
                  </div>
                  <div style={{ fontFamily: 'var(--mono)', fontSize: 11 }}>
                    {waypoints.map((wp, i) => (
                      <div
                        key={i}
                        style={{
                          padding: '6px 0',
                          borderBottom: '1px solid var(--border)',
                          display: 'flex',
                          gap: 8,
                          color: 'var(--text-2)',
                        }}
                      >
                        <span style={{ color: 'var(--text-3)' }}>#{i + 1}</span>
                        <span>{wp.label || `Stop ${wp.id}`}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div style={{ display: 'flex', gap: 12, alignItems: 'end' }}>
                  <div>
                    <label
                      style={{
                        fontSize: 11,
                        fontFamily: 'var(--mono)',
                        color: 'var(--text-3)',
                        display: 'block',
                        marginBottom: 4,
                      }}
                    >
                      Job
                    </label>
                    <select
                      value={assignJobId}
                      onChange={(e) => setAssignJobId(e.target.value)}
                      style={{
                        background: 'var(--bg-2)',
                        color: 'var(--text-1)',
                        border: '1px solid var(--border)',
                        borderRadius: 'var(--radius)',
                        padding: '8px 12px',
                        fontSize: 12,
                        fontFamily: 'var(--mono)',
                        minWidth: 200,
                      }}
                    >
                      <option value="">Select job...</option>
                      {jobs.map((j) => (
                        <option key={j.job_id} value={j.job_id}>
                          {j.job_id.slice(0, 8)} — {j.total_locations} locs
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label
                      style={{
                        fontSize: 11,
                        fontFamily: 'var(--mono)',
                        color: 'var(--text-3)',
                        display: 'block',
                        marginBottom: 4,
                      }}
                    >
                      Vehicle
                    </label>
                    <input
                      value={assignVehicleId}
                      onChange={(e) => setAssignVehicleId(e.target.value)}
                      placeholder="0"
                      type="number"
                      style={{
                        background: 'var(--bg-2)',
                        color: 'var(--text-1)',
                        border: '1px solid var(--border)',
                        borderRadius: 'var(--radius)',
                        padding: '8px 12px',
                        fontSize: 12,
                        fontFamily: 'var(--mono)',
                        width: 80,
                      }}
                    />
                  </div>
                  <button
                    onClick={handleAssign}
                    style={{
                      background: 'var(--accent)',
                      color: 'var(--on-accent)',
                      fontWeight: 600,
                      border: 'none',
                      borderRadius: 'var(--radius)',
                      padding: '8px 20px',
                      fontSize: 12,
                      cursor: 'pointer',
                    }}
                  >
                    Assign
                  </button>
                </div>
              )}
            </div>
          </div>
        )}

        {!loading && !driver && (
          <p style={{ color: 'var(--text-2)', fontFamily: 'var(--mono)', fontSize: 13 }}>
            Driver not found.
          </p>
        )}
      </main>
    </div>
  )
}
