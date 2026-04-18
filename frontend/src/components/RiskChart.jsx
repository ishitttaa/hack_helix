import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts'

const CustomTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null
  const score = payload[0].value
  const color = score >= 0.65 ? '#ef4444' : score >= 0.30 ? '#f59e0b' : '#10b981'
  return (
    <div style={{
      background: 'rgba(13,19,34,0.95)',
      border: `1px solid ${color}44`,
      borderRadius: 8,
      padding: '8px 12px',
      fontSize: 12,
    }}>
      <div style={{ color, fontWeight: 700 }}>
        Risk Score: {(score * 100).toFixed(0)}%
      </div>
      <div style={{ color: '#64748b', marginTop: 2 }}>
        {score >= 0.65 ? '🚫 DANGEROUS' : score >= 0.30 ? '⚠️ SUSPICIOUS' : '✅ SAFE'}
      </div>
    </div>
  )
}

export default function RiskChart({ scores }) {
  const data = scores.slice().reverse().map((s, i) => ({
    index: i + 1,
    score: s,
    fill: s >= 0.65 ? '#ef4444' : s >= 0.30 ? '#f59e0b' : '#10b981',
  }))

  // If no real data yet, show a demo wave
  const displayData = data.length > 0 ? data : Array.from({ length: 20 }, (_, i) => ({
    index: i + 1,
    score: [0.1, 0.05, 0.85, 0.9, 0.2, 0.55, 0.15, 0.7, 0.08, 0.95,
            0.3, 0.12, 0.6, 0.88, 0.04, 0.72, 0.18, 0.5, 0.92, 0.14][i],
  }))

  return (
    <div className="glass-card">
      <div className="glass-card-header">
        <div className="glass-card-title">
          📈 Risk Score Timeline
        </div>
        <span style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>
          Last {displayData.length} requests
        </span>
      </div>
      <div className="glass-card-body" style={{ paddingTop: 4 }}>
        <ResponsiveContainer width="100%" height={200}>
          <AreaChart data={displayData} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
            <defs>
              <linearGradient id="riskGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#6366f1" stopOpacity={0.4} />
                <stop offset="95%" stopColor="#6366f1" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(99,102,241,0.08)" />
            <XAxis
              dataKey="index"
              tick={{ fontSize: 10, fill: '#64748b' }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              domain={[0, 1]}
              tick={{ fontSize: 10, fill: '#64748b' }}
              axisLine={false}
              tickLine={false}
              tickFormatter={v => `${(v * 100).toFixed(0)}%`}
            />
            <Tooltip content={<CustomTooltip />} />
            {/* Danger zone reference */}
            <Area
              type="monotone"
              dataKey="score"
              stroke="#6366f1"
              strokeWidth={2}
              fill="url(#riskGrad)"
              dot={displayData.map((d, i) => ({
                key: i,
                r: 3,
                fill: d.score >= 0.65 ? '#ef4444' : d.score >= 0.30 ? '#f59e0b' : '#10b981',
                stroke: 'none',
              }))}
            />
          </AreaChart>
        </ResponsiveContainer>

        {/* Threshold legend */}
        <div style={{ display: 'flex', gap: 16, marginTop: 8, fontSize: 11 }}>
          {[
            { label: '≥65% Dangerous', color: '#ef4444' },
            { label: '30–65% Suspicious', color: '#f59e0b' },
            { label: '<30% Safe', color: '#10b981' },
          ].map(({ label, color }) => (
            <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 5, color: '#64748b' }}>
              <div style={{ width: 8, height: 8, borderRadius: '50%', background: color }} />
              {label}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
