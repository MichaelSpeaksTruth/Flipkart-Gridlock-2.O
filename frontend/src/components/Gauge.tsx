import { useEffect, useState } from 'react';

interface GaugeProps {
  value: number; // 0–100
}

export function Gauge({ value }: GaugeProps) {
  const [animated, setAnimated] = useState(0);

  useEffect(() => {
    setAnimated(0);
    const t = setTimeout(() => setAnimated(value), 80);
    return () => clearTimeout(t);
  }, [value]);

  // SVG parameters — semicircle
  const cx = 120, cy = 110, r = 90;
  const strokeW = 14;
  const arcLen = Math.PI * r; // half circumference

  const getRiskColor = (v: number) => {
    if (v < 20) return '#22c55e';   // green — low
    if (v < 50) return '#d97706';   // amber — medium
    if (v < 75) return '#f97316';   // orange-red — high
    return '#ef4444';               // red — critical
  };

  const getRiskLabel = (v: number) => {
    if (v < 20) return 'LOW RISK';
    if (v < 50) return 'MEDIUM RISK';
    if (v < 75) return 'HIGH RISK';
    return 'CRITICAL RISK';
  };

  const color = getRiskColor(value);
  const dashOffset = arcLen - (animated / 100) * arcLen;

  // Needle angle: -180deg = 0%, 0deg = 100%
  const needleAngle = (animated / 100) * 180 - 180;
  const rad = (needleAngle * Math.PI) / 180;
  const needleLen = r - strokeW / 2 - 4;
  const nx = cx + Math.cos(rad) * needleLen;
  const ny = cy + Math.sin(rad) * needleLen;

  // Arc path helper
  const arcPath = (startDeg: number, endDeg: number) => {
    const s = (startDeg * Math.PI) / 180;
    const e = (endDeg * Math.PI) / 180;
    return `M ${cx + Math.cos(s) * r} ${cy + Math.sin(s) * r} A ${r} ${r} 0 0 1 ${cx + Math.cos(e) * r} ${cy + Math.sin(e) * r}`;
  };

  return (
    <div className="gauge-shell">
      <div className="gauge-title">ROAD CLOSURE PROBABILITY</div>
      <div className="gauge-svg-wrap">
        <svg viewBox="0 0 240 120" className="gauge-svg">
          {/* Zone arcs — background */}
          <path d={arcPath(-180, -144)} fill="none" strokeWidth={strokeW} strokeLinecap="butt"
            stroke="rgba(34,197,94,0.25)" />
          <path d={arcPath(-144, -90)} fill="none" strokeWidth={strokeW} strokeLinecap="butt"
            stroke="rgba(245,158,11,0.25)" />
          <path d={arcPath(-90, -45)} fill="none" strokeWidth={strokeW} strokeLinecap="butt"
            stroke="rgba(239,68,68,0.25)" />
          <path d={arcPath(-45, 0)} fill="none" strokeWidth={strokeW} strokeLinecap="butt"
            stroke="rgba(220,38,38,0.25)" />

          {/* Progress arc */}
          <path
            d={arcPath(-180, 0)}
            fill="none"
            stroke={color}
            strokeWidth={strokeW}
            strokeLinecap="butt"
            strokeDasharray={arcLen}
            strokeDashoffset={dashOffset}
            style={{ transition: 'stroke-dashoffset 1.2s cubic-bezier(0.34,1.56,0.64,1), stroke 0.6s ease' }}
          />

          {/* Tick marks */}
          {[0, 20, 50, 75, 100].map((pv) => {
            const a = ((pv / 100) * 180 - 180) * Math.PI / 180;
            const r1 = r + strokeW / 2 + 4;
            const r2 = r + strokeW / 2 + 10;
            return (
              <line key={pv}
                x1={cx + Math.cos(a) * r1} y1={cy + Math.sin(a) * r1}
                x2={cx + Math.cos(a) * r2} y2={cy + Math.sin(a) * r2}
                stroke="rgba(100,116,139,0.5)" strokeWidth="1.5" />
            );
          })}

          {/* Zone labels */}
          {[
            { v: 10, label: 'LOW' },
            { v: 35, label: 'MED' },
            { v: 62, label: 'HIGH' },
            { v: 87, label: 'CRIT' },
          ].map(({ v, label }) => {
            const a = ((v / 100) * 180 - 180) * Math.PI / 180;
            const lr = r + strokeW / 2 + 18;
            return (
              <text key={label}
                x={cx + Math.cos(a) * lr}
                y={cy + Math.sin(a) * lr}
                textAnchor="middle"
                dominantBaseline="central"
                fill="rgba(100,116,139,0.7)"
                fontSize="5"
                fontFamily="'JetBrains Mono', monospace"
                fontWeight="600"
              >{label}</text>
            );
          })}

          {/* Needle */}
          <line
            x1={cx} y1={cy}
            x2={nx} y2={ny}
            stroke={color}
            strokeWidth="2"
            strokeLinecap="round"
            style={{ transition: 'x2 1.2s cubic-bezier(0.34,1.56,0.64,1), y2 1.2s cubic-bezier(0.34,1.56,0.64,1)' }}
          />
          <circle cx={cx} cy={cy} r="5" fill={color} />
          <circle cx={cx} cy={cy} r="3" fill="var(--bg)" />
        </svg>
      </div>

      <div className="gauge-reading">
        <div className="gauge-prob" style={{ color }}>{value.toFixed(1)}%</div>
        <div className="gauge-risk-label" style={{ color }}>{getRiskLabel(value)}</div>
      </div>
    </div>
  );
}
