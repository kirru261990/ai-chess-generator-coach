import { useEffect, useState } from 'react'
import { api } from './api'
import {
  comparisonLines, dueText, practiceLines, realComparisonLine, realWindowLines, testLines, type Progress as ProgressData,
  type ProgressType, type RealGame, type RealType,
} from './progressState'

/** Did practice help? The tests (unassisted) against the starting test, and assisted practice kept apart (PRD v2 §7.6). */
export default function ProgressPage({ onHome, onResults, onTake }: {
  onHome: () => void
  onResults: (id: number) => void
  onTake: (id: number) => void
}) {
  const [data, setData] = useState<ProgressData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [real, setReal] = useState<RealGame | null>(null)
  const [realError, setRealError] = useState<string | null>(null)

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

  useEffect(() => {
    let stop = false
    api<RealGame>('/coach/progress/realgame')
      .then((d) => !stop && setReal(d))
      .catch((e: Error) => !stop && setRealError(e.message))
    return () => { stop = true }
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
      <RealGames real={real} error={realError} />
    </div>
  )
}

/** Your real games: the windows before and after the first practice, per time control, with every denominator (PRD v2 §8). */
function RealGames({ real, error }: { real: RealGame | null; error: string | null }) {
  return (
    <div className="real-games">
      <h2>Your real games</h2>
      <p className="note">
        Do the mistakes drop in the games you actually play? Each mistake type compares the 30 games before your first practice
        session of that type with the games played after it, one time control at a time. A comparison needs at
        least {real?.floors.games ?? 20} games (hanging pieces) or {real?.floors.opportunities ?? 20} chances (free captures) in
        both windows; until then you see the numbers but no comparison. A move the check was not sure about is left out. This
        is <strong>{real?.label ?? 'directional evidence, not proof of cause'}</strong>.
      </p>
      {error && <p className="error">{error}</p>}
      {!real && !error && <p>Loading…</p>}
      <div className="columns">
        {real?.types.map((t) => <RealTypeCard key={t.mistake_type} t={t} />)}
      </div>
      {real && (
        <p className="note small">
          Rates version {real.rates_version}; {real.types.map((t) => t.detector).join(', ')}; engine config{' '}
          {real.engine_config_ids.join(', ') || 'none yet'}.
        </p>
      )}
    </div>
  )
}

function RealTypeCard({ t }: { t: RealType }) {
  const unit = t.mistake_type === 'M1' ? 'Mistakes per 100 player moves (lower is better)' : 'Share of free captures missed (lower is better)'
  return (
    <div className="card">
      <h3>{t.label}</h3>
      {t.status === 'not_started' ? (
        <p className="note">Not started: your starting window is set when you begin your first practice session of this type.</p>
      ) : (
        <>
          <p className="note small">{unit}. Starting window set {t.frozen_at?.slice(0, 10)}.</p>
          {t.time_controls.map((tc) => (
            <div key={tc.time_control}>
              <h4>{tc.label}</h4>
              <p><strong>Before</strong> (the 30 games before practice)</p>
              {realWindowLines(tc.baseline, t.mistake_type).map((l) => <p key={l} className="what">{l}</p>)}
              <p><strong>After</strong> (games since)</p>
              {realWindowLines(tc.post, t.mistake_type).map((l) => <p key={l} className="what">{l}</p>)}
              <p className="note">{realComparisonLine(tc.comparison, t.mistake_type)}</p>
            </div>
          ))}
        </>
      )}
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
