import { useState, useCallback } from 'react'
import { vehicleColor, exportRoute } from '../api.js'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'

export default function ResultsPanel({ result, selectedVehicle, onSelectVehicle }) {
  const [tab, setTab] = useState('routes') // routes | unassigned | chart | json
  const [copied, setCopied] = useState(false)

  const handleShare = useCallback(() => {
    const url = new URL(window.location.href)
    url.searchParams.set('job', result.job_id)
    navigator.clipboard.writeText(url.toString())
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }, [result.job_id])

  const handleExport = useCallback(async (format) => {
    try {
      const blob = await exportRoute(result.job_id, format)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `route_${result.job_id.slice(0, 8)}.${format}`
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      console.error('Export failed:', err)
    }
  }, [result.job_id])

  return (
    <div style={{
      display: 'flex', flexDirection: 'column',
      background: 'var(--bg-1)', borderRight: '1px solid var(--border)',
      overflow: 'hidden', height: '100%',
    }}>
      {/* Tabs */}
      <div role="tablist" aria-label="Results sections" style={{
        display: 'flex', background: 'var(--bg-2)',
        borderBottom: '1px solid var(--border)', padding: '0 8px',
        flexShrink: 0, alignItems: 'center',
      }}>
        {[
          ['routes', `Routes (${result.vehicles_used})`],
          ['unassigned', `Unassigned (${result.unassigned_count})`],
          ['chart', 'Charts'],
          ['json', 'JSON'],
        ].map(([key, label]) => (
          <button key={key} role="tab" aria-selected={tab === key} onClick={() => setTab(key)} style={{
            padding: '10px 14px', fontSize: 11, fontFamily: 'var(--mono)',
            background: 'none', borderBottom: tab === key ? '2px solid var(--accent)' : '2px solid transparent',
            color: tab === key ? 'var(--text)' : 'var(--text-3)',
            marginBottom: -1, transition: 'color 0.15s',
            whiteSpace: 'nowrap',
          }}>{label}</button>
        ))}
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 6 }}>
          <button onClick={handleShare} aria-label="Copy shareable link" style={{
            padding: '5px 10px', fontSize: 10, fontFamily: 'var(--mono)',
            background: copied ? 'var(--green-dim)' : 'var(--bg-3)',
            color: copied ? 'var(--green)' : 'var(--text-2)',
            border: '1px solid var(--border)', borderRadius: 'var(--radius)',
            cursor: 'pointer',
          }}>{copied ? '✓ Copied' : 'Share'}</button>
          <button onClick={() => handleExport('csv')} aria-label="Export as CSV" style={{
            padding: '5px 10px', fontSize: 10, fontFamily: 'var(--mono)',
            background: 'var(--bg-3)', color: 'var(--text-2)',
            border: '1px solid var(--border)', borderRadius: 'var(--radius)',
            cursor: 'pointer',
          }}>CSV</button>
          <button onClick={() => handleExport('gpx')} aria-label="Export as GPX" style={{
            padding: '5px 10px', fontSize: 10, fontFamily: 'var(--mono)',
            background: 'var(--bg-3)', color: 'var(--text-2)',
            border: '1px solid var(--border)', borderRadius: 'var(--radius)',
            cursor: 'pointer',
          }}>GPX</button>
        </div>
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflowY: 'auto', padding: 12 }}>
        {tab === 'routes' && (
          <RouteList
            vehicles={result.vehicles}
            selectedVehicle={selectedVehicle}
            onSelect={onSelectVehicle}
          />
        )}
        {tab === 'unassigned' && (
          <UnassignedList
            unassigned={result.unassigned}
            labels={result.unassigned_labels}
          />
        )}
        {tab === 'chart' && (
          <ChartsView vehicles={result.vehicles} />
        )}
        {tab === 'json' && (
          <JsonView result={result} />
        )}
      </div>
    </div>
  )
}

function RouteList({ vehicles, selectedVehicle, onSelect }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      {vehicles.map((v, i) => {
        const color = vehicleColor(i)
        const isSelected = selectedVehicle === v.vehicle_id
        return (
          <div
            key={v.vehicle_id}
            role="button"
            tabIndex={0}
            aria-pressed={isSelected}
            aria-label={`Vehicle ${v.vehicle_id}${isSelected ? ', selected' : ''}`}
            onClick={() => onSelect(isSelected ? null : v.vehicle_id)}
            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') onSelect(isSelected ? null : v.vehicle_id) }}
            style={{
              background: isSelected ? 'var(--bg-3)' : 'var(--bg-2)',
              borderStyle: 'solid',
              borderColor: isSelected ? color : 'var(--border)',
              borderWidth: 1,
              borderLeftWidth: 3,
              borderRadius: 'var(--radius)', padding: '10px 12px',
              cursor: 'pointer', transition: 'all 0.15s',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
              <span style={{ fontFamily: 'var(--mono)', fontSize: 11, fontWeight: 600, color }}>
                VEHICLE {v.vehicle_id}
              </span>
              <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
                {(() => {
                  const priorities = v.waypoints.map(wp => wp.priority).filter(Boolean)
                  const maxP = priorities.length ? Math.max(...priorities) : 1
                  const pColors = { 5: '#f2614a', 4: '#f5a623', 3: '#f5d623', 2: '#4b9eff', 1: '#6b7280' }
                  return priorities.length > 0 ? (
                    <span style={{
                      fontSize: 9, fontFamily: 'var(--mono)', fontWeight: 600,
                      color: pColors[maxP], background: `${pColors[maxP]}15`,
                      padding: '1px 5px', borderRadius: 3,
                    }}>P{maxP}</span>
                  ) : null
                })()}
                <span style={{
                  background: 'var(--bg-3)', fontSize: 10, fontFamily: 'var(--mono)',
                  color: 'var(--text-3)', padding: '2px 6px', borderRadius: 3
                }}>
                  {v.route.length - 2} stops
                </span>
              </div>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8 }}>
              <Metric label="Distance" value={`${v.distance_km} km`} />
              <Metric label="Time" value={`${v.time_minutes} min`} />
              <Metric label="Packages" value={v.packages_delivered} />
            </div>
            {isSelected && (
              <div style={{ marginTop: 8, paddingTop: 8, borderTop: '1px solid var(--border)' }}>
                <div style={{ fontSize: 10, color: 'var(--text-3)', fontFamily: 'var(--mono)', marginBottom: 6 }}>
                  STOPS ({v.waypoints.length - 2} deliveries):
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  {v.waypoints.map((wp, wi) => {
                    const isDepot = wi === 0 || wi === v.waypoints.length - 1
                    const arrival = v.arrival_times?.[wi]
                    const mins = arrival != null ? Math.floor(arrival / 60) : null
                    const secs = arrival != null ? arrival % 60 : null
                    return (
                      <div key={wi} style={{
                        display: 'flex', alignItems: 'center', gap: 6,
                        padding: '3px 6px', borderRadius: 3,
                        background: isDepot ? 'var(--bg-3)' : 'transparent',
                        fontSize: 10, fontFamily: 'var(--mono)', color: 'var(--text-2)',
                      }}>
                        <span style={{ color: isDepot ? 'var(--accent)' : 'var(--text-3)', width: 14, flexShrink: 0 }}>
                          {isDepot ? '⬡' : '•'}
                        </span>
                        <span style={{ flex: '0 0 auto', color: 'var(--text-3)', width: 60 }}>
                          {isDepot ? 'Depot' : `#${wp.id}`}
                        </span>
                        <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {wp.label || (v.route_labels?.[wi] || '') || (isDepot ? 'Depot' : `Stop ${wp.id}`)}
                        </span>
                        {arrival != null && !isDepot && (
                          <span style={{ color: 'var(--text-3)', flexShrink: 0 }}>
                            {`${mins}:${String(secs).padStart(2, '0')}`}
                          </span>
                        )}
                      </div>
                    )
                  })}
                </div>
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

function Metric({ label, value }) {
  return (
    <div>
      <div style={{ fontSize: 12, fontFamily: 'var(--mono)', color: 'var(--text)', fontWeight: 500 }}>{value}</div>
      <div style={{ fontSize: 10, color: 'var(--text-3)', fontFamily: 'var(--mono)' }}>{label}</div>
    </div>
  )
}

function UnassignedList({ unassigned, labels }) {
  if (!unassigned.length) {
    return (
      <div style={{ textAlign: 'center', padding: 40 }}>
        <div style={{ fontSize: 32, marginBottom: 10 }}>✅</div>
        <p style={{ color: 'var(--green)', fontFamily: 'var(--mono)', fontSize: 13 }}>
          All locations assigned!
        </p>
      </div>
    )
  }
  return (
    <div>
      <div style={{
        background: 'var(--red-dim)', border: '1px solid var(--red)',
        borderRadius: 'var(--radius)', padding: '10px 14px', marginBottom: 12,
        fontSize: 12, color: 'var(--red)', fontFamily: 'var(--mono)'
      }}>
        ⚠ {unassigned.length} locations could not be served within constraints
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
        {unassigned.map((id, i) => (
          <div key={id} style={{
            background: 'var(--bg-2)', border: '1px solid var(--border)',
            borderRadius: 4, padding: '4px 8px',
            fontSize: 11, fontFamily: 'var(--mono)', color: 'var(--text-2)'
          }}>
            #{id}{labels[i] ? ` · ${labels[i]}` : ''}
          </div>
        ))}
      </div>
    </div>
  )
}

function ChartsView({ vehicles }) {
  const distData = vehicles.map((v, i) => ({
    name: `V${v.vehicle_id}`, dist: v.distance_km, color: vehicleColor(i)
  }))
  const timeData = vehicles.map((v, i) => ({
    name: `V${v.vehicle_id}`, time: v.time_minutes, color: vehicleColor(i)
  }))

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <ChartBlock title="Distance per Vehicle (km)" dataKey="dist" data={distData} />
      <ChartBlock title="Time per Vehicle (min)" dataKey="time" data={timeData} />
    </div>
  )
}

function ChartBlock({ title, dataKey, data }) {
  return (
    <div>
      <div style={{ fontSize: 11, fontFamily: 'var(--mono)', color: 'var(--text-3)', marginBottom: 10, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
        {title}
      </div>
      <ResponsiveContainer width="100%" height={160}>
        <BarChart data={data} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
          <XAxis dataKey="name" tick={{ fill: 'var(--text-3)', fontSize: 9, fontFamily: 'var(--mono)' }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fill: 'var(--text-3)', fontSize: 9, fontFamily: 'var(--mono)' }} axisLine={false} tickLine={false} />
          <Tooltip
            contentStyle={{ background: 'var(--bg-2)', border: '1px solid var(--border)', borderRadius: 4, fontSize: 11, fontFamily: 'var(--mono)' }}
            labelStyle={{ color: 'var(--text)', marginBottom: 4 }}
          />
          <Bar dataKey={dataKey} radius={[2, 2, 0, 0]}>
            {data.map((entry, i) => <Cell key={i} fill={entry.color} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

function JsonView({ result }) {
  const [copied, setCopied] = useState(false)
  const json = JSON.stringify(result, null, 2)

  const copy = () => {
    navigator.clipboard.writeText(json)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 8 }}>
        <button onClick={copy} style={{
          fontSize: 11, fontFamily: 'var(--mono)',
          background: copied ? 'var(--green-dim)' : 'var(--bg-3)',
          color: copied ? 'var(--green)' : 'var(--text-2)',
          border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: '4px 12px'
        }}>
          {copied ? '✓ Copied' : 'Copy JSON'}
        </button>
      </div>
      <pre style={{
        fontFamily: 'var(--mono)', fontSize: 10, lineHeight: 1.6,
        color: 'var(--text-2)', whiteSpace: 'pre-wrap', wordBreak: 'break-all',
        background: 'var(--bg-2)', border: '1px solid var(--border)',
        borderRadius: 'var(--radius)', padding: 12, overflowY: 'auto',
        maxHeight: 'calc(100vh - 250px)',
      }}>
        {json}
      </pre>
    </div>
  )
}
