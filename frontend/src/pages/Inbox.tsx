import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

type Interaction = {
  id: string
  platform: 'facebook' | 'instagram'
  external_id: string
  content: string
  sender_name?: string | null
  type: 'comment' | 'message'
  is_outgoing?: boolean
  created_at: string
}

type ActiveFilter = 'all' | 'facebook' | 'instagram' | 'comments' | 'messages'

// ── AI reply state per interaction ──
type AiState = {
  loading: boolean
  suggestion: string | null
  escalate: boolean
  error: string | null
  persona: 'ember' | 'blaze' | null
}

function Inbox() {
  const navigate = useNavigate()
  const storedEmail = useMemo(() => localStorage.getItem('autosocial_email') ?? '', [])
  const [email] = useState(storedEmail)

  useEffect(() => {
    if (!storedEmail) navigate('/login')
  }, [storedEmail, navigate])

  const [interactions, setInteractions] = useState<Interaction[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [activeFilter, setActiveFilter] = useState<ActiveFilter>('all')
  const [replyingTo, setReplyingTo] = useState<string | null>(null)
  const [replyContent, setReplyContent] = useState('')
  const [sendingReply, setSendingReply] = useState(false)
  const [replyStatus, setReplyStatus] = useState<{ id: string; msg: string; type: 'success' | 'error' } | null>(null)
  const [isPolling, setIsPolling] = useState(false)
  const [deletingComment, setDeletingComment] = useState<string | null>(null)
  const [deleteStatus, setDeleteStatus] = useState<{ id: string; msg: string; type: 'success' | 'error' } | null>(null)

  // Pagination
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const PAGE_SIZE = 10

  // AI state map: keyed by interaction.id
  const [aiStates, setAiStates] = useState<Record<string, AiState>>({})

  // ── Load Inbox ──
  const loadInbox = async (
    resetPage = false,
    targetPlatform?: ActiveFilter,
    targetType?: ActiveFilter,
    silent = false
  ) => {
    if (!email) return
    const targetPage = resetPage ? 1 : page
    const platformFilter = targetPlatform || activeFilter
    const typeFilter = targetType || activeFilter
    if (resetPage) setPage(1)

    if (silent) {
      setIsPolling(true)
      setTimeout(() => setIsPolling(false), 800)
    } else {
      setLoading(true)
    }
    setError('')

    try {
      let url = `${API_BASE}/inbox?user_email=${encodeURIComponent(email)}&page=${targetPage}&page_size=${PAGE_SIZE}`
      const p = platformFilter === 'facebook' || platformFilter === 'instagram' ? platformFilter : 'all'
      const t = typeFilter === 'comments' || typeFilter === 'messages' ? typeFilter : 'all'
      if (p !== 'all') url += `&platform=${p}`
      if (t !== 'all') url += `&interaction_type=${t}`

      const res = await fetch(url, { headers: { 'ngrok-skip-browser-warning': 'true' } })
      const data = await res.json()
      if (!res.ok) throw new Error(data?.detail || 'Failed to load inbox')
      setInteractions(data.data)
      setTotal(data.total)
    } catch (err) {
      if (!silent) setError(err instanceof Error ? err.message : 'Failed to load inbox')
    } finally {
      if (!silent) setLoading(false)
    }
  }

  // ── Send Manual Reply ──
  const sendReply = async (platform: string, external_id: string) => {
    if (!replyContent.trim()) return
    setSendingReply(true)
    setReplyStatus(null)
    try {
      const res = await fetch(`${API_BASE}/inbox/reply`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'ngrok-skip-browser-warning': 'true' },
        body: JSON.stringify({ user_email: email, platform, external_id, content: replyContent }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data?.detail || 'Failed to post reply')
      setReplyStatus({ id: external_id, msg: data.message || 'Reply sent!', type: 'success' })
      setReplyContent('')
      setReplyingTo(null)
      loadInbox(false, undefined, undefined, true)
    } catch (err) {
      setReplyStatus({
        id: external_id,
        msg: err instanceof Error ? err.message : 'Failed to post reply',
        type: 'error',
      })
    } finally {
      setSendingReply(false)
    }
  }

  // ── Delete Comment ──
  const deleteComment = async (item: Interaction) => {
    const confirmMsg = item.platform === 'instagram'
      ? 'Hide this comment on Instagram? (Instagram only supports hiding, not full deletion via API)'
      : 'Permanently delete this comment from Facebook?'
    if (!window.confirm(confirmMsg)) return

    setDeletingComment(item.external_id)
    setDeleteStatus(null)
    try {
      const res = await fetch(
        `${API_BASE}/inbox/comment/${item.external_id}?user_email=${encodeURIComponent(email)}`,
        { method: 'DELETE', headers: { 'ngrok-skip-browser-warning': 'true' } }
      )
      const data = await res.json()
      if (!res.ok) throw new Error(data?.detail || 'Delete failed')
      // Remove from local state immediately
      setInteractions(prev => prev.filter(i => i.external_id !== item.external_id))
      setDeleteStatus({
        id: item.external_id,
        msg: item.platform === 'instagram' ? 'Comment hidden on Instagram.' : 'Comment deleted from Facebook.',
        type: 'success',
      })
    } catch (err) {
      setDeleteStatus({
        id: item.external_id,
        msg: err instanceof Error ? err.message : 'Delete failed',
        type: 'error',
      })
    } finally {
      setDeletingComment(null)
    }
  }

  // ── Get AI Suggestion ──
  const getAiSuggestion = async (item: Interaction) => {
    setAiStates(prev => ({
      ...prev,
      [item.id]: { loading: true, suggestion: null, escalate: false, error: null, persona: null },
    }))

    // When reply box isn't open yet, open it
    if (replyingTo !== item.id) setReplyingTo(item.id)

    try {
      const res = await fetch(`${API_BASE}/inbox/ai-suggest`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'ngrok-skip-browser-warning': 'true' },
        body: JSON.stringify({
          user_email: email,
          external_id: item.external_id,
          platform: item.platform,
          message: item.content,
          sender_name: item.sender_name,
          interaction_type: item.type,
        }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data?.detail || 'AI suggestion failed')

      setAiStates(prev => ({
        ...prev,
        [item.id]: {
          loading: false,
          suggestion: data.suggested_reply,
          escalate: data.escalate,
          error: null,
          persona: data.ai_persona || null,
        },
      }))

      // Pre-fill the reply textarea with the suggestion
      setReplyContent(data.suggested_reply)
    } catch (err) {
      setAiStates(prev => ({
        ...prev,
        [item.id]: {
          loading: false,
          suggestion: null,
          escalate: false,
          error: err instanceof Error ? err.message : 'AI suggestion failed',
          persona: null,
        },
      }))
    }
  }

  useEffect(() => {
    loadInbox()
    const intervalId = setInterval(() => loadInbox(false, undefined, undefined, true), 5000)
    return () => clearInterval(intervalId)
  }, [page, activeFilter, email])

  // ── Render Single Interaction ──
  const renderInteractionItem = (item: Interaction) => {
    const ai = aiStates[item.id]
    const isOpen = replyingTo === item.id

    return (
      <div
        key={item.id}
        className="post-item inbox-item"
        style={{ flexDirection: 'column', alignItems: 'flex-start', marginBottom: '0' }}
      >
        {/* Row: avatar + content + actions */}
        <div style={{ display: 'flex', width: '100%', alignItems: 'center' }}>
          <div
            className="avatar"
            style={{
              marginRight: '16px',
              background:
                item.platform === 'facebook'
                  ? '#1877f2'
                  : 'linear-gradient(45deg, #f09433 0%, #e6683c 25%, #dc2743 50%, #cc2366 75%, #bc1888 100%)',
            }}
          >
            {item.platform === 'facebook' ? 'FB' : 'IG'}
          </div>

          <div className="post-body" style={{ flex: 1 }}>
            <div className="post-meta" style={{ marginBottom: '4px' }}>
              {item.is_outgoing && (
                <span
                  style={{
                    color: 'var(--primary)',
                    fontWeight: 700,
                    fontSize: '10px',
                    textTransform: 'uppercase',
                    marginRight: '8px',
                    border: '1px solid var(--primary)',
                    padding: '2px 6px',
                    borderRadius: '4px',
                  }}
                >
                  {item.sender_name === 'Firebelly (AI)' ? '🤖 AI SENT' : 'SENT BY YOU'}
                </span>
              )}
              <span style={{ fontWeight: 600, color: 'var(--text-bright)' }}>
                {item.sender_name || 'Anonymous'}
              </span>
              <span style={{ margin: '0 8px', color: 'var(--muted)' }}>•</span>
              <span
                className={`badge badge--${item.type === 'comment' ? 'draft' : 'published'}`}
                style={{ textTransform: 'uppercase', fontSize: '10px' }}
              >
                {item.type}
              </span>
              <span style={{ marginLeft: 'auto', color: 'var(--muted)', fontSize: '12px' }}>
                {new Date(item.created_at).toLocaleString()}
              </span>
            </div>
            <div className="post-caption" style={{ fontSize: '15px' }}>{item.content}</div>
          </div>

          {/* Action buttons — only on incoming messages */}
          {!item.is_outgoing && (
            <div className="post-actions" style={{ marginLeft: '16px', display: 'flex', gap: '8px' }}>
              {/* AI Suggest button */}
              <button
                className="btn-secondary"
                style={{
                  fontSize: '12px',
                  padding: '6px 10px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                  background: ai?.loading
                    ? 'rgba(130,80,255,0.15)'
                    : 'rgba(130,80,255,0.1)',
                  border: '1px solid rgba(130,80,255,0.4)',
                  color: '#b48aff',
                  borderRadius: '6px',
                  cursor: ai?.loading ? 'not-allowed' : 'pointer',
                  transition: 'all 0.2s',
                }}
                disabled={ai?.loading}
                onClick={() => getAiSuggestion(item)}
                title="Get AI reply suggestion"
              >
                {ai?.loading ? (
                  <>
                    <span style={{ fontSize: '14px' }}>⟳</span> Thinking...
                  </>
                ) : (
                  <>
                    <span style={{ fontSize: '14px' }}>✦</span> AI Suggest
                  </>
                )}
              </button>

              {/* Manual Reply button */}
              <button
                className="btn-primary"
                style={{ fontSize: '13px', padding: '6px 12px' }}
                onClick={() => {
                  if (isOpen) {
                    setReplyingTo(null)
                    setReplyContent('')
                  } else {
                    setReplyingTo(item.id)
                    setReplyContent('')
                    setAiStates(prev => ({ ...prev, [item.id]: { loading: false, suggestion: null, escalate: false, error: null, persona: null } }))
                  }
                }}
              >
                {isOpen ? 'Cancel' : 'Reply'}
              </button>

              {/* Delete button — comments only */}
              {item.type === 'comment' && (
                <button
                  style={{
                    fontSize: '12px', padding: '6px 10px', borderRadius: '6px', cursor: 'pointer',
                    background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.3)',
                    color: '#ef4444', transition: 'all 0.2s',
                  }}
                  disabled={deletingComment === item.external_id}
                  onClick={() => deleteComment(item)}
                  title={item.platform === 'instagram' ? 'Hide comment on Instagram' : 'Delete comment from Facebook'}
                >
                  {deletingComment === item.external_id ? '...' : '🗑'}
                </button>
              )}
            </div>
          )}

          {/* Outgoing comment — show delete only */}
          {item.is_outgoing && item.type === 'comment' && (
            <div className="post-actions" style={{ marginLeft: '16px' }}>
              <button
                style={{
                  fontSize: '12px', padding: '6px 10px', borderRadius: '6px', cursor: 'pointer',
                  background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.3)',
                  color: '#ef4444',
                }}
                disabled={deletingComment === item.external_id}
                onClick={() => deleteComment(item)}
                title={item.platform === 'instagram' ? 'Hide comment on Instagram' : 'Delete comment from Facebook'}
              >
                {deletingComment === item.external_id ? '...' : '🗑'}
              </button>
            </div>
          )}
        </div>

        {/* AI Escalation Banner */}
        {ai?.escalate && (
          <div
            style={{
              width: '100%',
              marginTop: '10px',
              padding: '10px 14px',
              background: 'rgba(255,80,80,0.1)',
              border: '1px solid rgba(255,80,80,0.3)',
              borderRadius: '8px',
              color: '#ff8080',
              fontSize: '13px',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
            }}
          >
            <span>⚠️</span>
            <span>Escalation detected — this message has been flagged for human follow-up. Review the AI suggestion before sending.</span>
          </div>
        )}

        {/* AI Error */}
        {ai?.error && (
          <div
            style={{
              width: '100%',
              marginTop: '8px',
              padding: '8px 12px',
              background: 'rgba(255,100,100,0.08)',
              borderRadius: '6px',
              color: '#ff9999',
              fontSize: '12px',
            }}
          >
            AI error: {ai.error}
          </div>
        )}

        {/* Reply Box */}
        {isOpen && (
          <div
            className="reply-box"
            style={{
              width: '100%',
              marginTop: '16px',
              padding: '16px',
              background: 'rgba(255,255,255,0.05)',
              borderRadius: '8px',
              border: ai?.suggestion ? '1px solid rgba(130,80,255,0.25)' : '1px solid rgba(255,255,255,0.08)',
            }}
          >
            {/* AI suggestion notice */}
            {ai?.suggestion && replyContent === ai.suggestion && (
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  marginBottom: '10px',
                  fontSize: '12px',
                  color: ai.persona === 'blaze' ? '#ff9f43' : '#b48aff',
                }}
              >
                <span>{ai.persona === 'blaze' ? '🔥' : '✦'}</span>
                <span>
                  {ai.persona === 'blaze'
                    ? 'Blaze (comment AI) — keep it short and punchy'
                    : 'Ember (DM AI) — review and edit before sending'}
                </span>
              </div>
            )}

            <textarea
              className="form-input"
              placeholder="Type your reply..."
              style={{
                background: 'var(--bg-card)',
                minHeight: '80px',
                marginBottom: '12px',
                border: ai?.suggestion && replyContent === ai.suggestion
                  ? '1px solid rgba(130,80,255,0.4)'
                  : undefined,
              }}
              value={replyContent}
              onChange={e => setReplyContent(e.target.value)}
            />

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              {/* Re-generate button */}
              <button
                className="btn-secondary"
                style={{
                  fontSize: '12px',
                  padding: '5px 10px',
                  color: '#b48aff',
                  border: '1px solid rgba(130,80,255,0.3)',
                  background: 'transparent',
                  borderRadius: '6px',
                  cursor: ai?.loading ? 'not-allowed' : 'pointer',
                }}
                disabled={ai?.loading}
                onClick={() => getAiSuggestion(item)}
              >
                {ai?.loading ? '⟳ Generating...' : '✦ Regenerate'}
              </button>

              <button
                className="btn-primary"
                disabled={sendingReply || !replyContent.trim()}
                onClick={() => sendReply(item.platform, item.external_id)}
              >
                {sendingReply ? 'Sending...' : 'Post Reply'}
              </button>
            </div>
          </div>
        )}

        {/* Reply send status */}
        {replyStatus?.id === item.external_id && (
          <div
            className={`form-message ${replyStatus.type}`}
            style={{ width: '100%', marginTop: '8px', padding: '8px' }}
          >
            {replyStatus.msg}
          </div>
        )}

        {/* Delete status */}
        {deleteStatus?.id === item.external_id && (
          <div
            className={`form-message ${deleteStatus.type}`}
            style={{ width: '100%', marginTop: '8px', padding: '8px' }}
          >
            {deleteStatus.msg}
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="workspace-shell">
      {/* ── Sidebar ── */}
      <aside className="workspace-sidebar">
        <div className="sidebar-header">
          <div className="sidebar-title">Menu</div>
        </div>
        <Link to="/workspace" className="sidebar-item">
          <div className="avatar">WS</div>
          <div className="sidebar-text">Workspace</div>
        </Link>
        <Link to="/inbox" className={`sidebar-item ${window.location.pathname === '/inbox' ? 'active' : ''}`}>
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

        <div className="sidebar-divider" style={{ margin: '20px 0', borderTop: '1px solid var(--dark-border)' }} />

        <div className="sidebar-header">
          <div className="sidebar-title">Inbox</div>
          <button className="icon-button" onClick={() => loadInbox(true)}>Refresh</button>
        </div>

        <div
          className={`sidebar-item${activeFilter === 'all' ? ' active' : ''}`}
          onClick={() => { setActiveFilter('all'); loadInbox(true, 'all', 'all') }}
        >
          <div className="avatar">📥</div>
          <div className="sidebar-text"><div>All Activity</div><span>{total}</span></div>
        </div>

        <div className="sidebar-section">Platforms</div>
        <div
          className={`sidebar-item${activeFilter === 'facebook' ? ' active' : ''}`}
          onClick={() => { setActiveFilter('facebook'); loadInbox(true, 'facebook', 'all') }}
        >
          <div className="avatar">FB</div>
          <div className="sidebar-text"><div>Facebook</div></div>
        </div>
        <div
          className={`sidebar-item${activeFilter === 'instagram' ? ' active' : ''}`}
          onClick={() => { setActiveFilter('instagram'); loadInbox(true, 'instagram', 'all') }}
        >
          <div className="avatar">IG</div>
          <div className="sidebar-text"><div>Instagram</div></div>
        </div>

        <div className="sidebar-section">Types</div>
        <div
          className={`sidebar-item${activeFilter === 'comments' ? ' active' : ''}`}
          onClick={() => { setActiveFilter('comments'); loadInbox(true, 'all', 'comments') }}
        >
          <div className="avatar">💬</div>
          <div className="sidebar-text"><div>Comments</div></div>
        </div>
        <div
          className={`sidebar-item${activeFilter === 'messages' ? ' active' : ''}`}
          onClick={() => { setActiveFilter('messages'); loadInbox(true, 'all', 'messages') }}
        >
          <div className="avatar">✉️</div>
          <div className="sidebar-text"><div>Direct Messages</div></div>
        </div>

        <div style={{ marginTop: 'auto', padding: '20px', borderTop: '1px solid var(--dark-border)' }}>
          <div style={{ paddingBottom: '12px', fontSize: '13px', color: 'var(--muted)', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {email}
          </div>
          <button
            className="ghost-dark"
            style={{ width: '100%', textAlign: 'left', color: '#ff6b6b', padding: '10px', background: 'transparent', border: 'none', cursor: 'pointer' }}
            type="button"
            onClick={() => {
              localStorage.removeItem('autosocial_email')
              navigate('/login')
            }}
          >
            Log out
          </button>
          <div style={{ height: '12px' }}></div>
        </div>
      </aside>

      {/* ── Main ── */}
      <main className="workspace-main">
        <header className="workspace-topbar">
          <div className="topbar-left">
            <div className="topbar-icon">📥</div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <div className="topbar-title">Unified Inbox</div>
                {isPolling && (
                  <div className="badge badge--success" style={{ fontSize: '10px', height: '18px', display: 'flex', alignItems: 'center' }}>
                    <span style={{ display: 'inline-block', width: '6px', height: '6px', borderRadius: '50%', background: '#fff', marginRight: '4px', animation: 'pulse 1.5s infinite' }}></span>
                    Live
                  </div>
                )}
                {/* AI indicator */}
                <div style={{
                  display: 'flex', alignItems: 'center', gap: '4px',
                  fontSize: '11px', color: '#b48aff',
                  background: 'rgba(130,80,255,0.1)',
                  border: '1px solid rgba(130,80,255,0.25)',
                  borderRadius: '12px', padding: '2px 8px'
                }}>
                  <span>✦</span> Ember AI active
                </div>
              </div>
              <div className="topbar-subtitle">
                {loading ? 'Syncing...' : `${total} interactions found`}
              </div>
            </div>
          </div>
          <div className="topbar-actions">
            <Link className="btn-primary" to="/composer">New Post</Link>
          </div>
        </header>

        <section className="workspace-content" style={{ display: 'flex', flexDirection: 'column' }}>
          {loading ? (
            <div className="posts-loading">Syncing your inbox...</div>
          ) : error ? (
            <div className="form-message error">{error}</div>
          ) : interactions.length === 0 ? (
            <div className="empty-card">
              <div className="empty-callout">
                <h3>Your inbox is empty</h3>
                <p>New comments and messages will appear here once they are synced.</p>
                <button className="btn-primary" onClick={() => loadInbox(true)}>Sync Now</button>
              </div>
            </div>
          ) : (
            <>
              <div className="posts-list" style={{ flex: 1 }}>
                {['facebook', 'instagram'].map(platform => {
                  const platformItems = interactions.filter(i => i.platform === platform)
                  if (platformItems.length === 0) return null

                  const platformComments = platformItems.filter(i => i.type === 'comment')
                  const platformMessages = platformItems.filter(i => i.type === 'message')

                  return (
                    <div key={platform} className="inbox-category-section" style={{ marginBottom: '48px' }}>
                      <div
                        className="platform-header-sticky"
                        style={{
                          position: 'sticky', top: 0, zIndex: 10,
                          display: 'flex', alignItems: 'center', marginBottom: '24px',
                          padding: '12px 16px',
                          background: 'rgba(255,255,255,0.03)',
                          backdropFilter: 'blur(10px)',
                          borderRadius: '12px',
                          borderLeft: `6px solid ${platform === 'facebook' ? '#1877f2' : '#e1306c'}`,
                          boxShadow: '0 4px 15px rgba(0,0,0,0.1)',
                        }}
                      >
                        <div
                          className="avatar"
                          style={{
                            marginRight: '16px',
                            background: platform === 'facebook'
                              ? '#1877f2'
                              : 'linear-gradient(45deg, #f09433 0%, #e6683c 25%, #dc2743 50%, #cc2366 75%, #bc1888 100%)',
                          }}
                        >
                          {platform === 'facebook' ? 'FB' : 'IG'}
                        </div>
                        <h2 style={{ margin: 0, fontSize: '20px', fontWeight: 700, color: 'var(--text-bright)' }}>
                          {platform === 'facebook' ? 'Facebook' : 'Instagram'} Workdesk
                        </h2>
                        <span className="badge" style={{ marginLeft: 'auto', background: 'rgba(255,255,255,0.1)' }}>
                          {platformItems.length} Shown
                        </span>
                      </div>

                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '32px' }}>
                        {/* Comments column */}
                        <div
                          className="interaction-type-section"
                          style={{ flex: '1 1 400px', background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.05)', borderRadius: '12px', padding: '24px' }}
                        >
                          <div style={{ display: 'flex', alignItems: 'center', marginBottom: '20px', color: 'var(--text-bright)' }}>
                            <span style={{ marginRight: '12px', fontSize: '24px' }}>💬</span>
                            <h4 style={{ margin: 0, fontSize: '18px', fontWeight: 600 }}>Feed Comments</h4>
                            <span className="badge" style={{ marginLeft: 'auto', background: 'rgba(255,255,255,0.1)' }}>{platformComments.length}</span>
                          </div>
                          <div className="grid-stack" style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
                            {platformComments.length > 0 ? (
                              <>
                                {platformComments.filter(c => c.is_outgoing).length > 0 && (
                                  <div>
                                    <div style={{ fontSize: '11px', textTransform: 'uppercase', color: 'var(--muted)', marginBottom: '12px', letterSpacing: '0.05em', fontWeight: 600 }}>From You</div>
                                    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                                      {platformComments.filter(c => c.is_outgoing).map(item => renderInteractionItem(item))}
                                    </div>
                                  </div>
                                )}
                                {platformComments.filter(c => !c.is_outgoing).length > 0 && (
                                  <div>
                                    <div style={{ fontSize: '11px', textTransform: 'uppercase', color: 'var(--muted)', marginBottom: '12px', letterSpacing: '0.05em', fontWeight: 600 }}>To You</div>
                                    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                                      {platformComments.filter(c => !c.is_outgoing).map(item => renderInteractionItem(item))}
                                    </div>
                                  </div>
                                )}
                              </>
                            ) : (
                              <div style={{ color: 'var(--muted)', fontSize: '14px', fontStyle: 'italic', padding: '16px 0' }}>No comments yet.</div>
                            )}
                          </div>
                        </div>

                        {/* Messages column */}
                        <div
                          className="interaction-type-section"
                          style={{ flex: '1 1 400px', background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.05)', borderRadius: '12px', padding: '24px' }}
                        >
                          <div style={{ display: 'flex', alignItems: 'center', marginBottom: '20px', color: 'var(--text-bright)' }}>
                            <span style={{ marginRight: '12px', fontSize: '24px' }}>✉️</span>
                            <h4 style={{ margin: 0, fontSize: '18px', fontWeight: 600 }}>Direct Messages</h4>
                            <span className="badge" style={{ marginLeft: 'auto', background: 'rgba(255,255,255,0.1)' }}>{platformMessages.length}</span>
                          </div>
                          <div className="grid-stack" style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
                            {platformMessages.length > 0 ? (
                              <>
                                {platformMessages.filter(m => m.is_outgoing).length > 0 && (
                                  <div>
                                    <div style={{ fontSize: '11px', textTransform: 'uppercase', color: 'var(--muted)', marginBottom: '12px', letterSpacing: '0.05em', fontWeight: 600 }}>From You</div>
                                    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                                      {platformMessages.filter(m => m.is_outgoing).map(item => renderInteractionItem(item))}
                                    </div>
                                  </div>
                                )}
                                {platformMessages.filter(m => !m.is_outgoing).length > 0 && (
                                  <div>
                                    <div style={{ fontSize: '11px', textTransform: 'uppercase', color: 'var(--muted)', marginBottom: '12px', letterSpacing: '0.05em', fontWeight: 600 }}>To You</div>
                                    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                                      {platformMessages.filter(m => !m.is_outgoing).map(item => renderInteractionItem(item))}
                                    </div>
                                  </div>
                                )}
                              </>
                            ) : (
                              <div style={{ color: 'var(--muted)', fontSize: '14px', fontStyle: 'italic', padding: '16px 0' }}>No messages yet.</div>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>

              {/* Pagination */}
              <div
                className="pagination-bar"
                style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  gap: '24px', padding: '32px 0 16px', marginTop: 'auto',
                  borderTop: '1px solid rgba(255,255,255,0.05)',
                }}
              >
                <button
                  className="btn-secondary"
                  disabled={page === 1 || loading}
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                  style={{ minWidth: '100px' }}
                >
                  Previous
                </button>
                <div style={{ color: 'var(--muted)', fontSize: '14px', fontWeight: 500 }}>
                  Page <span style={{ color: 'var(--text-bright)' }}>{page}</span> of {Math.ceil(total / PAGE_SIZE) || 1}
                </div>
                <button
                  className="btn-secondary"
                  disabled={page * PAGE_SIZE >= total || loading}
                  onClick={() => setPage(p => p + 1)}
                  style={{ minWidth: '100px' }}
                >
                  Next
                </button>
              </div>
            </>
          )}
        </section>
      </main>
    </div>
  )
}

export default Inbox