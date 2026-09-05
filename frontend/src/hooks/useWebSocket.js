import { useEffect, useRef, useCallback, useState } from 'react'

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
  const [connected, setConnected] = useState(false)

  const connect = useCallback(() => {
    if (!runId || !token) {
      setConnected(false)
      return
    }
    if (wsRef.current) wsRef.current.close()

    const url = `${wsUrl(`/api/v1/ws/optimization/${runId}`)}?token=${encodeURIComponent(token)}`
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      if (reconnectTimer.current) {
        clearTimeout(reconnectTimer.current)
        reconnectTimer.current = null
      }
      setConnected(true)
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (onMessage) onMessage(data)
      } catch {
        // ignore malformed messages
      }
    }

    ws.onerror = () => {}

    ws.onclose = () => {
      if (wsRef.current !== ws) return
      wsRef.current = null
      setConnected(false)
      if (mountedRef.current && runId) {
        reconnectTimer.current = setTimeout(connect, 2000)
      }
    }
  }, [runId, token, onMessage])

  useEffect(() => {
    mountedRef.current = true
    setConnected(false)
    connect()
    return () => {
      mountedRef.current = false
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
      if (wsRef.current) wsRef.current.close()
    }
  }, [connect])

  return connected
}
