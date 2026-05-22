import type { ItineraryPlanVariant } from './types'

export function pickFeaturedPlan(plans: ItineraryPlanVariant[]): string | null {
  if (plans.length <= 0) return null

  const plan2 = plans.find((p) => p.plan_id === 'plan_2')?.plan_id ?? null
  if (plan2) return plan2

  const valid = plans
    .filter(
      (p) =>
        Number.isFinite(p.total_cost) &&
        Number.isFinite(p.experience_score ?? p.average_score),
    )
    .slice()

  if (valid.length <= 0) return plans[0]?.plan_id ?? null

  const maxScore = valid.reduce((a, b) =>
    (a.experience_score ?? a.average_score) >= (b.experience_score ?? b.average_score) ? a : b,
  )
  return maxScore.plan_id
}
