import { useEffect, useRef } from 'react'
import { SendHorizontal, Bot, User, Plus } from 'lucide-react'
import { useItineraryStore } from '../store/useItineraryStore'
import { invokeStream } from '../api/invoke'
import clsx from 'clsx'
import { PlanPanel } from './PlanPanel'
import { ProcessBubble } from './ProcessBubble'

export function ChatView() {
  const sessions = useItineraryStore((s) => s.sessions)
  const currentSessionId = useItineraryStore((s) => s.currentSessionId)
  const userInput = useItineraryStore((s) => s.userInput)
  const setUserInput = useItineraryStore((s) => s.setUserInput)
  const invokeStatus = useItineraryStore((s) => s.invokeStatus)
  const currentProcessBubble = useItineraryStore((s) => s.currentProcessBubble)
  const errorMessage = useItineraryStore((s) => s.errorMessage)
  
  const addLocalMessage = useItineraryStore((s) => s.addLocalMessage)
  const setInvokeRunning = useItineraryStore((s) => s.setInvokeRunning)
  const applyInvokeStreamEvent = useItineraryStore((s) => s.applyInvokeStreamEvent)
  const setInvokeError = useItineraryStore((s) => s.setInvokeError)
  const toggleProcessBubble = useItineraryStore((s) => s.toggleProcessBubble)
  const resetSession = useItineraryStore((s) => s.reset)

  const currentSession = sessions.find((s) => s.id === currentSessionId)
  const messages = currentSession?.messages || []
  const processHistory = currentSession?.processHistory ?? []
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

  const renderContent = (content: any) => {
    if (typeof content === 'string') {
      return content
    }
    if (Array.isArray(content)) {
      return content.map(c => typeof c === 'string' ? c : JSON.stringify(c)).join(' ')
    }
    return JSON.stringify(content)
  }

  const renderProcessBubbles = (relatedUserMessageId?: string) => {
    const historyBubbles = processHistory.filter(
      (bubble) => bubble.relatedUserMessageId === relatedUserMessageId,
    )
    const activeBubble =
      currentProcessBubble?.relatedUserMessageId === relatedUserMessageId ? currentProcessBubble : null

    return (
      <>
        {historyBubbles.map((bubble) => (
          <ProcessBubble
            key={bubble.id}
            bubble={bubble}
            onToggleExpanded={toggleProcessBubble}
          />
        ))}
        {activeBubble ? (
          <ProcessBubble
            key={activeBubble.id}
            bubble={activeBubble}
            onToggleExpanded={toggleProcessBubble}
          />
        ) : null}
      </>
    )
  }

  return (
    <div className="flex flex-col h-full bg-[#F6F7FB]">
      <div className="absolute top-0 right-0 p-4 z-20">
        <button 
          onClick={() => resetSession()}
          className="p-2 text-slate-600 bg-white/50 backdrop-blur hover:bg-white rounded-full shadow-sm"
          title="新建对话"
        >
          <Plus className="h-5 w-5" />
        </button>
      </div>
      <div 
        ref={scrollRef}
        className="flex-1 overflow-y-auto px-4 py-6 space-y-6"
      >
        {messages.map((msg, idx) => {
          if (msg.type === 'tool' || msg.type === 'system') return null // 隐藏工具和系统消息
          
          const isHuman = msg.type === 'human'
          const hasContent = msg.content && msg.content !== ''
          
          if (!hasContent) return null // 忽略空消息（如只包含 tool_calls 的 AI 消息）

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
                  {renderContent(msg.content)}
                </div>
              </div>

              {isHuman ? renderProcessBubbles(typeof msg.id === 'string' ? msg.id : undefined) : null}
            </div>
          )
        })}
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
