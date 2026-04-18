import { useEffect, useState, useCallback } from 'react'
import { BarChart2, Activity, Shield, Terminal, Menu } from 'lucide-react'
import Dashboard from './components/Dashboard.jsx'
import LiveDemo from './components/LiveDemo.jsx'
import AttackLog from './components/AttackLog.jsx'

const NAV_ITEMS = [
  { id: 'dashboard', label: 'Dashboard', icon: BarChart2 },
  { id: 'demo',      label: 'Live Demo',  icon: Terminal  },
  { id: 'logs',      label: 'Attack Log', icon: Activity  },
]

export default function App() {
  const [activePage, setActivePage] = useState('dashboard')
  const [stats, setStats] = useState(null)
  const [logs, setLogs]   = useState([])
  const [toasts, setToasts] = useState([])

  const addToast = useCallback((msg, type = 'safe') => {
    const id = Date.now()
    setToasts(prev => [...prev, { id, msg, type }])
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 3500)
  }, [])

  const fetchStats = useCallback(async () => {
    try {
      const r = await fetch('/api/stats')
      if (r.ok) setStats(await r.json())
    } catch { /* backend may not be up */ }
  }, [])

  const fetchLogs = useCallback(async () => {
    try {
      const r = await fetch('/api/logs?limit=50')
      if (r.ok) setLogs(await r.json())
    } catch { /* backend may not be up */ }
  }, [])

  useEffect(() => {
    fetchStats()
    fetchLogs()
    const interval = setInterval(() => {
      fetchStats()
      fetchLogs()
    }, 5000)
    return () => clearInterval(interval)
  }, [fetchStats, fetchLogs])

  const renderPage = () => {
    switch (activePage) {
      case 'dashboard': return <Dashboard stats={stats} logs={logs} />
      case 'demo':      return <LiveDemo onResult={fetchStats} onNewLog={fetchLogs} addToast={addToast} />
      case 'logs':      return <AttackLog logs={logs} onRefresh={fetchLogs} />
      default:          return <Dashboard stats={stats} logs={logs} />
    }
  }

  return (
    <>
      <div className="bg-grid" />
      <div className="app-wrapper">
        {/* ── Sidebar ─────────────────────────── */}
        <aside className="sidebar">
          <div className="sidebar-brand">
            <div className="brand-logo">
              <div className="brand-icon">🛡️</div>
              <div>
                <div className="brand-name">PromptGuard</div>
                <div className="brand-tagline">AI Firewall Layer</div>
              </div>
            </div>
          </div>

          <nav className="sidebar-nav">
            <div className="nav-label">Navigation</div>
            {NAV_ITEMS.map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                className={`nav-item ${activePage === id ? 'active' : ''}`}
                onClick={() => setActivePage(id)}
              >
                <Icon className="nav-icon" size={16} />
                {label}
              </button>
            ))}

            <div className="nav-label" style={{ marginTop: 16 }}>System</div>
            <button className="nav-item" onClick={fetchStats}>
              <Activity className="nav-icon" size={16} />
              Refresh Data
            </button>
            <a
              href="http://localhost:8000/docs"
              target="_blank"
              rel="noreferrer"
              className="nav-item"
              style={{ textDecoration: 'none' }}
            >
              <Shield className="nav-icon" size={16} />
              API Docs
            </a>
          </nav>

          <div className="sidebar-status">
            <div className="status-badge">
              <div className="status-dot" />
              <span className="status-text">Firewall Active</span>
            </div>
          </div>
        </aside>

        {/* ── Main Content ─────────────────────── */}
        <main className="main-content">
          <header className="topbar">
            <div>
              <div className="topbar-title">
                {NAV_ITEMS.find(n => n.id === activePage)?.label ?? 'PromptGuard'}
              </div>
              <div className="topbar-subtitle">
                Adversarial Prompt Firewall · Real-time Detection
              </div>
            </div>
            <div className="topbar-right">
              {stats && (
                <div className="topbar-badge">
                  <span style={{ color: '#ef4444' }}>●</span>
                  {stats.blocked} blocked
                </div>
              )}
              <div className="topbar-badge">
                <span style={{ color: '#10b981' }}>●</span>
                ML + Rules Active
              </div>
            </div>
          </header>

          <div className="page" style={{ position: 'relative', zIndex: 1 }}>
            {renderPage()}
          </div>
        </main>
      </div>

      {/* ── Toast Notifications ──────────────── */}
      <div className="toast-container">
        {toasts.map(t => (
          <div key={t.id} className={`toast toast-${t.type}`}>
            {t.msg}
          </div>
        ))}
      </div>
    </>
  )
}
