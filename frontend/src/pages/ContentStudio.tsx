import { useState, useMemo } from 'react'
import { Link, useNavigate } from 'react-router-dom'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

type Platform = 'instagram' | 'facebook' | 'both'
type Mode = 'surprise' | 'idea_only' | 'image_idea'

type GeneratedContent = {
  caption_instagram: string
  caption_facebook: string
  hashtags: string[]                  // flat combined list
  hashtags_brand: string[]
  hashtags_niche: string[]
  hashtags_discovery: string[]
  content_theme: string               // alias for content_pillar_label
  content_pillar: string              // same as chosen_pillar
  content_pillar_label: string
  chosen_pillar: string
  chosen_dish: string | null
  content_angle: string
  image_description?: string
  generated_image_url?: string        // DALL-E generated image URL
  image_prompt?: string               // the LLM-written DALL-E prompt
  suggested_schedule: {
    datetime: string
    datetime_str: string
    reason: string
    pillar: string
  }
}

function ContentStudio() {
  const navigate = useNavigate()
  const email = useMemo(() => localStorage.getItem('autosocial_email') ?? '', [])

  const [mode, setMode] = useState<Mode>('surprise')
  const [platform, setPlatform] = useState<Platform>('both')
  const [ownerIdea, setOwnerIdea] = useState('')
  const [imageFile, setImageFile] = useState<File | null>(null)
  const [imagePreview, setImagePreview] = useState<string | null>(null)
  const [generating, setGenerating] = useState(false)
  const [result, setResult] = useState<GeneratedContent | null>(null)
  const [error, setError] = useState('')

  // Editable output state
  const [editedCaption, setEditedCaption] = useState('')
  const [editedHashtags, setEditedHashtags] = useState<string[]>([])
  const [activeTab, setActiveTab] = useState<'instagram' | 'facebook'>('instagram')
  const [scheduling, setScheduling] = useState(false)
  const [scheduled, setScheduled] = useState(false)
  const [showImagePrompt, setShowImagePrompt] = useState(false)

  const handleImageChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setImageFile(file)
    const reader = new FileReader()
    reader.onload = (ev) => setImagePreview(ev.target?.result as string)
    reader.readAsDataURL(file)
  }

  const handleGenerate = async () => {
    setGenerating(true)
    setError('')
    setResult(null)
    setScheduled(false)
    setShowImagePrompt(false)

    try {
      let response: Response

      if (mode === 'image_idea' && imageFile) {
        // Multipart upload with image
        const formData = new FormData()
        formData.append('file', imageFile)
        formData.append('user_email', email)
        formData.append('platform', platform)
        if (ownerIdea) formData.append('owner_idea', ownerIdea)

        response = await fetch(
          `${API_BASE}/content/generate-from-image?user_email=${encodeURIComponent(email)}&platform=${platform}${ownerIdea ? `&owner_idea=${encodeURIComponent(ownerIdea)}` : ''}`,
          {
            method: 'POST',
            headers: { 'ngrok-skip-browser-warning': 'true' },
            body: formData,
          }
        )
      } else {
        response = await fetch(`${API_BASE}/content/generate`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'ngrok-skip-browser-warning': 'true',
          },
          body: JSON.stringify({
            user_email: email,
            platform,
            mode: mode === 'idea_only' ? 'idea' : 'surprise',
            owner_idea: ownerIdea || null,
          }),
        })
      }

      const data = await response.json()
      if (!response.ok) throw new Error(data?.detail || 'Generation failed')

      setResult(data)
      setEditedCaption(platform === 'facebook' ? data.caption_facebook : data.caption_instagram)
      setEditedHashtags(data.hashtags || [])
      setActiveTab(platform === 'facebook' ? 'facebook' : 'instagram')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Generation failed')
    } finally {
      setGenerating(false)
    }
  }

  const handleSchedule = async () => {
    if (!result) return
    setScheduling(true)
    setError('')
    try {
      const hashtagStr = editedHashtags.join(' ')
      const fullCaption = `${editedCaption}\n\n${hashtagStr}`

      const res = await fetch(`${API_BASE}/content/publish`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'ngrok-skip-browser-warning': 'true',
        },
        body: JSON.stringify({
          user_email: email,
          caption: fullCaption,
          hashtags: hashtagStr,
          media_url: result.generated_image_url || null,
          media_type: 'image',
          targets: platform === 'both' ? ['facebook', 'instagram'] : [platform],
          scheduled_at: result.suggested_schedule?.datetime || null,
        }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data?.detail || 'Scheduling failed')
      setScheduled(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Scheduling failed')
    } finally {
      setScheduling(false)
    }
  }

  const handlePostNow = async () => {
    if (!result) return
    setScheduling(true)
    setError('')
    try {
      const hashtagStr = editedHashtags.join(' ')
      const fullCaption = `${editedCaption}\n\n${hashtagStr}`
 
      const res = await fetch(`${API_BASE}/content/publish`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'ngrok-skip-browser-warning': 'true',
        },
        body: JSON.stringify({
          user_email: email,
          caption: fullCaption,
          hashtags: hashtagStr,
          media_url: result.generated_image_url || null,
          media_type: 'image',
          targets: platform === 'both' ? ['facebook', 'instagram'] : [platform],
          scheduled_at: null,   // ← null = publish immediately
        }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data?.detail || 'Publishing failed')
      setScheduled(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to publish')
    } finally {
      setScheduling(false)
    }
  }

  const removeHashtag = (tag: string) => {
    setEditedHashtags(prev => prev.filter(t => t !== tag))
  }

  const pillarEmoji: Record<string, string> = {
    food:              '🍽️',
    experience:        '✨',
    offers:            '🥂',
    behind_the_scenes: '👨‍🍳',
    // legacy keys
    signature_dish:    '🔥',
    sunday_brunch:     '🥂',
    seasonal_special:  '🌿',
    customer_love:     '❤️',
    event_announcement:'🎉',
  }

  return (
    <div className="workspace-shell">
      {/* Sidebar */}
      <aside className="workspace-sidebar">
        <div className="sidebar-header"><div className="sidebar-title">Menu</div></div>
        <Link to="/workspace" className="sidebar-item">
          <div className="avatar">WS</div><div className="sidebar-text">Workspace</div>
        </Link>
        <Link to="/inbox" className="sidebar-item">
          <div className="avatar">IN</div><div className="sidebar-text">Engagement Inbox</div>
        </Link>
        <Link to="/content-studio" className={`sidebar-item ${window.location.pathname === '/content-studio' ? 'active' : ''}`}>
          <div className="avatar">✦</div><div className="sidebar-text">Content Studio</div>
        </Link>
        <Link to="/dashboard" className="sidebar-item">
          <div className="avatar">DB</div><div className="sidebar-text">Analytics Dashboard</div>
        </Link>
        <Link to="/accounts" className="sidebar-item">
          <div className="avatar">AC</div><div className="sidebar-text">Connections</div>
        </Link>
        <div style={{ marginTop: 'auto', padding: '20px', borderTop: '1px solid var(--dark-border)' }}>
          <div style={{ paddingBottom: '12px', fontSize: '13px', color: 'var(--muted)' }}>{email}</div>
          <button
            className="ghost-dark"
            style={{ width: '100%', textAlign: 'left', color: '#ff6b6b', padding: '10px', background: 'transparent', border: 'none', cursor: 'pointer' }}
            onClick={() => { localStorage.removeItem('autosocial_email'); navigate('/login') }}>
            Log out
          </button>
        </div>
      </aside>

      {/* Main */}
      <main className="workspace-main">
        <header className="workspace-topbar">
          <div className="topbar-left">
            <div className="topbar-icon">✦</div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <div className="topbar-title">Content Studio</div>
                <div style={{ fontSize: '11px', color: '#b48aff', background: 'rgba(130,80,255,0.1)', border: '1px solid rgba(130,80,255,0.25)', borderRadius: '12px', padding: '2px 8px' }}>
                  AI Powered
                </div>
              </div>
              <div className="topbar-subtitle">Generate, schedule, and publish social media content</div>
            </div>
          </div>
        </header>

        <section className="workspace-content">
          <div style={{ display: 'flex', gap: '32px', alignItems: 'flex-start' }}>

            {/* LEFT — Input panel */}
            <div style={{ flex: '0 0 420px', display: 'flex', flexDirection: 'column', gap: '24px' }}>

              {/* Mode selector */}
              <div style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '16px', padding: '24px' }}>
                <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '16px' }}>
                  How do you want to create?
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  {[
                    { value: 'surprise',   label: '✦ Surprise me',    desc: 'AI picks the best content for today + generates image' },
                    { value: 'idea_only',  label: '💬 I have an idea', desc: 'Describe what you want — AI writes copy + generates image' },
                    { value: 'image_idea', label: '📸 I have an image', desc: 'Upload a photo, AI writes the copy' },
                  ].map(opt => (
                    <button key={opt.value}
                      onClick={() => setMode(opt.value as Mode)}
                      style={{
                        background: mode === opt.value ? 'rgba(130,80,255,0.15)' : 'rgba(255,255,255,0.03)',
                        border: mode === opt.value ? '1px solid rgba(130,80,255,0.5)' : '1px solid rgba(255,255,255,0.08)',
                        borderRadius: '10px', padding: '12px 16px',
                        textAlign: 'left', cursor: 'pointer', transition: 'all 0.2s',
                      }}>
                      <div style={{ fontSize: '14px', fontWeight: 600, color: mode === opt.value ? '#b48aff' : 'var(--text-bright)' }}>{opt.label}</div>
                      <div style={{ fontSize: '12px', color: 'var(--muted)', marginTop: '2px' }}>{opt.desc}</div>
                    </button>
                  ))}
                </div>
              </div>

              {/* Platform selector */}
              <div style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '16px', padding: '24px' }}>
                <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '16px' }}>Platform</div>
                <div style={{ display: 'flex', gap: '10px' }}>
                  {(['both', 'instagram', 'facebook'] as Platform[]).map(p => (
                    <button key={p}
                      onClick={() => setPlatform(p)}
                      style={{
                        flex: 1, padding: '10px',
                        background: platform === p ? 'rgba(130,80,255,0.15)' : 'rgba(255,255,255,0.03)',
                        border: platform === p ? '1px solid rgba(130,80,255,0.5)' : '1px solid rgba(255,255,255,0.08)',
                        borderRadius: '8px', cursor: 'pointer', fontSize: '13px',
                        color: platform === p ? '#b48aff' : 'var(--text-bright)',
                        fontWeight: platform === p ? 600 : 400,
                        transition: 'all 0.2s',
                      }}>
                      {p === 'both' ? '🌐 Both' : p === 'instagram' ? '📷 Instagram' : '👤 Facebook'}
                    </button>
                  ))}
                </div>
              </div>

              {/* Idea input */}
              {(mode === 'idea_only' || mode === 'image_idea') && (
                <div style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '16px', padding: '24px' }}>
                  <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '12px' }}>
                    {mode === 'image_idea' ? 'Add context (optional)' : 'Your idea'}
                  </div>
                  <textarea className="form-input"
                    placeholder={mode === 'image_idea'
                      ? "e.g. 'Highlight the lamb chops' or 'Weekend vibes'"
                      : "e.g. 'Post about Sunday Brunch this weekend' or 'Feature the new pizza'"}
                    style={{ minHeight: '90px', background: 'var(--bg-card)' }}
                    value={ownerIdea}
                    onChange={e => setOwnerIdea(e.target.value)}
                  />
                </div>
              )}

              {/* Image upload */}
              {mode === 'image_idea' && (
                <div style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '16px', padding: '24px' }}>
                  <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '12px' }}>Upload Image</div>
                  {imagePreview ? (
                    <div style={{ position: 'relative' }}>
                      <img src={imagePreview} alt="preview" style={{ width: '100%', borderRadius: '10px', maxHeight: '200px', objectFit: 'cover' }} />
                      <button onClick={() => { setImageFile(null); setImagePreview(null) }}
                        style={{ position: 'absolute', top: '8px', right: '8px', background: 'rgba(0,0,0,0.7)', border: 'none', color: '#fff', borderRadius: '50%', width: '28px', height: '28px', cursor: 'pointer', fontSize: '14px' }}>
                        ×
                      </button>
                    </div>
                  ) : (
                    <label style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px', padding: '32px', border: '2px dashed rgba(255,255,255,0.15)', borderRadius: '10px', cursor: 'pointer' }}>
                      <span style={{ fontSize: '32px' }}>📸</span>
                      <span style={{ fontSize: '13px', color: 'var(--muted)' }}>Click to upload or drag & drop</span>
                      <input type="file" accept="image/*" style={{ display: 'none' }} onChange={handleImageChange} />
                    </label>
                  )}
                </div>
              )}

              {/* Generate button */}
              <button
                className="btn-primary"
                style={{ width: '100%', padding: '16px', fontSize: '15px', fontWeight: 600, borderRadius: '12px', opacity: generating ? 0.7 : 1 }}
                disabled={generating || (mode === 'image_idea' && !imageFile && !ownerIdea)}
                onClick={handleGenerate}>
                {generating ? (
                  <span style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}>
                    <span style={{ animation: 'spin 1s linear infinite', display: 'inline-block' }}>⟳</span>
                    Generating...
                  </span>
                ) : '✦ Generate Content'}
              </button>

              {error && (
                <div className="form-message error">{error}</div>
              )}
            </div>

            {/* RIGHT — Output panel */}
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '24px' }}>
              {!result && !generating && (
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '400px', color: 'var(--muted)', gap: '16px' }}>
                  <div style={{ fontSize: '48px', opacity: 0.3 }}>✦</div>
                  <div style={{ fontSize: '16px' }}>Your generated content will appear here</div>
                  <div style={{ fontSize: '13px', opacity: 0.6 }}>Choose a mode and click Generate</div>
                </div>
              )}

              {generating && (
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '400px', gap: '16px' }}>
                  <div style={{ fontSize: '40px', animation: 'pulse 1.5s infinite' }}>✦</div>
                  <div style={{ fontSize: '15px', color: 'var(--text-bright)' }}>Ember is crafting your content...</div>
                  <div style={{ fontSize: '13px', color: 'var(--muted)' }}>
                    {mode === 'image_idea'
                      ? 'Analysing image → Writing captions → Picking hashtags'
                      : 'Fetching menu data → Writing captions → Generating image → Picking hashtags'}
                  </div>
                </div>
              )}

              {result && !generating && (
                <>
                  {/* Content theme badge */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <span style={{ fontSize: '20px' }}>{pillarEmoji[result.chosen_pillar || result.content_pillar] || '✨'}</span>
                    <div>
                      <div style={{ fontSize: '16px', fontWeight: 600, color: 'var(--text-bright)' }}>
                        {result.content_theme || result.content_pillar_label}
                      </div>
                      <div style={{ fontSize: '12px', color: '#b48aff' }}>
                        {(result.chosen_pillar || result.content_pillar || '').replace(/_/g, ' ')}
                        {result.image_description && ' · Vision analyzed'}
                        {result.generated_image_url && ' · Image generated'}
                      </div>
                    </div>
                    <button
                      className="btn-secondary"
                      style={{ marginLeft: 'auto', fontSize: '12px', padding: '6px 12px' }}
                      onClick={handleGenerate}>
                      ⟳ Regenerate
                    </button>
                  </div>

                  {/* ── Generated image ── */}
                  {result.generated_image_url && (
                    <div style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '16px', overflow: 'hidden' }}>
                      <img
                        src={result.generated_image_url}
                        alt="AI generated post image"
                        style={{ width: '100%', display: 'block', maxHeight: '400px', objectFit: 'cover' }}
                      />
                      <div style={{ padding: '12px 16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                        <span style={{ fontSize: '12px', color: 'var(--muted)' }}>
                          ✦ AI-generated image · Will be attached when you schedule
                        </span>
                        {result.image_prompt && (
                          <button
                            onClick={() => setShowImagePrompt(p => !p)}
                            style={{ fontSize: '11px', color: '#b48aff', background: 'none', border: 'none', cursor: 'pointer', padding: '0' }}>
                            {showImagePrompt ? 'Hide prompt' : 'View prompt'}
                          </button>
                        )}
                      </div>
                      {showImagePrompt && result.image_prompt && (
                        <div style={{ padding: '0 16px 16px' }}>
                          <div style={{
                            background: 'rgba(0,0,0,0.3)', border: '1px solid rgba(255,255,255,0.06)',
                            borderRadius: '8px', padding: '12px', fontSize: '12px',
                            color: 'var(--muted)', lineHeight: '1.6', fontStyle: 'italic'
                          }}>
                            {result.image_prompt}
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* User-provided image (image_idea mode) */}
                  {mode === 'image_idea' && imagePreview && !result.generated_image_url && (
                    <div style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '16px', overflow: 'hidden' }}>
                      <img
                        src={imagePreview}
                        alt="Your uploaded image"
                        style={{ width: '100%', display: 'block', maxHeight: '300px', objectFit: 'cover' }}
                      />
                      <div style={{ padding: '10px 16px', fontSize: '12px', color: 'var(--muted)' }}>
                        📸 Your uploaded image
                      </div>
                    </div>
                  )}

                  {/* Caption editor with platform tabs */}
                  <div style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '16px', overflow: 'hidden' }}>
                    <div style={{ display: 'flex', borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
                      {(['instagram', 'facebook'] as const).map(tab => (
                        <button key={tab}
                          onClick={() => {
                            setActiveTab(tab)
                            setEditedCaption(tab === 'instagram' ? result.caption_instagram : result.caption_facebook)
                          }}
                          style={{
                            flex: 1, padding: '12px',
                            background: activeTab === tab ? 'rgba(130,80,255,0.1)' : 'transparent',
                            border: 'none',
                            borderBottom: activeTab === tab ? '2px solid #b48aff' : '2px solid transparent',
                            color: activeTab === tab ? '#b48aff' : 'var(--muted)',
                            cursor: 'pointer', fontSize: '13px', fontWeight: activeTab === tab ? 600 : 400,
                          }}>
                          {tab === 'instagram' ? '📷 Instagram' : '👤 Facebook'}
                        </button>
                      ))}
                    </div>
                    <div style={{ padding: '20px' }}>
                      <div style={{ fontSize: '11px', color: '#b48aff', marginBottom: '8px' }}>✦ AI generated — edit freely</div>
                      <textarea
                        className="form-input"
                        style={{ minHeight: '160px', background: 'var(--bg-card)', fontSize: '14px', lineHeight: '1.6' }}
                        value={editedCaption}
                        onChange={e => setEditedCaption(e.target.value)}
                      />
                    </div>
                  </div>

                  {/* Hashtags */}
                  <div style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '16px', padding: '20px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', marginBottom: '14px' }}>
                      <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-bright)' }}>Hashtags</div>
                      <span style={{ marginLeft: '8px', fontSize: '12px', color: 'var(--muted)' }}>{editedHashtags.length} tags</span>
                    </div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                      {editedHashtags.map(tag => (
                        <span key={tag} style={{
                          background: 'rgba(130,80,255,0.1)', border: '1px solid rgba(130,80,255,0.25)',
                          borderRadius: '20px', padding: '4px 12px', fontSize: '12px', color: '#b48aff',
                          display: 'flex', alignItems: 'center', gap: '6px',
                        }}>
                          {tag}
                          <button onClick={() => removeHashtag(tag)}
                            style={{ background: 'none', border: 'none', color: '#b48aff', cursor: 'pointer', padding: '0', fontSize: '14px', lineHeight: 1 }}>
                            ×
                          </button>
                        </span>
                      ))}
                    </div>
                  </div>

                  {/* Schedule suggestion */}
                  {result.suggested_schedule?.datetime_str && (
                    <div style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '16px', padding: '20px' }}>
                      <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-bright)', marginBottom: '8px' }}>
                        🕐 Suggested posting time
                      </div>
                      <div style={{ fontSize: '18px', fontWeight: 700, color: '#b48aff', marginBottom: '6px' }}>
                        {result.suggested_schedule.datetime_str}
                      </div>
                      <div style={{ fontSize: '13px', color: 'var(--muted)' }}>
                        {result.suggested_schedule.reason}
                      </div>
                    </div>
                  )}

                  {/* Action buttons */}
                  {scheduled ? (
                    <div className="form-message success" style={{ padding: '16px', borderRadius: '12px', textAlign: 'center', fontSize: '15px' }}>
                      ✅ Post scheduled successfully!
                    </div>
                  ) : (
                    // <div style={{ display: 'flex', gap: '12px' }}>
                    //   <button
                    //     className="btn-secondary"
                    //     style={{ flex: 1, padding: '14px' }}
                    //     onClick={() => setResult(null)}>
                    //     Discard
                    //   </button>
                    //   <button
                    //     className="btn-primary"
                    //     style={{ flex: 2, padding: '14px', fontSize: '15px', fontWeight: 600 }}
                    //     disabled={scheduling}
                    //     onClick={handleSchedule}>
                    //     {scheduling ? 'Scheduling...' : `📅 Schedule Post`}
                    //   </button>
                    // </div>
                    <div style={{ display: 'flex', gap: '12px' }}>
                      <button
                        className="btn-secondary"
                        style={{ flex: 1, padding: '14px' }}
                        onClick={() => setResult(null)}>
                        Discard
                      </button>
                      <button
                        className="btn-secondary"
                        style={{ flex: 1, padding: '14px', fontSize: '14px', fontWeight: 600 }}
                        disabled={scheduling}
                        onClick={handleSchedule}>
                        {scheduling ? 'Scheduling...' : '📅 Schedule'}
                      </button>
                      <button
                        className="btn-primary"
                        style={{ flex: 1, padding: '14px', fontSize: '14px', fontWeight: 600 }}
                        disabled={scheduling}
                        onClick={handlePostNow}>
                        {scheduling ? 'Posting...' : '🚀 Post Now'}
                      </button>
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        </section>
      </main>
    </div>
  )
}

export default ContentStudio