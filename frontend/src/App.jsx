import { useState, useCallback, useRef, useEffect } from 'react'
import { Routes, Route, useSearchParams } from 'react-router-dom'
import Header from './components/Header.jsx'
import UploadPanel from './components/UploadPanel.jsx'
import MapView from './components/MapView.jsx'
import ResultsPanel from './components/ResultsPanel.jsx'
import MetricsBar from './components/MetricsBar.jsx'
import ProtectedRoute from './components/ProtectedRoute.jsx'
import ErrorBoundary from './ErrorBoundary.jsx'
import LoginPage from './pages/LoginPage.jsx'
import RegisterPage from './pages/RegisterPage.jsx'
import HistoryPage from './pages/HistoryPage.jsx'
import DashboardPage from './pages/DashboardPage.jsx'
import DriversPage from './pages/DriversPage.jsx'
import DriverDetailPage from './pages/DriverDetailPage.jsx'
import NotificationSettingsPage from './pages/NotificationSettingsPage.jsx'
import BillingPage from './pages/BillingPage.jsx'
import AdminPage from './pages/AdminPage.jsx'
import ApiKeysPage from './pages/ApiKeysPage.jsx'
import useWebSocket from './hooks/useWebSocket.js'
import { optimizeRoutes, getJobResult } from './api.js'
import { useAuth } from './context/AuthContext.jsx'
import { ThemeProvider } from './context/ThemeContext.jsx'

export default function App() {
  return (
    <ThemeProvider>
      <ErrorBoundary>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route
            path="/history"
            element={
              <ProtectedRoute>
                <HistoryPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <DashboardPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/drivers"
            element={
              <ProtectedRoute>
                <DriversPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/drivers/:id"
            element={
              <ProtectedRoute>
                <DriverDetailPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/notifications"
            element={
              <ProtectedRoute>
                <NotificationSettingsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/billing"
            element={
              <ProtectedRoute>
                <BillingPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin"
            element={
              <ProtectedRoute>
                <AdminPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/api-keys"
            element={
              <ProtectedRoute>
                <ApiKeysPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="*"
            element={
              <ProtectedRoute>
                <AppContent />
              </ProtectedRoute>
            }
          />
        </Routes>
      </ErrorBoundary>
    </ThemeProvider>
  )
}

function AppContent() {
  const { token } = useAuth()
  const [searchParams, setSearchParams] = useSearchParams()
  const [phase, setPhase] = useState('idle')
  const [jobData, setJobData] = useState(null)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [selectedVehicle, setSelectedVehicle] = useState(null)
  const [solverProgress, setSolverProgress] = useState({ pct: 0, message: '' })
  const [runId, setRunId] = useState(null)
  const loadedRef = useRef(false)

  // WebSocket progress listener
  const onWsMessage = useCallback((data) => {
    if (data.type === 'progress') {
      setSolverProgress({ pct: data.pct || 0, message: data.message || '' })
    }
  }, [])
  useWebSocket(runId, runId ? token : null, onWsMessage)

  // Load from URL on mount
  useEffect(() => {
    if (loadedRef.current) return
    const jobId = searchParams.get('job')
    if (jobId && token) {
      loadedRef.current = true
      setPhase('solving')
      getJobResult(jobId, token)
        .then((data) => {
          setResult(data)
          setPhase('results')
        })
        .catch(() => {
          setPhase('idle')
        })
    }
  }, [searchParams, token])

  const handleSubmit = useCallback(
    async (payload) => {
      const id = crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).slice(2)
      setRunId(id)
      setPhase('solving')
      setError(null)
      setResult(null)
      setSelectedVehicle(null)
      setSolverProgress({ pct: 0, message: 'Request queued...' })

      try {
        const data = await optimizeRoutes(payload, token, id)
        setRunId(null)
        setSolverProgress({ pct: 100, message: 'Complete!' })
        setJobData(payload)
        setResult(data)
        setPhase('results')
        loadedRef.current = true
        setSearchParams({ job: data.job_id }, { replace: true })
      } catch (err) {
        setRunId(null)
        setError(err.message || 'Optimization failed')
        setPhase('error')
      }
    },
    [token, setSearchParams],
  )

  const handleReset = useCallback(() => {
    setRunId(null)
    setPhase('idle')
    setJobData(null)
    setResult(null)
    setError(null)
    setSelectedVehicle(null)
    setSolverProgress({ pct: 0, message: '' })
    loadedRef.current = false
    setSearchParams({}, { replace: true })
  }, [setSearchParams])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
      <Header onReset={handleReset} phase={phase} />

      {phase === 'results' && result && <MetricsBar result={result} />}

      <main
        className="optimize-main"
        style={{
          flex: 1,
          display: 'grid',
          gridTemplateColumns: phase === 'results' ? 'minmax(320px, 380px) 1fr' : '1fr',
          gap: 0,
          overflow: 'hidden',
          height: phase === 'results' ? 'calc(100vh - 120px)' : 'calc(100vh - 64px)',
        }}
      >
        {(phase === 'idle' || phase === 'error') && (
          <UploadPanel phase={phase} error={error} onSubmit={handleSubmit} onReset={handleReset} />
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
              depots={jobData?.depots}
              deliveries={jobData?.deliveries}
              selectedVehicle={selectedVehicle}
              onSelectVehicle={setSelectedVehicle}
            />
          </>
        )}

        {phase === 'solving' && <SolvingScreen progress={solverProgress} />}
      </main>
    </div>
  )
}

function SolvingScreen({ progress }) {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 24,
        padding: 40,
        gridColumn: '1/-1',
      }}
    >
      <div style={{ width: '100%', maxWidth: 480 }}>
        <div
          style={{
            height: 6,
            background: 'var(--bg-3)',
            borderRadius: 3,
            overflow: 'hidden',
            marginBottom: 8,
          }}
        >
          <div
            style={{
              width: `${progress.pct || 0}%`,
              height: '100%',
              background: 'var(--accent)',
              borderRadius: 3,
              transition: 'width 0.4s ease',
            }}
          />
        </div>
        <p
          style={{
            textAlign: 'center',
            fontFamily: 'var(--mono)',
            fontSize: 11,
            color: 'var(--text-2)',
          }}
        >
          {progress.message || 'Solving...'}
        </p>
      </div>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(2, 1fr)',
          gap: 12,
          maxWidth: 480,
          width: '100%',
        }}
      >
        {[
          ['Building matrix', 10],
          ['Solving VRP', 30],
          ['Optimizing', 50],
          ['Formatting', 90],
        ].map(([label, threshold], i) => {
          const active = (progress.pct || 0) >= threshold
          return (
            <div
              key={i}
              style={{
                background: active ? 'var(--accent-dim)' : 'var(--bg-2)',
                border: `1px solid ${active ? 'var(--accent)' : 'var(--border)'}`,
                borderRadius: 'var(--radius)',
                padding: '10px 14px',
                fontSize: 11,
                color: active ? 'var(--accent)' : 'var(--text-3)',
                fontFamily: 'var(--mono)',
                transition: 'all 0.3s',
              }}
            >
              {active ? '▶' : '○'} {label}
            </div>
          )
        })}
      </div>
    </div>
  )
}
