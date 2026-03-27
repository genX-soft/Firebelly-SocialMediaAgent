import { useEffect, useMemo, useState } from 'react'
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

type Post = {
  id: string
  caption: string
  media_url?: string | null
  media_type: string
  hashtags?: string | null
  targets: string[]
  status: string
  error_message?: string | null
  scheduled_at?: string | null
}

type ActiveTab = 'queue' | 'drafts' | 'approvals' | 'sent'

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
          if (item && typeof item === 'object' && 'msg' in item) return String((item as { msg?: unknown }).msg)
          return JSON.stringify(item)
        })
        .join(', ')
    }
  }
  return fallback
}

function statusBadgeClass(status: string) {
  if (status === 'published') return 'badge badge--published'
  if (status === 'draft') return 'badge badge--draft'
  if (status === 'publishing') return 'badge badge--publishing'
  if (status === 'failed') return 'badge badge--failed'
  if (status === 'scheduled') return 'badge badge--scheduled'
  return 'badge'
}

function Workspace() {
  const navigate = useNavigate()
  const storedEmail = useMemo(() => localStorage.getItem('autosocial_email') ?? '', [])
  const [email] = useState(storedEmail)

  useEffect(() => {
      if (!storedEmail) {
      navigate('/login')
    }
  }, [storedEmail, navigate])

  // Accounts
  const [accounts, setAccounts] = useState<SocialAccount[]>([])
  const [acctStatus, setAcctStatus] = useState<'idle' | 'loading' | 'error'>('idle')
  const [acctMsg, setAcctMsg] = useState('')
  const [activeChannel, setActiveChannel] = useState<'all' | 'facebook' | 'instagram'>('all')

  // Posts
  const [posts, setPosts] = useState<Post[]>([])
  const [postsLoading, setPostsLoading] = useState(false)
  const [postsError, setPostsError] = useState('')

  // Tabs
  const [activeTab, setActiveTab] = useState<ActiveTab>('drafts')
  const [viewMode, setViewMode] = useState<'list' | 'grid'>('grid')

  const loadAccounts = async () => {
    if (!email) return setAccounts([])
    setAcctStatus('loading')
    setAcctMsg('')
    try {
      const res = await fetch(`${API_BASE}/accounts?user_email=${encodeURIComponent(email)}`, {
        headers: {
          'ngrok-skip-browser-warning': 'true'
        }
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data?.detail || 'Failed to load accounts')
      setAccounts(data)
      setAcctStatus('idle')
    } catch (err) {
      setAcctStatus('error')
      setAcctMsg(err instanceof Error ? err.message : 'Failed to load accounts')
    }
  }

  const loadPosts = async () => {
    if (!email) return setPosts([])
    setPostsLoading(true)
    setPostsError('')
    try {
      const res = await fetch(`${API_BASE}/posts?user_email=${encodeURIComponent(email)}`, {
        headers: {
          'ngrok-skip-browser-warning': 'true'
        }
      })
      const data = await res.json()
      if (!res.ok) throw new Error(getErrorMessage(data, 'Failed to load posts'))
      setPosts(data)
    } catch (err) {
      setPostsError(err instanceof Error ? err.message : 'Failed to load posts')
    } finally {
      setPostsLoading(false)
    }
  }

  const refreshAccounts = async () => {
    if (!email) return
    setAcctStatus('loading')
    try {
      const res = await fetch(`${API_BASE}/accounts/refresh?user_email=${encodeURIComponent(email)}`, { 
        method: 'POST',
        headers: { 'ngrok-skip-browser-warning': 'true' }
      })
      const data = await res.json()
      if (!res.ok) throw new Error(getErrorMessage(data, 'Failed to refresh accounts'))
      await loadAccounts()
    } catch (err) {
      setAcctStatus('error')
      setAcctMsg(err instanceof Error ? err.message : 'Failed to refresh accounts')
    }
  }

  const publishDraft = async (postId: string) => {
    try {
      const res = await fetch(`${API_BASE}/posts/${postId}/publish`, { 
        method: 'POST',
        headers: { 'ngrok-skip-browser-warning': 'true' }
      })
      if (!res.ok) throw new Error('Publish failed')
      await loadPosts()
    } catch {
      // silently fail for now; user can refresh
    }
  }

  const deletePost = async (postId: string) => {
    if (!window.confirm('Are you sure you want to delete this post?')) return
    try {
      const res = await fetch(`${API_BASE}/posts/${postId}?user_email=${encodeURIComponent(email)}`, { 
        method: 'DELETE',
        headers: { 'ngrok-skip-browser-warning': 'true' }
      })
      if (!res.ok) throw new Error('Delete failed')
      setPosts((prev) => prev.filter((p) => p.id !== postId))
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to delete post')
    }
  }

  useEffect(() => {
    loadAccounts()
    loadPosts()
  }, [])

  const connectedAccounts = accounts.filter((a) => a.is_connected)
  const fbAccounts = connectedAccounts.filter((a) => a.platform === 'facebook')
  const igAccounts = connectedAccounts.filter((a) => a.platform === 'instagram')
  const filteredAccounts =
    activeChannel === 'all' ? connectedAccounts : connectedAccounts.filter((a) => a.platform === activeChannel)

  // Tab filtering
  const tabPosts: Record<ActiveTab, Post[]> = {
    queue: posts.filter((p) => p.status === 'scheduled' || p.status === 'publishing'),
    drafts: posts.filter((p) => p.status === 'draft'),
    approvals: posts.filter((p) => p.status === 'pending_approval'),
    sent: posts.filter((p) => p.status === 'published' || p.status === 'failed'),
  }

  const currentPosts = tabPosts[activeTab]

  const emptyMessages: Record<ActiveTab, { heading: string; body: string }> = {
    queue: { heading: 'No posts scheduled', body: 'Schedule some posts and they will appear here.' },
    drafts: { heading: 'No drafts yet', body: 'Save a post as draft in the composer and it will appear here.' },
    approvals: { heading: 'Nothing pending approval', body: 'Posts awaiting review will appear here.' },
    sent: { heading: 'Nothing sent yet', body: 'Published posts will appear here once they go live.' },
  }

  return (
    <div className="workspace-shell">
      {/* ── Sidebar ── */}
      <aside className="workspace-sidebar">
        <div className="sidebar-header">
          <div className="sidebar-title">Menu</div>
        </div>
        <Link to="/workspace" className={`sidebar-item ${window.location.pathname === '/workspace' ? 'active' : ''}`}>
          <div className="avatar">WS</div>
          <div className="sidebar-text">Workspace</div>
        </Link>
        <Link to="/content-studio" className="sidebar-item">
          <div className="avatar">✦</div>
          <div className="sidebar-text">Content Studio</div>
        </Link>
        <Link to="/inbox" className="sidebar-item">
          <div className="avatar">IN</div>
          <div className="sidebar-text">Engagement Inbox</div>
        </Link>
        <Link to="/dashboard" className="sidebar-item">
          <div className="avatar">DB</div>
          <div className="sidebar-text">Analytics Dashboard</div>
        </Link>
        <Link to="/accounts" className="sidebar-item">
          <div className="avatar">AC</div>
          <div className="sidebar-text">Connections</div>
        </Link>

        <div className="sidebar-divider" style={{ margin: '20px 0', borderTop: '1px solid rgba(255,255,255,0.1)' }} />

        <div className="sidebar-header">
          <div className="sidebar-title">Channels</div>
          <button className="icon-button" type="button" onClick={refreshAccounts}>Refresh</button>
        </div>

        {(['all', 'facebook', 'instagram'] as const).map((ch) => (
          <div
            key={ch}
            className={`sidebar-item${activeChannel === ch ? ' active' : ''}`}
            role="button"
            tabIndex={0}
            onClick={() => setActiveChannel(ch)}
            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') setActiveChannel(ch) }}
          >
            <div className="avatar">{ch === 'all' ? 'ALL' : ch === 'facebook' ? 'FB' : 'IG'}</div>
            <div className="sidebar-text">
              <div>{ch === 'all' ? 'All Channels' : ch === 'facebook' ? 'Facebook Pages' : 'Instagram Business'}</div>
              <span>{ch === 'all' ? connectedAccounts.length : ch === 'facebook' ? fbAccounts.length : igAccounts.length}</span>
            </div>
          </div>
        ))}

        <div className="sidebar-section">Connected</div>
        {filteredAccounts.length === 0 ? (
          <div className="sidebar-empty">No connected accounts yet.</div>
        ) : (
          filteredAccounts.map((account) => (
            <div key={account.id} className="sidebar-item">
              <div className="avatar">
                {(account.page_name || account.instagram_username || 'AC').slice(0, 2).toUpperCase()}
              </div>
              <div className="sidebar-text">
                <div>{account.page_name || account.instagram_username || account.external_id}</div>
                <span>{account.platform === 'facebook' ? 'Facebook' : 'Instagram'}</span>
              </div>
            </div>
          ))
        )}

        <Link className="sidebar-item" to="/inbox">
          <div className="avatar">📥</div>
          <div className="sidebar-text"><div>Unified Inbox</div><span>Engagement</span></div>
        </Link>

        <Link className="sidebar-item" to="/accounts">
          <div className="avatar">+</div>
          <div className="sidebar-text"><div>Connect accounts</div><span>Meta</span></div>
        </Link>

        <div className="sidebar-footer" style={{ marginTop: 'auto', borderTop: '1px solid var(--dark-border)', paddingTop: '16px' }}>
          <div style={{ padding: '0 12px 12px', fontSize: '13px', color: 'var(--muted)', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {email}
          </div>
          <button 
            className="ghost-dark" 
            style={{ width: '100%', textAlign: 'left', color: '#ff6b6b' }} 
            type="button"
            onClick={() => {
              localStorage.removeItem('autosocial_email')
              navigate('/login')
            }}
          >
            Log out
          </button>
        </div>
      </aside>

      {/* ── Main ── */}
      <main className="workspace-main">
        <header className="workspace-topbar">
          <div className="topbar-left">
            <div className="topbar-icon">AS</div>
            <div>
              <div className="topbar-title">
                {activeChannel === 'all' ? 'All Channels' : activeChannel === 'facebook' ? 'Facebook Pages' : 'Instagram Business'}
              </div>
              <div className="topbar-subtitle">
                {acctStatus === 'loading' ? 'Loading…' : `${filteredAccounts.length} connected`}
                {acctMsg && <span style={{ color: '#ff6b6b', marginLeft: 8 }}>{acctMsg}</span>}
              </div>
            </div>
          </div>
          <div className="topbar-actions">
            <button 
              className={`chip ${viewMode === 'list' ? 'active' : ''}`} 
              type="button"
              onClick={() => setViewMode('list')}
            >
              List
            </button>
            <button 
              className={`chip ${viewMode === 'grid' ? 'active' : ''}`} 
              type="button"
              onClick={() => setViewMode('grid')}
            >
              Grid
            </button>
            <button
              className="chip"
              type="button"
              onClick={loadPosts}
              disabled={postsLoading}
            >
              {postsLoading ? 'Refreshing…' : 'Refresh'}
            </button>
            <Link className="btn-primary" to="/composer">New Post</Link>
          </div>
        </header>

        <nav className="workspace-tabs">
          {(['queue', 'drafts', 'approvals', 'sent'] as ActiveTab[]).map((tab) => (
            <button
              key={tab}
              className={`tab${activeTab === tab ? ' active' : ''}`}
              type="button"
              onClick={() => setActiveTab(tab)}
            >
              {tab.charAt(0).toUpperCase() + tab.slice(1)}
              <span>{tabPosts[tab].length}</span>
            </button>
          ))}
          <div className="tab-spacer" />
        </nav>

        <section className="workspace-content">
          {postsLoading ? (
            <div className="posts-loading">Loading posts…</div>
          ) : postsError ? (
            <div className="form-message error">{postsError}</div>
          ) : currentPosts.length === 0 ? (
            <div className="empty-card">
              <div className="empty-stack">
                <div className="empty-line" />
                <div className="empty-line" />
                <div className="empty-line" />
              </div>
              <div className="empty-callout">
                <h3>{emptyMessages[activeTab].heading}</h3>
                <p>{emptyMessages[activeTab].body}</p>
                <Link className="btn-primary" to="/composer">New Post</Link>
              </div>
            </div>
          ) : (
            <div className={viewMode === 'grid' ? 'posts-grid' : 'posts-list'}>
              {currentPosts.map((post) => (
                <div key={post.id} className={viewMode === 'grid' ? 'post-card' : 'post-item'}>
                  {post.media_url && (
                    <div className={viewMode === 'grid' ? 'post-card-media' : 'post-thumb'}>
                      {post.media_type === 'image' ? (
                        <img src={post.media_url} alt="" />
                      ) : (
                        <div className="post-thumb-video">🎬</div>
                      )}
                    </div>
                  )}
                  <div className={viewMode === 'grid' ? 'post-card-content' : 'post-body'}>
                    <div className="post-caption">{post.caption || <em style={{ color: 'var(--muted)' }}>No caption</em>}</div>
                    <div className="post-meta">
                      <span className={statusBadgeClass(post.status)}>{post.status}</span>
                      {post.targets.length > 0 && (
                        <span className="post-targets">{post.targets.join(' · ')}</span>
                      )}
                      {post.scheduled_at && (
                        <span className="post-scheduled" style={viewMode === 'grid' ? {display: 'block', marginTop: '8px'} : {}}>
                          🕐 {new Date(post.scheduled_at).toLocaleString()}
                        </span>
                      )}
                    </div>
                    {post.error_message && (
                      <div className="post-error">⚠ {post.error_message}</div>
                    )}
                  </div>
                  <div className={viewMode === 'grid' ? 'post-card-actions' : 'post-actions'}>
                    {(post.status === 'draft' || post.status === 'failed') && (
                      <button
                        className="btn-primary"
                        type="button"
                        onClick={() => publishDraft(post.id)}
                        style={{ fontSize: '12px', padding: '6px 10px' }}
                      >
                        {post.status === 'failed' ? 'Retry' : 'Publish'}
                      </button>
                    )}
                    <Link
                      className="btn-secondary"
                      to={`/composer?edit=${post.id}`}
                      style={{ fontSize: '12px', padding: '6px 10px' }}
                    >
                      Edit
                    </Link>
                    <button
                      className="btn-secondary"
                      type="button"
                      onClick={() => deletePost(post.id)}
                      style={{ fontSize: '12px', padding: '6px 10px', color: '#ff6b6b' }}
                    >
                      Delete
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </main>
    </div>
  )
}

export default Workspace