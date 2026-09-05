import { describe, it, expect } from 'vitest'
import { validatePayload } from '../components/UploadPanel.jsx'

const basePayload = {
  depot: { id: 0, lat: 51.5074, lon: -0.1278, demand: 0 },
  deliveries: [{ id: 1, lat: 51.51, lon: -0.07, demand: 1 }],
  vehicles: { count: 2, capacity: 50, max_route_duration_seconds: 9000, speed_kmh: 30 },
}

describe('validatePayload traffic rules', () => {
  it('rejects traffic=true when routing_backend is not "ors"', () => {
    const errors = validatePayload({ ...basePayload, traffic: true, routing_backend: 'haversine' })
    expect(
      errors.some((e) => e.includes('"traffic": true requires "routing_backend": "ors"')),
    ).toBe(true)
  })
})
