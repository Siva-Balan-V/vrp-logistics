import { useState, useCallback } from 'react'
import Header from './components/Header.jsx'
import UploadPanel from './components/UploadPanel.jsx'
import MapView from './components/MapView.jsx'
import ResultsPanel from './components/ResultsPanel.jsx'
import MetricsBar from './components/MetricsBar.jsx'
import { optimizeRoutes } from './api.js'

export default function App() {
  const [phase, setPhase] = useState('idle') // idle | solving | results | error
  const [jobData, setJobData] = useState(null)
  const [result, setResult]   = useState(null)
  const [error, setError]     = useState(null)
  const [selectedVehicle, setSelectedVehicle] = useState(null)

  const handleSubmit = useCallback(async (payload) => {
    setPhase('solving')
    setError(null)
    setResult(null)
    setSelectedVehicle(null)
    try {
      const data = await optimizeRoutes(payload)
      setJobData(payload)
      setResult(data)
      setPhase('results')
    } catch (err) {
      setError(err.message || 'Optimization failed')
      setPhase('error')
    }
  }, [])

  const handleReset = useCallback(() => {
    setPhase('idle')
    setJobData(null)
    setResult(null)
    setError(null)
    setSelectedVehicle(null)
  }, [])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
      <Header onReset={handleReset} phase={phase} />

      {phase === 'results' && result && (
        <MetricsBar result={result} />
      )}

      <main style={{
        flex: 1,
        display: 'grid',
        gridTemplateColumns: phase === 'results' ? '380px 1fr' : '1fr',
        gap: 0,
        overflow: 'hidden',
        height: phase === 'results' ? 'calc(100vh - 120px)' : 'calc(100vh - 64px)',
      }}>
        {(phase === 'idle' || phase === 'error') && (
          <UploadPanel
            phase={phase}
            error={error}
            onSubmit={handleSubmit}
            onReset={handleReset}
          />
        )}

        {phase === 'results' && result && (
          <>
            <ResultsPanel
              result={result}
              selectedVehicle={selectedVehicle}
              onSelectVehicle={setSelectedVehicle}
            />
            <MapView
              result={result}
              depot={jobData?.depot}
              selectedVehicle={selectedVehicle}
              onSelectVehicle={setSelectedVehicle}
            />
          </>
        )}

        {phase === 'solving' && <SolvingScreen />}
      </main>
    </div>
  )
}

function SolvingScreen() {
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      justifyContent: 'center', gap: 24, padding: 40, gridColumn: '1/-1'
    }}>
      <div style={{
        width: 64, height: 64, border: '3px solid var(--border)',
        borderTopColor: 'var(--accent)', borderRadius: '50%',
        animation: 'spin 0.8s linear infinite'
      }} />
      <div style={{ textAlign: 'center' }}>
        <h2 style={{ fontFamily: 'var(--display)', marginBottom: 8, fontSize: 24 }}>
          Solving VRP
        </h2>
        <p style={{ color: 'var(--text-2)', fontFamily: 'var(--mono)', fontSize: 13 }}>
          OR-Tools GUIDED_LOCAL_SEARCH running…
        </p>
      </div>
      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12,
        maxWidth: 480, width: '100%'
      }}>
        {['Building distance matrix', 'Applying constraints', 'Optimizing routes'].map((s, i) => (
          <div key={i} style={{
            background: 'var(--bg-2)', border: '1px solid var(--border)',
            borderRadius: 'var(--radius)', padding: '10px 14px',
            fontSize: 11, color: 'var(--text-2)', fontFamily: 'var(--mono)',
            animation: `fadeUp 0.4s ${i * 0.15}s both`
          }}>
            <span style={{ color: 'var(--accent)', marginRight: 6 }}>▶</span>{s}
          </div>
        ))}
      </div>
    </div>
  )
}
