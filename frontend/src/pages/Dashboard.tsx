import { useEffect, useState, useMemo, useCallback } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area } from 'recharts'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

// ── Types ─────────────────────────────────────────────────────────────────────
type MetricPoint = { date: string; value: number }

type AnalyticsSummary = {
  reach: number
  engagement: number
  follower_growth: number
  top_posts: any[]
  engagement_over_time: MetricPoint[]
  platform: string
}

type AccountStat = {
  platform: 'facebook' | 'instagram'
  name: string
  profile_picture_url: string | null
  followers: number
  following: number
  total_posts: number
  profile_views: number
}

type PostInsight = {
  post_id: string
  platform: string
  fb_post_id: string | null
  ig_media_id: string | null
  caption: string
  media_url: string | null
  created_at: string
  likes: number
  comments: number
  shares: number
  saves: number
  reach: number
  impressions: number
  status: string
}

type SocialAccount = {
  id: string
  platform: 'facebook' | 'instagram'
  page_name?: string | null
  instagram_username?: string | null
  profile_picture_url?: string | null
  is_connected: boolean
}

// ── Helpers ───────────────────────────────────────────────────────────────────
const fmt = (n: number) =>
  n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n)

function Dashboard() {
  const navigate = useNavigate()
  const email = useMemo(() => localStorage.getItem('autosocial_email') ?? '', [])

  const [summaries, setSummaries]         = useState<AnalyticsSummary[]>([])
  const [accountStats, setAccountStats]   = useState<AccountStat[]>([])
  const [postInsights, setPostInsights]   = useState<PostInsight[]>([])
  const [accounts, setAccounts]           = useState<SocialAccount[]>([])
  const [loading, setLoading]             = useState(true)
  const [insightsLoading, setInsightsLoading] = useState(false)
  const [error, setError]                 = useState('')
  const [activePlatform, setActivePlatform] = useState<'all' | 'facebook' | 'instagram'>('all')
  const [activeTab, setActiveTab]         = useState<'overview' | 'posts'>('overview')
  const [deletingPost, setDeletingPost]   = useState<string | null>(null)
  const [deletingComment, setDeletingComment] = useState<string | null>(null)
  const [actionMsg, setActionMsg]         = useState<{ msg: string; type: 'success' | 'error' } | null>(null)

  useEffect(() => {
    if (!email) { navigate('/login'); return }
    loadData()
  }, [email])

  // ── Load summary + accounts ───────────────────────────────────────────────
  const loadData = async () => {
    setLoading(true)
    setError('')
    try {
      const [acctRes, summaryRes, statsRes] = await Promise.all([
        fetch(`${API_BASE}/accounts?user_email=${encodeURIComponent(email)}`, { headers: { 'ngrok-skip-browser-warning': 'true' } }),
        fetch(`${API_BASE}/analytics/summary?user_email=${encodeURIComponent(email)}`, { headers: { 'ngrok-skip-browser-warning': 'true' } }),
        fetch(`${API_BASE}/analytics/account-stats?user_email=${encodeURIComponent(email)}`, { headers: { 'ngrok-skip-browser-warning': 'true' } }),
      ])
      const [acctData, summaryData, statsData] = await Promise.all([
        acctRes.json(), summaryRes.json(), statsRes.json()
      ])
      setAccounts(acctData.filter((a: SocialAccount) => a.is_connected))
      setSummaries(summaryData)
      setAccountStats(statsData)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load data')
    } finally {
      setLoading(false)
    }
  }

  // ── Load per-post insights (on-demand) ────────────────────────────────────
  const loadPostInsights = useCallback(async () => {
    setInsightsLoading(true)
    try {
      const res = await fetch(
        `${API_BASE}/analytics/post-insights?user_email=${encodeURIComponent(email)}&limit=20`,
        { headers: { 'ngrok-skip-browser-warning': 'true' } }
      )
      const data = await res.json()
      setPostInsights(Array.isArray(data) ? data : [])
    } catch (err) {
      console.error('Post insights failed:', err)
    } finally {
      setInsightsLoading(false)
    }
  }, [email])

  // Load post insights when switching to posts tab
  useEffect(() => {
    if (activeTab === 'posts' && postInsights.length === 0) {
      loadPostInsights()
    }
  }, [activeTab])

  // ── Delete post ───────────────────────────────────────────────────────────
  const handleDeletePost = async (postId: string, platform: string) => {
    if (!window.confirm(
      platform === 'instagram'
        ? 'Remove this post from your dashboard? (Instagram does not allow deleting published posts via API — it will only be removed here.)'
        : 'Permanently delete this post from Facebook and your dashboard?'
    )) return

    setDeletingPost(postId)
    setActionMsg(null)
    try {
      const res = await fetch(
        `${API_BASE}/posts/${postId}?user_email=${encodeURIComponent(email)}`,
        { method: 'DELETE', headers: { 'ngrok-skip-browser-warning': 'true' } }
      )
      if (!res.ok) throw new Error('Delete failed')
      setPostInsights(prev => prev.filter(p => p.post_id !== postId))
      setActionMsg({ msg: platform === 'instagram' ? 'Removed from dashboard (Instagram posts cannot be deleted via API).' : 'Post deleted from Facebook.', type: 'success' })
    } catch (err) {
      setActionMsg({ msg: err instanceof Error ? err.message : 'Delete failed', type: 'error' })
    } finally {
      setDeletingPost(null)
    }
  }

  // ── Delete comment ────────────────────────────────────────────────────────
  const handleDeleteComment = async (externalId: string, platform: string) => {
    if (!window.confirm(
      platform === 'instagram'
        ? 'Hide this comment on Instagram?'
        : 'Delete this comment from Facebook?'
    )) return

    setDeletingComment(externalId)
    setActionMsg(null)
    try {
      const res = await fetch(
        `${API_BASE}/inbox/comment/${externalId}?user_email=${encodeURIComponent(email)}`,
        { method: 'DELETE', headers: { 'ngrok-skip-browser-warning': 'true' } }
      )
      const data = await res.json()
      if (!res.ok) throw new Error(data?.detail || 'Failed')
      setActionMsg({ msg: data.note || 'Comment removed.', type: 'success' })
    } catch (err) {
      setActionMsg({ msg: err instanceof Error ? err.message : 'Failed to delete comment', type: 'error' })
    } finally {
      setDeletingComment(null)
    }
  }

  // ── Computed ──────────────────────────────────────────────────────────────
  const filteredSummaries = useMemo(() =>
    activePlatform === 'all' ? summaries : summaries.filter(s => s.platform === activePlatform),
    [summaries, activePlatform]
  )

  const aggregateMetrics = useMemo(() =>
    filteredSummaries.reduce((acc, curr) => ({
      reach: acc.reach + curr.reach,
      engagement: acc.engagement + curr.engagement,
      growth: acc.growth + curr.follower_growth,
    }), { reach: 0, engagement: 0, growth: 0 }),
    [filteredSummaries]
  )

  const chartData = useMemo(() => {
    const map: Record<string, number> = {}
    filteredSummaries.forEach(s =>
      s.engagement_over_time.forEach(p => { map[p.date] = (map[p.date] || 0) + p.value })
    )
    return Object.entries(map).map(([date, value]) => ({ date, value })).sort((a, b) => a.date.localeCompare(b.date))
  }, [filteredSummaries])

  const filteredInsights = useMemo(() =>
    activePlatform === 'all'
      ? postInsights
      : postInsights.filter(p => p.platform === activePlatform),
    [postInsights, activePlatform]
  )

  if (loading) return (
    <div className="workspace-shell">
      <aside className="workspace-sidebar"><div className="sidebar-header"><div className="sidebar-title">Analytics</div></div></aside>
      <main className="workspace-main" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div className="loader">Loading Dashboard...</div>
      </main>
    </div>
  )

  return (
    <div className="workspace-shell">

      {/* ── Sidebar ── */}
      <aside className="workspace-sidebar">
        <div className="sidebar-header"><div className="sidebar-title">Analytics</div></div>

        <Link to="/workspace" className="sidebar-item"><div className="avatar">WS</div><div className="sidebar-text">Workspace</div></Link>
        <Link to="/inbox" className="sidebar-item"><div className="avatar">IN</div><div className="sidebar-text">Engagement Inbox</div></Link>
        <Link to="/content-studio" className="sidebar-item"><div className="avatar">CS</div><div className="sidebar-text">Content Studio</div></Link>

        <div className="sidebar-divider" style={{ margin: '20px 0', borderTop: '1px solid rgba(255,255,255,0.1)' }} />

        {(['all', 'facebook', 'instagram'] as const).map(p => (
          <div key={p} className={`sidebar-item ${activePlatform === p ? 'active' : ''}`} onClick={() => setActivePlatform(p)}>
            <div className="avatar">{p === 'all' ? 'Σ' : p === 'facebook' ? 'FB' : 'IG'}</div>
            <div className="sidebar-text"><div style={{ textTransform: 'capitalize' }}>{p} Metrics</div></div>
          </div>
        ))}

        <div className="sidebar-divider" style={{ margin: '20px 0', borderTop: '1px solid rgba(255,255,255,0.1)' }} />

        <div style={{ padding: '0 12px' }}>
          <button className="btn-secondary" style={{ width: '100%', padding: '10px', fontSize: '13px' }} onClick={() => { loadData(); if (activeTab === 'posts') loadPostInsights() }}>
            ↻ Refresh All
          </button>
        </div>

        <div style={{ marginTop: 'auto', padding: '20px', borderTop: '1px solid var(--dark-border)' }}>
          <div style={{ paddingBottom: '12px', fontSize: '13px', color: 'var(--muted)', overflow: 'hidden', textOverflow: 'ellipsis' }}>{email}</div>
          <button className="ghost-dark" style={{ width: '100%', textAlign: 'left', color: '#ff6b6b', padding: '10px', background: 'transparent', border: 'none', cursor: 'pointer' }}
            onClick={() => { localStorage.removeItem('autosocial_email'); navigate('/login') }}>Log out</button>
        </div>
      </aside>

      {/* ── Main ── */}
      <main className="workspace-main">
        <header className="workspace-topbar">
          <div className="topbar-left">
            <div className="topbar-icon">📊</div>
            <div>
              <div className="topbar-title">Analytics Dashboard</div>
              <div className="topbar-subtitle">
                {activePlatform === 'all' ? 'All platforms' : activePlatform.charAt(0).toUpperCase() + activePlatform.slice(1)} · Last 30 days
              </div>
            </div>
          </div>
        </header>

        {error && <div className="form-message error" style={{ margin: '0 0 16px' }}>{error}</div>}
        {actionMsg && (
          <div className={`form-message ${actionMsg.type}`} style={{ margin: '0 0 16px', borderRadius: '8px' }}>
            {actionMsg.msg}
          </div>
        )}

        <section className="workspace-content" style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>

          {/* ── Account stats row ── */}
          {accountStats.length > 0 && (
            <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
              {accountStats
                .filter(a => activePlatform === 'all' || a.platform === activePlatform)
                .map(acc => (
                  <div key={acc.platform} style={{
                    flex: '1 1 220px', background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.07)',
                    borderRadius: '14px', padding: '18px', display: 'flex', flexDirection: 'column', gap: '12px',
                    borderLeft: `4px solid ${acc.platform === 'instagram' ? '#e1306c' : '#1877f2'}`,
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      {acc.profile_picture_url
                        ? <img src={acc.profile_picture_url} style={{ width: '36px', height: '36px', borderRadius: '50%' }} alt="" />
                        : <div style={{ width: '36px', height: '36px', borderRadius: '50%', background: acc.platform === 'instagram' ? '#e1306c' : '#1877f2', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '14px', fontWeight: 700, color: '#fff' }}>{acc.platform === 'instagram' ? 'IG' : 'FB'}</div>
                      }
                      <div>
                        <div style={{ fontWeight: 600, fontSize: '14px', color: 'var(--text-bright)' }}>{acc.name}</div>
                        <div style={{ fontSize: '11px', color: 'var(--muted)', textTransform: 'capitalize' }}>{acc.platform}</div>
                      </div>
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                      {[
                        { label: 'Followers', value: fmt(acc.followers) },
                        { label: 'Posts', value: fmt(acc.total_posts) },
                        ...(acc.platform === 'instagram' ? [
                          { label: 'Following', value: fmt(acc.following) },
                          { label: 'Profile Views', value: fmt(acc.profile_views) },
                        ] : []),
                      ].map(({ label, value }) => (
                        <div key={label} style={{ background: 'rgba(255,255,255,0.04)', borderRadius: '8px', padding: '8px 10px' }}>
                          <div style={{ fontSize: '11px', color: 'var(--muted)' }}>{label}</div>
                          <div style={{ fontSize: '18px', fontWeight: 700, color: 'var(--text-bright)' }}>{value}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
            </div>
          )}

          {/* ── Aggregate metric cards ── */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '16px' }}>
            {[
              { label: 'Total Reach', value: fmt(aggregateMetrics.reach), color: '#6366f1' },
              { label: 'Total Engagement', value: fmt(aggregateMetrics.engagement), color: '#06b6d4' },
              { label: 'Follower Growth', value: `+${fmt(aggregateMetrics.growth)}`, color: '#22c55e' },
            ].map(({ label, value, color }) => (
              <div key={label} className="glass" style={{ padding: '20px', borderRadius: '14px', borderLeft: `3px solid ${color}` }}>
                <div style={{ fontSize: '12px', color: 'var(--muted)', marginBottom: '6px' }}>{label}</div>
                <div style={{ fontSize: '28px', fontWeight: 700, color: 'var(--text-bright)' }}>{value}</div>
              </div>
            ))}
          </div>

          {/* ── Tabs ── */}
          <div style={{ display: 'flex', gap: '0', borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
            {([['overview', 'Engagement Chart'], ['posts', 'Post Performance']] as const).map(([key, label]) => (
              <button key={key} onClick={() => setActiveTab(key)}
                style={{
                  padding: '12px 20px', fontSize: '14px', fontWeight: 600, background: 'transparent', border: 'none', cursor: 'pointer',
                  color: activeTab === key ? 'var(--text-bright)' : 'var(--muted)',
                  borderBottom: activeTab === key ? '2px solid #6366f1' : '2px solid transparent',
                }}>
                {label}
              </button>
            ))}
          </div>

          {/* ── Tab: Engagement Chart ── */}
          {activeTab === 'overview' && (
            <div className="glass" style={{ padding: '24px', borderRadius: '16px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                <div>
                  <div style={{ fontSize: '16px', fontWeight: 600, color: 'var(--text-bright)' }}>Engagement over time</div>
                  <div style={{ fontSize: '13px', color: 'var(--muted)' }}>Daily interactions · last 30 days</div>
                </div>
              </div>
              {chartData.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '60px', color: 'var(--muted)', fontSize: '14px' }}>
                  No engagement data yet — connect your accounts and start posting.
                </div>
              ) : (
                <div style={{ width: '100%', height: 300 }}>
                  <ResponsiveContainer>
                    <AreaChart data={chartData}>
                      <defs>
                        <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
                          <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                      <XAxis dataKey="date" stroke="rgba(255,255,255,0.4)" fontSize={11} tickFormatter={s => s.split('-').slice(1).join('/')} />
                      <YAxis stroke="rgba(255,255,255,0.4)" fontSize={11} />
                      <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: 'none', borderRadius: '8px', color: '#fff' }} itemStyle={{ color: '#6366f1' }} />
                      <Area type="monotone" dataKey="value" stroke="#6366f1" fillOpacity={1} fill="url(#colorValue)" strokeWidth={2.5} />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              )}
            </div>
          )}

          {/* ── Tab: Post Performance ── */}
          {activeTab === 'posts' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ fontSize: '13px', color: 'var(--muted)' }}>
                  {insightsLoading ? 'Fetching live metrics from Meta...' : `${filteredInsights.length} published posts`}
                </div>
                <button className="btn-secondary" style={{ padding: '8px 14px', fontSize: '13px' }}
                  onClick={loadPostInsights} disabled={insightsLoading}>
                  {insightsLoading ? '↻ Loading...' : '↻ Refresh Metrics'}
                </button>
              </div>

              {filteredInsights.length === 0 && !insightsLoading && (
                <div style={{ textAlign: 'center', padding: '60px', background: 'rgba(255,255,255,0.02)', borderRadius: '14px', color: 'var(--muted)', fontSize: '14px' }}>
                  No published posts yet.
                </div>
              )}

              {filteredInsights.map(post => (
                <div key={post.post_id} style={{
                  background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.07)',
                  borderRadius: '14px', padding: '18px', display: 'flex', gap: '16px', alignItems: 'flex-start',
                  borderLeft: `4px solid ${post.platform === 'instagram' ? '#e1306c' : '#1877f2'}`,
                }}>
                  {/* Thumbnail */}
                  {post.media_url ? (
                    <img src={post.media_url} alt="" style={{ width: '72px', height: '72px', borderRadius: '8px', objectFit: 'cover', flexShrink: 0 }} />
                  ) : (
                    <div style={{ width: '72px', height: '72px', borderRadius: '8px', background: 'rgba(255,255,255,0.06)', flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '24px' }}>
                      {post.platform === 'instagram' ? '📸' : '👥'}
                    </div>
                  )}

                  {/* Content */}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: '14px', color: 'var(--text-bright)', marginBottom: '10px', lineHeight: 1.5 }}>
                      {post.caption}
                    </div>

                    {/* Metrics row */}
                    <div style={{ display: 'flex', gap: '18px', flexWrap: 'wrap', marginBottom: '12px' }}>
                      {[
                        { icon: '❤️', label: 'Likes', value: post.likes },
                        { icon: '💬', label: 'Comments', value: post.comments },
                        { icon: '🔁', label: 'Shares', value: post.shares },
                        { icon: '🔖', label: 'Saves', value: post.saves },
                        { icon: '👁️', label: 'Reach', value: post.reach },
                        { icon: '📊', label: 'Impressions', value: post.impressions },
                      ].map(({ icon, label, value }) => (
                        <div key={label} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: '52px' }}>
                          <div style={{ fontSize: '16px' }}>{icon}</div>
                          <div style={{ fontSize: '15px', fontWeight: 700, color: 'var(--text-bright)' }}>{fmt(value)}</div>
                          <div style={{ fontSize: '10px', color: 'var(--muted)' }}>{label}</div>
                        </div>
                      ))}
                    </div>

                    {/* Meta */}
                    <div style={{ fontSize: '12px', color: 'var(--muted)' }}>
                      {new Date(post.created_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}
                      &nbsp;·&nbsp;
                      <span style={{ textTransform: 'capitalize' }}>{post.platform}</span>
                    </div>
                  </div>

                  {/* Actions */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', flexShrink: 0 }}>
                    <button
                      onClick={() => handleDeletePost(post.post_id, post.platform)}
                      disabled={deletingPost === post.post_id}
                      style={{
                        padding: '7px 14px', fontSize: '12px', fontWeight: 600, borderRadius: '8px', cursor: 'pointer',
                        background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', color: '#ef4444',
                      }}>
                      {deletingPost === post.post_id ? 'Deleting...' : '🗑 Delete'}
                    </button>

                    {post.platform === 'instagram' && (
                      <div style={{ fontSize: '10px', color: 'var(--muted)', textAlign: 'center', maxWidth: '80px', lineHeight: 1.3 }}>
                        IG posts removed from dashboard only
                      </div>
                    )}
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

export default Dashboard