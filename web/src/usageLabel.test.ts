import { describe, expect, it } from 'vitest'
import { usageLabel, type Usage } from './usageLabel'

const u = (spent: number, budget = 10): Usage => ({
  month: '2026-10', spent_usd: spent, budget_usd: budget, remaining_usd: Math.max(0, budget - spent), calls: 3,
})

describe('usageLabel', () => {
  it('shows spend against the budget, marked as an estimate', () => {
    const l = usageLabel(u(0.42))
    expect(l.text).toBe('Model spend this month (estimate): $0.42 of $10.00')
    expect(l.level).toBe('ok')
  })

  it('warns at 80% and says plainly when the budget is reached', () => {
    expect(usageLabel(u(8)).level).toBe('warn')
    expect(usageLabel(u(7.99)).level).toBe('ok')
    const stop = usageLabel(u(10))
    expect(stop.level).toBe('stop')
    expect(stop.text).toContain('checked facts only')
  })

  it('treats a zero budget as reached', () => {
    expect(usageLabel(u(0, 0)).level).toBe('stop')
  })
})
