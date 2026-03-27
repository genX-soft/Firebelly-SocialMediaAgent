import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import AuthShell from '../components/AuthShell'

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

function Login() {
  const navigate = useNavigate()
  const [status, setStatus] = useState<'idle' | 'loading' | 'error' | 'success'>('idle')
  const [message, setMessage] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setStatus('loading')
    setMessage('')

    const payload = {
      email: email.trim(),
      password,
    }

    if (!payload.email || !payload.password) {
      setStatus('error')
      setMessage('Email and password are required.')
      return
    }

    try {
      const response = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'ngrok-skip-browser-warning': 'true'
        },
        body: JSON.stringify(payload),
      })

      const data = await response.json()
      if (!response.ok) {
        throw new Error(getErrorMessage(data, 'Login failed'))
      }

      setStatus('success')
      setMessage(`Welcome back, ${data.user?.name ?? 'creator'}!`)
      if (data.user?.email) {
        localStorage.setItem('autosocial_email', data.user.email)
      }
      navigate('/workspace')
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Login failed'
      setStatus('error')
      setMessage(errorMessage)
    }
  }

  return (
    <AuthShell
      title="Welcome back"
      subtitle="Your next week of Facebook and Instagram posts is already mapped out."
      mode="login"
    >
      <form className="auth-form" onSubmit={handleSubmit}>
        <label className="field">
          <span>Email</span>
          <input
            type="email"
            name="email"
            placeholder="you@studio.com"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
          />
        </label>

        <label className="field">
          <span>Password</span>
          <input
            type="password"
            name="password"
            placeholder="Minimum 8 characters"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />
        </label>

        <div className="form-row">
          <label className="checkbox">
            <input type="checkbox" name="remember" />
            <span>Remember this device</span>
          </label>
          <a className="text-link" href="#">Forgot password?</a>
        </div>

        <button className="btn-primary" type="submit" disabled={status === 'loading'}>
          {status === 'loading' ? 'Signing in...' : 'Log in'}
        </button>

        {status !== 'idle' && (
          <div className={`form-message ${status}`}>
            {message}
          </div>
        )}
      </form>
    </AuthShell>
  )
}

export default Login
