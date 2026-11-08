/**
 * Review and Blind spots are the Analyze part of the product (Play, Practice, Progress, powered by Analyze). They were hidden by
 * default to keep the page simple while practising (owner's request, PR 59) and are shown by default since 2026-11-08 (owner:
 * "finish the partly built items"). Open the page with `?analysis=0` to hide them again.
 */
export const SHOW_ANALYSIS_TABS_BY_DEFAULT = true

export function showAnalysisTabs(search: string): boolean {
  const flag = new URLSearchParams(search).get('analysis')
  if (flag === '1' || flag === 'true') return true
  if (flag === '0' || flag === 'false') return false
  return SHOW_ANALYSIS_TABS_BY_DEFAULT
}
