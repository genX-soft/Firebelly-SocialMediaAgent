import { useEffect, useState } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

const getErrorMessage = (data: unknown, fallback: string) => {
  if (!data) return fallback
  if (typeof data === 'string') return data
  if (typeof data === 'object' && data !== null) {
    const detail = (data as { detail?: unknown }).detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
      return detail
        .map((item) => {
          if (typeof item === 'string') return item
          if (item && typeof item === 'object' && 'msg' in item) {
            return String((item as { msg?: unknown }).msg)
          }
          return JSON.stringify(item)
        })
        .join(', ')
    }
  }
  return fallback
}

function OAuthCallback() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading')
  const [message, setMessage] = useState('')

  useEffect(() => {
    const code = searchParams.get('code')
    const state = searchParams.get('state')
    const statusParam = searchParams.get('status')
    const platformParam = searchParams.get('platform')
    const messageParam = searchParams.get('message')

    if (statusParam === 'received') {
      setStatus('success')
      setMessage(`Meta authorization received for ${platformParam ?? 'account'}. Return to Accounts.`)
      const timer = window.setTimeout(() => {
        navigate('/accounts')
      }, 1500)
      return () => window.clearTimeout(timer)
    }

    if (statusParam === 'error') {
      setStatus('error')
      setMessage(messageParam ?? 'Meta authorization failed.')
      return
    }

    if (!code || !state) {
      setStatus('error')
      setMessage('Missing authorization response.')
      return
    }

    const run = async () => {
      try {
        const response = await fetch(`${API_BASE}/oauth/meta/callback?code=${code}&state=${state}`, {
          headers: { 'ngrok-skip-browser-warning': 'true' }
        })
        const data = await response.json()
        if (!response.ok) {
          throw new Error(getErrorMessage(data, 'OAuth callback failed'))
        }
        setStatus('success')
        setMessage('Meta authorization received. You can return to Accounts.')
        window.setTimeout(() => {
          navigate('/accounts')
        }, 1500)
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : 'OAuth callback failed'
        setStatus('error')
        setMessage(errorMessage)
      }
    }

    run()
  }, [searchParams, navigate])

  return (
    <div className="workspace-light">
      <div className="auth-card">
        <h3>Meta Connection</h3>
        <p className="muted">{status === 'loading' ? 'Processing...' : message}</p>
      </div>
    </div>
  )
}

export default OAuthCallback
