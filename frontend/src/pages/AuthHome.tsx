import { Link } from 'react-router-dom'

function AuthHome() {
  return (
    <div className="auth-landing">
      <div className="landing-card">
        <div className="landing-brand">
          <div className="brand-mark">AS</div>
          <div>
            <div className="brand-title">AutoSocial</div>
            <div className="brand-subtitle">Automation for Facebook and Instagram</div>
          </div>
        </div>

        <h1>Simple social media automation.</h1>
        <p>
          AutoSocial helps you plan, schedule, and keep your Facebook and Instagram content
          consistent without daily manual effort.
        </p>

        <ul className="landing-points">
          <li>Plan posts in one calendar.</li>
          <li>Publish on repeat for steady engagement.</li>
          <li>Track performance at a glance.</li>
        </ul>

        <div className="landing-actions">
          <Link className="btn-primary" to="/login">Log in</Link>
          <Link className="btn-secondary" to="/signup">Sign up</Link>
        </div>
      </div>
    </div>
  )
}

export default AuthHome
