import { RefreshCw, Download } from 'lucide-react'

const RISK_COLORS = {
  SAFE:       '#10b981',
  SUSPICIOUS: '#f59e0b',
  DANGEROUS:  '#ef4444',
}

const ACTION_ICON = {
  ALLOW:    '✅',
  SANITIZE: '✏️',
  BLOCK:    '🚫',
}

function CategoryBadge({ category }) {
  if (!category) return <span style={{ color: 'var(--color-text-muted)', fontSize: 12 }}>—</span>
  return (
    <span className="tag tag-info" style={{ fontSize: 10 }}>
      {category.replace(/_/g, ' ')}
    </span>
  )
}

export default function AttackLog({ logs, onRefresh }) {
  const downloadCSV = () => {
    if (!logs?.length) return
    const header = 'ID,Timestamp,Risk Level,Action,Score,Category,Prompt\n'
    const rows = logs.map(l =>
      `${l.id},"${l.timestamp ?? ''}",${l.risk_level},${l.action},${l.raw_score},"${l.attack_category ?? ''}","${(l.original_prompt ?? '').replace(/"/g, '""')}"`
    ).join('\n')
    const blob = new Blob([header + rows], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = 'promptguard_logs.csv'; a.click()
    URL.revokeObjectURL(url)
  }

  const dangerous  = logs?.filter(l => l.risk_level === 'DANGEROUS').length  ?? 0
  const suspicious = logs?.filter(l => l.risk_level === 'SUSPICIOUS').length ?? 0
  const safe       = logs?.filter(l => l.risk_level === 'SAFE').length       ?? 0

  return (
    <>
      {/* ── Summary Bar ─────────────────────────────────────────── */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(3, 1fr)',
        gap: 12,
        marginBottom: 20,
      }}>
        {[
          { label: 'Blocked',    count: dangerous,  color: '#ef4444', icon: '🚫' },
          { label: 'Sanitized',  count: suspicious, color: '#f59e0b', icon: '✏️' },
          { label: 'Allowed',    count: safe,       color: '#10b981', icon: '✅' },
        ].map(({ label, count, color, icon }) => (
          <div key={label} style={{
            background: 'var(--color-surface)',
            border: `1px solid ${color}22`,
            borderRadius: 'var(--radius-md)',
            padding: '16px 20px',
            display: 'flex',
            alignItems: 'center',
            gap: 14,
          }}>
            <span style={{ fontSize: 26 }}>{icon}</span>
            <div>
              <div style={{ fontSize: 24, fontWeight: 800, color, fontVariantNumeric: 'tabular-nums' }}>
                {count}
              </div>
              <div style={{ fontSize: 12, color: 'var(--color-text-muted)', fontWeight: 600 }}>{label}</div>
            </div>
          </div>
        ))}
      </div>

      {/* ── Log Table ────────────────────────────────────────────── */}
      <div className="glass-card">
        <div className="glass-card-header">
          <div className="glass-card-title">
            📋 Request Log
            <span style={{
              fontSize: 11,
              background: 'var(--color-surface-2)',
              color: 'var(--color-text-muted)',
              padding: '2px 8px',
              borderRadius: 10,
              fontWeight: 600,
            }}>
              {logs?.length ?? 0} entries
            </span>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="btn btn-ghost" style={{ padding: '6px 12px', fontSize: 12 }} onClick={onRefresh}>
              <RefreshCw size={13} /> Refresh
            </button>
            <button className="btn btn-ghost" style={{ padding: '6px 12px', fontSize: 12 }} onClick={downloadCSV}>
              <Download size={13} /> Export CSV
            </button>
          </div>
        </div>

        {!logs?.length ? (
          <div className="empty-state" style={{ padding: '60px 20px' }}>
            <div className="empty-icon">📭</div>
            <div className="empty-text">No requests logged yet</div>
            <div style={{ fontSize: 12, color: 'var(--color-text-muted)', marginTop: 8 }}>
              Try the Live Demo to generate firewall events
            </div>
          </div>
        ) : (
          <div className="log-table-wrap">
            <table className="log-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Time</th>
                  <th>Risk</th>
                  <th>Action</th>
                  <th>Score</th>
                  <th>Category</th>
                  <th>Prompt</th>
                </tr>
              </thead>
              <tbody>
                {logs.map(log => {
                  const color = RISK_COLORS[log.risk_level] ?? '#64748b'
                  const time  = log.timestamp
                    ? new Date(log.timestamp).toLocaleTimeString()
                    : '—'
                  return (
                    <tr key={log.id} title={log.explanation ?? ''}>
                      <td style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--color-text-muted)' }}>
                        {log.id}
                      </td>
                      <td style={{ fontSize: 11, color: 'var(--color-text-muted)', whiteSpace: 'nowrap' }}>
                        {time}
                      </td>
                      <td>
                        <span
                          className={`risk-pill risk-pill-${log.risk_level}`}
                          style={{ letterSpacing: 0.2 }}
                        >
                          {log.risk_level === 'DANGEROUS'  ? '🚫' :
                           log.risk_level === 'SUSPICIOUS' ? '⚠️' : '✅'}
                          {' '}{log.risk_level}
                        </span>
                      </td>
                      <td>
                        <span className="action-pill">
                          {ACTION_ICON[log.action] ?? ''} {log.action}
                        </span>
                      </td>
                      <td>
                        <span style={{
                          fontFamily: 'var(--font-mono)',
                          fontSize: 12,
                          fontWeight: 700,
                          color,
                        }}>
                          {(log.raw_score * 100).toFixed(0)}%
                        </span>
                      </td>
                      <td>
                        <CategoryBadge category={log.attack_category} />
                      </td>
                      <td>
                        <div className="prompt-cell" title={log.original_prompt}>
                          {log.original_prompt}
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ── Explanation note ─────────────────────────────────────── */}
      <div style={{
        marginTop: 16,
        padding: '12px 16px',
        background: 'var(--color-surface)',
        border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-md)',
        fontSize: 12,
        color: 'var(--color-text-muted)',
        lineHeight: 1.6,
      }}>
        💡 <strong style={{ color: 'var(--color-text-dim)' }}>Hover over a row</strong> to see the full explanation.
        Click <strong style={{ color: 'var(--color-text-dim)' }}>Export CSV</strong> to download the full audit trail.
        Logs auto-refresh every 5 seconds.
      </div>
    </>
  )
}
