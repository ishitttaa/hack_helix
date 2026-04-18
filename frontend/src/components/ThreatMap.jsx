import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from 'recharts'

const CATEGORY_META = {
  prompt_injection:        { label: 'Prompt Injection',    color: '#ef4444' },
  jailbreak:               { label: 'Jailbreak / DAN',     color: '#f97316' },
  system_prompt_extraction:{ label: 'Prompt Extraction',   color: '#eab308' },
  role_override:           { label: 'Role Override',        color: '#a855f7' },
  data_extraction:         { label: 'Data Extraction',      color: '#3b82f6' },
  indirect_injection:      { label: 'Indirect Injection',   color: '#06b6d4' },
  obfuscation:             { label: 'Obfuscation',          color: '#64748b' },
}

const FALLBACK_DATA = [
  { name: 'prompt_injection', value: 34 },
  { name: 'jailbreak', value: 28 },
  { name: 'system_prompt_extraction', value: 18 },
  { name: 'role_override', value: 10 },
  { name: 'data_extraction', value: 7 },
  { name: 'indirect_injection', value: 3 },
]

const CustomTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null
  const item = payload[0]
  const meta = CATEGORY_META[item.name] ?? { label: item.name, color: '#6366f1' }
  return (
    <div style={{
      background: 'rgba(13,19,34,0.95)',
      border: `1px solid ${meta.color}44`,
      borderRadius: 8,
      padding: '8px 12px',
      fontSize: 12,
    }}>
      <div style={{ color: meta.color, fontWeight: 700 }}>{meta.label}</div>
      <div style={{ color: '#94a3b8', marginTop: 2 }}>{item.value} detections</div>
    </div>
  )
}

export default function ThreatMap({ categories }) {
  const hasData = Object.keys(categories).length > 0
  const rawData = hasData
    ? Object.entries(categories).map(([name, value]) => ({ name, value }))
    : FALLBACK_DATA

  const total = rawData.reduce((s, d) => s + d.value, 0)

  return (
    <div className="glass-card">
      <div className="glass-card-header">
        <div className="glass-card-title">
          🎯 Attack Type Breakdown
        </div>
        <span style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>
          {hasData ? `${total} total` : 'Demo data'}
        </span>
      </div>
      <div className="glass-card-body">
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, alignItems: 'center' }}>
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie
                data={rawData}
                cx="50%"
                cy="50%"
                innerRadius={50}
                outerRadius={85}
                paddingAngle={3}
                dataKey="value"
              >
                {rawData.map(entry => {
                  const meta = CATEGORY_META[entry.name] ?? { color: '#6366f1' }
                  return <Cell key={entry.name} fill={meta.color} />
                })}
              </Pie>
              <Tooltip content={<CustomTooltip />} />
            </PieChart>
          </ResponsiveContainer>

          <div className="donut-legend">
            {rawData.map(entry => {
              const meta = CATEGORY_META[entry.name] ?? { label: entry.name, color: '#6366f1' }
              const pct = total > 0 ? Math.round(entry.value / total * 100) : 0
              return (
                <div key={entry.name} className="legend-item">
                  <div className="legend-dot" style={{ background: meta.color }} />
                  <span style={{ fontSize: 12 }}>{meta.label}</span>
                  <span className="legend-count" style={{ color: meta.color, fontSize: 12 }}>
                    {pct}%
                  </span>
                </div>
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}
