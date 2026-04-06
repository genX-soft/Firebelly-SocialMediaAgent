import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'

const PERMISSIONS = [
  {
    id: 'business_asset_user_profile_access',
    label: 'Business Asset User Profile Access',
    description: 'Access basic profile info of users who interact with your business assets.',
  },
  {
    id: 'business_management',
    label: 'business_management',
    description: 'Manage your business and access business-related data on Facebook.',
  },
  {
    id: 'pages_user_gender',
    label: 'pages_user_gender',
    description: 'Access the gender of users who interact with your Page.',
  },
  {
    id: 'page_public_content_access',
    label: 'Page Public Content Access',
    description: 'Read public posts, photos, and videos from any Facebook Page.',
  },
  {
    id: 'instagram_public_content_access',
    label: 'Instagram Public Content Access',
    description: 'Read public Instagram content including posts, reels, and profile info.',
  },
  {
    id: 'page_mentions',
    label: 'Page Mentions',
    description: 'Receive notifications when your Page is mentioned in posts or comments.',
  },
  {
    id: 'instagram_manage_contents',
    label: 'instagram_manage_contents',
    description: 'Create, manage, and delete Instagram posts and stories.',
  },
  {
    id: 'pages_read_user_content',
    label: 'pages_read_user_content',
    description: 'Read user-generated content such as posts and comments on your Page.',
  },
  {
    id: 'instagram_manage_insights',
    label: 'instagram_manage_insights',
    description: 'Access analytics and performance metrics for your Instagram account.',
  },
  {
    id: 'pages_manage_posts',
    label: 'pages_manage_posts',
    description: 'Create, edit, and delete posts on your Facebook Pages.',
  },
  {
    id: 'instagram_content_publish',
    label: 'instagram_content_publish',
    description: 'Publish photos, videos, reels, and stories to Instagram.',
  },
  {
    id: 'instagram_basic',
    label: 'instagram_basic',
    description: 'Read basic Instagram profile information and media.',
  },
  {
    id: 'pages_read_engagement',
    label: 'pages_read_engagement',
    description: 'Read engagement data such as likes, comments, and shares on Page posts.',
  },
  {
    id: 'instagram_business_manage_messages',
    label: 'instagram_business_manage_messages',
    description: 'Send and receive direct messages for Instagram Business accounts.',
  },
  {
    id: 'instagram_manage_comments',
    label: 'instagram_manage_comments',
    description: 'Read, reply to, hide, and delete comments on Instagram posts.',
  },
  {
    id: 'pages_manage_metadata',
    label: 'pages_manage_metadata',
    description: 'Update Page settings, cover photos, and other metadata.',
  },
  {
    id: 'pages_messaging',
    label: 'pages_messaging',
    description: 'Send and receive messages through your Facebook Page inbox.',
  },
  {
    id: 'pages_show_list',
    label: 'pages_show_list',
    description: 'View the list of Facebook Pages you manage.',
  },
  {
    id: 'instagram_manage_messages',
    label: 'instagram_manage_messages',
    description: 'Manage Instagram direct messages including reading and sending.',
  },
  {
    id: 'instagram_business_basic',
    label: 'instagram_business_basic',
    description: 'Access basic info for Instagram Business and Creator accounts.',
  },
]

function PermissionsConsent() {
  const navigate = useNavigate()
  const [checked, setChecked] = useState<Record<string, boolean>>(
    Object.fromEntries(PERMISSIONS.map(p => [p.id, false]))
  )

  useEffect(() => {
    // If user is not logged in, send them back
    const email = localStorage.getItem('autosocial_email')
    if (!email) navigate('/signup')
  }, [navigate])

  const allChecked = Object.values(checked).every(Boolean)
  const checkedCount = Object.values(checked).filter(Boolean).length

  const toggleAll = () => {
    const newVal = !allChecked
    setChecked(Object.fromEntries(PERMISSIONS.map(p => [p.id, newVal])))
  }

  const toggle = (id: string) => {
    setChecked(prev => ({ ...prev, [id]: !prev[id] }))
  }

  const handleContinue = () => {
    navigate('/workspace')
  }

  return (
    <div style={{
      minHeight: '100vh',
      background: 'var(--bg-base)',
      display: 'flex',
      alignItems: 'flex-start',
      justifyContent: 'center',
      padding: '40px 16px',
    }}>
      <div style={{ width: '100%', maxWidth: '680px' }}>

        {/* Header */}
        <div style={{ textAlign: 'center', marginBottom: '36px' }}>
          <div style={{
            display: 'inline-flex', alignItems: 'center', gap: '10px',
            marginBottom: '20px',
          }}>
            <div style={{
              width: '40px', height: '40px', borderRadius: '10px',
              background: 'var(--primary)', display: 'flex', alignItems: 'center',
              justifyContent: 'center', fontWeight: 700, fontSize: '16px', color: '#fff',
            }}>AS</div>
            <span style={{ fontSize: '20px', fontWeight: 700, color: 'var(--text-bright)' }}>AutoSocial</span>
          </div>
          <h1 style={{ fontSize: '26px', fontWeight: 700, color: 'var(--text-bright)', marginBottom: '10px' }}>
            Permissions Required
          </h1>
          <p style={{ fontSize: '15px', color: 'var(--muted)', maxWidth: '480px', margin: '0 auto', lineHeight: 1.6 }}>
            AutoSocial needs the following Meta permissions to manage your Facebook and Instagram accounts.
            Please review and acknowledge each permission before continuing.
          </p>
        </div>

        {/* Card */}
        <div style={{
          background: 'var(--bg-card)',
          border: '1px solid var(--dark-border)',
          borderRadius: '16px',
          overflow: 'hidden',
        }}>
          {/* Select all bar */}
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '16px 24px',
            borderBottom: '1px solid var(--dark-border)',
            background: 'rgba(255,255,255,0.02)',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <input
                type="checkbox"
                id="select-all"
                checked={allChecked}
                onChange={toggleAll}
                style={{ width: '16px', height: '16px', cursor: 'pointer', accentColor: 'var(--primary)' }}
              />
              <label htmlFor="select-all" style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-bright)', cursor: 'pointer' }}>
                Select all permissions
              </label>
            </div>
            <span style={{
              fontSize: '12px', color: 'var(--muted)',
              background: 'rgba(255,255,255,0.06)',
              padding: '4px 10px', borderRadius: '20px',
            }}>
              {checkedCount} / {PERMISSIONS.length} selected
            </span>
          </div>

          {/* Permission list */}
          <div style={{ maxHeight: '480px', overflowY: 'auto', padding: '8px 0' }}>
            {PERMISSIONS.map((perm, idx) => (
              <label
                key={perm.id}
                htmlFor={perm.id}
                style={{
                  display: 'flex', alignItems: 'flex-start', gap: '14px',
                  padding: '14px 24px',
                  cursor: 'pointer',
                  borderBottom: idx < PERMISSIONS.length - 1 ? '1px solid rgba(255,255,255,0.04)' : 'none',
                  background: checked[perm.id] ? 'rgba(99,102,241,0.05)' : 'transparent',
                  transition: 'background 0.15s',
                }}
              >
                <input
                  type="checkbox"
                  id={perm.id}
                  checked={checked[perm.id]}
                  onChange={() => toggle(perm.id)}
                  style={{ marginTop: '3px', width: '16px', height: '16px', flexShrink: 0, cursor: 'pointer', accentColor: 'var(--primary)' }}
                />
                <div>
                  <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-bright)', marginBottom: '3px', fontFamily: 'monospace' }}>
                    {perm.label}
                  </div>
                  <div style={{ fontSize: '13px', color: 'var(--muted)', lineHeight: 1.5 }}>
                    {perm.description}
                  </div>
                </div>
                {checked[perm.id] && (
                  <span style={{ marginLeft: 'auto', color: '#22c55e', fontSize: '16px', flexShrink: 0 }}>✓</span>
                )}
              </label>
            ))}
          </div>

          {/* Footer */}
          <div style={{
            padding: '20px 24px',
            borderTop: '1px solid var(--dark-border)',
            background: 'rgba(255,255,255,0.02)',
          }}>
            {!allChecked && (
              <div style={{
                fontSize: '13px', color: '#f59e0b',
                marginBottom: '14px',
                display: 'flex', alignItems: 'center', gap: '6px',
              }}>
                <span>⚠️</span>
                <span>Please acknowledge all {PERMISSIONS.length} permissions to continue.</span>
              </div>
            )}
            <button
              onClick={handleContinue}
              disabled={!allChecked}
              style={{
                width: '100%', padding: '14px', fontSize: '15px', fontWeight: 600,
                borderRadius: '10px', border: 'none', cursor: allChecked ? 'pointer' : 'not-allowed',
                background: allChecked ? 'var(--primary)' : 'rgba(255,255,255,0.08)',
                color: allChecked ? '#fff' : 'var(--muted)',
                transition: 'all 0.2s',
              }}
            >
              {allChecked ? '✓ Continue to Workspace' : `Acknowledge all permissions to continue (${checkedCount}/${PERMISSIONS.length})`}
            </button>
          </div>
        </div>

        <p style={{ textAlign: 'center', fontSize: '12px', color: 'var(--muted)', marginTop: '20px', lineHeight: 1.6 }}>
          These permissions are required by Meta's platform policy for apps that manage Facebook Pages and Instagram Business accounts.
          AutoSocial will only use these permissions to provide the features you use.
        </p>

      </div>
    </div>
  )
}

export default PermissionsConsent