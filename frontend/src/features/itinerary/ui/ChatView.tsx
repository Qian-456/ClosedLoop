import { useEffect, useRef } from 'react'
import { SendHorizontal, Bot, User } from 'lucide-react'
import { useItineraryStore } from '../store/useItineraryStore'
import { invokeStream } from '../api/invoke'
import clsx from 'clsx'
import { PlanPanel } from './PlanPanel'
import { shouldRenderChatMessage } from '../model/display'
import type { Message } from '../model/types'
import MarkdownText from '../../../shared/ui/MarkdownText'

const EMPTY_MESSAGES: Message[] = []

export function ChatView() {
  const sessions = useItineraryStore((s) => s.sessions)
  const currentSessionId = useItineraryStore((s) => s.currentSessionId)
  const userInput = useItineraryStore((s) => s.userInput)
  const setUserInput = useItineraryStore((s) => s.setUserInput)
  const invokeStatus = useItineraryStore((s) => s.invokeStatus)
  const errorMessage = useItineraryStore((s) => s.errorMessage)
  
  const addLocalMessage = useItineraryStore((s) => s.addLocalMessage)
  const setInvokeRunning = useItineraryStore((s) => s.setInvokeRunning)
  const applyInvokeStreamEvent = useItineraryStore((s) => s.applyInvokeStreamEvent)
  const setInvokeError = useItineraryStore((s) => s.setInvokeError)

  const currentSession = sessions.find((s) => s.id === currentSessionId)
  const messages = currentSession?.messages || EMPTY_MESSAGES
  const itinerary = currentSession?.itinerary
  const confirmation = currentSession?.confirmation

  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages, invokeStatus])

  const handleSend = async () => {
    const text = userInput.trim()
    if (!text || !currentSessionId) return

    setUserInput('')
    const messageId = `msg_${Date.now()}`
    addLocalMessage({
      id: messageId,
      type: 'human',
      content: text,
    })
    setInvokeRunning(messageId)

    try {
      await invokeStream(text, currentSessionId, {
        onEvent(event) {
          applyInvokeStreamEvent(event)
        },
      })
    } catch (error) {
      console.error(error)
      setInvokeError(error instanceof Error ? error.message : '未知错误')
      addLocalMessage({
        id: `err_${Date.now()}`,
        type: 'ai',
        content: '抱歉，系统出现错误，请稍后再试。',
      })
    }
  }

  const renderContent = (content: unknown) => {
    if (typeof content === 'string') {
      return <MarkdownText text={content} />
    }
    if (Array.isArray(content)) {
      return content.map(c => typeof c === 'string' ? c : JSON.stringify(c)).join(' ')
    }
    return JSON.stringify(content)
  }

  return (
    <div className="flex flex-col h-full bg-[#F6F7FB]">
      <div 
        ref={scrollRef}
        className="flex-1 overflow-y-auto px-4 py-6 space-y-6"
      >
        {(() => {
          return messages.map((msg, idx) => {
          const isHuman = msg.type === 'human'

          if (
            !shouldRenderChatMessage(msg, {
              session: currentSession ?? {
                id: '',
                title: '',
                messages: [],
                updatedAt: 0,
              },
            })
          ) {
            return null
          }

          if (!isHuman && !msg.content && (invokeStatus !== 'running' || idx !== messages.length - 1)) {
            return null
          }

          return (
            <div key={msg.id || idx} className="space-y-3">
              <div
                className={clsx(
                  "flex gap-3 max-w-[85%]",
                  isHuman ? "ml-auto flex-row-reverse" : "mr-auto"
                )}
              >
                <div className={clsx(
                  "w-8 h-8 rounded-full flex items-center justify-center shrink-0 shadow-sm",
                  isHuman ? "bg-blue-600 text-white" : "bg-white border border-slate-100 text-blue-600"
                )}>
                  {isHuman ? <User className="w-5 h-5" /> : <Bot className="w-5 h-5" />}
                </div>
                <div className={clsx(
                  "px-4 py-3 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap break-words",
                  isHuman 
                    ? "bg-blue-600 text-white rounded-tr-sm" 
                    : "bg-white text-slate-800 shadow-sm border border-slate-100/50 rounded-tl-sm"
                )}>
                  {!isHuman && msg.transientStatus && (
                    <div
                      className="text-slate-400 italic transition-all duration-1000 overflow-hidden animate-pulse"
                      style={{
                        opacity: (invokeStatus === 'running' && idx === messages.length - 1) ? 1 : 0,
                        maxHeight: (invokeStatus === 'running' && idx === messages.length - 1) ? '24px' : '0px',
                        marginBottom: (invokeStatus === 'running' && idx === messages.length - 1 && msg.content) ? '4px' : '0px'
                      }}
                    >
                      {msg.transientStatus}
                    </div>
                  )}
                  {renderContent(msg.content)}
                </div>
              </div>

              {/* {isHuman ? renderProcessBubbles(typeof msg.id === 'string' ? msg.id : undefined) : null} */}
            </div>
          )
          })
        })()}
      </div>

      <PlanPanel itinerary={itinerary} confirmation={confirmation} errorMessage={errorMessage} />

      <div className="p-4 bg-white border-t border-slate-100">
        <div className="relative flex items-end">
          <textarea
            value={userInput}
            onChange={(e) => setUserInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                handleSend()
              }
            }}
            placeholder="继续对话..."
            rows={1}
            className="w-full max-h-[120px] min-h-[44px] bg-slate-50 rounded-2xl outline-none text-sm text-slate-900 placeholder:text-slate-400 resize-none py-3 pl-4 pr-12"
          />
          <button
            type="button"
            onClick={handleSend}
            disabled={userInput.trim().length === 0 || invokeStatus === 'running'}
            className="absolute right-1.5 bottom-1.5 h-8 w-8 rounded-xl bg-blue-600 text-white flex items-center justify-center disabled:opacity-30 disabled:bg-slate-300 transition-colors"
          >
            <SendHorizontal className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  )
}
