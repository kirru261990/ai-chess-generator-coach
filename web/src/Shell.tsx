import { useEffect, useState } from 'react'
import { showAnalysisTabs } from './analysisTabs'
import App from './App'
import BlindSpots from './BlindSpots'
import DrillCycles from './DrillCycles'
import LossMap from './LossMap'
import Openings from './Openings'
import SlipRounds from './SlipRounds'
import Mistakes from './Mistakes'
import ReviewPage from './Review'
import { usageLabel, type Usage } from './usageLabel'

const API = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

type Tab = 'play' | 'test' | 'drills' | 'slips' | 'spots' | 'review' | 'lossmap' | 'openings'

// The Analyze tabs (Review, Blind spots, Loss map) show by default; `?analysis=0` hides them (see analysisTabs.ts).
const SHOW_ANALYSIS_TABS = showAnalysisTabs(window.location.search)

export default function Shell() {
  const [tab, setTab] = useState<Tab>('play')
  const [usage, setUsage] = useState<Usage | null>(null)

  // Refresh the spend line when the tab changes (a coach call may have happened since).
  useEffect(() => {
    fetch(`${API}/usage`)
      .then((res) => (res.ok ? res.json() : null))
      .then((u: Usage | null) => setUsage(u))
      .catch(() => setUsage(null))
  }, [tab])
  const spend = usage ? usageLabel(usage) : null

  return (
    <>
      <header className="masthead">
        <h1 className="wordmark">
          AI Chess <b>Coach</b>
        </h1>
        <nav className="tabs" aria-label="Sections">
          <button className={tab === 'play' ? 'on' : ''} aria-current={tab === 'play' ? 'page' : undefined} onClick={() => setTab('play')}>
            Play
          </button>
          <button className={tab === 'test' ? 'on' : ''} aria-current={tab === 'test' ? 'page' : undefined} onClick={() => setTab('test')}>
            My mistakes
          </button>
          <button className={tab === 'drills' ? 'on' : ''} aria-current={tab === 'drills' ? 'page' : undefined} onClick={() => setTab('drills')}>
            Drill cycles
          </button>
          <button className={tab === 'slips' ? 'on' : ''} aria-current={tab === 'slips' ? 'page' : undefined} onClick={() => setTab('slips')}>
            Slip rounds
          </button>
          <button className={tab === 'openings' ? 'on' : ''} aria-current={tab === 'openings' ? 'page' : undefined} onClick={() => setTab('openings')}>
            Openings
          </button>
          {SHOW_ANALYSIS_TABS && (
            <>
              <button className={tab === 'review' ? 'on' : ''} aria-current={tab === 'review' ? 'page' : undefined} onClick={() => setTab('review')}>
                Review
              </button>
              <button className={tab === 'spots' ? 'on' : ''} aria-current={tab === 'spots' ? 'page' : undefined} onClick={() => setTab('spots')}>
                Blind spots
              </button>
              <button className={tab === 'lossmap' ? 'on' : ''} aria-current={tab === 'lossmap' ? 'page' : undefined} onClick={() => setTab('lossmap')}>
                Loss map
              </button>
            </>
          )}
        </nav>
      </header>
      {/* Spend is shown only near or over the monthly budget, when it changes what the coach can do. */}
      {spend && spend.level !== 'ok' && <p className={`usage ${spend.level}`}>{spend.text}</p>}
      {/* Both stay mounted so a game in progress is not lost when you look at the map. */}
      <div hidden={tab !== 'play'}>
        <App />
      </div>
      <div hidden={tab !== 'test'}>{tab === 'test' && <Mistakes />}</div>
      <div hidden={tab !== 'drills'}>{tab === 'drills' && <DrillCycles />}</div>
      <div hidden={tab !== 'slips'}>{tab === 'slips' && <SlipRounds />}</div>
      <div hidden={tab !== 'openings'}>{tab === 'openings' && <Openings />}</div>
      <div hidden={tab !== 'review'}>{tab === 'review' && <ReviewPage />}</div>
      <div hidden={tab !== 'spots'}>{tab === 'spots' && <BlindSpots />}</div>
      <div hidden={tab !== 'lossmap'}>{tab === 'lossmap' && <LossMap />}</div>
    </>
  )
}
