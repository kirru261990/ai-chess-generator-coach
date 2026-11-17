import { rankFill } from './todayState'

/** A rate drawn as a rank of eight board squares, filled to the nearest eighth. The words beside it carry the exact n of m. */
export default function Rank({ n, of }: { n: number; of: number }) {
  const filled = rankFill(n, of)
  return (
    <div className="rank" role="img" aria-label={`${n} of ${of}`}>
      {Array.from({ length: 8 }, (_, i) => (
        <i key={i} className={i < filled ? 'f' : undefined} />
      ))}
    </div>
  )
}
