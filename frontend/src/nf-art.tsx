import React from 'react';

/* Detailed NagrikFlow artwork: sunset cityscape for the hero (photo-style
   layered SVG — fully offline, no external image requests). */

function WindowGrid({ x, y, cols, rows, w = 9, h = 12, dx = 15, dy = 19, color = '#ffd98a', opacity = 0.75 }: {
  x: number; y: number; cols: number; rows: number; w?: number; h?: number; dx?: number; dy?: number; color?: string; opacity?: number;
}) {
  const cells = [];
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      // deterministic pseudo-random lit pattern
      const lit = ((r * 7 + c * 13 + x) % 10) < 6;
      if (!lit) continue;
      cells.push(<rect key={`${r}-${c}`} x={x + c * dx} y={y + r * dy} width={w} height={h} rx={1.5} fill={color} opacity={opacity} />);
    }
  }
  return <g>{cells}</g>;
}

export function HeroCityscape() {
  return <div className="nf-hero-bg" aria-hidden="true">
    <svg viewBox="0 0 1200 500" preserveAspectRatio="xMidYMid slice" style={{ width: '100%', height: '100%', display: 'block' }}>
      <defs>
        <linearGradient id="nf-sky" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#081738" />
          <stop offset="0.45" stopColor="#17356e" />
          <stop offset="0.68" stopColor="#4a5f9e" />
          <stop offset="0.82" stopColor="#e08a4e" />
          <stop offset="1" stopColor="#f2b25c" />
        </linearGradient>
        <radialGradient id="nf-sun" cx="0.5" cy="0.5" r="0.5">
          <stop offset="0" stopColor="#ffe9b8" />
          <stop offset="0.55" stopColor="#ffcf7d" stopOpacity="0.85" />
          <stop offset="1" stopColor="#ffcf7d" stopOpacity="0" />
        </radialGradient>
        <linearGradient id="nf-shade" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="#081738" stopOpacity="0.88" />
          <stop offset="0.45" stopColor="#081738" stopOpacity="0.45" />
          <stop offset="0.8" stopColor="#081738" stopOpacity="0.05" />
          <stop offset="1" stopColor="#081738" stopOpacity="0" />
        </linearGradient>
      </defs>

      <rect width="1200" height="500" fill="url(#nf-sky)" />
      <circle cx="830" cy="368" r="150" fill="url(#nf-sun)" />
      <circle cx="830" cy="368" r="34" fill="#ffedbe" />

      {/* clouds */}
      <g fill="#ffffff" opacity="0.22">
        <ellipse cx="250" cy="130" rx="120" ry="20" /><ellipse cx="330" cy="112" rx="80" ry="16" />
        <ellipse cx="640" cy="90" rx="140" ry="18" /><ellipse cx="1050" cy="150" rx="110" ry="18" />
      </g>
      <g fill="#f7b46a" opacity="0.35">
        <ellipse cx="830" cy="330" rx="220" ry="14" /><ellipse cx="830" cy="352" rx="300" ry="12" />
      </g>

      {/* birds */}
      <g stroke="#0d1b3d" strokeWidth="3" fill="none" opacity="0.8" strokeLinecap="round">
        <path d="M180 200 q10 -10 20 0 q10 -10 20 0" />
        <path d="M240 170 q8 -8 16 0 q8 -8 16 0" />
        <path d="M990 200 q10 -10 20 0 q10 -10 20 0" />
        <path d="M1050 240 q8 -8 16 0 q8 -8 16 0" />
      </g>

      {/* far towers */}
      <g fill="#22376b">
        <rect x="60" y="240" width="70" height="200" /><rect x="150" y="200" width="52" height="240" />
        <rect x="960" y="210" width="60" height="230" /><rect x="1040" y="250" width="80" height="190" />
      </g>
      <WindowGrid x={70} y={252} cols={4} rows={9} />
      <WindowGrid x={158} y={212} cols={3} rows={11} />
      <WindowGrid x={970} y={222} cols={3} rows={10} />
      <WindowGrid x={1050} y={262} cols={4} rows={8} />

      {/* CST-inspired heritage building */}
      <g fill="#0e1e46">
        <rect x="300" y="300" width="240" height="140" />
        <rect x="280" y="330" width="60" height="110" />
        <rect x="500" y="330" width="60" height="110" />
        {/* central dome */}
        <path d="M390 300 q0 -70 30 -92 q30 22 30 92 Z" />
        <rect x="416" y="180" width="8" height="34" />
        <circle cx="420" cy="174" r="6" />
        {/* side domes */}
        <path d="M292 330 q0 -34 18 -44 q18 10 18 44 Z" />
        <path d="M512 330 q0 -34 18 -44 q18 10 18 44 Z" />
        {/* clock tower */}
        <rect x="648" y="220" width="44" height="220" />
        <path d="M644 220 L670 170 L696 220 Z" />
        <rect x="666" y="130" width="8" height="44" />
        <circle cx="670" cy="238" r="11" fill="#ffedbe" />
      </g>
      <g fill="#ffedbe" opacity="0.9">
        {Array.from({ length: 9 }).map((_, i) => <path key={i} d={`M${318 + i * 24} 400 v-36 a10 10 0 0 1 20 0 v36 Z`} />)}
        {Array.from({ length: 4 }).map((_, i) => <path key={`t${i}`} d={`M${654 + i * 0} 300 v-24 a8 8 0 0 1 16 0 v24 Z`} />)}
      </g>

      {/* near towers right */}
      <g fill="#0a1730">
        <rect x="740" y="250" width="90" height="250" />
        <rect x="850" y="200" width="70" height="300" />
        <rect x="1120" y="280" width="60" height="220" />
      </g>
      <WindowGrid x={752} y={264} cols={5} rows={11} />
      <WindowGrid x={860} y={214} cols={4} rows={13} />
      <WindowGrid x={1128} y={292} cols={3} rows={9} />

      {/* foreground rooftops + trees */}
      <g fill="#060f24">
        <rect x="0" y="430" width="1200" height="70" />
        <rect x="120" y="400" width="90" height="40" /><rect x="420" y="404" width="110" height="36" />
        <rect x="880" y="402" width="100" height="38" />
      </g>
      <g fill="#0d3a2e">
        <circle cx="240" cy="424" r="26" /><circle cx="288" cy="430" r="18" />
        <circle cx="580" cy="426" r="24" /><circle cx="1010" cy="426" r="26" /><circle cx="1058" cy="432" r="16" />
      </g>

      {/* legibility shade for headline */}
      <rect width="1200" height="500" fill="url(#nf-shade)" />
    </svg>
  </div>;
}
