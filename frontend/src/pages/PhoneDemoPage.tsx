export default function PhoneDemoPage() {
  return (
    <div className="min-h-screen bg-slate-100 flex items-center justify-center p-8">
      <div className="relative w-[430px] h-[900px] rounded-[64px] bg-neutral-950 p-[12px] shadow-2xl">
        <div className="absolute left-[-4px] top-[170px] h-16 w-1 rounded-l bg-neutral-800" />
        <div className="absolute right-[-4px] top-[260px] h-24 w-1 rounded-r bg-neutral-800" />

        <div className="relative h-full w-full overflow-hidden rounded-[52px] bg-white">
          <div className="pointer-events-none absolute left-1/2 top-[18px] z-20 h-[36px] w-[126px] -translate-x-1/2 rounded-full bg-black" />
          <iframe
            src="/app"
            title="closedloop-demo"
            className="h-full w-full border-0"
          />
        </div>
      </div>
    </div>
  )
}

