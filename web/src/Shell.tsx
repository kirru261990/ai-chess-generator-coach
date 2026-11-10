import { useEffect, useState } from 'react'
import { showAnalysisTabs } from './analysisTabs'
import App from './App'
import BlindSpots from './BlindSpots'
import DrillCycles from './DrillCycles'
import LossMap from './LossMap'
import SlipRounds from './SlipRounds'
import Mistakes from './Mistakes'
import ReviewPage from './Review'
import { usageLabel, type Usage } from './usageLabel'

const API = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

type Tab = 'play' | 'test' | 'drills' | 'slips' | 'spots' | 'review' | 'lossmap'

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
      <nav className="tabs">
        <button className={tab === 'play' ? 'on' : ''} onClick={() => setTab('play')}>
          Play
        </button>
        <button className={tab === 'test' ? 'on' : ''} onClick={() => setTab('test')}>
          My mistakes
        </button>
        <button className={tab === 'drills' ? 'on' : ''} onClick={() => setTab('drills')}>
          Drill cycles
        </button>
        <button className={tab === 'slips' ? 'on' : ''} onClick={() => setTab('slips')}>
          Slip rounds
        </button>
        {SHOW_ANALYSIS_TABS && (
          <>
            <button className={tab === 'review' ? 'on' : ''} onClick={() => setTab('review')}>
              Review
            </button>
            <button className={tab === 'spots' ? 'on' : ''} onClick={() => setTab('spots')}>
              Blind spots
            </button>
            <button className={tab === 'lossmap' ? 'on' : ''} onClick={() => setTab('lossmap')}>
              Loss map
            </button>
          </>
        )}
      </nav>
      {spend && <p className={`usage ${spend.level}`}>{spend.text}</p>}
      {/* Both stay mounted so a game in progress is not lost when you look at the map. */}
      <div hidden={tab !== 'play'}>
        <App />
      </div>
      <div hidden={tab !== 'test'}>{tab === 'test' && <Mistakes />}</div>
      <div hidden={tab !== 'drills'}>{tab === 'drills' && <DrillCycles />}</div>
      <div hidden={tab !== 'slips'}>{tab === 'slips' && <SlipRounds />}</div>
      <div hidden={tab !== 'review'}>{tab === 'review' && <ReviewPage />}</div>
      <div hidden={tab !== 'spots'}>{tab === 'spots' && <BlindSpots />}</div>
      <div hidden={tab !== 'lossmap'}>{tab === 'lossmap' && <LossMap />}</div>
    </>
  )
}
