import { useEffect, useState } from 'react'
import { api } from './api'
import {
  comparisonLines, dueText, practiceLines, testLines, type Progress as ProgressData, type ProgressType,
} from './progressState'

/** Did practice help? The tests (unassisted) against the starting test, and assisted practice kept apart (PRD v2 §7.6). */
export default function ProgressPage({ onHome, onResults, onTake }: {
  onHome: () => void
  onResults: (id: number) => void
  onTake: (id: number) => void
}) {
  const [data, setData] = useState<ProgressData | null>(null)
  const [error, setError] = useState<string | null>(null)

  // The random-guess move rates take a minute to work out after a test: look again until they are all in.
  useEffect(() => {
    let stop = false
    let timer: ReturnType<typeof setTimeout> | undefined
    const load = () => {
      api<ProgressData>('/coach/progress')
        .then((d) => {
          if (stop) return
          setData(d)
          const pending = d.types.some((t) => [t.baseline, ...t.delayed].some((x) => x?.chance_pending))
          if (pending) timer = setTimeout(load, 4000)
        })
        .catch((e: Error) => !stop && setError(e.message))
    }
    load()
    return () => {
      stop = true
      if (timer) clearTimeout(timer)
    }
  }, [])

  if (error) return <div className="app"><p className="error">{error}</p><button onClick={onHome}>Back</button></div>
  if (!data) return <div className="app"><p>Loading…</p></div>
  return (
    <div className="spots">
      <button onClick={onHome}>Back</button>
      <h2>Your progress</h2>
      <p className="note">
        Two kinds of results, kept apart. <strong>Tests</strong> have no help, so they show what you can do on your own.
        <strong> Practice</strong> has hints and feedback, so it is never mixed into the test scores. Every score has the
        number a random guesser would get next to it. Five positions is a small sample: this shows direction, not proof.
      </p>
      <div className="columns">
        {data.types.map((t) => <TypeCard key={t.mistake_type} t={t} target={data.targets_delayed_per_type} onResults={onResults} onTake={onTake} />)}
      </div>
    </div>
  )
}

function TypeCard({ t, target, onResults, onTake }: { t: ProgressType; target: number; onResults: (id: number) => void; onTake: (id: number) => void }) {
  return (
    <div className="card">
      <h3>{t.label}</h3>

      <h4>Starting test (no help)</h4>
      {t.baseline ? (
        <>
          {testLines(t.baseline).map((l) => <p key={l} className="what">{l}</p>)}
          <button onClick={() => onResults(t.baseline!.assessment_id)}>See the answers</button>
        </>
      ) : <p className="note">Not taken yet.</p>}
      {t.set_aside > 0 && <p className="note small">{t.set_aside} earlier test(s) set aside (kept, not counted).</p>}

      <h4>Delayed tests (no help): {t.delayed.length} of {target} planned</h4>
      {t.delayed.map((d, i) => (
        <div key={d.assessment_id}>
          <p><strong>Delayed test {i + 1}</strong></p>
          {testLines(d).map((l) => <p key={l} className="what">{l}</p>)}
          <button onClick={() => onResults(d.assessment_id)}>See the answers</button>
        </div>
      ))}
      {t.waiting && (
        <p className="note">
          Waiting: {dueText(t.waiting.due_at)}.{' '}
          {t.waiting.available && <button onClick={() => onTake(t.waiting!.assessment_id)}>Take it</button>}
        </p>
      )}
      {t.delayed.length === 0 && !t.waiting && <p className="note">A delayed test is set when you finish a practice session.</p>}

      <h4>Starting test against delayed tests</h4>
      {t.comparison
        ? comparisonLines(t.comparison).map((l) => <p key={l} className="what">{l}</p>)
        : <p className="note">Available after your first delayed test.</p>}

      <h4>Practice <span className="badge">assisted</span></h4>
      {practiceLines(t.practice).map((l) => <p key={l} className="what">{l}</p>)}
    </div>
  )
}
