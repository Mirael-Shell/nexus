import { useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import type { TabId } from './TabNav'

interface CommandPaletteProps {
  open: boolean
  onClose: () => void
  onNavigate: (tab: TabId) => void
}

const COMMANDS: { id: string; label: string; hint: string; tab: TabId }[] = [
  { id: 'overview', label: 'Go to Overview', hint: 'Dashboard home', tab: 'overview' },
  { id: 'demo', label: 'Run Live Demo', hint: 'Orchestrated end-to-end scenario', tab: 'demo' },
  { id: 'predict', label: 'Classify Text', hint: 'Run text prediction', tab: 'inference' },
  { id: 'filter', label: 'Filter API', hint: 'Production content filter', tab: 'filter' },
  { id: 'guardrails', label: 'Guardrails', hint: 'Multi-layer moderation pipeline', tab: 'guardrails' },
  { id: 'image', label: 'Moderate Image', hint: 'Upload image for moderation', tab: 'inference' },
  { id: 'stream', label: 'Live Stream', hint: 'Real-time WebSocket moderation', tab: 'stream' },
  { id: 'review', label: 'Review Queue', hint: 'Active learning — label uncertain predictions', tab: 'review' },
  { id: 'business', label: 'Business Dashboard', hint: 'Precision, funnel, cost analysis', tab: 'business' },
  { id: 'alerts', label: 'Alerting System', hint: 'Webhooks, thresholds, alert history', tab: 'alerts' },
  { id: 'models', label: 'Model Registry', hint: 'View model versions', tab: 'models' },
  { id: 'experiments', label: 'A/B Experiments', hint: 'Bayesian analysis', tab: 'experiments' },
  { id: 'drift', label: 'Drift Detection', hint: 'Run drift analysis', tab: 'monitoring' },
  { id: 'cost', label: 'Cost Analytics', hint: 'Revenue & ROI', tab: 'monitoring' },
  { id: 'mlflow', label: 'Open MLflow ↗', hint: 'External', tab: 'overview' },
  { id: 'grafana', label: 'Open Grafana ↗', hint: 'External', tab: 'overview' },
]

export function CommandPalette({ open, onClose, onNavigate }: CommandPaletteProps) {
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState(0)

  const filtered = COMMANDS.filter((c) =>
    c.label.toLowerCase().includes(query.toLowerCase()),
  )

  useEffect(() => {
    if (open) {
      setQuery('')
      setSelected(0)
    }
  }, [open])

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setSelected((s) => Math.min(s + 1, filtered.length - 1))
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault()
        setSelected((s) => Math.max(s - 1, 0))
      }
      if (e.key === 'Enter' && filtered[selected]) {
        const cmd = filtered[selected]
        if (cmd.id === 'mlflow') {
          window.open('http://localhost:5001', '_blank')
        } else if (cmd.id === 'grafana') {
          window.open('http://localhost:3030', '_blank')
        } else {
          onNavigate(cmd.tab)
        }
        onClose()
      }
    }
    if (open) window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [open, filtered, selected, onClose, onNavigate])

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm"
            onClick={onClose}
          />
          <motion.div
            initial={{ opacity: 0, scale: 0.96, y: -10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: -10 }}
            transition={{ duration: 0.15 }}
            className="fixed left-1/2 top-[30%] z-50 w-full max-w-lg -translate-x-1/2"
          >
            <div className="overflow-hidden rounded-xl border border-zinc-700 bg-zinc-900 shadow-2xl">
              <input
                autoFocus
                type="text"
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value)
                  setSelected(0)
                }}
                placeholder="Search commands…"
                className="w-full border-b border-zinc-800 bg-transparent px-4 py-3 text-sm text-zinc-200 placeholder-zinc-600 focus:outline-none"
              />
              <div className="max-h-72 overflow-y-auto p-1">
                {filtered.map((cmd, i) => (
                  <button
                    key={cmd.id}
                    onMouseEnter={() => setSelected(i)}
                    onClick={() => {
                      if (cmd.id === 'mlflow') {
                        window.open('http://localhost:5001', '_blank')
                      } else if (cmd.id === 'grafana') {
                        window.open('http://localhost:3030', '_blank')
                      } else {
                        onNavigate(cmd.tab)
                      }
                      onClose()
                    }}
                    className={`flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-sm transition-colors ${
                      i === selected ? 'bg-zinc-800' : 'hover:bg-zinc-800/50'
                    }`}
                  >
                    <span className="text-zinc-200">{cmd.label}</span>
                    <span className="text-xs text-zinc-600">{cmd.hint}</span>
                  </button>
                ))}
                {filtered.length === 0 && (
                  <div className="py-6 text-center text-sm text-zinc-600">
                    No commands found
                  </div>
                )}
              </div>
              <div className="border-t border-zinc-800 px-4 py-2 text-xs text-zinc-700">
                ↑↓ navigate · ↵ select · esc close
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
