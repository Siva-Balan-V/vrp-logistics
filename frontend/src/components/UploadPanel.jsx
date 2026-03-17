import { useState, useCallback, useRef } from 'react'

const SAMPLE_LONDON_MINI = {
  depot: { id: 0, lat: 51.5074, lon: -0.1278, demand: 0, label: 'London Depot' },
  deliveries: Array.from({ length: 30 }, (_, i) => ({
    id: i + 1,
    lat: 51.5074 + (Math.random() - 0.5) * 0.12,
    lon: -0.1278 + (Math.random() - 0.5) * 0.18,
    demand: Math.floor(Math.random() * 4) + 1,
    label: `Stop-${String(i + 1).padStart(3, '0')}`,
  })),
  vehicles: { count: 5, capacity: 50, max_route_duration_seconds: 9000, speed_kmh: 30 },
}

function genSample(n, city) {
  const centres = {
    london:   [51.5074, -0.1278],
    berlin:   [52.520,   13.405],
    new_york: [40.7128, -74.006],
    paris:    [48.8566,   2.352],
    tokyo:    [35.6762, 139.650],
  }
  const [clat, clon] = centres[city] || centres.london
  const deliveries = Array.from({ length: n }, (_, i) => {
    const angle = Math.random() * 2 * Math.PI
    const r = Math.random() * 0.09
    return {
      id: i + 1,
      lat: parseFloat((clat + r * Math.cos(angle)).toFixed(6)),
      lon: parseFloat((clon + r * Math.sin(angle) * 1.4).toFixed(6)),
      demand: Math.floor(Math.random() * 4) + 1,
      label: `Stop-${String(i + 1).padStart(3, '0')}`,
    }
  })
  return {
    depot: { id: 0, lat: clat, lon: clon, demand: 0, label: `${city.charAt(0).toUpperCase() + city.slice(1)} Depot` },
    deliveries,
    vehicles: { count: 18, capacity: 50, max_route_duration_seconds: 9000, speed_kmh: 30 },
  }
}

export default function UploadPanel({ phase, error, onSubmit, onReset }) {
  const [mode, setMode] = useState('generate') // 'generate' | 'upload' | 'paste'
  const [city, setCity] = useState('london')
  const [nLocs, setNLocs] = useState(60)
  const [nVehicles, setNVehicles] = useState(18)
  const [capacity, setCapacity] = useState(50)
  const [speed, setSpeed] = useState(30)
  const [routing, setRouting] = useState('haversine')
  const [pasteText, setPasteText] = useState('')
  const [pasteError, setPasteError] = useState('')
  const [dragOver, setDragOver] = useState(false)
  const fileRef = useRef(null)

  const handleGenerate = useCallback(() => {
    const payload = genSample(nLocs, city)
    payload.vehicles.count = nVehicles
    payload.vehicles.capacity = capacity
    payload.vehicles.speed_kmh = speed
    payload.routing_backend = routing
    onSubmit(payload)
  }, [nLocs, city, nVehicles, capacity, speed, routing, onSubmit])

  const handleFileUpload = useCallback((file) => {
    const reader = new FileReader()
    reader.onload = (e) => {
      try {
        const json = JSON.parse(e.target.result)
        json.routing_backend = routing
        onSubmit(json)
      } catch {
        setPasteError('Invalid JSON file')
      }
    }
    reader.readAsText(file)
  }, [routing, onSubmit])

  const handlePasteSubmit = useCallback(() => {
    try {
      const json = JSON.parse(pasteText)
      json.routing_backend = routing
      onSubmit(json)
    } catch {
      setPasteError('Invalid JSON – check format')
    }
  }, [pasteText, routing, onSubmit])

  const onDrop = useCallback((e) => {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files[0]
    if (file) handleFileUpload(file)
  }, [handleFileUpload])

  const disabled = phase === 'solving'

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      justifyContent: 'center', minHeight: '100%',
      background: 'var(--bg)', padding: '40px 24px',
    }}>
      <div style={{
        width: '100%', maxWidth: 560,
        animation: 'fadeUp 0.4s ease both',
      }}>
        {/* Title */}
        <div style={{ marginBottom: 32, textAlign: 'center' }}>
          <h1 style={{
            fontFamily: 'var(--display)', fontSize: 36, fontWeight: 800,
            letterSpacing: '-0.04em', lineHeight: 1.1, marginBottom: 10
          }}>
            Last-Mile<br />
            <span style={{ color: 'var(--accent)' }}>Route Optimizer</span>
          </h1>
          <p style={{ color: 'var(--text-2)', fontSize: 14, lineHeight: 1.6 }}>
            Solve 600+ delivery locations across 18+ vehicles<br />
            using Google OR-Tools with real road-network distances.
          </p>
        </div>

        {/* Mode tabs */}
        <div style={{
          display: 'flex', background: 'var(--bg-2)',
          borderRadius: 'var(--radius)', padding: 3,
          marginBottom: 24, border: '1px solid var(--border)',
        }}>
          {[['generate','⚡ Generate'], ['upload','📁 Upload JSON'], ['paste','✏️ Paste JSON']].map(([m, label]) => (
            <button key={m} onClick={() => setMode(m)} style={{
              flex: 1, padding: '8px 0', fontSize: 12, fontWeight: 500,
              borderRadius: 4, transition: 'all 0.15s',
              background: mode === m ? 'var(--bg-3)' : 'transparent',
              color: mode === m ? 'var(--text)' : 'var(--text-2)',
              border: mode === m ? '1px solid var(--border-hover)' : '1px solid transparent',
            }}>
              {label}
            </button>
          ))}
        </div>

        {/* Card */}
        <div style={{
          background: 'var(--bg-1)', border: '1px solid var(--border)',
          borderRadius: 'var(--radius-lg)', padding: 24, marginBottom: 20,
        }}>
          {mode === 'generate' && (
            <GenerateForm
              city={city} setCity={setCity}
              nLocs={nLocs} setNLocs={setNLocs}
              nVehicles={nVehicles} setNVehicles={setNVehicles}
              capacity={capacity} setCapacity={setCapacity}
              speed={speed} setSpeed={setSpeed}
            />
          )}

          {mode === 'upload' && (
            <div
              onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
              onDragLeave={() => setDragOver(false)}
              onDrop={onDrop}
              onClick={() => fileRef.current?.click()}
              style={{
                border: `2px dashed ${dragOver ? 'var(--accent)' : 'var(--border)'}`,
                borderRadius: 'var(--radius)', padding: '40px 20px',
                textAlign: 'center', cursor: 'pointer',
                background: dragOver ? 'var(--accent-dim)' : 'var(--bg-2)',
                transition: 'all 0.15s',
              }}
            >
              <div style={{ fontSize: 32, marginBottom: 10 }}>📦</div>
              <p style={{ color: 'var(--text-2)', fontSize: 13 }}>
                Drop a JSON file or <span style={{ color: 'var(--accent)' }}>click to browse</span>
              </p>
              <p style={{ color: 'var(--text-3)', fontSize: 11, marginTop: 6, fontFamily: 'var(--mono)' }}>
                Format: {`{ depot, deliveries[], vehicles }`}
              </p>
              <input ref={fileRef} type="file" accept=".json"
                style={{ display: 'none' }}
                onChange={(e) => { if (e.target.files[0]) handleFileUpload(e.target.files[0]) }}
              />
            </div>
          )}

          {mode === 'paste' && (
            <div>
              <label style={{ fontSize: 12, color: 'var(--text-2)', fontFamily: 'var(--mono)', display: 'block', marginBottom: 8 }}>
                Paste OptimizeRequest JSON:
              </label>
              <textarea
                rows={10}
                value={pasteText}
                onChange={(e) => { setPasteText(e.target.value); setPasteError('') }}
                placeholder={'{\n  "depot": {...},\n  "deliveries": [...],\n  "vehicles": {...}\n}'}
                style={{
                  width: '100%', fontFamily: 'var(--mono)', fontSize: 12,
                  resize: 'vertical', background: 'var(--bg-2)',
                  border: `1px solid ${pasteError ? 'var(--red)' : 'var(--border)'}`,
                  borderRadius: 'var(--radius)', padding: 12, color: 'var(--text)'
                }}
              />
              {pasteError && (
                <p style={{ color: 'var(--red)', fontSize: 11, marginTop: 4, fontFamily: 'var(--mono)' }}>
                  ✗ {pasteError}
                </p>
              )}
            </div>
          )}
        </div>

        {/* Routing backend */}
        <div style={{
          background: 'var(--bg-1)', border: '1px solid var(--border)',
          borderRadius: 'var(--radius-lg)', padding: '16px 20px',
          marginBottom: 20, display: 'flex', alignItems: 'center',
          gap: 16, flexWrap: 'wrap'
        }}>
          <span style={{ fontSize: 12, color: 'var(--text-2)', fontFamily: 'var(--mono)', flex: '0 0 auto' }}>
            Distance backend:
          </span>
          {[['haversine','Haversine (fast)'],['osrm','OSRM (road)'],['ors','ORS (road+key)']].map(([v, label]) => (
            <label key={v} style={{ display: 'flex', alignItems: 'center', gap: 6,
              cursor: 'pointer', fontSize: 12, color: routing === v ? 'var(--accent)' : 'var(--text-2)' }}>
              <input type="radio" name="routing" value={v}
                checked={routing === v} onChange={() => setRouting(v)}
                style={{ accentColor: 'var(--accent)' }}
              />
              {label}
            </label>
          ))}
        </div>

        {/* Error */}
        {error && (
          <div style={{
            background: 'var(--red-dim)', border: '1px solid var(--red)',
            borderRadius: 'var(--radius)', padding: '10px 14px',
            color: 'var(--red)', fontSize: 13, fontFamily: 'var(--mono)',
            marginBottom: 16
          }}>✗ {error}</div>
        )}

        {/* Submit */}
        <button
          disabled={disabled}
          onClick={mode === 'generate' ? handleGenerate : mode === 'paste' ? handlePasteSubmit : undefined}
          style={{
            width: '100%', padding: '14px 0', fontSize: 15, fontWeight: 700,
            fontFamily: 'var(--display)', letterSpacing: '-0.01em',
            background: disabled ? 'var(--bg-3)' : 'var(--accent)',
            color: disabled ? 'var(--text-3)' : '#000',
            border: 'none', borderRadius: 'var(--radius-lg)',
            cursor: disabled ? 'not-allowed' : 'pointer',
            transition: 'all 0.2s',
            boxShadow: disabled ? 'none' : 'var(--shadow-accent)',
          }}
        >
          {disabled ? 'Solving…' : '⚡ Optimize Routes'}
        </button>
      </div>
    </div>
  )
}

function Field({ label, children }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <label style={{ fontSize: 11, fontFamily: 'var(--mono)', color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
        {label}
      </label>
      {children}
    </div>
  )
}

function GenerateForm({ city, setCity, nLocs, setNLocs, nVehicles, setNVehicles, capacity, setCapacity, speed, setSpeed }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
      <Field label="City">
        <select value={city} onChange={(e) => setCity(e.target.value)} style={{ width: '100%' }}>
          {['london','berlin','new_york','paris','tokyo'].map(c => (
            <option key={c} value={c}>{c.charAt(0).toUpperCase() + c.slice(1).replace('_',' ')}</option>
          ))}
        </select>
      </Field>

      <Field label={`Deliveries: ${nLocs}`}>
        <input type="range" min={10} max={600} step={10}
          value={nLocs} onChange={(e) => setNLocs(+e.target.value)}
          style={{ accentColor: 'var(--accent)', width: '100%', cursor: 'pointer' }}
        />
      </Field>

      <Field label={`Vehicles: ${nVehicles}`}>
        <input type="range" min={1} max={50} step={1}
          value={nVehicles} onChange={(e) => setNVehicles(+e.target.value)}
          style={{ accentColor: 'var(--accent)', width: '100%', cursor: 'pointer' }}
        />
      </Field>

      <Field label={`Capacity: ${capacity} pkgs`}>
        <input type="range" min={5} max={200} step={5}
          value={capacity} onChange={(e) => setCapacity(+e.target.value)}
          style={{ accentColor: 'var(--accent)', width: '100%', cursor: 'pointer' }}
        />
      </Field>

      <Field label={`Speed: ${speed} km/h`}>
        <input type="range" min={10} max={80} step={5}
          value={speed} onChange={(e) => setSpeed(+e.target.value)}
          style={{ accentColor: 'var(--accent)', width: '100%', cursor: 'pointer' }}
        />
      </Field>

      <Field label="Max route: 2.5 h">
        <div style={{
          background: 'var(--bg-3)', border: '1px solid var(--border)',
          borderRadius: 'var(--radius)', padding: '8px 12px',
          fontSize: 13, fontFamily: 'var(--mono)', color: 'var(--text-2)'
        }}>
          9000 s (fixed)
        </div>
      </Field>
    </div>
  )
}
