import { useState } from 'react'
import { vehicleColor } from '../api.js'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'

export default function ResultsPanel({ result, selectedVehicle, onSelectVehicle }) {
  const [tab, setTab] = useState('routes') // routes | unassigned | chart | json

  return (
    <div style={{
      display: 'flex', flexDirection: 'column',
      background: 'var(--bg-1)', borderRight: '1px solid var(--border)',
      overflow: 'hidden', height: '100%',
    }}>
      {/* Tabs */}
      <div style={{
        display: 'flex', background: 'var(--bg-2)',
        borderBottom: '1px solid var(--border)', padding: '0 8px',
        flexShrink: 0,
      }}>
        {[
          ['routes', `Routes (${result.vehicles_used})`],
          ['unassigned', `Unassigned (${result.unassigned_count})`],
          ['chart', 'Charts'],
          ['json', 'JSON'],
        ].map(([key, label]) => (
          <button key={key} onClick={() => setTab(key)} style={{
            padding: '10px 14px', fontSize: 11, fontFamily: 'var(--mono)',
            background: 'none', borderBottom: tab === key ? '2px solid var(--accent)' : '2px solid transparent',
            color: tab === key ? 'var(--text)' : 'var(--text-3)',
            marginBottom: -1, transition: 'color 0.15s',
            whiteSpace: 'nowrap',
          }}>{label}</button>
        ))}
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
            onClick={() => onSelect(isSelected ? null : v.vehicle_id)}
            style={{
              background: isSelected ? 'var(--bg-3)' : 'var(--bg-2)',
              border: `1px solid ${isSelected ? color : 'var(--border)'}`,
              borderLeft: `3px solid ${color}`,
              borderRadius: 'var(--radius)', padding: '10px 12px',
              cursor: 'pointer', transition: 'all 0.15s',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
              <span style={{ fontFamily: 'var(--mono)', fontSize: 11, fontWeight: 600, color }}>
                VEHICLE {v.vehicle_id}
              </span>
              <span style={{
                background: 'var(--bg-3)', fontSize: 10, fontFamily: 'var(--mono)',
                color: 'var(--text-3)', padding: '2px 6px', borderRadius: 3
              }}>
                {v.route.length - 2} stops
              </span>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8 }}>
              <Metric label="Distance" value={`${v.distance_km} km`} />
              <Metric label="Time" value={`${v.time_minutes} min`} />
              <Metric label="Packages" value={v.packages_delivered} />
            </div>
            {isSelected && (
              <div style={{ marginTop: 8, paddingTop: 8, borderTop: '1px solid var(--border)' }}>
                <div style={{ fontSize: 10, color: 'var(--text-3)', fontFamily: 'var(--mono)', marginBottom: 4 }}>
                  ROUTE SEQUENCE:
                </div>
                <div style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--text-2)', lineHeight: 1.8, wordBreak: 'break-all' }}>
                  {v.route.join(' → ')}
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
