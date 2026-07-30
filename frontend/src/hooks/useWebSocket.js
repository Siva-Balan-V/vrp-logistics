import { useEffect, useRef, useCallback } from 'react'

const BASE = import.meta.env.VITE_API_URL || ''

function wsUrl(path) {
  const proto = BASE.startsWith('https') ? 'wss' : 'ws'
  const host = BASE.replace(/^https?:\/\//, '')
  return `${proto}://${host}${path}`
}

export default function useWebSocket(runId, token, onMessage) {
  const wsRef = useRef(null)
  const reconnectTimer = useRef(null)
  const mountedRef = useRef(true)

  const connect = useCallback(() => {
    if (!runId || !token) return
    if (wsRef.current) wsRef.current.close()

    const url = `${wsUrl(`/api/v1/ws/optimization/${runId}`)}?token=${encodeURIComponent(token)}`
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      if (reconnectTimer.current) {
        clearTimeout(reconnectTimer.current)
        reconnectTimer.current = null
      }
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (onMessage) onMessage(data)
      } catch {}
    }

    ws.onerror = () => {}

    ws.onclose = () => {
      wsRef.current = null
      if (mountedRef.current && runId) {
        reconnectTimer.current = setTimeout(connect, 2000)
      }
    }
  }, [runId, token, onMessage])

  useEffect(() => {
    mountedRef.current = true
    connect()
    return () => {
      mountedRef.current = false
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
      if (wsRef.current) wsRef.current.close()
    }
  }, [connect])
}
