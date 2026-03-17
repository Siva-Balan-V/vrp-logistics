const BASE = import.meta.env.VITE_API_URL || ''

export async function optimizeRoutes(payload) {
  const res = await fetch(`${BASE}/api/v1/optimize-routes`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export async function getRoutes(jobId) {
  const res = await fetch(`${BASE}/api/v1/routes/${jobId}`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function checkHealth() {
  const res = await fetch(`${BASE}/health`)
  return res.json()
}

export const VEHICLE_COLORS = [
  '#f5a623','#4b9eff','#3ecf8e','#f2614a','#c97ff5',
  '#54d2f5','#f5d623','#ff6b9d','#7fff6b','#ff9e6b',
  '#6bceff','#ffce6b','#b46bff','#6bffb4','#ff6b6b',
  '#6b8fff','#ffb46b','#6bffc4','#ff6bd4','#c4ff6b',
  '#6baaff','#ffd46b','#6bffaa','#ff6baa','#aaffb4',
  '#ffaa6b','#6bc4ff','#fff06b','#ff6bf5','#6bffe0',
]

export function vehicleColor(idx) {
  return VEHICLE_COLORS[idx % VEHICLE_COLORS.length]
}
