const BASE = import.meta.env.VITE_API_URL || ''

export async function apiFetch(path, { token, ...options } = {}) {
  const headers = { 'Content-Type': 'application/json', ...options.headers }
  if (token) headers['Authorization'] = `Bearer ${token}`
  const res = await fetch(`${BASE}${path}`, { ...options, headers })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export async function optimizeRoutes(payload, token, runId) {
  const qs = runId ? `?run_id=${encodeURIComponent(runId)}` : ''
  return apiFetch(`/api/v1/optimize-routes${qs}`, {
    method: 'POST',
    body: JSON.stringify(payload),
    token,
  })
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
  return VEHICLE_COLORS[((idx % VEHICLE_COLORS.length) + VEHICLE_COLORS.length) % VEHICLE_COLORS.length]
}

export async function getOptimizationStatus(runId, token) {
  return apiFetch(`/api/v1/optimize-routes/${runId}/status`, { token })
}

export async function getJobResult(jobId, token) {
  return apiFetch(`/api/v1/routes/${jobId}`, { token })
}

export async function listJobs(token, limit = 20) {
  return apiFetch(`/api/v1/routes?limit=${limit}`, { token })
}

export async function getDashboard(token, days = 30) {
  return apiFetch(`/api/v1/bi/dashboard?days=${days}`, { token })
}

export async function getTerritory(token, jobId) {
  const qs = jobId ? `?job_id=${jobId}` : ''
  return apiFetch(`/api/v1/bi/territory${qs}`, { token })
}

export async function listDrivers(token) {
  return apiFetch('/api/v1/drivers', { token })
}

export async function createDriver(name, phone, token) {
  return apiFetch('/api/v1/drivers', {
    method: 'POST', body: JSON.stringify({ name, phone }), token,
  })
}

export async function getDriver(id, token) {
  return apiFetch(`/api/v1/drivers/${id}`, { token })
}

export async function updateDriverLocation(id, lat, lon, token) {
  return apiFetch(`/api/v1/drivers/${id}/location`, {
    method: 'PATCH', body: JSON.stringify({ lat, lon }), token,
  })
}

export async function getDriverEta(id, token) {
  return apiFetch(`/api/v1/drivers/${id}/eta`, { token })
}

export async function assignDriverRoute(id, jobId, vehicleId, token) {
  return apiFetch(`/api/v1/drivers/${id}/assign`, {
    method: 'POST', body: JSON.stringify({ job_id: jobId, vehicle_id: vehicleId }), token,
  })
}

export async function getNotificationConfig(token) {
  return apiFetch('/api/v1/notifications/config', { token })
}

export async function updateNotificationConfig(body, token) {
  return apiFetch('/api/v1/notifications/config', {
    method: 'PUT', body: JSON.stringify(body), token,
  })
}

export async function triggerNotification(body, token) {
  return apiFetch('/api/v1/notifications/trigger', {
    method: 'POST', body: JSON.stringify(body), token,
  })
}

export async function listPlans(token) {
  return apiFetch('/api/v1/billing/plans', { token })
}

export async function getUsage(token) {
  return apiFetch('/api/v1/billing/usage', { token })
}

export async function createCheckoutSession(plan, token) {
  return apiFetch(`/api/v1/billing/create-checkout?plan=${plan}`, {
    method: 'POST', token,
  })
}

export async function createPortalSession(token) {
  return apiFetch('/api/v1/billing/portal', {
    method: 'POST', token,
  })
}

export async function listAdminCompanies(token) {
  return apiFetch('/api/v1/admin/companies', { token })
}

export async function getAdminCompany(id, token) {
  return apiFetch(`/api/v1/admin/companies/${id}`, { token })
}

export async function updateCompanyPlan(companyId, plan, token) {
  return apiFetch(`/api/v1/admin/companies/${companyId}/plan?plan=${plan}`, {
    method: 'PUT', token,
  })
}

export async function listNotificationLogs(limit, token) {
  return apiFetch(`/api/v1/notifications/logs?limit=${limit}`, { token })
}

export async function exportRoute(jobId, format, token) {
  const headers = {}
  if (token) headers['Authorization'] = `Bearer ${token}`
  const res = await fetch(`${BASE}/api/v1/routes/${jobId}/export?format=${format}`, { headers })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `Export failed: ${res.status}`)
  }
  return res.blob()
}
