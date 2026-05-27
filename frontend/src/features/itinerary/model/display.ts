import type { ItineraryItem, Message, Session } from './types'

export function commuteModeLabel(mode: string | null | undefined): string {
  if (mode === 'walking') return '步行'
  if (mode === 'taxi') return '打车'
  if (mode === 'driving') return '自驾'
  return '未知'
}

export function resolveItemTitle(item: ItineraryItem): string {
  const displayName = item.display_name?.trim()
  if (displayName) return displayName

  if (item.type === 'commute') {
    const from = item.commute_from?.trim() || '出发点'
    const to = item.commute_to?.trim() || '目的地'
    return `${from} -> ${to}`
  }

  const parentName = item.parent_name?.trim()
  if (parentName) return parentName
  return item.name
}

export function resolveItemSubtitle(
  item: ItineraryItem,
  options?: {
    note?: string | null
    fallback?: string
    preferNote?: boolean
  },
): string {
  const title = resolveItemTitle(item)
  const note = options?.note?.trim()
  const fallback = options?.fallback ?? ''
  const explicitSubName = item.sub_name?.trim()
  const rawName = item.name?.trim()

  if (item.type === 'commute') {
    if (note) return note
    if (explicitSubName) return explicitSubName
    return `推荐方式：${commuteModeLabel(item.commute_recommended_mode ?? item.commute_mode)}`
  }

  if (options?.preferNote && note) return note
  if (explicitSubName && explicitSubName !== title) return explicitSubName
  if (rawName && rawName !== title) return rawName
  if (note) return note
  return fallback
}

type ChatMessageRenderContext = {
  session: Session
}

/**
 * Decides whether a chat message should appear in the visible timeline.
 */
export function shouldRenderChatMessage(
  message: Message,
  context: ChatMessageRenderContext,
): boolean {
  void context
  if (message.type === 'tool' || message.type === 'system') {
    return false
  }

  const content = message.content
  if ((content === '' || content == null) && !message.transientStatus) {
    return false
  }
  if (Array.isArray(content) && content.length === 0 && !message.transientStatus) {
    return false
  }

  return true
}
