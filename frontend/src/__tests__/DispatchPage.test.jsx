import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import DispatchPage from '../pages/DispatchPage.jsx'
import { isOffline, OFFLINE_AFTER_MS } from '../components/DispatchMap.jsx'

const mockState = vi.hoisted(() => ({
  path: null,
  token: null,
  onMessage: null,
  AuthProvider: ({ children }) => children,
  useAuth: () => ({
    token: 'tok-123',
    user: { company_id: 'co-a', email: 'a@b.example', role: 'admin' },
    logout: vi.fn(),
  }),
  useTheme: () => ({ theme: 'dark', toggleTheme: vi.fn() }),
}))

vi.mock('../hooks/useWebSocket.js', () => ({
  default: (path, token, onMessage) => {
    mockState.path = path
    mockState.token = token
    mockState.onMessage = onMessage
  },
}))

vi.mock('../context/AuthContext.jsx', () => ({
  AuthProvider: mockState.AuthProvider,
  useAuth: mockState.useAuth,
}))

vi.mock('../context/ThemeContext.jsx', () => ({
  ThemeProvider: ({ children }) => children,
  useTheme: mockState.useTheme,
}))

vi.mock('../api.js', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    listDrivers: vi.fn(),
  }
})

vi.mock('../components/DispatchMap.jsx', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    default: ({ drivers, now }) => (
      <div data-testid="dispatch-map" data-count={drivers.length} data-now={now}>
        map:{drivers.length}
      </div>
    ),
  }
})

import { listDrivers } from '../api.js'

const now = Date.now()

const BASE_DRIVERS = [
  {
    id: 'd1',
    name: 'Jane',
    status: 'on_route',
    current_lat: 51.5,
    current_lon: -0.11,
    last_ping_at: new Date(now - 30000).toISOString(),
  },
  {
    id: 'd2',
    name: 'Bob',
    status: 'active',
    current_lat: 51.51,
    current_lon: -0.12,
    last_ping_at: new Date(now - 600000).toISOString(),
  },
]

beforeEach(() => {
  vi.clearAllMocks()
  mockState.path = null
  mockState.token = null
  mockState.onMessage = null
})

describe('DispatchPage', () => {
  it('shows the fleet roster from the API snapshot', async () => {
    listDrivers.mockResolvedValue(BASE_DRIVERS)
    render(<DispatchPage />)
    expect(await screen.findByText('Jane')).toBeInTheDocument()
    expect(screen.getByText('Bob')).toBeInTheDocument()
    waitFor(() => expect(screen.getByText('1 / 2 online')).toBeInTheDocument())
  })

  it('marks stale drivers as OFFLINE', async () => {
    const stale = {
      ...BASE_DRIVERS[0],
      last_ping_at: new Date(now - 60 * 60 * 1000).toISOString(),
    }
    listDrivers.mockResolvedValue([stale])
    render(<DispatchPage />)
    await screen.findByText('Jane')
    expect(screen.getByText('OFFLINE')).toBeInTheDocument()
    expect(screen.getByText('0 / 1 online')).toBeInTheDocument()
  })

  it('subscribes to the tenant-scoped fleet channel', async () => {
    listDrivers.mockResolvedValue([])
    render(<DispatchPage />)
    await screen.findByText('No drivers yet. Add one on the Drivers page to see it live here.')
    expect(mockState.path).toBe('/api/v1/ws/drivers/co-a')
    expect(mockState.token).toBe('tok-123')
  })

  it('applies a live driver.update broadcast', async () => {
    listDrivers.mockResolvedValue(BASE_DRIVERS)
    render(<DispatchPage />)
    await screen.findByText('Jane')

    mockState.onMessage({
      type: 'driver.update',
      company_id: 'co-a',
      driver_id: 'd3',
      name: 'Zola',
      status: 'on_route',
      lat: 51.52,
      lon: -0.13,
      last_ping_at: new Date().toISOString(),
      eta: {
        total_remaining_time_min: 42,
        total_remaining_distance_km: 8.5,
        remaining_stops: [{ id: 1, label: 'Stop 1', delta_min: 6 }],
      },
    })

    expect(await screen.findByText('Zola')).toBeInTheDocument()
    expect(screen.getByText('ETA 42 min (+6)')).toBeInTheDocument()
  })

  it('reflects a live fix on a driver that had none', async () => {
    const noFix = { ...BASE_DRIVERS[0], current_lat: null, current_lon: null }
    listDrivers.mockResolvedValue([noFix])
    render(<DispatchPage />)
    await screen.findByText('Jane')

    mockState.onMessage({
      type: 'driver.update',
      company_id: 'co-a',
      driver_id: 'd1',
      name: 'Jane',
      status: 'active',
      lat: 51.53,
      lon: -0.14,
      last_ping_at: new Date().toISOString(),
      eta: null,
    })
    expect(await screen.findByText('Jane')).toBeInTheDocument()
    expect(screen.getByText('no ETA yet')).toBeInTheDocument()
  })
})

describe('isOffline', () => {
  it('treats a missing ping as offline', () => {
    expect(isOffline(null, now)).toBe(true)
  })

  it('treats a fresh ping as online', () => {
    const recent = new Date(now - 60000).toISOString()
    expect(isOffline(recent, now)).toBe(false)
  })

  it('treats a stale ping as offline', () => {
    const stale = new Date(now - OFFLINE_AFTER_MS - 1).toISOString()
    expect(isOffline(stale, now)).toBe(true)
  })
})
