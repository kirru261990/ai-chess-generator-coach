import { evalLabel, evalWords, whiteShare, type Evaluation } from './evaluation'

/** A vertical evaluation bar beside the board, like the ones on chess sites. White's share fills from White's side. */
export default function EvalBar({ evaluation, orientation }: { evaluation: Evaluation | null; orientation: 'white' | 'black' }) {
  const share = evaluation ? whiteShare(evaluation) : 0.5
  const whiteOnTop = orientation === 'black' // the bar turns with the board: your side is at the bottom
  const label = evaluation ? evalLabel(evaluation) : '…'
  const words = evaluation ? evalWords(evaluation) : 'Evaluating the position'
  return (
    <div
      className={`evalbar ${evaluation ? '' : 'pending'}`}
      role="img"
      aria-label={`Evaluation bar. ${words}.`}
      title={words}
    >
      <div className="evalbar-black" style={{ height: `${(1 - share) * 100}%`, order: whiteOnTop ? 1 : 0 }} />
      <div className="evalbar-white" style={{ height: `${share * 100}%`, order: whiteOnTop ? 0 : 1 }} />
      <span className={`evalbar-label ${share >= 0.5 ? 'on-white' : 'on-black'} ${share >= 0.5 !== whiteOnTop ? 'bottom' : 'top'}`}>
        {label}
      </span>
    </div>
  )
}
