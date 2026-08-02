import { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react'
import { apiFetch } from '../api.js'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [token, setToken] = useState(() => localStorage.getItem('access_token'))
  const [loading, setLoading] = useState(true)
  const tokenRef = useRef(token)

  useEffect(() => {
    tokenRef.current = token
  }, [token])

  const login = useCallback(async (email, password) => {
    const data = await apiFetch('/api/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    })
    localStorage.setItem('access_token', data.access_token)
    localStorage.setItem('refresh_token', data.refresh_token)
    setToken(data.access_token)
  }, [])

  const register = useCallback(async (email, password, companyName) => {
    const data = await apiFetch('/api/v1/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password, company_name: companyName || undefined }),
    })
    localStorage.setItem('access_token', data.access_token)
    localStorage.setItem('refresh_token', data.refresh_token)
    setToken(data.access_token)
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    setToken(null)
    setUser(null)
  }, [])

  useEffect(() => {
    if (!token) {
      setLoading(false)
      return
    }
    apiFetch('/api/v1/auth/me', { token })
      .then((u) => {
        if (tokenRef.current === token) setUser(u)
      })
      .catch((err) => {
        if (tokenRef.current === token && err?.status === 401) logout()
      })
      .finally(() => {
        if (tokenRef.current === token) setLoading(false)
      })
  }, [token, logout])

  return (
    <AuthContext.Provider value={{ user, token, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
