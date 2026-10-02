import { useCallback, useEffect, useRef, useState } from 'react'

const API_KEY_STORAGE = 'warden.apiKey'

export const getApiKey = () => localStorage.getItem(API_KEY_STORAGE) || ''
export const setApiKey = (value) => localStorage.setItem(API_KEY_STORAGE, value)

async function request(path, opts = {}) {
  const res = await fetch(path, {
    ...opts,
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': getApiKey(),
      'X-Approved-By': 'warden-ui',
      ...(opts.headers || {}),
    },
  })
  const body = await res.json().catch(() => ({}))
  if (!res.ok) {
    const error = new Error(body.error || `HTTP ${res.status}`)
    error.status = res.status
    throw error
  }
  return body
}

export const api = {
  summary: () => request('/api/dashboard/summary'),
  infra: () => request('/api/dashboard/infra'),
  decisions: (limit = 20) => request(`/api/dashboard/decisions?limit=${limit}`),
  history: (limit = 8) => request(`/api/dashboard/history?limit=${limit}`),
  safety: () => request('/api/safety/check'),
  pending: () => request('/api/approvals/pending'),
  decide: (id, decision) => request(`/api/approvals/${encodeURIComponent(id)}/${decision}`, { method: 'POST' }),
}

export function usePoll(fn, interval = 5000) {
  const [state, setState] = useState({ data: null, error: null })
  const fnRef = useRef(fn)
  fnRef.current = fn

  const refresh = useCallback(async () => {
    try {
      setState({ data: await fnRef.current(), error: null })
    } catch (error) {
      setState((current) => ({ data: current.data, error }))
    }
  }, [])

  useEffect(() => {
    refresh()
    const id = setInterval(refresh, interval)
    return () => clearInterval(id)
  }, [refresh, interval])

  return { ...state, refresh }
}
