import { describe, expect, it } from 'vitest'
import { showAnalysisTabs } from './analysisTabs'
import shell from './Shell.tsx?raw'

describe('showAnalysisTabs', () => {
  it('hides Review and Blind spots by default and shows them with ?analysis=1', () => {
    expect(showAnalysisTabs('')).toBe(false)
    expect(showAnalysisTabs('?analysis=1')).toBe(true)
    expect(showAnalysisTabs('?foo=bar&analysis=true')).toBe(true)
    expect(showAnalysisTabs('?analysis=0')).toBe(false)
  })

  it('is what the page uses to decide whether the tabs are drawn', () => {
    expect(shell).toContain('showAnalysisTabs(window.location.search)')
    expect(shell).toContain("setTab('review')")
    expect(shell).toContain("setTab('spots')")
  })
})
