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
  price_breakdown?: {
    base_price?: number
    gift_price?: number
    delivery_fee?: number
    commute_fee?: number
    total?: number
  } | null
  duration_breakdown?: {
    base_minutes?: number
    wait_minutes?: number
    buffer_minutes?: number
    total_minutes?: number
  } | null
  expected_wait_minutes?: number | null
  queue_required?: boolean | null
  requires_booking?: boolean | null
  booking_target_type?: 'restaurant' | 'package' | null
  booking_target_id?: string | null
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
  start_time?: string | null
  end_time?: string | null
  item: ItineraryItem
}

export type ItineraryPlanVariant = {
  plan_id: string
  title: string
  steps: ItineraryStep[]
  selected_item_ids: string[]
  total_duration_minutes: number
  total_cost: number
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
  execution_id?: string
  payment_required?: boolean
  payment_status?: 'pending' | 'paid' | 'failed' | string
  commit_status?: 'not_started' | 'success' | 'failed' | 'not_found' | string
  execution_command?: {
    execution_id?: string
    plan_id?: string
    payment_required?: boolean
    payment_status?: string
    commit_status?: string
    pricing_summary?: {
      expected_charge_cost?: number
      original_amount?: number
      discount_amount?: number
      payable_amount?: number
      coupon?: string
      currency?: string
    } | null
  }
  reason?: string
  plans?: Partial<ThreePlansCopywriting>
  interrupt?: unknown
  fixup?: {
    plan_id?: string
    target_item_id?: string
    reason?: string
    backup_candidates?: Array<{
      id: string
      name: string
      violation_reason?: string
      requires_confirmation?: boolean
    }>
  }
  execution_summary?: {
    execution_id?: string
    replacements?: Array<{
      original_id?: string
      original_name?: string
      new_item_id?: string
      new_item_name?: string
      item_type?: ItineraryItemType | string
    }>
    failures?: Array<{
      item_id?: string
      item_name?: string
      item_type?: ItineraryItemType | string
    }>
    items?: unknown[]
  }
}

export type Constraints = {
  group_type?: 'family' | 'friends' | 'business'
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
  content: unknown
  node?: string
  transientStatus?: string
  [key: string]: unknown
}

export type ProcessBubblePhase =
  | 'bootstrap'
  | 'search_candidates'
  | 'plan_trip'
  | 'generate_alternative_plans'
  | 'adjust_plan_item'
  | 'transfer_to_execute'
  | 'confirm_trip'
  | 'done'
  | 'error'

export type BubbleEntry = {
  kind: 'step' | 'tool'
  title: string
  summary: string
  tool?: string
  status?: 'running' | 'success' | 'failed'
  meta?: string[]
  raw?: unknown
}

export type Session = {
  id: string
  title: string
  messages: Message[]
  itinerary?: ItineraryPlan | null
  confirmation?: Confirmation | null
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

export type InvokeStreamMessageEvent = {
  event: 'message'
  data: {
    text: string
    node?: string
  }
}

export type InvokeStreamBubbleEvent = {
  event: 'bubble'
  data: {
    phase: ProcessBubblePhase
    text: string
    step?: string
    node?: string
    status?: 'running' | 'success' | 'failed'
    entries: BubbleEntry[]
  }
}

export type InvokeStreamResultEvent = {
  event: 'result'
  data: {
    itinerary?: ItineraryPlan
    confirmation?: Confirmation
    constraints?: Constraints
    current_step?: string
  }
}

export type InvokeStreamDoneEvent = {
  event: 'done'
  data: {
    success: boolean
  }
}

export type InvokeStreamErrorEvent = {
  event: 'error'
  data: {
    message: string
    code?: string
    recoverable?: boolean
  }
}

export type InvokeStreamEvent =
  | InvokeStreamMessageEvent
  | InvokeStreamBubbleEvent
  | InvokeStreamResultEvent
  | InvokeStreamDoneEvent
  | InvokeStreamErrorEvent
