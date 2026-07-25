import { describe, it, expect, vi } from 'vitest'
import { vehicleColor, VEHICLE_COLORS } from '../api.js'

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
    VEHICLE_COLORS.forEach(color => {
      expect(color).toMatch(/^#[0-9a-f]{6}$/i)
    })
  })
})
