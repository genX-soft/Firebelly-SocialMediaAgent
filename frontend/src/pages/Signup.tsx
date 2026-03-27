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

function Signup() {
  const navigate = useNavigate()
  const [status, setStatus] = useState<'idle' | 'loading' | 'error' | 'success'>('idle')
  const [message, setMessage] = useState('')
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [company, setCompany] = useState('')

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setStatus('loading')
    setMessage('')

    const payload = {
      name: name.trim(),
      email: email.trim(),
      password,
      company: company.trim() || null,
    }

    if (!payload.name || !payload.email || !payload.password) {
      setStatus('error')
      setMessage('Name, email, and password are required.')
      return
    }

    try {
      const response = await fetch(`${API_BASE}/auth/signup`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'ngrok-skip-browser-warning': 'true'
        },
        body: JSON.stringify(payload),
      })

      const data = await response.json()
      if (!response.ok) {
        throw new Error(getErrorMessage(data, 'Sign up failed'))
      }

      setStatus('success')
      setMessage('Account created. Redirecting...')
      if (data.user?.email) {
        localStorage.setItem('autosocial_email', data.user.email)
      }
      setName('')
      setEmail('')
      setPassword('')
      setCompany('')
      navigate('/workspace')
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Sign up failed'
      setStatus('error')
      setMessage(errorMessage)
    }
  }

  return (
    <AuthShell
      title="Launch your content engine"
      subtitle="AutoSocial keeps your brand present while you focus on running the business."
      mode="signup"
    >
      <form className="auth-form" onSubmit={handleSubmit}>
        <label className="field">
          <span>Full name</span>
          <input
            type="text"
            name="name"
            placeholder="Alex Johnson"
            value={name}
            onChange={(event) => setName(event.target.value)}
            required
          />
        </label>

        <label className="field">
          <span>Work email</span>
          <input
            type="email"
            name="email"
            placeholder="alex@company.com"
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
            placeholder="Create a strong password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />
        </label>

        <label className="field">
          <span>Company or brand</span>
          <input
            type="text"
            name="company"
            placeholder="Studio Sol"
            value={company}
            onChange={(event) => setCompany(event.target.value)}
          />
        </label>

        <label className="checkbox">
          <input type="checkbox" name="terms" required />
          <span>I agree to the terms and privacy policy</span>
        </label>

        <button className="btn-primary" type="submit" disabled={status === 'loading'}>
          {status === 'loading' ? 'Creating account...' : 'Create account'}
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

export default Signup
