import { X, Plus, MessageSquare } from 'lucide-react'
import { useItineraryStore } from '../store/useItineraryStore'
import clsx from 'clsx'

type SidebarProps = {
  isOpen: boolean
  onClose: () => void
}

export function Sidebar({ isOpen, onClose }: SidebarProps) {
  const sessions = useItineraryStore((s) => s.sessions)
  const currentSessionId = useItineraryStore((s) => s.currentSessionId)
  const switchSession = useItineraryStore((s) => s.switchSession)
  const deleteSession = useItineraryStore((s) => s.deleteSession)
  const reset = useItineraryStore((s) => s.reset)

  const handleNewChat = () => {
    reset()
    onClose()
  }

  return (
    <>
      {/* Backdrop */}
      <div
        className={clsx(
          'fixed inset-0 z-40 bg-black/40 transition-opacity',
          isOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'
        )}
        onClick={onClose}
      />

      {/* Drawer */}
      <div
        className={clsx(
          'fixed inset-y-0 left-0 z-50 w-[280px] bg-white shadow-xl transition-transform duration-300 ease-in-out flex flex-col',
          isOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        <div className="flex items-center justify-between p-4 border-b border-slate-100">
          <h2 className="text-lg font-semibold text-slate-800">历史记录</h2>
          <button
            onClick={onClose}
            className="p-2 text-slate-500 hover:bg-slate-100 rounded-full"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-4">
          <button
            onClick={handleNewChat}
            className="w-full flex items-center justify-center gap-2 py-3 px-4 bg-blue-50 text-blue-600 rounded-xl font-medium hover:bg-blue-100 transition-colors"
          >
            <Plus className="w-5 h-5" />
            新对话
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-2 pb-4 space-y-1">
          {sessions.length === 0 ? (
            <div className="text-center text-sm text-slate-400 mt-10">
              暂无历史记录
            </div>
          ) : (
            sessions.map((session) => (
              <div
                key={session.id}
                className={clsx(
                  'group flex items-center justify-between p-3 rounded-xl cursor-pointer transition-colors',
                  currentSessionId === session.id
                    ? 'bg-blue-50/50'
                    : 'hover:bg-slate-50'
                )}
                onClick={() => {
                  switchSession(session.id)
                  onClose()
                }}
              >
                <div className="flex items-center gap-3 overflow-hidden">
                  <MessageSquare className={clsx("w-5 h-5 shrink-0", currentSessionId === session.id ? "text-blue-500" : "text-slate-400")} />
                  <span className={clsx("truncate text-sm font-medium", currentSessionId === session.id ? "text-blue-700" : "text-slate-700")}>
                    {session.title}
                  </span>
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    deleteSession(session.id)
                  }}
                  className="opacity-0 group-hover:opacity-100 p-1.5 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-all"
                  title="删除"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            ))
          )}
        </div>
      </div>
    </>
  )
}