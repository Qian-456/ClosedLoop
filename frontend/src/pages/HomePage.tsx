import { useMemo, useState } from 'react'
import {
  SendHorizontal,
  MapPin,
  Sparkles,
  User,
  Users,
  Baby,
  UsersRound,
  Plus,
  Menu,
} from 'lucide-react'
import { useItineraryStore } from '../features/itinerary/store/useItineraryStore'
import homeIllustration from '../assets/home-illustration.png'
import { getGreeting } from '../utils/greeting'
import { Sidebar } from '../features/itinerary/ui/Sidebar'
import { ChatView } from '../features/itinerary/ui/ChatView'
import { invokeStream } from '../features/itinerary/api/invoke'

function randomSessionId(sessionsCount: number): string {
  const paddedCount = String(sessionsCount + 1).padStart(3, '0')
  return `Jason_session${paddedCount}_fde3`
}

function QuickCard({
  icon,
  label,
  subtitle,
  onClick,
}: {
  icon: React.ReactNode
  label: string
  subtitle: string
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="rounded-2xl bg-white/70 backdrop-blur border border-white/60 shadow-sm px-3 py-4 text-left hover:bg-white"
    >
      <div className="h-11 w-11 rounded-2xl bg-slate-50 border border-slate-100 flex items-center justify-center">
        {icon}
      </div>
      <div className="mt-2 text-sm font-medium text-slate-800">{label}</div>
      <div className="mt-0.5 text-[11px] text-slate-500">{subtitle}</div>
    </button>
  )
}

export default function HomePage() {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  const sessions = useItineraryStore((s) => s.sessions)
  const currentSessionId = useItineraryStore((s) => s.currentSessionId)
  const userInput = useItineraryStore((s) => s.userInput)
  const setUserInput = useItineraryStore((s) => s.setUserInput)
  const startSession = useItineraryStore((s) => s.startSession)
  const resetSession = useItineraryStore((s) => s.reset)
  
  const setInvokeRunning = useItineraryStore((s) => s.setInvokeRunning)
  const applyInvokeStreamEvent = useItineraryStore((s) => s.applyInvokeStreamEvent)
  const setInvokeError = useItineraryStore((s) => s.setInvokeError)

  const currentSession = sessions.find(s => s.id === currentSessionId)
  const hasMessages = currentSession && currentSession.messages.length > 0

  const scenarios = useMemo(() => {
    return [
      {
        key: 'solo' as const,
        label: '一个人',
        subtitle: '独处放松',
        icon: <User className="h-5 w-5 text-indigo-600" />,
        prompt:
          '今天下午我一个人想出去放松一下，时间大概 14:00-19:00，预算 200 元以内。不吃辣，想找点安静的活动（比如咖啡/书店/展览），路程别太远，帮我安排一下。',
      },
      {
        key: 'couple' as const,
        label: '两个人',
        subtitle: '情侣约会',
        icon: <Users className="h-5 w-5 text-emerald-600" />,
        prompt:
          '今天傍晚我和对象两个人想出去约会，时间 17:30-22:00，预算 500 元以内。不要太辣，想要浪漫一点、能拍照打卡的地方，最好顺便安排一顿饭，行程别太赶。',
      },
      {
        key: 'family' as const,
        label: '一家三口',
        subtitle: '亲子出游',
        icon: <Baby className="h-5 w-5 text-amber-600" />,
        prompt:
          '今天下午我们一家三口（2 个大人 + 1 个 5 岁小朋友）想出去玩，时间 13:00-19:00，预算 600 元以内。不吃海鲜，想要亲子友好、少走路、最好室内为主，帮我规划一个 4-6 小时的行程。',
      },
      {
        key: 'friends' as const,
        label: '朋友聚会',
        subtitle: '轻松好玩',
        icon: <UsersRound className="h-5 w-5 text-rose-600" />,
        prompt:
          '这周末下午我和 3 个朋友（共 4 人）想聚一下，时间 14:00-20:00，预算 800 元以内。有 1 个朋友不吃牛，想安排点好玩的活动再吃饭，氛围热闹一点但别排队太久，帮我规划一下。',
      },
    ]
  }, [])

  const canSend = userInput.trim().length > 0

  const handleInitialSend = async () => {
    if (!canSend) return
    const text = userInput.trim()
    const sid = currentSessionId || randomSessionId(sessions.length)
    
    if (!currentSessionId) {
      startSession(sid, text)
    }
    
    setUserInput('')
    // Set running state and call invoke here so ChatView takes over immediately
    useItineraryStore.getState().addLocalMessage({
      id: `msg_${Date.now()}`,
      type: 'human',
      content: text,
    })
    setInvokeRunning()

    try {
      await invokeStream(text, sid, {
        onEvent(event) {
          applyInvokeStreamEvent(event)
        },
      })
    } catch (error) {
      console.error(error)
      setInvokeError(error instanceof Error ? error.message : '未知错误')
      useItineraryStore.getState().addLocalMessage({
        id: `err_${Date.now()}`,
        type: 'ai',
        content: '抱歉，系统出现错误，请稍后再试。',
      })
    }
  }

  return (
    <div className="relative h-screen w-full overflow-hidden bg-[#F6F7FB] flex flex-col">
      <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      
      {/* Header */}
      <div className="shrink-0 h-14 flex items-center justify-between px-4 bg-white/50 backdrop-blur-md border-b border-white/60 z-10">
        <button
          onClick={() => setSidebarOpen(true)}
          className="p-2 -ml-2 text-slate-600 hover:bg-slate-100 rounded-full"
        >
          <Menu className="h-5 w-5" />
        </button>
        <div className="text-[15px] font-semibold text-slate-800">
          ClosedLoop
        </div>
        <button 
          onClick={() => resetSession()}
          className="p-2 -mr-2 text-slate-600 hover:bg-slate-100 rounded-full"
          title="新建对话"
        >
          <Plus className="h-5 w-5" />
        </button>
      </div>

      {hasMessages ? (
        <div className="flex-1 overflow-hidden relative">
          <ChatView />
        </div>
      ) : (
        <main className="flex-1 overflow-y-auto px-5 pt-6 pb-10 bg-gradient-to-b from-[#EAF1FF] via-white to-[#F6F7FB]">
          <div className="mx-auto max-w-[430px]">
            <div className="flex items-center justify-center">
              <div className="mt-2 h-16 w-16 rounded-3xl bg-gradient-to-br from-violet-200 to-sky-200 flex items-center justify-center shadow-sm ring-1 ring-white/80">
                <MapPin className="h-7 w-7 text-slate-700" />
              </div>
            </div>

            <h1 className="mt-6 text-center text-3xl font-semibold tracking-tight text-slate-900">
              你的本地生活助手
            </h1>
            <p className="mt-2 text-center text-sm text-slate-500">
              告诉我你的需求，我来帮你规划吃喝玩乐行程
            </p>

            <div className="mt-10 rounded-[26px] bg-white/75 backdrop-blur border border-white shadow-xl shadow-slate-200/40">
              <div className="px-4 pt-4 text-sm font-semibold text-blue-600">
                {getGreeting()}
              </div>
              <div className="relative px-4 pb-4 pt-2">
                <textarea
                  value={userInput}
                  onChange={(e) => setUserInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault()
                      handleInitialSend()
                    }
                  }}
                  placeholder="例如：今天下午一家三口想出去玩 6 小时，预算 350 以内"
                  rows={1}
                  className="w-full h-[120px] bg-transparent outline-none text-base text-slate-900 placeholder:text-slate-400 resize-none leading-6 overflow-y-auto pt-3 pb-12 pr-16"
                />

                <button
                  type="button"
                  onClick={handleInitialSend}
                  disabled={!canSend}
                  className="absolute bottom-4 right-4 h-11 w-11 rounded-full bg-gradient-to-br from-[#4F86FF] to-[#2D5BFF] text-white flex items-center justify-center disabled:opacity-30 shadow-lg shadow-blue-500/20"
                  aria-label="发送"
                >
                  <SendHorizontal className="h-5 w-5" />
                </button>
              </div>
            </div>

            <div className="mt-8">
              <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                <Sparkles className="h-4 w-4 text-slate-500" />
                热门推荐
              </div>
              <div className="mt-3 grid grid-cols-4 gap-3">
                {scenarios.map((c) => (
                  <QuickCard
                    key={c.key}
                    label={c.label}
                    icon={c.icon}
                    subtitle={c.subtitle}
                    onClick={() => setUserInput(c.prompt)}
                  />
                ))}
              </div>
            </div>

            <div className="mt-5 rounded-3xl bg-white/70 backdrop-blur border border-white/60 shadow-sm p-4 flex items-center justify-between gap-3">
              <div>
                <div className="text-sm font-semibold text-slate-900">
                  专属本地规划
                </div>
                <div className="mt-1 text-xs text-slate-500">
                  智能推荐路线、餐厅和玩法
                  <br />
                  省心更省力
                </div>
              </div>
              <div className="h-16 w-24 rounded-2xl bg-gradient-to-br from-sky-100 to-violet-100 border border-white/70 relative overflow-hidden flex items-center justify-center">
                <img
                  src={homeIllustration}
                  alt="illustration"
                  className="h-[72px] w-auto translate-y-[6px] opacity-95"
                />
              </div>
            </div>

            <div className="mt-10 opacity-70 flex items-center justify-center gap-2 text-xs text-slate-500">
              <Sparkles className="h-4 w-4" />
              <span>本地生活规划 Agent</span>
            </div>

            <div className="mt-10 hidden"></div>
          </div>
        </main>
      )}
    </div>
  )
}
