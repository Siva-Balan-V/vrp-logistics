import { useEffect, useRef, useMemo, useState } from 'react'
import L from 'leaflet'
import { vehicleColor } from '../api.js'

export default function MapView({ result, depot, depots, deliveries, selectedVehicle, onSelectVehicle }) {
  const [showDensity, setShowDensity] = useState(false)
  const mapRef = useRef(null)
  const mapInstanceRef = useRef(null)
  const layersRef = useRef([])

  // Support both single depot and multiple depots
  const depotList = useMemo(() => {
    if (depots && depots.length) return depots
    if (depot) return [depot]
    return []
  }, [depot, depots])

  // Centre the map on the first depot or mean of waypoints
  const centre = useMemo(() => {
    if (depotList.length) return [depotList[0].lat, depotList[0].lon]
    const pts = result.vehicles.flatMap((v) => v.waypoints)
    if (!pts.length) return [51.5074, -0.1278]
    const lat = pts.reduce((s, p) => s + p.lat, 0) / pts.length
    const lon = pts.reduce((s, p) => s + p.lon, 0) / pts.length
    return [lat, lon]
  }, [depotList, result])

  // Initialize map
  useEffect(() => {
    if (!mapRef.current || mapInstanceRef.current) return

    mapInstanceRef.current = L.map(mapRef.current, {
      center: centre,
      zoom: 12,
      zoomControl: true,
    })

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap contributors',
      maxZoom: 19,
    }).addTo(mapInstanceRef.current)

    requestAnimationFrame(() => {
      mapInstanceRef.current?.invalidateSize()
    })

    return () => {
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove()
        mapInstanceRef.current = null
      }
    }
  }, []) // eslint-disable-line

  // Re-render layers when result or selection changes
  useEffect(() => {
    const map = mapInstanceRef.current
    if (!map) return

    // Clear existing layers
    layersRef.current.forEach((l) => map.removeLayer(l))
    layersRef.current = []

    const bounds = []

    result.vehicles.forEach((vehicle, vi) => {
      const color = vehicleColor(vi)
      const isSelected = selectedVehicle === vehicle.vehicle_id
      const opacity = selectedVehicle ? (isSelected ? 1 : 0.2) : 0.8

      const points = vehicle.waypoints.map((wp) => [wp.lat, wp.lon])
      bounds.push(...points)

      if (points.length < 2) return

      // Route polyline
      const line = L.polyline(points, {
        color,
        weight: isSelected ? 4 : 2,
        opacity,
        dashArray: isSelected ? undefined : '4 4',
      }).addTo(map)

      line.on('click', () => onSelectVehicle(isSelected ? null : vehicle.vehicle_id))
      layersRef.current.push(line)

      // Stop markers (only show all when selected, else just dots)
      vehicle.waypoints.forEach((wp, wi) => {
        if (wi === 0 || wi === vehicle.waypoints.length - 1) return // skip depot copies

        // Priority-based color: P5=red, P4=orange, P3=yellow, P2=blue, P1=gray
        const priorityColors = {
          5: '#f2614a',
          4: '#f5a623',
          3: '#f5d623',
          2: '#4b9eff',
          1: '#6b7280',
        }
        const pColor = priorityColors[wp.priority] || priorityColors[1]

        const circle = L.circleMarker([wp.lat, wp.lon], {
          radius: isSelected ? 5 : 3,
          color: pColor,
          fillColor: pColor,
          fillOpacity: opacity,
          weight: 1,
          opacity,
        }).addTo(map)

        if (isSelected) {
          circle.bindTooltip(
            `
            <div style="font-family:monospace;font-size:11px">
              <strong>Stop ${wp.id}</strong> <span style="color:${pColor}">P${wp.priority || 1}</span><br/>
              ${wp.lat.toFixed(5)}, ${wp.lon.toFixed(5)}
            </div>
          `,
            { sticky: true },
          )
        }
        layersRef.current.push(circle)
      })
    })

    // Depot markers (support multiple depots)
    depotList.forEach((dep, idx) => {
      const depotIcon = L.divIcon({
        html: `<div style="
          width:24px;height:24px;
          background:var(--accent,#f5a623);
          border:2px solid #000;
          border-radius:50% 50% 50% 0;
          transform:rotate(-45deg);
          box-shadow:0 2px 8px rgba(0,0,0,0.4);
          ${idx > 0 ? 'opacity:0.7;' : ''}
        "></div>`,
        iconSize: [24, 24],
        iconAnchor: [12, 24],
      })
      const label = depotList.length > 1 ? `Depot ${String.fromCharCode(65 + idx)}` : 'Depot'
      const dm = L.marker([dep.lat, dep.lon], { icon: depotIcon })
        .addTo(map)
        .bindTooltip(`<strong>${label}</strong><br/>${dep.label || label}`, { sticky: true })
      layersRef.current.push(dm)
      bounds.push([dep.lat, dep.lon])
    })

    // Density heatmap layer
    if (showDensity && deliveries) {
      const heatLats = deliveries.map((d) => d.lat)
      const heatLons = deliveries.map((d) => d.lon)
      const heatBounds = L.latLngBounds(
        [Math.min(...heatLats), Math.min(...heatLons)],
        [Math.max(...heatLats), Math.max(...heatLons)],
      )
      const latRange = heatBounds.getNorth() - heatBounds.getSouth()
      const lonRange = heatBounds.getEast() - heatBounds.getWest()
      const radius = Math.max(latRange, lonRange) / 20

      deliveries.forEach((d) => {
        const heatCircle = L.circleMarker([d.lat, d.lon], {
          radius: Math.max(radius, 8),
          color: 'var(--accent)',
          fillColor: '#f5a623',
          fillOpacity: 0.15,
          weight: 0.5,
          opacity: 0.3,
        }).addTo(map)
        layersRef.current.push(heatCircle)
      })
    }

    // Unassigned locations (red X)
    const unassignedCoords = deliveries
      ? result.unassigned
          .map((id) => deliveries.find((d) => d.id === id))
          .filter(Boolean)
      : []
    unassignedCoords.forEach((loc) => {
      const xIcon = L.divIcon({
        html: `<div style="
          width:20px;height:20px;
          color:var(--red,#f2614a);
          font-size:18px;font-weight:700;
          display:flex;align-items:center;justify-content:center;
          text-shadow:0 1px 4px rgba(0,0,0,0.6);
        ">✕</div>`,
        iconSize: [20, 20],
        iconAnchor: [10, 10],
      })
      const marker = L.marker([loc.lat, loc.lon], { icon: xIcon })
        .addTo(map)
        .bindTooltip(`<strong>Unassigned</strong><br/>#${loc.id}${loc.label ? ` · ${loc.label}` : ''}`, { sticky: true })
      layersRef.current.push(marker)
      bounds.push([loc.lat, loc.lon])
    })

    // Fit bounds
    if (bounds.length > 1) {
      try {
        map.fitBounds(bounds, { padding: [30, 30], maxZoom: 14 })
      } catch (_) {
        void _
      }
    }
  }, [result, selectedVehicle, depot, depots, deliveries, onSelectVehicle, showDensity])

  return (
    <div style={{ position: 'relative', height: '100%', background: 'var(--bg)' }}>
      <div ref={mapRef} style={{ width: '100%', height: '100%' }} />

      {/* Legend overlay */}
      <div
        style={{
          position: 'absolute',
          bottom: 20,
          right: 20,
          zIndex: 1000,
          background: 'rgba(17,19,24,0.92)',
          backdropFilter: 'blur(6px)',
          border: '1px solid var(--border)',
          borderRadius: 'var(--radius)',
          padding: '10px 14px',
          maxHeight: 260,
          overflowY: 'auto',
          minWidth: 160,
        }}
      >
        <div
          style={{
            fontSize: 10,
            fontFamily: 'var(--mono)',
            color: 'var(--text-3)',
            textTransform: 'uppercase',
            letterSpacing: '0.06em',
            marginBottom: 8,
          }}
        >
          Vehicles
        </div>
        {result.vehicles.map((v, i) => (
          <div
            key={v.vehicle_id}
            role="button"
            tabIndex={0}
            aria-pressed={selectedVehicle === v.vehicle_id}
            aria-label={`Vehicle ${v.vehicle_id}`}
            onClick={() => onSelectVehicle(selectedVehicle === v.vehicle_id ? null : v.vehicle_id)}
            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') onSelectVehicle(selectedVehicle === v.vehicle_id ? null : v.vehicle_id) }}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              padding: '3px 0',
              cursor: 'pointer',
              opacity: selectedVehicle && selectedVehicle !== v.vehicle_id ? 0.4 : 1,
            }}
          >
            <div style={{ width: 12, height: 3, background: vehicleColor(i), borderRadius: 2 }} />
            <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--text-2)' }}>
              V{v.vehicle_id} · {v.route.length - 2} stops
            </span>
          </div>
        ))}
      </div>

      {/* Density toggle */}
      {deliveries && (
        <button
          onClick={() => setShowDensity((v) => !v)}
          style={{
            position: 'absolute',
            top: 12,
            right: 20,
            zIndex: 1000,
            background: showDensity ? 'var(--accent)' : 'rgba(17,19,24,0.92)',
            backdropFilter: 'blur(6px)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius)',
            padding: '6px 12px',
            fontSize: 11,
            fontFamily: 'var(--mono)',
            color: showDensity ? '#000' : 'var(--text-2)',
            cursor: 'pointer',
          }}
        >
          {showDensity ? '✕ Hide Density' : '⊙ Show Density'}
        </button>
      )}

      {/* Instruction hint */}
      <div
        style={{
          position: 'absolute',
          top: 12,
          left: '50%',
          transform: 'translateX(-50%)',
          zIndex: 1000,
          background: 'rgba(17,19,24,0.8)',
          backdropFilter: 'blur(4px)',
          border: '1px solid var(--border)',
          borderRadius: 20,
          padding: '5px 14px',
          fontSize: 10,
          fontFamily: 'var(--mono)',
          color: 'var(--text-3)',
          pointerEvents: 'none',
        }}
      >
        Click a route or vehicle to highlight
      </div>
    </div>
  )
}
