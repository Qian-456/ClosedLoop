import type { ItineraryPlanVariant } from './types'

export function pickFeaturedPlan(plans: ItineraryPlanVariant[]): string | null {
  if (plans.length <= 0) return null

  const plan2 = plans.find((p) => p.plan_id === 'plan_2')?.plan_id ?? null
  if (plan2) return plan2

  const valid = plans
    .filter((p) => Number.isFinite(p.total_cost))
    .slice()

  if (valid.length <= 0) return plans[0]?.plan_id ?? null

  return valid[0]?.plan_id ?? null
}
