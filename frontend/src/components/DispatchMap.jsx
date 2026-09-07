import { useEffect, useRef } from 'react'
import L from 'leaflet'
import { vehicleColor } from '../api.js'

export const OFFLINE_AFTER_MS = 10 * 60 * 1000

export function isOffline(lastPingAt, now) {
  if (!lastPingAt) return true
  return now - new Date(lastPingAt).getTime() > OFFLINE_AFTER_MS
}

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;')
}

function tooltipHtml(driver, offline) {
  const eta = driver.eta
  const first = eta?.remaining_stops?.[0]
  const delta = first && first.delta_min != null ? first.delta_min : null
  const etaLine =
    eta?.total_remaining_time_min != null
      ? `ETA ~${Math.round(eta.total_remaining_time_min)} min${delta ? ` <span style="color:var(--red)">(+${Math.round(delta)})</span>` : ''}`
      : 'no ETA'
  return `
    <div style="font-family:monospace;font-size:11px;line-height:1.5">
      <strong>${escapeHtml(driver.name)}</strong>
      <span style="color:${offline ? 'var(--text-3)' : 'var(--green)'}"> · ${escapeHtml(driver.status)}${offline ? ' · OFFLINE' : ''}</span><br/>
      ${etaLine}<br/>
      ping ${new Date(driver.last_ping_at).toLocaleTimeString()}
    </div>
  `
}

export default function DispatchMap({ drivers, now = Date.now() }) {
  const mapRef = useRef(null)
  const mapInstanceRef = useRef(null)
  const markerLayerRef = useRef(null)
  const listenersRef = useRef([])

  // Initialize map once
  useEffect(() => {
    if (!mapRef.current || mapInstanceRef.current) return

    const map = L.map(mapRef.current, {
      center: [51.5074, -0.1278],
      zoom: 12,
      zoomControl: true,
    })
    mapInstanceRef.current = map

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap contributors',
      maxZoom: 19,
    }).addTo(map)

    markerLayerRef.current = L.layerGroup().addTo(map)

    requestAnimationFrame(() => map.invalidateSize())

    return () => {
      listenersRef.current.forEach((h) => {
        map.off('moveend', h)
        map.off('zoomend', h)
      })
      listenersRef.current = []
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove()
        mapInstanceRef.current = null
        markerLayerRef.current = null
      }
    }
  }, [])

  // Render markers whenever the driver list changes
  useEffect(() => {
    const map = mapInstanceRef.current
    const layer = markerLayerRef.current
    if (!map || !layer) return

    layer.clearLayers()

    const bounds = []
    drivers.forEach((driver, i) => {
      if (driver.current_lat == null || driver.current_lon == null) return
      const offline = isOffline(driver.last_ping_at, now)
      const color = offline ? '#6b7280' : vehicleColor(i)
      const marker = L.circleMarker([driver.current_lat, driver.current_lon], {
        radius: offline ? 6 : driver.moving ? 9 : 7,
        color,
        fillColor: color,
        fillOpacity: 0.75,
        weight: 2,
      }).addTo(layer)
      marker.bindTooltip(tooltipHtml(driver, offline), { sticky: true })
      bounds.push([driver.current_lat, driver.current_lon])
    })

    if (bounds.length > 1) {
      const mapId = mapInstanceRef.current
      const fit = () => {
        try {
          map.fitBounds(bounds, { padding: [40, 40], maxZoom: 14 })
        } catch (_) {
          void _
        }
      }
      const handler = () => {
        listenersRef.current = listenersRef.current.filter((h) => h !== handler)
        fit()
      }
      // Fit once when markers exist, guarded from repeated re-fits per keystroke
      listenersRef.current.forEach((h) => {
        map.off('moveend', h)
        map.off('zoomend', h)
      })
      listenersRef.current = []
      listenersRef.current.push(handler)
      map.on('moveend', handler)
      map.on('zoomend', handler)
      if (mapId) fit()
    }
  }, [drivers, now])

  return (
    <div style={{ position: 'relative', height: '100%', background: 'var(--bg)' }}>
      <div ref={mapRef} style={{ width: '100%', height: '100%' }} />
    </div>
  )
}
