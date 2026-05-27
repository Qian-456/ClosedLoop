import { useEffect, useRef } from 'react'
import { SendHorizontal, Bot, User, Plus } from 'lucide-react'
import { useItineraryStore } from '../store/useItineraryStore'
import { invokeStream } from '../api/invoke'
import clsx from 'clsx'

export function ChatView() {
  const sessions = useItineraryStore((s) => s.sessions)
  const currentSessionId = useItineraryStore((s) => s.currentSessionId)
  const userInput = useItineraryStore((s) => s.userInput)
  const setUserInput = useItineraryStore((s) => s.setUserInput)
  const invokeStatus = useItineraryStore((s) => s.invokeStatus)
  
  const addLocalMessage = useItineraryStore((s) => s.addLocalMessage)
  const setInvokeRunning = useItineraryStore((s) => s.setInvokeRunning)
  const applyInvokeStreamState = useItineraryStore((s) => s.applyInvokeStreamState)
  const finishInvokeStream = useItineraryStore((s) => s.finishInvokeStream)
  const setInvokeError = useItineraryStore((s) => s.setInvokeError)
  const resetSession = useItineraryStore((s) => s.reset)

  const currentSession = sessions.find((s) => s.id === currentSessionId)
  const messages = currentSession?.messages || []
  const hasVisibleAiMessage = messages.some((msg) => {
    if (msg.type !== 'ai') return false
    return Boolean(msg.content && msg.content !== '')
  })

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
    addLocalMessage({
      id: `msg_${Date.now()}`,
      type: 'human',
      content: text,
    })
    setInvokeRunning()

    try {
      await invokeStream(text, currentSessionId, {
        onEvent(event) {
          if (event.event === 'state') {
            applyInvokeStreamState(event.data.state)
            return
          }

          if (event.event === 'done') {
            finishInvokeStream(event.data.state)
          }
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
            <div
              key={msg.id || idx}
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
          )
        })}

        {invokeStatus === 'running' && !hasVisibleAiMessage && (
          <div className="flex gap-3 max-w-[85%] mr-auto">
            <div className="w-8 h-8 rounded-full bg-white border border-slate-100 text-blue-600 flex items-center justify-center shrink-0 shadow-sm">
              <Bot className="w-5 h-5" />
            </div>
            <div className="px-4 py-3 rounded-2xl bg-white text-slate-800 shadow-sm border border-slate-100/50 rounded-tl-sm flex items-center gap-1.5">
              <div className="w-1.5 h-1.5 rounded-full bg-slate-300 animate-bounce" />
              <div className="w-1.5 h-1.5 rounded-full bg-slate-300 animate-bounce [animation-delay:0.2s]" />
              <div className="w-1.5 h-1.5 rounded-full bg-slate-300 animate-bounce [animation-delay:0.4s]" />
            </div>
          </div>
        )}
      </div>

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
