import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

type AuthShellProps = {
  title: string
  subtitle: string
  mode: 'login' | 'signup'
  children: ReactNode
}

function AuthShell({ title, subtitle, mode, children }: AuthShellProps) {
  const isLogin = mode === 'login'

  return (
    <div className="auth-page">
      <aside className="auth-aside">
        <header className="auth-brand">
          <div className="brand-mark">AS</div>
          <div>
            <div className="brand-title">AutoSocial</div>
            <div className="brand-subtitle">Automation for Facebook and Instagram</div>
          </div>
        </header>

        <div className="aside-content">
          <h1 className="aside-title">{title}</h1>
          <p className="aside-subtitle">{subtitle}</p>

          <div className="aside-cards">
            <div className="promo-card">
              <div className="promo-heading">Weekly momentum</div>
              <p className="promo-text">
                AutoSocial queues posts, tracks engagement, and keeps your brand active without
                daily manual effort.
              </p>
              <div className="stat-grid">
                <div>
                  <div className="stat-value">2.4x</div>
                  <div className="stat-label">post consistency</div>
                </div>
                <div>
                  <div className="stat-value">18%</div>
                  <div className="stat-label">avg. engagement lift</div>
                </div>
                <div>
                  <div className="stat-value">4h</div>
                  <div className="stat-label">saved per week</div>
                </div>
              </div>
            </div>

            <div className="feature-list">
              <div className="feature-item">
                <span className="feature-dot" />
                Draft, schedule, and recycle content in one calendar.
              </div>
              <div className="feature-item">
                <span className="feature-dot" />
                Unified inbox for comments and DMs.
              </div>
              <div className="feature-item">
                <span className="feature-dot" />
                Simple analytics to prove ROI to clients.
              </div>
            </div>
          </div>
        </div>
      </aside>

      <main className="auth-main">
        <nav className="auth-nav">
          <div className="nav-links">
            <Link to="/login">Login</Link>
            <Link to="/signup">Sign up</Link>
          </div>
          <button className="ghost-button" type="button">Contact</button>
        </nav>

        <div className="auth-card">
          <div className="card-header">
            <h2>{isLogin ? 'Log in to AutoSocial' : 'Create your AutoSocial account'}</h2>
            <p>
              {isLogin
                ? 'Pick up where you left off and keep your social calendar full.'
                : 'Start scheduling smarter posts for Facebook and Instagram.'}
            </p>
          </div>

          {children}

          <div className="switch-row">
            {isLogin ? 'New to AutoSocial?' : 'Already have an account?'}
            <Link to={isLogin ? '/signup' : '/login'}>
              {isLogin ? 'Create an account' : 'Log in'}
            </Link>
          </div>
        </div>
      </main>
    </div>
  )
}

export default AuthShell
