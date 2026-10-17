import { SERIES, squareCentre, type Lane, type Series } from './practiceState'

/** Numbered, coloured arrows drawn over the board (an 8x8 viewBox, so it scales with the board). Each series has its own colour
 *  and its own 1, 2, 3; a lone move needs no number. */
export default function MoveArrows({ lanes, orientation }: { lanes: Lane[]; orientation: 'white' | 'black' }) {
  return (
    <svg className="move-arrows" viewBox="0 0 8 8" aria-hidden="true">
      {lanes.map((l) => {
        const st = SERIES[l.series]
        const numbered = lanes.filter((x) => x.series === l.series).length > 1 // a lone move needs no number
        const a0 = squareCentre(l.uci.slice(0, 2), orientation)
        const b0 = squareCentre(l.uci.slice(2, 4), orientation)
        const len = Math.hypot(b0.x - a0.x, b0.y - a0.y) || 1
        const ux = (b0.x - a0.x) / len
        const uy = (b0.y - a0.y) / len
        // Lichess's arrow proportions: a chunky shaft and a large head, slightly see-through, one flat colour.
        const head = 0.47
        const tip = { x: b0.x - ux * 0.1, y: b0.y - uy * 0.1 }
        const base = { x: tip.x - ux * head, y: tip.y - uy * head }
        const px = -uy * 0.31
        const py = ux * 0.31
        const a = a0
        const b = b0
        // Each series puts its number at a different point along the arrow, so badges do not pile up.
        const t = l.series === 'now' ? 0.35 : 0.6
        const badge = { x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t }
        return (
          <g key={`${l.series}${l.n}`}>
            <line x1={a.x} y1={a.y} x2={base.x} y2={base.y} stroke={st.color} strokeWidth={0.16} strokeLinecap="butt" opacity={0.85} />
            <polygon points={`${tip.x},${tip.y} ${base.x + px},${base.y + py} ${base.x - px},${base.y - py}`} fill={st.color} opacity={0.85} />
            {numbered && (
              <>
                <circle cx={badge.x} cy={badge.y} r={0.25} fill={st.color} stroke="#fff" strokeWidth={0.05} />
                <text x={badge.x} y={badge.y} textAnchor="middle" dominantBaseline="central" fontSize={0.33} fontWeight={700} fill={st.text}>{l.n}</text>
              </>
            )}
          </g>
        )
      })}
    </svg>
  )
}

/** The swimlane legend under the board: one row per series, its moves numbered 1, 2, 3 in the same colour. */
export function LaneLegend({ lanes }: { lanes: Lane[] }) {
  const order: Series[] = ['now', 'best']
  return (
    <div className="lanes">
      {order.map((series) => {
        const row = lanes.filter((l) => l.series === series)
        if (row.length === 0) return null
        const st = SERIES[series]
        return (
          <div key={series} className="lane-row" style={{ borderLeftColor: st.color }}>
            <span className="lane-title">{st.title}</span>
            <span className="lane-moves">
              {row.map((l) => (
                <span key={l.n} className="lane-move">
                  <span className="lane-n" style={{ background: st.color, color: st.text }}>{row.length > 1 ? l.n : ''}</span>
                  <span className="lane-san">{l.san}</span>
                  <span className="lane-who">{l.notSound ? 'not sound' : l.who === 'You' ? 'you' : 'them'}</span>
                </span>
              ))}
            </span>
          </div>
        )
      })}
    </div>
  )
}
