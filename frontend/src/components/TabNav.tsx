import { motion } from 'framer-motion'
import type { ReactNode } from 'react'

export type TabId =
  | 'overview'
  | 'demo'
  | 'inference'
  | 'filter'
  | 'guardrails'
  | 'stream'
  | 'review'
  | 'business'
  | 'alerts'
  | 'models'
  | 'experiments'
  | 'monitoring'

interface TabNavProps {
  active: TabId
  onChange: (tab: TabId) => void
}

const TABS: { id: TabId; label: string }[] = [
  { id: 'overview', label: 'Overview' },
  { id: 'demo', label: '🎬 Demo' },
  { id: 'inference', label: 'Inference' },
  { id: 'filter', label: 'Filter API' },
  { id: 'guardrails', label: 'Guardrails' },
  { id: 'stream', label: 'Live Stream' },
  { id: 'review', label: 'Review Queue' },
  { id: 'business', label: 'Business' },
  { id: 'alerts', label: 'Alerts' },
  { id: 'models', label: 'Models' },
  { id: 'experiments', label: 'Experiments' },
  { id: 'monitoring', label: 'Monitoring' },
]

export function TabNav({ active, onChange }: TabNavProps) {
  return (
    <nav className="flex items-center gap-1 overflow-x-auto border-b border-zinc-800/60">
      {TABS.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onChange(tab.id)}
          className={`relative shrink-0 px-4 py-2.5 text-sm font-medium transition-colors ${
            active === tab.id
              ? 'text-zinc-100'
              : 'text-zinc-500 hover:text-zinc-300'
          }`}
        >
          {tab.label}
          {active === tab.id && (
            <motion.div
              layoutId="tab-indicator"
              className="absolute inset-x-0 -bottom-px h-0.5 bg-blue-500"
              transition={{ type: 'spring', stiffness: 400, damping: 30 }}
            />
          )}
        </button>
      ))}
    </nav>
  )
}

export function TabContent({ children }: { children: ReactNode }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, ease: 'easeOut' }}
    >
      {children}
    </motion.div>
  )
}
