import { describe, it, expect, vi, beforeEach } from 'vitest'
import {
  optimizeRoutes as rawOptimizeRoutes,
  apiFetch,
  exportRoute,
  getRouteDirections,
  vehicleColor,
  VEHICLE_COLORS,
} from '../api.js'

// We use the real import but mock fetch globally
const mockFetch = vi.fn()
globalThis.fetch = mockFetch

describe('vehicleColor', () => {
  it('should return first color for index 0', () => {
    expect(vehicleColor(0)).toBe(VEHICLE_COLORS[0])
  })

  it('should cycle through colors', () => {
    expect(vehicleColor(VEHICLE_COLORS.length)).toBe(VEHICLE_COLORS[0])
    expect(vehicleColor(VEHICLE_COLORS.length + 1)).toBe(VEHICLE_COLORS[1])
  })

  it('should handle negative index', () => {
    const color = vehicleColor(-1)
    expect(VEHICLE_COLORS).toContain(color)
  })
})

describe('VEHICLE_COLORS', () => {
  it('should have at least 10 colors', () => {
    expect(VEHICLE_COLORS.length).toBeGreaterThanOrEqual(10)
  })

  it('should contain valid hex colors', () => {
    VEHICLE_COLORS.forEach((color) => {
      expect(color).toMatch(/^#[0-9a-f]{6}$/i)
    })
  })
})

describe('optimizeRoutes', () => {
  const samplePayload = {
    depot: { id: 0, lat: 51.5074, lon: -0.1278, demand: 0 },
    deliveries: [{ id: 1, lat: 51.515, lon: -0.072, demand: 1 }],
    vehicles: { count: 2, capacity: 50, max_route_duration_seconds: 9000 },
  }

  const sampleResponse = {
    job_id: 'test-job-123',
    status: 'success',
    solver_time_seconds: 1.23,
    vehicles: [{ vehicle_id: 1, route: [0, 1, 0] }],
    unassigned: [],
  }

  beforeEach(() => {
    mockFetch.mockReset()
  })

  it('should POST to /api/v1/optimize-routes', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(sampleResponse),
    })

    const result = await rawOptimizeRoutes(samplePayload)

    expect(mockFetch).toHaveBeenCalledTimes(1)
    const [url, options] = mockFetch.mock.calls[0]
    expect(url).toContain('/api/v1/optimize-routes')
    expect(options.method).toBe('POST')
    expect(options.headers['Content-Type']).toBe('application/json')
  })

  it('should return parsed JSON on success', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(sampleResponse),
    })

    const result = await rawOptimizeRoutes(samplePayload)
    expect(result).toEqual(sampleResponse)
  })

  it('should throw on HTTP error', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 422,
      json: () => Promise.resolve({ detail: 'Validation failed' }),
    })

    await expect(rawOptimizeRoutes(samplePayload)).rejects.toThrow('Validation failed')
  })

  it('should throw on 500 error', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: () => Promise.resolve({ detail: 'Internal server error' }),
    })

    await expect(rawOptimizeRoutes(samplePayload)).rejects.toThrow('Internal server error')
  })

  it('should fall back to status text when JSON parsing fails', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 503,
      statusText: 'Service Unavailable',
      json: () => Promise.reject(new Error('Invalid JSON')),
    })

    await expect(rawOptimizeRoutes(samplePayload)).rejects.toThrow('Service Unavailable')
  })

  it('should stringify the payload as JSON body', async () => {
    let requestBody
    mockFetch.mockImplementationOnce(async (url, options) => {
      requestBody = options.body
      return {
        ok: true,
        json: () => Promise.resolve(sampleResponse),
      }
    })

    await rawOptimizeRoutes(samplePayload)
    expect(requestBody).toBe(JSON.stringify(samplePayload))
  })
})

describe('apiFetch', () => {
  beforeEach(() => {
    mockFetch.mockReset()
  })

  it('should attach status to thrown errors', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 401,
      json: () => Promise.resolve({ detail: 'Unauthorized' }),
    })

    await expect(apiFetch('/api/v1/auth/me')).rejects.toMatchObject({
      message: 'Unauthorized',
      status: 401,
    })
  })

  it('should attach status even when body JSON parsing fails', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 503,
      statusText: 'Service Unavailable',
      json: () => Promise.reject(new Error('Invalid JSON')),
    })

    await expect(apiFetch('/api/v1/routes')).rejects.toMatchObject({
      message: 'Service Unavailable',
      status: 503,
    })
  })
})

describe('exportRoute', () => {
  beforeEach(() => {
    mockFetch.mockReset()
  })

  it('should attach status to thrown errors', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 404,
      json: () => Promise.resolve({ detail: 'No result found' }),
    })

    await expect(exportRoute('job-1', 'csv')).rejects.toMatchObject({
      message: 'No result found',
      status: 404,
    })
  })

  it('should include the bearer token header when provided', async () => {
    mockFetch.mockResolvedValueOnce({ ok: true, blob: () => Promise.resolve(new Blob()) })

    await exportRoute('job-1', 'gpx', 'secret-token')
    const [url, options] = mockFetch.mock.calls[0]
    expect(url).toContain('/api/v1/routes/job-1/export?format=gpx')
    expect(options.headers.Authorization).toBe('Bearer secret-token')
  })
})

describe('getRouteDirections', () => {
  beforeEach(() => {
    mockFetch.mockReset()
  })

  it('should fetch directions for a whole job when no vehicle given', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ job_id: 'job-1', backend: 'osrm', vehicles: [] }),
    })

    const data = await getRouteDirections('job-1', null, 'secret-token')

    expect(data.backend).toBe('osrm')
    const [url, options] = mockFetch.mock.calls[0]
    expect(url).toContain('/api/v1/routes/job-1/directions')
    expect(options.headers.Authorization).toBe('Bearer secret-token')
  })

  it('should include the vehicle_id query param when provided', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ job_id: 'job-1', backend: 'osrm', vehicles: [] }),
    })

    await getRouteDirections('job-1', 3, null)

    const [url] = mockFetch.mock.calls[0]
    expect(url).toContain('/api/v1/routes/job-1/directions?vehicle_id=3')
  })

  it('should throw on error', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 404,
      json: () => Promise.resolve({ detail: 'No result found' }),
    })

    await expect(getRouteDirections('nope', null, null)).rejects.toMatchObject({
      message: 'No result found',
      status: 404,
    })
  })
})
