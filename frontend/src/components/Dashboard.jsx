import { Shield, AlertTriangle, CheckCircle, Zap, TrendingUp, Lock } from 'lucide-react'
import RiskChart from './RiskChart.jsx'
import ThreatMap from './ThreatMap.jsx'

function StatCard({ label, value, sub, icon: Icon, iconColor, accentColor, trend }) {
  return (
    <div
      className="stat-card"
      style={{ '--card-accent': accentColor }}
    >
      <div className="stat-card-header">
        <span className="stat-card-label">{label}</span>
        <div
          className="stat-card-icon"
          style={{ background: `${iconColor}20` }}
        >
          <Icon size={18} color={iconColor} />
        </div>
      </div>
      <div className="stat-card-value">{value ?? '—'}</div>
      {sub && <div className="stat-card-sub">{sub}</div>}
      {trend !== undefined && (
        <div
          className="stat-card-trend"
          style={{
            background: trend > 0 ? 'rgba(239,68,68,0.12)' : 'rgba(16,185,129,0.12)',
            color: trend > 0 ? '#f87171' : '#34d399',
          }}
        >
          <TrendingUp size={10} />
          {trend > 0 ? `+${trend}%` : `${trend}%`} today
        </div>
      )}
    </div>
  )
}

export default function Dashboard({ stats, logs }) {
  const total    = stats?.total_requests ?? 0
  const blocked  = stats?.blocked ?? 0
  const suspicious = stats?.suspicious ?? 0
  const safe     = stats?.safe ?? 0
  const blockRate = stats?.block_rate ?? 0

  // Recent threat feed from logs
  const threats = logs?.slice(0, 8) ?? []

  return (
    <>
      {/* ── Hero Banner ─────────────────────────────────────────── */}
      <div style={{
        background: 'linear-gradient(135deg, rgba(99,102,241,0.12) 0%, rgba(34,211,238,0.06) 100%)',
        border: '1px solid rgba(99,102,241,0.2)',
        borderRadius: '18px',
        padding: '28px 32px',
        marginBottom: '24px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 24,
      }}>
        <div>
          <h1 className="glow-text" style={{ fontSize: 28, fontWeight: 800, letterSpacing: -0.5, marginBottom: 6 }}>
            PromptGuard Firewall
          </h1>
          <p style={{ color: 'var(--color-text-dim)', fontSize: 14, maxWidth: 480 }}>
            Modular, pluggable adversarial prompt detection layer for LLM-integrated products.
            Hybrid ML + Rule engine with real-time scoring and sanitization.
          </p>
          <div style={{ display: 'flex', gap: 8, marginTop: 14, flexWrap: 'wrap' }}>
            {['Prompt Injection', 'Jailbreak Detection', 'Data Extraction', 'Role Override', 'Context Memory'].map(t => (
              <span key={t} className="tag tag-info">{t}</span>
            ))}
          </div>
        </div>
        <div style={{
          fontSize: 72,
          lineHeight: 1,
          filter: 'drop-shadow(0 0 30px rgba(99,102,241,0.5))',
          flexShrink: 0,
        }}>
          🛡️
        </div>
      </div>

      {/* ── Stat Cards ──────────────────────────────────────────── */}
      <div className="stats-grid">
        <StatCard
          label="Total Requests"
          value={total.toLocaleString()}
          sub="All-time"
          icon={Zap}
          iconColor="#6366f1"
          accentColor="linear-gradient(90deg,#6366f1,#818cf8)"
        />
        <StatCard
          label="Blocked"
          value={blocked.toLocaleString()}
          sub={`${blockRate}% block rate`}
          icon={Lock}
          iconColor="#ef4444"
          accentColor="linear-gradient(90deg,#ef4444,#f87171)"
          trend={blockRate > 0 ? Math.round(blockRate) : undefined}
        />
        <StatCard
          label="Suspicious"
          value={suspicious.toLocaleString()}
          sub="Sanitized & forwarded"
          icon={AlertTriangle}
          iconColor="#f59e0b"
          accentColor="linear-gradient(90deg,#f59e0b,#fbbf24)"
        />
        <StatCard
          label="Safe"
          value={safe.toLocaleString()}
          sub="Passed through"
          icon={CheckCircle}
          iconColor="#10b981"
          accentColor="linear-gradient(90deg,#10b981,#34d399)"
        />
      </div>

      {/* ── Charts ──────────────────────────────────────────────── */}
      <div className="charts-grid">
        <RiskChart scores={stats?.recent_risk_scores ?? []} />
        <ThreatMap categories={stats?.attack_categories ?? {}} />
      </div>

      {/* ── Live Threat Feed ─────────────────────────────────────── */}
      <div className="glass-card">
        <div className="glass-card-header">
          <div className="glass-card-title">
            <span style={{ color: '#ef4444' }}>●</span>
            Live Threat Feed
          </div>
          <span style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>
            Latest {threats.length} requests
          </span>
        </div>
        <div className="glass-card-body" style={{ padding: '12px 16px' }}>
          {threats.length === 0 ? (
            <div className="empty-state">
              <div className="empty-icon">📭</div>
              <div className="empty-text">No requests yet. Try the Live Demo →</div>
            </div>
          ) : (
            <div className="threat-feed">
              {threats.map(log => (
                <div key={log.id} className={`threat-item threat-item-${log.risk_level}`}>
                  <span className="risk-pill risk-pill-SAFE" style={{
                    background: log.risk_level === 'DANGEROUS' ? 'rgba(239,68,68,0.1)' :
                                log.risk_level === 'SUSPICIOUS' ? 'rgba(245,158,11,0.1)' :
                                'rgba(16,185,129,0.1)',
                    color: log.risk_level === 'DANGEROUS' ? '#f87171' :
                           log.risk_level === 'SUSPICIOUS' ? '#fbbf24' : '#34d399',
                    fontSize: 10,
                    padding: '2px 7px',
                    borderRadius: 10,
                    flexShrink: 0,
                  }}>
                    {log.risk_level}
                  </span>
                  <span className="threat-item-prompt">{log.original_prompt}</span>
                  <span className="threat-item-time">
                    {log.timestamp ? new Date(log.timestamp).toLocaleTimeString() : ''}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ── Model Status ─────────────────────────────────────────── */}
      {stats && (
        <div style={{
          marginTop: 16,
          padding: '10px 16px',
          background: 'var(--color-surface)',
          border: '1px solid var(--color-border)',
          borderRadius: 'var(--radius-md)',
          fontSize: 12,
          color: 'var(--color-text-muted)',
          display: 'flex',
          alignItems: 'center',
          gap: 8,
        }}>
          <Shield size={14} color="#6366f1" />
          {stats.model_accuracy_note}
        </div>
      )}
    </>
  )
}
