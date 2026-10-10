/**
 * Review and Blind spots are built but hidden by default, to keep the page simple while practising (owner's request,
 * PR 59). They stay reachable: open the page with `?analysis=1` to show the tabs.
 */
export const SHOW_ANALYSIS_TABS_BY_DEFAULT = false

export function showAnalysisTabs(search: string): boolean {
  const flag = new URLSearchParams(search).get('analysis')
  if (flag === '1' || flag === 'true') return true
  if (flag === '0' || flag === 'false') return false
  return SHOW_ANALYSIS_TABS_BY_DEFAULT
}
