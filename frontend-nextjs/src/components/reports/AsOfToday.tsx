import { CalendarClock } from 'lucide-react'

/** For reports that show today's position and ignore the period picked at the top (finding F6 of the review). */
export function AsOfToday({ children }: { children: React.ReactNode }) {
  return (
    <p className="flex items-start gap-2 rounded-xl border border-sky-500/20 bg-sky-500/10 px-3 py-2 text-sm text-sky-900 dark:text-sky-200">
      <CalendarClock className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
      <span>{children}</span>
    </p>
  )
}
