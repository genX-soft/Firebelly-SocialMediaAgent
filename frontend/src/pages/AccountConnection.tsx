import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

type SocialAccount = {
  id: string
  platform: 'facebook' | 'instagram'
  external_id: string
  page_name?: string | null
  instagram_username?: string | null
  profile_picture_url?: string | null
  is_connected: boolean
}

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

function AccountConnection() {
  const navigate = useNavigate()
  const storedEmail = useMemo(() => localStorage.getItem('autosocial_email') ?? '', [])
  const [email] = useState(storedEmail)

  useEffect(() => {
    if (!storedEmail) {
      navigate('/login')
    }
  }, [storedEmail, navigate])

  const [accounts, setAccounts] = useState<SocialAccount[]>([])
  const [status, setStatus] = useState<'idle' | 'loading' | 'error'>('idle')
  const [message, setMessage] = useState('')
  const [oauthStatus, setOauthStatus] = useState('')

  const [platform, setPlatform] = useState<'facebook' | 'instagram'>('facebook')
  const [externalId, setExternalId] = useState('')
  const [pageName, setPageName] = useState('')
  const [igUsername, setIgUsername] = useState('')
  const [profileUrl, setProfileUrl] = useState('')

  const loadAccounts = async (targetEmail = email) => {
    if (!targetEmail) {
      setAccounts([])
      return
    }

    setStatus('loading')
    setMessage('')
    try {
      const response = await fetch(`${API_BASE}/accounts?user_email=${encodeURIComponent(targetEmail)}`, {
        headers: {
          'ngrok-skip-browser-warning': 'true'
        }
      })
      const data = await response.json()
      if (!response.ok) {
        throw new Error(getErrorMessage(data, 'Failed to load accounts'))
      }
      setAccounts(data)
      setStatus('idle')
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to load accounts'
      setStatus('error')
      setMessage(errorMessage)
    }
  }

  useEffect(() => {
    loadAccounts()
  }, [])

  const startOAuth = async (targetPlatform: 'facebook' | 'instagram') => {
    if (!email) {
      setOauthStatus('Enter your email before starting OAuth.')
      return
    }

    setOauthStatus('')
    try {
      const response = await fetch(
        `${API_BASE}/oauth/meta/authorize?platform=${targetPlatform}&user_email=${encodeURIComponent(email)}`,
        {
          headers: {
            'ngrok-skip-browser-warning': 'true'
          }
        }
      )
      const data = await response.json()
      if (!response.ok) {
        throw new Error(getErrorMessage(data, 'OAuth start failed'))
      }
      if (!data?.url) {
        throw new Error('OAuth URL missing')
      }
      window.location.href = data.url as string
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'OAuth start failed'
      setOauthStatus(errorMessage)
    }
  }

  const handleConnect = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!email) {
      setStatus('error')
      setMessage('Enter an email to load accounts.')
      return
    }

    setStatus('loading')
    setMessage('')

    const payload = {
      user_email: email,
      platform,
      external_id: externalId || `${platform}-${Date.now()}`,
      page_name: pageName || null,
      instagram_username: igUsername || null,
      profile_picture_url: profileUrl || null,
    }

    try {
      const response = await fetch(`${API_BASE}/accounts/connect`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'ngrok-skip-browser-warning': 'true'
        },
        body: JSON.stringify(payload),
      })
      const data = await response.json()
      if (!response.ok) {
        throw new Error(getErrorMessage(data, 'Failed to connect account'))
      }

      setAccounts((prev) => [data, ...prev])
      setExternalId('')
      setPageName('')
      setIgUsername('')
      setProfileUrl('')
      setStatus('idle')
      localStorage.setItem('autosocial_email', email)
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to connect account'
      setStatus('error')
      setMessage(errorMessage)
    }
  }

  const handleDisconnect = async (accountId: string) => {
    setStatus('loading')
    setMessage('')
    try {
      const response = await fetch(`${API_BASE}/accounts/disconnect`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'ngrok-skip-browser-warning': 'true'
        },
        body: JSON.stringify({ account_id: accountId, user_email: email }),
      })
      const data = await response.json()
      if (!response.ok) {
        throw new Error(getErrorMessage(data, 'Failed to disconnect account'))
      }

      setAccounts((prev) => prev.map((account) => (
        account.id === accountId ? { ...account, is_connected: false } : account
      )))
      setStatus('idle')
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to disconnect account'
      setStatus('error')
      setMessage(errorMessage)
    }
  }

  return (
    <div className="workspace-light">
      <header className="workspace-header">
        <div>
          <div className="workspace-title">Connected Accounts</div>
          <p>Connect your Facebook Pages and Instagram Business accounts.</p>
        </div>
        <div style={{ display: 'flex', gap: '12px' }}>
          <Link className="btn-secondary" to="/workspace">Workspace</Link>
          <Link className="btn-secondary" to="/inbox">Engagement Inbox</Link>
          <Link className="btn-secondary" to="/dashboard">Analytics Dashboard</Link>
        </div>
      </header>

      <section className="account-panel">
        <div className="account-card">
          <h3>Meta login</h3>
          <p className="muted">Start OAuth to connect your Meta-managed accounts.</p>
          <div className="oauth-buttons">
            <button className="btn-primary" type="button" onClick={() => startOAuth('facebook')}>
              Login with Facebook (Business)
            </button>
            <button className="btn-secondary" type="button" onClick={() => startOAuth('instagram')}>
              Login with Instagram
            </button>
          </div>
          {oauthStatus && <div className="form-message error">{oauthStatus}</div>}
        </div>

        <div className="account-card" style={{ display: 'none' }}>
          <h3>Manual connect</h3>
          <p className="muted">Temporary manual form for testing before OAuth is wired.</p>
          {/* Form hidden for cleaner production feel */}
        </div>

        <div className="account-card account-span">
          <div className="account-card-header">
            <h3>Connected accounts</h3>
            <button className="btn-secondary" type="button" onClick={() => loadAccounts(email)}>
              Refresh
            </button>
          </div>

          {status === 'loading' && accounts.length === 0 ? (
            <p className="muted">Loading accounts...</p>
          ) : accounts.length === 0 ? (
            <p className="muted">No connected accounts yet.</p>
          ) : (
            <div className="account-list">
              {accounts.map((account) => (
                <div key={account.id} className="account-item">
                  <div className="account-meta">
                    <div className="account-platform">{account.platform}</div>
                    <div className="account-title">
                      {account.page_name || account.instagram_username || account.external_id}
                    </div>
                    <div className="account-subtitle">{account.instagram_username ?? account.page_name}</div>
                  </div>
                  <div className="account-actions">
                    {account.is_connected ? (
                      <button
                        className="btn-secondary"
                        type="button"
                        onClick={() => handleDisconnect(account.id)}
                      >
                        Disconnect
                      </button>
                    ) : (
                      <span className="muted">Disconnected</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      <div style={{ marginTop: '40px', paddingTop: '20px', borderTop: '1px solid var(--dark-border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ fontSize: '14px', color: 'var(--muted)' }}>Logged in as: <strong>{email}</strong></div>
        <button 
          className="btn-secondary" 
          style={{ color: '#ff6b6b', borderColor: 'rgba(255, 107, 107, 0.2)' }}
          onClick={() => {
            localStorage.removeItem('autosocial_email')
            navigate('/login')
          }}
        >
          Sign Out
        </button>
      </div>
    </div>
  )
}

export default AccountConnection
