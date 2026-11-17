import { useEffect, useState } from 'react'
import { showAnalysisTabs } from './analysisTabs'
import { API, api } from './api'
import App from './App'
import type { HomeType } from './assessState'
import BlindSpots from './BlindSpots'
import DrillCycles from './DrillCycles'
import LossMap from './LossMap'
import Openings from './Openings'
import SlipRounds from './SlipRounds'
import Mistakes, { type Screen as MistakesScreen } from './Mistakes'
import ReviewPage from './Review'
import { todayStep, type Today } from './todayState'
import { usageLabel, type Usage } from './usageLabel'

type Tab = 'play' | 'test' | 'drills' | 'slips' | 'spots' | 'review' | 'lossmap' | 'openings'
type Group = 'play' | 'train' | 'insights'

// The Analyze tabs (Insights) show by default; `?analysis=0` hides them (see analysisTabs.ts).
const SHOW_ANALYSIS_TABS = showAnalysisTabs(window.location.search)

// Three places instead of eight tabs. Each label is the page's own title. Conversion (Where you lose) leads Insights.
const GROUPS: { key: Group; label: string; tabs: { key: Tab; label: string }[] }[] = [
  { key: 'play', label: 'Play', tabs: [{ key: 'play', label: 'Play' }] },
  {
    key: 'train',
    label: 'Train',
    tabs: [
      { key: 'test', label: 'My mistakes' },
      { key: 'openings', label: 'Openings' },
      { key: 'drills', label: 'Drill cycles' },
      { key: 'slips', label: 'Slip rounds' },
    ],
  },
  ...(SHOW_ANALYSIS_TABS
    ? [
        {
          key: 'insights' as const,
          label: 'Insights',
          tabs: [
            { key: 'lossmap' as const, label: 'Where you lose' },
            { key: 'spots' as const, label: 'Blind spots' },
            { key: 'review' as const, label: 'Review' },
          ],
        },
      ]
    : []),
]

const groupOf = (tab: Tab): Group => GROUPS.find((g) => g.tabs.some((t) => t.key === tab))!.key

export default function Shell() {
  const [tab, setTab] = useState<Tab>('play')
  // The tab last open in each group, so going back to Train returns to where you were.
  const [lastIn, setLastIn] = useState<Record<Group, Tab>>({ play: 'play', train: 'test', insights: 'lossmap' })
  const [usage, setUsage] = useState<Usage | null>(null)
  const [today, setToday] = useState<Today | null>(null)
  const [todayError, setTodayError] = useState<string | null>(null)
  // The Today strip opens My mistakes on a given screen; a new key remounts it there.
  const [mistakes, setMistakes] = useState<{ key: number; initial: MistakesScreen }>({ key: 0, initial: { name: 'home' } })
  const group = groupOf(tab)

  function open(next: Tab) {
    setTab(next)
    setLastIn((l) => ({ ...l, [groupOf(next)]: next }))
  }

  // Refresh the spend line when the tab changes (a coach call may have happened since).
  useEffect(() => {
    fetch(`${API}/usage`)
      .then((res) => (res.ok ? res.json() : null))
      .then((u: Usage | null) => setUsage(u))
      .catch(() => setUsage(null))
  }, [tab])
  const spend = usage ? usageLabel(usage) : null

  // The next step is read again on every tab change and after the strip opens something, so it never stays stale for long.
  useEffect(() => {
    if (group === 'play') return
    api<{ types: HomeType[] }>('/coach/home').then(
      (h) => setToday(todayStep(h.types)),
      () => setToday(null),
    )
  }, [tab, group, mistakes.key])

  function openMistakes(initial: MistakesScreen) {
    setMistakes((m) => ({ key: m.key + 1, initial }))
    open('test')
  }

  function act(t: Today) {
    setTodayError(null)
    const a = t.action
    if (a.kind === 'play') return open('play')
    if (a.kind === 'test' || a.kind === 'practice') return openMistakes({ name: a.kind, id: a.id })
    const started =
      a.kind === 'start-test'
        ? api<{ assessment_id: number }>('/coach/assessments/baseline', { mistake_type: a.mistakeType }).then((s): MistakesScreen => ({ name: 'test', id: s.assessment_id }))
        : api<{ session_id: number }>('/coach/practice/sessions', { mistake_type: a.mistakeType }).then((s): MistakesScreen => ({ name: 'practice', id: s.session_id }))
    started.then(openMistakes, (e: Error) => setTodayError(e.message))
  }

  const current = GROUPS.find((g) => g.key === group)!
  return (
    <>
      <header className="masthead">
        <h1 className="wordmark">
          AI Chess <b>Coach</b>
        </h1>
        <nav className="tabs" aria-label="Sections">
          {GROUPS.map((g) => (
            <button key={g.key} className={group === g.key ? 'on' : ''} aria-current={group === g.key ? 'page' : undefined} onClick={() => open(lastIn[g.key])}>
              {g.label}
            </button>
          ))}
        </nav>
      </header>
      {current.tabs.length > 1 && (
        <nav className="subtabs" aria-label={current.label}>
          {current.tabs.map((t) => (
            <button key={t.key} className={tab === t.key ? 'on' : ''} aria-current={tab === t.key ? 'page' : undefined} onClick={() => open(t.key)}>
              {t.label}
            </button>
          ))}
        </nav>
      )}
      {group !== 'play' && today && (
        <div className="today" role="region" aria-label="Today">
          <span className="today-mark">Today</span>
          <span className="today-text">{today.text}</span>
          <button className="primary" onClick={() => act(today)}>
            {today.button}
          </button>
          {todayError && (
            <span className="error" role="alert">
              {todayError}
            </span>
          )}
        </div>
      )}
      {/* Spend is shown only near or over the monthly budget, when it changes what the coach can do. */}
      {spend && spend.level !== 'ok' && <p className={`usage ${spend.level}`}>{spend.text}</p>}
      {/* Both stay mounted so a game in progress is not lost when you look at the map. */}
      <div hidden={tab !== 'play'}>
        <App />
      </div>
      <div hidden={tab !== 'test'}>{tab === 'test' && <Mistakes key={mistakes.key} initial={mistakes.initial} />}</div>
      <div hidden={tab !== 'drills'}>{tab === 'drills' && <DrillCycles />}</div>
      <div hidden={tab !== 'slips'}>{tab === 'slips' && <SlipRounds />}</div>
      <div hidden={tab !== 'openings'}>{tab === 'openings' && <Openings />}</div>
      <div hidden={tab !== 'review'}>{tab === 'review' && <ReviewPage />}</div>
      <div hidden={tab !== 'spots'}>{tab === 'spots' && <BlindSpots />}</div>
      <div hidden={tab !== 'lossmap'}>{tab === 'lossmap' && <LossMap />}</div>
    </>
  )
}
