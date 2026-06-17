import { useState, useEffect } from 'react';
import { Gauge } from './components/Gauge';

/* ─── Types ─────────────────────────────────────────────────────────────── */
interface MetaData {
  event_cases: string[];
  corridors: string[];
  police_stations: string[];
}

interface AssessResult {
  risk_probability: number;
  risk_label: string;
  eta_minutes: number;
  fragility_score: number;
  diversion: string;
  recommendation: string;
  summary: string;
}

/* ─── Loading stages ─────────────────────────────────────────────────────── */
const STAGES = [
  'Analyzing Incident...',
  'Evaluating Corridor Impact...',
  'Calculating Closure Probability...',
  'Generating Recommendations...',
];

/* ─── SVG Icons (inline, no deps) ───────────────────────────────────────── */
function Icon({ d, size = 14 }: { d: string; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d={d} />
    </svg>
  );
}

const ICONS = {
  shield: 'M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z',
  clock:  'M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm0 6v6l4 2',
  nav:    'M3 12l9-9 9 9M5 10v9a1 1 0 0 0 1 1h4v-5h4v5h4a1 1 0 0 0 1-1v-9',
  zap:    'M13 2L3 14h9l-1 8 10-12h-9l1-8z',
  alert:  'M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0zm1.71 13.14v2m0-6v4',
  check:  'M9 12l2 2 4-4M22 12A10 10 0 1 1 2 12a10 10 0 0 1 20 0z',
  radio:  'M5.636 18.364a9 9 0 0 1 0-12.728M18.364 5.636a9 9 0 0 1 0 12.728M12 13a1 1 0 1 0 0-2 1 1 0 0 0 0 2z',
  target: 'M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10zM12 18a6 6 0 1 0 0-12 6 6 0 0 0 0 12zm0-4a2 2 0 1 0 0-4 2 2 0 0 0 0 4z',
  grid:   'M3 3h7v7H3zm11 0h7v7h-7zM3 14h7v7H3zm11 0h7v7h-7z',
};

/* ─── Live Clock ─────────────────────────────────────────────────────────── */
function LiveClock() {
  const [time, setTime] = useState(new Date());
  useEffect(() => {
    const t = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(t);
  }, []);
  const fmt = (n: number) => String(n).padStart(2, '0');
  return (
    <span className="live-clock">
      {fmt(time.getHours())}:{fmt(time.getMinutes())}:{fmt(time.getSeconds())} IST
    </span>
  );
}

/* ─── Toggle ─────────────────────────────────────────────────────────────── */
function Toggle({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <div className="toggle-row">
      <span className="toggle-label">{label}</span>
      <div className="toggle-wrapper" style={{ position: 'relative' }}>
        <input type="checkbox" className="toggle-input" checked={checked} onChange={e => onChange(e.target.checked)} />
        <div className="toggle-track" style={{
          background: checked ? 'var(--primary)' : 'var(--surface-2)',
          borderColor: checked ? 'var(--primary)' : 'var(--border)',
        }} />
        <div className="toggle-thumb" style={{
          transform: checked ? 'translateX(18px)' : 'translateX(0)',
          background: checked ? 'white' : 'var(--txt-2)',
        }} />
      </div>
    </div>
  );
}

/* ─── Segmented Control ──────────────────────────────────────────────────── */
function SegCtrl({ options, value, onChange }: { options: string[]; value: string; onChange: (v: string) => void }) {
  return (
    <div className="seg-ctrl">
      {options.map(opt => (
        <div key={opt} className={`seg-opt${value === opt ? ' active' : ''}`} onClick={() => onChange(opt)}>
          {opt}
        </div>
      ))}
    </div>
  );
}

/* ─── Tag ────────────────────────────────────────────────────────────────── */
function Tag({ children, variant }: { children: React.ReactNode; variant: 'success' | 'warning' | 'danger' | 'info' | 'neutral' | 'amber' }) {
  return <span className={`tag tag-${variant}`}>{children}</span>;
}

/* ─── Metric Tile ────────────────────────────────────────────────────────── */
function MetricTile({ label, value, sub, color }: { label: string; value: string; sub?: string; color?: string }) {
  return (
    <div className="metric-tile">
      <div className="metric-tile-label">{label}</div>
      <div className="metric-tile-value" style={{ color: color || 'var(--txt)' }}>{value}</div>
      {sub && <div className="metric-tile-sub">{sub}</div>}
    </div>
  );
}

/* ─── Intel Block ────────────────────────────────────────────────────────── */
function IntelBlock({ icon, title, children }: { icon: string; title: string; children: React.ReactNode }) {
  return (
    <div className="intel-block">
      <div className="intel-block-header">
        <Icon d={ICONS[icon as keyof typeof ICONS] || ''} />
        <span className="intel-block-title">{title}</span>
      </div>
      <div className="intel-block-body">{children}</div>
    </div>
  );
}

const getLocalDateString = (d: Date) => {
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
};

/* ═══════════════════════════════════════════════════════════════════════════
   MAIN APP
   ═══════════════════════════════════════════════════════════════════════════ */
export default function App() {
  const [meta, setMeta] = useState<MetaData | null>(null);
  const [loadingMeta, setLoadingMeta] = useState(true);

  // Form state
  const [eventCase, setEventCase] = useState('');
  const [corridor, setCorridor] = useState('');
  const [overrideMode, setOverrideMode] = useState('Auto');
  const [policeStation, setPoliceStation] = useState('');
  const today = new Date();
  const todayStr = getLocalDateString(today);
  const [date, setDate] = useState(todayStr);
  const [time, setTime] = useState(today.toTimeString().substring(0, 5));
  const [eventType, setEventType] = useState('Unplanned');
  const [authenticated, setAuthenticated] = useState(true);

  // Assessment state
  const [assessing, setAssessing] = useState(false);
  const [stageIdx, setStageIdx] = useState(0);
  const [result, setResult] = useState<AssessResult | null>(null);

  const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

  useEffect(() => {
    fetch(`${API_URL}/api/meta`)
      .then(r => r.json())
      .then((d: MetaData) => {
        setMeta(d);
        if (d.event_cases[0]) setEventCase(d.event_cases[0]);
        if (d.corridors[0]) setCorridor(d.corridors[0]);
        if (d.police_stations[0]) setPoliceStation(d.police_stations[0]);
      })
      .catch(console.error)
      .finally(() => setLoadingMeta(false));
  }, [API_URL]);

  // Cycle through loading stages
  useEffect(() => {
    if (!assessing) { setStageIdx(0); return; }
    const t = setInterval(() => setStageIdx(i => (i + 1) % STAGES.length), 900);
    return () => clearInterval(t);
  }, [assessing]);

  const handleAssess = async () => {
    setAssessing(true);
    setResult(null);
    try {
      const res = await fetch(`${API_URL}/api/assess`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          event_case: eventCase,
          corridor,
          override_mode: overrideMode,
          police_station: overrideMode === 'Manual' ? policeStation : '',
          date,
          time,
          event_type: eventType,
          authenticated,
        }),
      });
      if (!res.ok) throw new Error('API Error');
      setResult(await res.json());
    } catch (e) {
      console.error(e);
    } finally {
      setAssessing(false);
    }
  };

  const isPeak = () => {
    const h = parseInt(time.split(':')[0] || '0', 10);
    return h >= 10 && h <= 17;
  };
  const isWeekend = () => {
    const parts = date.split(/[-/]/);
    if (parts.length === 3) {
      const year = parseInt(parts[0], 10);
      const month = parseInt(parts[1], 10) - 1;
      const day = parseInt(parts[2], 10);
      const d = new Date(year, month, day);
      return d.getDay() === 0 || d.getDay() === 6;
    }
    return false;
  };

  const riskColor = (label: string) => {
    if (label === 'High') return 'var(--danger)';
    if (label === 'Medium') return 'var(--warning)';
    return 'var(--success)';
  };

  const fragColor = (score: number) => {
    if (score >= 4) return 'var(--danger)';
    if (score >= 2.5) return 'var(--warning)';
    return 'var(--success)';
  };

  if (loadingMeta) {
    return (
      <div className="app" style={{ alignItems: 'center', justifyContent: 'center', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        <div className="spinner" style={{ width: '24px', height: '24px', borderWidth: '3px' }} />
        <p style={{ fontSize: '0.75rem', color: 'var(--txt-2)', letterSpacing: '0.1em', textTransform: 'uppercase' }}>
          Connecting to Command Center
        </p>
      </div>
    );
  }

  return (
    <div className="app">
      {/* ── TOPBAR ─────────────────────────────────────────────────────── */}
      <header className="topbar">
        <div className="topbar-brand">
          <div className="topbar-brand-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="#000" strokeWidth="2.5">
              <path d={ICONS.radio} />
            </svg>
          </div>
          <div>
            <div className="topbar-title">Corridor Watch</div>
            <div className="topbar-subtitle">Bengaluru Traffic Command · Operations Center</div>
          </div>
        </div>

        <div className="topbar-meta">
          <div className="topbar-stat">
            <div className="topbar-stat-value">8,173</div>
            <div className="topbar-stat-label">Events Analysed</div>
          </div>
          <div className="topbar-divider" />
          <div className="topbar-stat">
            <div className="topbar-stat-value">0.8057</div>
            <div className="topbar-stat-label">Model AUC</div>
          </div>
          <div className="topbar-divider" />
          <LiveClock />
          <div className="topbar-divider" />
          <div className="status-row">
            <div className="status-dot" />
            <div className="status-text">Systems Nominal</div>
          </div>
        </div>
      </header>

      {/* ── MAIN GRID ──────────────────────────────────────────────────── */}
      <main className="main-grid">

        {/* ═══ LEFT PANEL — INCIDENT INTAKE ════════════════════════════ */}
        <div className="panel">
          <div className="panel-header">
            <span className="panel-header-label">Incident Intake Panel</span>
            <span className="panel-badge">INTAKE</span>
          </div>
          <div className="panel-body">

            <div className="field">
              <label className="field-label">Event Case</label>
              <select className="field-control" value={eventCase} onChange={e => setEventCase(e.target.value)}>
                {meta?.event_cases.map(c => <option key={c}>{c}</option>)}
              </select>
            </div>

            <div className="field">
              <label className="field-label">Corridor</label>
              <select className="field-control" value={corridor} onChange={e => setCorridor(e.target.value)}>
                {meta?.corridors.map(c => <option key={c}>{c}</option>)}
              </select>
            </div>

            <div className="field-sep" />

            <div className="field">
              <label className="field-label">Override Police Station</label>
              <SegCtrl options={['Auto', 'Manual']} value={overrideMode} onChange={setOverrideMode} />
            </div>

            {overrideMode === 'Manual' && (
              <div className="field">
                <label className="field-label">Police Station</label>
                <select className="field-control" value={policeStation} onChange={e => setPoliceStation(e.target.value)}>
                  {meta?.police_stations.map(ps => <option key={ps}>{ps}</option>)}
                </select>
              </div>
            )}

            <div className="field-sep" />

            <div className="field-row">
              <div className="field">
                <label className="field-label">Date</label>
                <input
                  type="date"
                  className="field-control"
                  value={date}
                  onChange={e => setDate(e.target.value)}
                  min={todayStr}
                />
              </div>
              <div className="field">
                <label className="field-label">Time (24h)</label>
                <input
                  type="time"
                  className="field-control"
                  value={time}
                  onChange={e => setTime(e.target.value)}
                />
              </div>
            </div>

            <div className="field">
              <label className="field-label">Event Type</label>
              <SegCtrl options={['Planned', 'Unplanned']} value={eventType} onChange={setEventType} />
            </div>

            <div className="field-sep" />

            <Toggle
              checked={authenticated}
              onChange={setAuthenticated}
              label="Authenticate Report"
            />

            <div style={{ marginTop: '1rem' }}>
              <button
                className={`btn-assess${assessing ? ' loading' : ''}`}
                onClick={handleAssess}
                disabled={assessing}
              >
                {assessing ? (
                  <>
                    <div className="spinner dark" />
                    {STAGES[stageIdx]}
                  </>
                ) : (
                  <>
                    <Icon d={ICONS.target} size={15} />
                    Assess Risk
                  </>
                )}
              </button>
            </div>
          </div>
        </div>

        {/* ═══ CENTRE PANEL — RISK ASSESSMENT ══════════════════════════ */}
        <div className="panel">
          <div className="panel-header">
            <span className="panel-header-label">Risk Assessment</span>
            {result && (
              <span className="panel-badge" style={{
                background: result.risk_label === 'High' ? 'var(--danger-glow)' : result.risk_label === 'Medium' ? 'var(--warning-glow)' : 'var(--success-glow)',
                color: riskColor(result.risk_label),
                borderColor: `${riskColor(result.risk_label)}55`,
              }}>
                {result.risk_label.toUpperCase()} RISK
              </span>
            )}
          </div>

          {result ? (
            <>
              <Gauge value={result.risk_probability} />

              {/* Metric grid */}
              <div className="metric-grid">
                <MetricTile
                  label="ETA to Clear"
                  value={`~${result.eta_minutes}`}
                  sub="minutes (historical median)"
                  color="var(--txt)"
                />
                <MetricTile
                  label="Fragility Score"
                  value={`${result.fragility_score.toFixed(1)}`}
                  sub="out of 10"
                  color={fragColor(result.fragility_score)}
                />
              </div>

              {/* Context tags */}
              <div className="tag-row">
                <Tag variant={isPeak() ? 'warning' : 'neutral'}>
                  {isPeak() ? '● Peak Hours' : '○ Off-Peak'}
                </Tag>
                <Tag variant="neutral">
                  {isWeekend() ? 'Weekend' : 'Weekday'}
                </Tag>
                <Tag variant={authenticated ? 'success' : 'danger'}>
                  {authenticated ? '✓ Authenticated' : '! Unverified'}
                </Tag>
                <Tag variant="info">
                  {eventType}
                </Tag>
              </div>

              {/* Corridor metadata */}
              <div style={{ padding: '0.875rem 1.25rem', borderBottom: '1px solid var(--border)', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                <div className="rec-line">
                  <span className="rec-line-key">Corridor</span>
                  <span className="rec-line-val">{corridor}</span>
                </div>
                <div className="rec-line">
                  <span className="rec-line-key">Cause</span>
                  <span className="rec-line-val">{eventCase}</span>
                </div>
                <div className="rec-line">
                  <span className="rec-line-key">Risk %</span>
                  <span className="rec-line-val" style={{ color: riskColor(result.risk_label) }}>
                    {result.risk_probability.toFixed(1)}%
                  </span>
                </div>
              </div>
            </>
          ) : (
            <div className="empty-state">
              <svg className="empty-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d={ICONS.target} />
              </svg>
              <div className="empty-text">
                Configure the incident parameters<br />and click <strong style={{ color: 'var(--txt)' }}>Assess Risk</strong> to begin.
              </div>
            </div>
          )}
        </div>

        {/* ═══ RIGHT PANEL — OPERATIONAL INTELLIGENCE ══════════════════ */}
        <div className="panel">
          <div className="panel-header">
            <span className="panel-header-label">Operational Intelligence</span>
            <span className="panel-badge">INTEL</span>
          </div>

          {result ? (
            <>
              {/* Recommendation block */}
              <IntelBlock icon="zap" title="Operational Recommendation">
                <div className="action-card">
                  <Icon d={ICONS.alert} size={15} />
                  <span style={{ fontSize: '0.82rem', lineHeight: 1.7 }}>{result.recommendation}</span>
                </div>
              </IntelBlock>

              {/* Quick stats */}
              <IntelBlock icon="grid" title="Risk Breakdown">
                <div className="rec-line">
                  <span className="rec-line-key">Closure Risk</span>
                  <span className="rec-line-val" style={{ color: riskColor(result.risk_label) }}>
                    {result.risk_probability.toFixed(1)}%
                  </span>
                </div>
                <div className="rec-line">
                  <span className="rec-line-key">ETA</span>
                  <span className="rec-line-val">~{result.eta_minutes} minutes</span>
                </div>
                <div className="rec-line">
                  <span className="rec-line-key">Fragility</span>
                  <span className="rec-line-val" style={{ color: fragColor(result.fragility_score) }}>
                    {result.fragility_score.toFixed(1)} / 10
                  </span>
                </div>
              </IntelBlock>

              {/* Diversion */}
              <IntelBlock icon="nav" title="Diversion Intelligence">
                {result.diversion && result.diversion !== 'None available' ? (
                  <div className="diversion-chip">
                    <Icon d={ICONS.nav} size={13} />
                    {result.diversion}
                  </div>
                ) : (
                  <span style={{ color: 'var(--warning)', fontSize: '0.78rem' }}>
                    No lower-fragility corridor available in zone.
                  </span>
                )}
              </IntelBlock>

              {/* Summary */}
              <IntelBlock icon="shield" title="Operational Summary">
                <p className="summary-block">{result.summary}</p>
              </IntelBlock>
            </>
          ) : (
            <div className="empty-state">
              <svg className="empty-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d={ICONS.shield} />
              </svg>
              <div className="empty-text">
                Operational intelligence will appear<br />after risk assessment.
              </div>
            </div>
          )}
        </div>
      </main>

      {/* ── STATUS BAR ─────────────────────────────────────────────────── */}
      <footer className="statusbar">
        <div className="statusbar-left">
          <div className="statusbar-item">CORRIDOR WATCH v2.0</div>
          <div className="statusbar-item">GRIDLOCK HACKATHON 2.0</div>
          <div className="statusbar-item">LightGBM · 5-fold OOF AUC 0.8057</div>
        </div>
        <div className="statusbar-right">
          <div className="statusbar-item">8,173 EVENTS · 14 NAMED CORRIDORS</div>
          <div className="statusbar-item" style={{ color: 'var(--success)' }}>◉ ONLINE</div>
        </div>
      </footer>
    </div>
  );
}
