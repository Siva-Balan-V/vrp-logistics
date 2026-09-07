import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import ResultsPanel from '../components/ResultsPanel.jsx'
import { AuthProvider } from '../context/AuthContext.jsx'
import { ThemeProvider } from '../context/ThemeContext.jsx'

vi.mock('../api.js', () => ({
  vehicleColor: (i) => (i % 2 ? '#4b9eff' : '#f5a623'),
  exportRoute: vi.fn(),
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
      route: ['a', 'b', 'a'],
      waypoints: [
        { id: 'a', lat: 1, lon: 2 },
        { id: 'b', lat: 3, lon: 4 },
        { id: 'a', lat: 1, lon: 2 },
      ],
      distance_km: 8,
      time_minutes: 12,
      packages_delivered: 1,
    },
  ],
}

function renderPanel() {
  return render(
    <ThemeProvider>
      <AuthProvider>
        <ResultsPanel
          result={result}
          selectedVehicle={null}
          onSelectVehicle={() => {}}
          directions={null}
          onDirectionsChange={() => {}}
          onFocusStep={() => {}}
        />
      </AuthProvider>
    </ThemeProvider>,
  )
}

describe('ResultsPanel keyboard tab navigation', () => {
  it('arrow keys move between result tabs', () => {
    vi.spyOn(HTMLButtonElement.prototype, 'focus')
    renderPanel()
    const routes = screen.getByRole('tab', { name: /routes/i })
    routes.focus()
    const tablist = routes.closest('[role="tablist"]')
    fireEvent.keyDown(tablist, { key: 'ArrowRight' })
    expect(screen.getByRole('tab', { name: /unassigned/i })).toHaveAttribute(
      'aria-selected',
      'true',
    )
    fireEvent.keyDown(tablist, { key: 'ArrowRight' })
    expect(screen.getByRole('tab', { name: /charts/i })).toHaveAttribute('aria-selected', 'true')
    fireEvent.keyDown(tablist, { key: 'ArrowLeft' })
    expect(screen.getByRole('tab', { name: /unassigned/i })).toHaveAttribute(
      'aria-selected',
      'true',
    )
    fireEvent.keyDown(tablist, { key: 'Home' })
    expect(screen.getByRole('tab', { name: /routes/i })).toHaveAttribute('aria-selected', 'true')
    fireEvent.keyDown(tablist, { key: 'End' })
    expect(screen.getByRole('tab', { name: /json/i })).toHaveAttribute('aria-selected', 'true')
  })

  it('activating a tab shows the matching tabpanel', () => {
    renderPanel()
    fireEvent.click(screen.getByRole('tab', { name: /directions/i }))
    const active = screen.getByRole('tabpanel')
    expect(active).toHaveAttribute('id', 'results-panel-directions')
  })
})
