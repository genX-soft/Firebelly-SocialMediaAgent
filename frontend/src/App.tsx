import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import AuthHome from './pages/AuthHome'
import Login from './pages/Login'
import Signup from './pages/Signup'
import Workspace from './pages/Workspace'
import AccountConnection from './pages/AccountConnection'
import PostComposer from './pages/PostComposer'
import Inbox from './pages/Inbox'
import OAuthCallback from './pages/OAuthCallback'
import Dashboard from './pages/Dashboard'
import './App.css'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<AuthHome />} />
        <Route path="/login" element={<Login />} />
        <Route path="/signup" element={<Signup />} />
        <Route path="/workspace" element={<Workspace />} />
        <Route path="/accounts" element={<AccountConnection />} />
        <Route path="/composer" element={<PostComposer />} />
        <Route path="/inbox" element={<Inbox />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/oauth/callback" element={<OAuthCallback />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
