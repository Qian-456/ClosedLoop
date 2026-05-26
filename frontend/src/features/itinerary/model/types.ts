export type ItineraryItemType = 'restaurant' | 'activity' | 'gift_shop' | 'commute'

export type ItineraryItem = {
  id: string
  name: string
  parent_name?: string | null
  display_name?: string | null
  sub_name?: string | null
  type: ItineraryItemType
  location: string
  distance_km: number
  cost?: number
  gift_price?: number | null
  delivery_fee?: number | null
  delivery_distance_km?: number | null
  intro?: string | null
  features?: string | null
  commute_from?: string | null
  commute_to?: string | null
  commute_mode?: 'walking' | 'taxi' | 'driving' | null
  commute_recommended_mode?: 'walking' | 'taxi' | 'driving' | null
  commute_options?: Array<{
    mode: 'walking' | 'taxi' | 'driving'
    time_minutes: number
    cost: number
  }>
}

export type ItineraryStep = {
  order_id: string
  duration_minutes: number
  note: string
  item: ItineraryItem
}

export type ItineraryPlanVariant = {
  plan_id: string
  title: string
  steps: ItineraryStep[]
  selected_item_ids: string[]
  total_duration_minutes: number
  total_cost: number
  average_score: number
  experience_score?: number
}

export type ItineraryPlan = {
  plans: ItineraryPlanVariant[]
  status: 'ok' | 'insufficient_candidates' | 'fallback_deterministic'
  missing_types?: Array<'restaurant' | 'activity' | 'gift_shop'>
}

export type PlanCopywriting = {
  plan_name: string
  pros_cons: string[]
  ai_reminder: string
}

export type ThreePlansCopywriting = {
  plan_1: PlanCopywriting
  plan_2: PlanCopywriting
  plan_3: PlanCopywriting
}

export type Confirmation = {
  status: 'ok' | 'skipped' | 'fallback_rules' | string
  reason?: string
  plans?: Partial<ThreePlansCopywriting>
}

export type Constraints = {
  group_type?: 'solo' | 'couple' | 'family' | 'friends' | 'business'
  budget?: number
  dietary_restrictions?: string[]
  preferred_distance?: '<2km' | '2km-5km' | '>5km'
  time_period?: string
  duration_hours?: [number, number] | null
  activity_preferences?: string[]
  adult_count?: number
  child_count?: number
  child_ages?: number[]
}

export type Message = {
  id?: string
  type: string // 'human', 'ai', 'system', 'tool'
  content: string | any
  [key: string]: any
}

export type Session = {
  id: string
  title: string
  messages: Message[]
  updatedAt: number
}

export type ClosedLoopState = {
  user_input: string
  constraints?: Constraints
  itinerary?: ItineraryPlan
  candidates?: unknown
  confirmation?: Confirmation
  messages?: Message[]
}

export type InvokeResponse = {
  status: string
  state: ClosedLoopState
}
