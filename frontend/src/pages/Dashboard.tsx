import { useEffect, useState, useMemo } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area } from 'recharts'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

type MetricPoint = {
  date: string
  value: number
}

type AnalyticsSummary = {
  reach: number
  engagement: number
  follower_growth: number
  top_posts: any[]
  engagement_over_time: MetricPoint[]
  platform: string
}

type SocialAccount = {
  id: string
  platform: 'facebook' | 'instagram'
  page_name?: string | null
  instagram_username?: string | null
  profile_picture_url?: string | null
  is_connected: boolean
}

function Dashboard() {
  const navigate = useNavigate()
  const email = useMemo(() => localStorage.getItem('autosocial_email') ?? '', [])
  
  const [summaries, setSummaries] = useState<AnalyticsSummary[]>([])
  const [accounts, setAccounts] = useState<SocialAccount[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [activePlatform, setActivePlatform] = useState<'all' | 'facebook' | 'instagram'>('all')

  useEffect(() => {
    if (!email) {
      navigate('/login')
      return
    }
    loadData()
  }, [email, navigate])

  const loadData = async () => {
    setLoading(true)
    setError('')
    try {
      const [acctRes, summaryRes] = await Promise.all([
        fetch(`${API_BASE}/accounts?user_email=${encodeURIComponent(email)}`, {
          headers: { 'ngrok-skip-browser-warning': 'true' }
        }),
        fetch(`${API_BASE}/analytics/summary?user_email=${encodeURIComponent(email)}`, {
          headers: { 'ngrok-skip-browser-warning': 'true' }
        })
      ])

      if (!acctRes.ok || !summaryRes.ok) throw new Error('Failed to fetch analytics data')

      const acctData = await acctRes.json()
      const summaryData = await summaryRes.json()

      setAccounts(acctData.filter((a: SocialAccount) => a.is_connected))
      setSummaries(summaryData)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setLoading(false)
    }
  }

  const filteredSummaries = useMemo(() => {
    if (activePlatform === 'all') return summaries
    return summaries.filter(s => s.platform === activePlatform)
  }, [summaries, activePlatform])

  const aggregateMetrics = useMemo(() => {
    return filteredSummaries.reduce((acc, curr) => ({
      reach: acc.reach + curr.reach,
      engagement: acc.engagement + curr.engagement,
      growth: acc.growth + curr.follower_growth,
    }), { reach: 0, engagement: 0, growth: 0 })
  }, [filteredSummaries])

  const chartData = useMemo(() => {
    // Merge daily data across platforms if "all" is selected
    const dailyMap: Record<string, number> = {}
    filteredSummaries.forEach(s => {
      s.engagement_over_time.forEach(p => {
        dailyMap[p.date] = (dailyMap[p.date] || 0) + p.value
      })
    })
    return Object.entries(dailyMap)
      .map(([date, value]) => ({ date, value }))
      .sort((a, b) => a.date.localeCompare(b.date))
  }, [filteredSummaries])

  if (loading) {
    return (
      <div className="workspace-shell">
        <aside className="workspace-sidebar">
          <div className="sidebar-header"><div className="sidebar-title">Analytics</div></div>
        </aside>
        <main className="workspace-main" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div className="loader">Loading Dashboard...</div>
        </main>
      </div>
    )
  }

  return (
    <div className="workspace-shell">
      {/* ── Sidebar ── */}
      <aside className="workspace-sidebar">
        <div className="sidebar-header">
          <div className="sidebar-title">Analytics</div>
        </div>
        
        <Link to="/workspace" className="sidebar-item">
          <div className="avatar">WS</div>
          <div className="sidebar-text">Back to Workspace</div>
        </Link>
        <Link to="/inbox" className="sidebar-item">
          <div className="avatar">IN</div>
          <div className="sidebar-text">Engagement Inbox</div>
        </Link>

        <div className="sidebar-divider" style={{ margin: '20px 0', borderTop: '1px solid rgba(255,255,255,0.1)' }} />

        {(['all', 'facebook', 'instagram'] as const).map(p => (
          <div 
            key={p} 
            className={`sidebar-item ${activePlatform === p ? 'active' : ''}`}
            onClick={() => setActivePlatform(p)}
          >
            <div className="avatar">{p === 'all' ? 'Σ' : p === 'facebook' ? 'FB' : 'IG'}</div>
            <div className="sidebar-text">
              <div style={{ textTransform: 'capitalize' }}>{p} Metrics</div>
            </div>
          </div>
        ))}
      </aside>

      {/* ── Main Content ── */}
      <main className="workspace-main">
        <header className="workspace-header">
           <h1>Analytics Overview</h1>
           <div className="header-actions">
             <button className="btn-secondary" onClick={loadData}>Refresh Data</button>
           </div>
        </header>

        {error && <div className="alert alert--error">{error}</div>}

        <section className="analytics-content">
          {/* Summary Cards */}
          <div className="stats-grid">
            <div className="stats-card glass">
              <div className="stats-label">Total Reach</div>
              <div className="stats-value">{aggregateMetrics.reach.toLocaleString()}</div>
              <div className="stats-trend pos">+12% vs last month</div>
            </div>
            <div className="stats-card glass">
              <div className="stats-label">Total Engagement</div>
              <div className="stats-value">{aggregateMetrics.engagement.toLocaleString()}</div>
              <div className="stats-trend pos">+5.2%</div>
            </div>
            <div className="stats-card glass">
              <div className="stats-label">Follower Growth</div>
              <div className="stats-value">+{aggregateMetrics.growth.toLocaleString()}</div>
              <div className="stats-trend">New followers</div>
            </div>
          </div>

          {/* Chart Section */}
          <div className="chart-container glass" style={{ marginTop: '24px', padding: '24px', borderRadius: '16px' }}>
            <h3>Engagement Trends</h3>
            <p style={{ opacity: 0.6, marginBottom: '20px' }}>Daily Interactions over the last 30 days</p>
            <div style={{ width: '100%', height: 350 }}>
              <ResponsiveContainer>
                <AreaChart data={chartData}>
                  <defs>
                    <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="#6366f1" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                  <XAxis 
                    dataKey="date" 
                    stroke="rgba(255,255,255,0.4)" 
                    fontSize={12}
                    tickFormatter={(str) => str.split('-').slice(1).join('/')}
                  />
                  <YAxis stroke="rgba(255,255,255,0.4)" fontSize={12} />
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#1e293b', border: 'none', borderRadius: '8px', color: '#fff' }}
                    itemStyle={{ color: '#6366f1' }}
                  />
                  <Area 
                    type="monotone" 
                    dataKey="value" 
                    stroke="#6366f1" 
                    fillOpacity={1} 
                    fill="url(#colorValue)" 
                    strokeWidth={3}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Connected Accounts Tracking */}
          <div style={{ marginTop: '24px' }}>
             <h3>Connected Channels</h3>
             <div className="accounts-mini-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '16px', marginTop: '12px' }}>
                {accounts.map(acc => (
                  <div key={acc.id} className="glass" style={{ padding: '16px', borderRadius: '12px', display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <img src={acc.profile_picture_url || ''} alt="" style={{ width: '40px', height: '40px', borderRadius: '50%', backgroundColor: '#334155' }} />
                    <div style={{ overflow: 'hidden' }}>
                      <div style={{ fontWeight: 600, fontSize: '14px', whiteSpace: 'nowrap', textOverflow: 'ellipsis' }}>{acc.page_name || acc.instagram_username}</div>
                      <div style={{ fontSize: '12px', opacity: 0.5, textTransform: 'capitalize' }}>{acc.platform}</div>
                    </div>
                  </div>
                ))}
             </div>
          </div>

        </section>
      </main>
    </div>
  )
}

export default Dashboard
