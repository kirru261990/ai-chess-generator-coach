import { useEffect, useState } from 'react'
import App from './App'
import BlindSpots from './BlindSpots'
import ReviewPage from './Review'
import { usageLabel, type Usage } from './usageLabel'

const API = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

type Tab = 'play' | 'spots' | 'review'

// Review and Blind spots are built but hidden for now, to keep the page simple while practising. Flip to show them again.
const SHOW_ANALYSIS_TABS = false

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
      {SHOW_ANALYSIS_TABS && (
      <nav className="tabs">
        <button className={tab === 'play' ? 'on' : ''} onClick={() => setTab('play')}>
          Play
        </button>
        <button className={tab === 'review' ? 'on' : ''} onClick={() => setTab('review')}>
          Review
        </button>
        <button className={tab === 'spots' ? 'on' : ''} onClick={() => setTab('spots')}>
          Blind spots
        </button>
      </nav>
      )}
      {spend && <p className={`usage ${spend.level}`}>{spend.text}</p>}
      {/* Both stay mounted so a game in progress is not lost when you look at the map. */}
      <div hidden={tab !== 'play'}>
        <App />
      </div>
      <div hidden={tab !== 'review'}>{tab === 'review' && <ReviewPage />}</div>
      <div hidden={tab !== 'spots'}>{tab === 'spots' && <BlindSpots />}</div>
    </>
  )
}
