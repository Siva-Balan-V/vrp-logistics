import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useState } from 'react'
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import RouteDetails from '../components/RouteDetails.jsx'
import { AuthProvider } from '../context/AuthContext.jsx'
import { ThemeProvider } from '../context/ThemeContext.jsx'
import { fetchDirections } from '../api.js'

vi.mock('../api.js', () => ({
  vehicleColor: (i) => (i % 2 ? '#4b9eff' : '#f5a623'),
  fetchDirections: vi.fn(),
}))

const result = {
  job_id: 'job-123',
  vehicles_used: 2,
  unassigned_count: 0,
  unassigned: [],
  unassigned_labels: [],
  vehicles: [
    {
      vehicle_id: 'v1',
      route: ['a', 'b', 'c', 'a'],
      waypoints: [
        { id: 'a', lat: 1, lon: 2, priority: 1 },
        { id: 'b', lat: 3, lon: 4, priority: 2 },
        { id: 'c', lat: 5, lon: 6, priority: 2 },
        { id: 'a', lat: 1, lon: 2, priority: 1 },
      ],
      route_labels: ['Depot', 'Stop b', 'Stop c', 'Depot'],
      distance_km: 12,
      time_minutes: 22,
      packages_delivered: 2,
    },
    {
      vehicle_id: 'v2',
      route: ['a', 'z', 'a'],
      waypoints: [
        { id: 'a', lat: 1, lon: 2, priority: 1 },
        { id: 'z', lat: 9, lon: 9, priority: 1 },
        { id: 'a', lat: 1, lon: 2, priority: 1 },
      ],
      route_labels: ['Depot', 'Stop z', 'Depot'],
      distance_km: 5,
      time_minutes: 8,
      packages_delivered: 1,
    },
  ],
}

const directionsFor = (idx) => ({
  job_id: 'job-123',
  route_index: idx,
  source: 'haversine',
  steps: [
    {
      instruction: `V${idx} Depart depot`,
      distance_m: 1200,
      duration_s: 144,
      lon: 2,
      lat: 1,
      maneuver: 'depart',
    },
    {
      instruction: `V${idx} Turn right onto Main St`,
      distance_m: 800,
      duration_s: 96,
      lon: 4,
      lat: 3,
      maneuver: 'right',
    },
  ],
  geometry: [
    [2, 1],
    [3, 2],
    [4, 3],
  ],
})

function Harness({ onFocusStep = vi.fn() }) {
  const [selected, setSelected] = useState(result.vehicles[0].vehicle_id)
  const [directions, setDirections] = useState(null)
  return (
    <ThemeProvider>
      <AuthProvider>
        <RouteDetails
          result={result}
          selectedVehicle={selected}
          onSelectVehicle={setSelected}
          directions={directions}
          onDirectionsChange={setDirections}
          onFocusStep={onFocusStep}
        />
      </AuthProvider>
    </ThemeProvider>
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  fetchDirections.mockResolvedValue(directionsFor(0))
})

function flush() {
  return act(() => new Promise((resolve) => setTimeout(resolve, 0)))
}

describe('RouteDetails', () => {
  it('renders a tab per vehicle', async () => {
    render(<Harness />)
    await flush()
    expect(screen.getByRole('tab', { name: /Vv1/ })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /Vv2/ })).toBeInTheDocument()
  })

  it('fetches and renders directions for the active vehicle', async () => {
    render(<Harness />)
    await flush()
    await waitFor(() => expect(screen.getByText('V0 Turn right onto Main St')).toBeInTheDocument())
    expect(screen.getByText('haversine')).toBeInTheDocument()
    expect(fetchDirections).toHaveBeenCalledWith('job-123', 0, null)
  })

  it('loads directions when switching vehicle tabs', async () => {
    fetchDirections.mockImplementation((jobId, idx) => Promise.resolve(directionsFor(idx)))
    render(<Harness />)
    await flush()
    await waitFor(() => expect(screen.getByText('V0 Depart depot')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('tab', { name: /Vv2/ }))
    expect(fetchDirections).toHaveBeenLastCalledWith('job-123', 1, null)
    await waitFor(() => expect(screen.getByText('V1 Turn right onto Main St')).toBeInTheDocument())
  })

  it('focuses the map when a step is clicked', async () => {
    const onFocusStep = vi.fn()
    render(<Harness onFocusStep={onFocusStep} />)
    await flush()
    await waitFor(() => expect(screen.getByText('V0 Depart depot')).toBeInTheDocument())

    fireEvent.click(screen.getByText('V0 Turn right onto Main St'))
    expect(onFocusStep).toHaveBeenCalledWith({ lat: 3, lon: 4 })
  })
})
