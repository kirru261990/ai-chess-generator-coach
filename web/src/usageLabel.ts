// What to show about model spend. Figures come from the backend's ledger; they are estimates from list prices.

export type Usage = { month: string; spent_usd: number; budget_usd: number; remaining_usd: number; calls: number }

export function usageLabel(u: Usage): { text: string; level: 'ok' | 'warn' | 'stop' } {
  const money = (x: number) => `$${x.toFixed(2)}`
  if (u.spent_usd >= u.budget_usd)
    return { text: `Model budget reached (${money(u.spent_usd)} of ${money(u.budget_usd)} this month). The coach shows checked facts only.`, level: 'stop' }
  const level = u.spent_usd >= 0.8 * u.budget_usd ? 'warn' : 'ok'
  return { text: `Model spend this month (estimate): ${money(u.spent_usd)} of ${money(u.budget_usd)}`, level }
}
