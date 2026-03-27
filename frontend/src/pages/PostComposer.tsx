import { useCallback, useEffect, useMemo, useRef, useState, type DragEvent, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

type PostTarget = 'facebook' | 'instagram'

type PostResponse = {
  id: string
  caption: string
  media_url?: string | null
  media_type: string
  hashtags?: string | null
  emojis?: string | null
  targets: string[]
  status: string
  error_message?: string | null
}

function PostComposer() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const editId = searchParams.get('edit')

  const storedEmail = useMemo(() => localStorage.getItem('autosocial_email') ?? '', [])
  const [email] = useState(storedEmail)

  useEffect(() => {
    if (!storedEmail) {
      navigate('/login')
    }
  }, [storedEmail, navigate])
  const [caption, setCaption] = useState('')
  const [hashtags, setHashtags] = useState('')
  const [emojis, setEmojis] = useState('')
  const [mediaUrl, setMediaUrl] = useState('')
  const [mediaType, setMediaType] = useState<'image' | 'video'>('image')
  const [targets, setTargets] = useState<PostTarget[]>(['facebook'])
  const [status, setStatus] = useState<'idle' | 'loading' | 'error' | 'success'>('idle')
  const [message, setMessage] = useState('')
  const [backendError, setBackendError] = useState('')
  const [isScheduled, setIsScheduled] = useState(false)
  const [scheduledDate, setScheduledDate] = useState('')
  const [scheduledTime, setScheduledTime] = useState('')


  // Diagnostics
  const isLocalMedia = useMemo(() => {
    return mediaUrl.includes('localhost') || mediaUrl.includes('127.0.0.1')
  }, [mediaUrl])

  const instagramMediaWarning = useMemo(() => {
    return targets.includes('instagram') && !mediaUrl
  }, [targets, mediaUrl])

  // Drag and drop state
  const [isDragging, setIsDragging] = useState(false)
  const [uploadStatus, setUploadStatus] = useState<'idle' | 'uploading' | 'done' | 'error'>('idle')
  const [uploadedFileName, setUploadedFileName] = useState('')
  const [previewSrc, setPreviewSrc] = useState('')
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Fetch post if editing
  useEffect(() => {
    if (editId) {
      const fetchPost = async () => {
        setStatus('loading')
        try {
          const res = await fetch(`${API_BASE}/posts/${editId}`, {
            headers: { 'ngrok-skip-browser-warning': 'true' }
          })
          if (!res.ok) throw new Error('Failed to load post')
          const post: PostResponse = await res.json()
          
          setCaption(post.caption)
          setHashtags(post.hashtags || '')
          setEmojis(post.emojis || '')
          setMediaUrl(post.media_url || '')
          setMediaType(post.media_type as 'image' | 'video')
          setTargets(post.targets as PostTarget[])
          setBackendError(post.error_message || '')
          
          if (post.media_url) {
            setPreviewSrc(post.media_url)
            setUploadStatus('done')
          }
          setStatus('idle')
        } catch (err) {
          setStatus('error')
          setMessage(err instanceof Error ? err.message : 'Error loading post')
        }
      }
      fetchPost()
    }
  }, [editId])

  const toggleTarget = (target: PostTarget) => {
    setTargets((prev) =>
      prev.includes(target) ? prev.filter((item) => item !== target) : [...prev, target]
    )
  }

  const uploadFile = async (file: File) => {
    setUploadStatus('uploading')
    setUploadedFileName(file.name)
    setPreviewSrc('')

    // Show local preview immediately
    const reader = new FileReader()
    reader.onload = (e) => setPreviewSrc(e.target?.result as string)
    reader.readAsDataURL(file)

    // Detect media type from file
    if (file.type.startsWith('video/')) setMediaType('video')
    else setMediaType('image')

    try {
      const formData = new FormData()
      formData.append('file', file)
      const res = await fetch(`${API_BASE}/upload`, { 
        method: 'POST', 
        headers: { 'ngrok-skip-browser-warning': 'true' },
        body: formData 
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data?.detail || 'Upload failed')
      setMediaUrl(data.url)
      setUploadStatus('done')
    } catch {
      setUploadStatus('error')
      setUploadedFileName('')
    }
  }

  const handleDrop = useCallback(
    (e: DragEvent<HTMLDivElement>) => {
      e.preventDefault()
      setIsDragging(false)
      const file = e.dataTransfer.files[0]
      if (file) uploadFile(file)
    },
    []
  )

  const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setIsDragging(true)
  }

  const handleDragLeave = () => setIsDragging(false)

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) uploadFile(file)
  }

  const clearMedia = () => {
    setMediaUrl('')
    setPreviewSrc('')
    setUploadedFileName('')
    setUploadStatus('idle')
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const buildPayload = () => ({
    user_email: email,
    caption: caption.trim(),
    media_url: mediaUrl.trim() || null,
    media_type: mediaType,
    hashtags: hashtags.trim() || null,
    emojis: emojis.trim() || null,
    targets,
    scheduled_at: (isScheduled && scheduledDate && scheduledTime) ? new Date(`${scheduledDate}T${scheduledTime}`).toISOString() : null,
  })

  const saveDraft = async () => {
    setStatus('loading')
    setMessage('')
    try {
      const url = editId ? `${API_BASE}/posts/${editId}` : `${API_BASE}/posts`
      const method = editId ? 'PUT' : 'POST'
      
      const response = await fetch(url, {
        method,
        headers: { 
          'Content-Type': 'application/json',
          'ngrok-skip-browser-warning': 'true'
        },
        body: JSON.stringify(buildPayload()),
      })
      const data = await response.json()
      if (!response.ok) throw new Error(data?.detail || 'Failed to save post')
      setStatus('success')
      setMessage(editId ? 'Post updated.' : `Draft saved (${data.status}).`)
      
      if (!editId) {
        setCaption('')
        setHashtags('')
        setEmojis('')
        setMediaUrl('')
        setPreviewSrc('')
        setUploadStatus('idle')
      }
    } catch (error) {
      setStatus('error')
      setMessage(error instanceof Error ? error.message : 'Failed to save post')
    }
  }

  const publishNow = async () => {
    setStatus('loading')
    setMessage('')
    try {
      // If editing an existing post, we use the PUT endpoint first to save changes,
      // then either the backend handles publishing or we call /publish.
      // Easiest is to save changes via PUT then call the publish-by-id endpoint.
      if (editId) {
        const updateRes = await fetch(`${API_BASE}/posts/${editId}`, {
          method: 'PUT',
          headers: { 
            'Content-Type': 'application/json',
            'ngrok-skip-browser-warning': 'true'
          },
          body: JSON.stringify(buildPayload()),
        })
        if (!updateRes.ok) throw new Error('Failed to update post before publishing')
        
        const pubRes = await fetch(`${API_BASE}/posts/${editId}/publish`, { 
          method: 'POST',
          headers: { 'ngrok-skip-browser-warning': 'true' }
        })
        const data = await pubRes.json()
        if (!pubRes.ok) throw new Error(data?.detail || 'Failed to publish post')
        
        setStatus('success')
        setMessage(`Post published (${data.status}).`)
      } else {
        console.log("DEBUG: Publishing to", `${API_BASE}/posts/publish`);
        const payload = buildPayload();
        console.log("DEBUG: Payload:", payload);
        const response = await fetch(`${API_BASE}/posts/publish`, {
          method: 'POST',
          headers: { 
            'Content-Type': 'application/json',
            'ngrok-skip-browser-warning': 'true'
          },
          body: JSON.stringify(payload),
        })
        const data = await response.json()
        if (!response.ok) throw new Error(data?.detail || 'Failed to publish post')
        setStatus('success')
        setMessage(`Post published (${data.status}).`)
        setCaption('')
        setHashtags('')
        setEmojis('')
        setMediaUrl('')
        setPreviewSrc('')
        setUploadStatus('idle')
      }
    } catch (error) {
      setStatus('error')
      setMessage(error instanceof Error ? error.message : 'Failed to publish post')
    }
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    await saveDraft()
  }

  const previewCaption = [caption, emojis, hashtags].filter(Boolean).join(' ')

  return (
    <div className="workspace-light">
      <header className="workspace-header">
        <div>
          <div className="workspace-title">{editId ? 'Edit Post' : 'Post Composer'}</div>
          <p>Create and preview posts before publishing to Facebook and Instagram.</p>
        </div>
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          <div style={{ fontSize: '13px', color: 'var(--muted)' }}>{email}</div>
          <Link className="btn-secondary" to="/workspace">Cancel</Link>
          <button 
            className="btn-secondary" 
            style={{ color: '#ff6b6b', borderColor: 'rgba(255, 107, 107, 0.2)' }}
            onClick={() => {
              localStorage.removeItem('autosocial_email')
              navigate('/login')
            }}
          >
            Logout
          </button>
        </div>
      </header>

      <section className="composer-grid">
        <div className="composer-card">
          <form onSubmit={handleSubmit}>
          {/* Manual email hidden - uses session email automatically */}
          <div style={{ display: 'none' }}>
            <label className="field">
              <span>User email</span>
              <input
                type="email"
                value={email}
                readOnly
                placeholder="you@company.com"
                required
              />
            </label>
          </div>

          <label className="field">
            <span>Caption</span>
            <textarea
              value={caption}
              onChange={(event) => setCaption(event.target.value)}
              placeholder="Write your post caption..."
              rows={4}
            />
          </label>

          <label className="field">
            <span>Hashtags</span>
            <input
              type="text"
              value={hashtags}
              onChange={(event) => setHashtags(event.target.value)}
              placeholder="#social #autosocial"
            />
          </label>

          <label className="field">
            <span>Emojis</span>
            <input
              type="text"
              value={emojis}
              onChange={(event) => setEmojis(event.target.value)}
              placeholder="✨ 🚀"
            />
          </label>

          <label className="field">
            <span>Media type</span>
            <select value={mediaType} onChange={(event) => setMediaType(event.target.value as 'image' | 'video')}>
              <option value="image">Image</option>
              <option value="video">Video</option>
            </select>
          </label>

          {/* Drag & Drop Upload Zone */}
          <div className="field">
            <span>Media</span>
            <div
              className={`dropzone${isDragging ? ' dropzone--active' : ''}${uploadStatus === 'done' ? ' dropzone--done' : ''}`}
              onDrop={handleDrop}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onClick={() => fileInputRef.current?.click()}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') fileInputRef.current?.click() }}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*,video/*"
                style={{ display: 'none' }}
                onChange={handleFileInput}
              />

              {uploadStatus === 'idle' && (
                <div className="dropzone-prompt">
                  <div className="dropzone-icon">📁</div>
                  <div className="dropzone-text">
                    <strong>Drop a file here</strong> or <span className="text-link">browse</span>
                  </div>
                  <button type="button" className="btn-secondary" style={{ marginTop: '12px' }}>
                    Choose File
                  </button>
                  <div className="dropzone-hint" style={{ marginTop: '8px' }}>Supports images and videos</div>
                </div>
              )}

              {uploadStatus === 'uploading' && (
                <div className="dropzone-prompt">
                  <div className="dropzone-spinner" />
                  <div className="dropzone-text">Uploading <strong>{uploadedFileName}</strong>…</div>
                </div>
              )}

              {uploadStatus === 'done' && previewSrc && (
                <div className="dropzone-preview">
                  {mediaType === 'image' ? (
                    <img src={previewSrc} alt="Preview" className="dropzone-preview-img" />
                  ) : (
                    <video src={previewSrc} className="dropzone-preview-img" muted />
                  )}
                  <div className="dropzone-preview-info">
                    <span>{uploadedFileName}</span>
                    <button
                      type="button"
                      className="dropzone-clear"
                      onClick={(e) => { e.stopPropagation(); clearMedia() }}
                    >
                      ✕ Remove
                    </button>
                  </div>
                </div>
              )}

              {uploadStatus === 'error' && (
                <div className="dropzone-prompt">
                  <div className="dropzone-icon">⚠️</div>
                  <div className="dropzone-text">Upload failed. <span className="text-link">Try again</span></div>
                </div>
              )}
            </div>

            {uploadStatus === 'done' && (
              <div style={{ marginTop: '8px', fontSize: '12px', color: '#888', display: 'flex', gap: '8px', alignItems: 'center' }}>
                <span style={{ color: '#4caf50' }}>✓ Media uploaded successfully</span>
                <span className="text-link" onClick={clearMedia} style={{ cursor: 'pointer', borderBottom: '1px dashed' }}>Replace file</span>
              </div>
            )}
          </div>

          <div className="target-row">
            <span>Publish to</span>
            <label className="checkbox">
              <input
                type="checkbox"
                checked={targets.includes('facebook')}
                onChange={() => toggleTarget('facebook')}
              />
              <span>Facebook Page</span>
            </label>
            <label className="checkbox">
              <input
                type="checkbox"
                checked={targets.includes('instagram')}
                onChange={() => toggleTarget('instagram')}
              />
              <span>Instagram Business</span>
            </label>
          </div>
          <div className="target-row" style={{ marginTop: '16px', borderTop: '1px solid var(--border)', paddingTop: '16px', marginBottom: '16px' }}>
            <label className="checkbox" style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={isScheduled}
                onChange={(e) => setIsScheduled(e.target.checked)}
              />
              <span style={{ fontWeight: 600 }}>Schedule for later</span>
            </label>
            
            {isScheduled && (
              <div style={{ display: 'flex', gap: '8px', marginLeft: '12px' }}>
                <input
                  type="date"
                  value={scheduledDate}
                  onChange={(e) => setScheduledDate(e.target.value)}
                  style={{ 
                    backgroundColor: 'rgba(255, 255, 255, 0.05)',
                    border: '1px solid rgba(255, 255, 255, 0.1)',
                    color: 'white',
                    padding: '6px 12px',
                    borderRadius: '6px',
                    fontSize: '13px'
                  }}
                  min={new Date().toISOString().split('T')[0]}
                />
                <input
                  type="time"
                  value={scheduledTime}
                  onChange={(e) => setScheduledTime(e.target.value)}
                  style={{ 
                    backgroundColor: 'rgba(255, 255, 255, 0.05)',
                    border: '1px solid rgba(255, 255, 255, 0.1)',
                    color: 'white',
                    padding: '6px 12px',
                    borderRadius: '6px',
                    fontSize: '13px'
                  }}
                />
              </div>
            )}
          </div>

          <div className="composer-actions">
            {backendError && (
              <div className="status-message error" style={{ width: '100%', marginBottom: '1rem', whiteSpace: 'pre-wrap' }}>
                <strong>Last Error:</strong> {backendError}
              </div>
            )}

            {isLocalMedia && (
              <div className="status-message warning" style={{ width: '100%', marginBottom: '1rem' }}>
                ⚠️ <strong>Media is Local:</strong> <code>localhost</code> URLs won't work on real Facebook/Instagram. 
                Use <strong>ngrok</strong> to get a public URL and set <code>API_BASE_URL</code> in your <code>.env</code>.
              </div>
            )}

            {instagramMediaWarning && (
              <div className="status-message error" style={{ width: '100%', marginBottom: '1rem' }}>
                ❌ <strong>Instagram Error:</strong> You must attach media to post on Instagram.
              </div>
            )}

            <button className="btn-secondary" type="submit" disabled={status === 'loading'}>
              Save Draft
            </button>
            <button className="btn-primary" type="button" onClick={publishNow} disabled={status === 'loading' || (isScheduled && (!scheduledDate || !scheduledTime))}>
              {status === 'loading' ? 'Processing…' : isScheduled ? 'Schedule Post' : 'Publish Now'}
            </button>
          </div>

          {message && <div className={`form-message ${status}`}>{message}</div>}
        </form>
      </div>

      <div className="composer-card">
          <h3>Preview</h3>
          <div className="preview-card">
            {previewSrc ? (
              <div className="preview-media" style={{ padding: 0, overflow: 'hidden' }}>
                {mediaType === 'image' ? (
                  <img src={previewSrc} alt="Preview" style={{ width: '100%', height: '100%', objectFit: 'cover', borderRadius: '14px' }} />
                ) : (
                  <video src={previewSrc} style={{ width: '100%', height: '100%', objectFit: 'cover', borderRadius: '14px' }} muted controls />
                )}
              </div>
            ) : mediaUrl ? (
              <div className="preview-media">
                {mediaType === 'image' ? (
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px' }}>
                    <span style={{ fontSize: '2rem' }}>🖼️</span>
                    <span>Image Ready</span>
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px' }}>
                    <span style={{ fontSize: '2rem' }}>🎬</span>
                    <span>Video Ready</span>
                  </div>
                )}
              </div>
            ) : (
              <div className="preview-media empty">No media</div>
            )}
            <p>{previewCaption || 'Your caption will appear here.'}</p>
          </div>

          <div className="preview-grid">
            <div className="preview-card small">
              <div className="preview-title">Facebook</div>
              <p>{previewCaption || 'Caption preview'}</p>
            </div>
            <div className="preview-card small">
              <div className="preview-title">Instagram</div>
              <p>{previewCaption || 'Caption preview'}</p>
            </div>
          </div>
        </div>
      </section>
    </div>
  )
}

export default PostComposer
