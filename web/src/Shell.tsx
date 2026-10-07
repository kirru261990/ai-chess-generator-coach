import { useState } from 'react'
import App from './App'
import BlindSpots from './BlindSpots'
import ReviewPage from './Review'

type Tab = 'play' | 'spots' | 'review'

export default function Shell() {
  const [tab, setTab] = useState<Tab>('play')
  return (
    <>
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
      {/* Both stay mounted so a game in progress is not lost when you look at the map. */}
      <div hidden={tab !== 'play'}>
        <App />
      </div>
      <div hidden={tab !== 'review'}>{tab === 'review' && <ReviewPage />}</div>
      <div hidden={tab !== 'spots'}>{tab === 'spots' && <BlindSpots />}</div>
    </>
  )
}
