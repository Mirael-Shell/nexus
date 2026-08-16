import { useEffect, useState } from 'react'
import { CommandPalette } from './components/CommandPalette'
import { Overview } from './components/Overview'
import { HealthBadge } from './components/HealthBadge'
import { TabContent, TabNav, type TabId } from './components/TabNav'
import { CostPanel } from './components/CostPanel'
import { DriftPanel } from './components/DriftPanel'
import { ExperimentsPanel } from './components/ExperimentsPanel'
import { ImagePanel } from './components/ImagePanel'
import { ModelsPanel } from './components/ModelsPanel'
import { PredictPanel } from './components/PredictPanel'
import { FilterPanel } from './components/FilterPanel'
import { GuardrailsPanel } from './components/GuardrailsPanel'
import { LiveStreamPanel } from './components/LiveStreamPanel'
import { DemoPanel } from './components/DemoPanel'
import { ReviewQueuePanel } from './components/ReviewQueuePanel'
import { BusinessPanel } from './components/BusinessPanel'
import { AlertPanel } from './components/AlertPanel'

function App() {
  const [tab, setTab] = useState<TabId>('overview')
  const [paletteOpen, setPaletteOpen] = useState(false)

  // Cmd+K shortcut
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        setPaletteOpen((v) => !v)
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-200">
      {/* Header */}
      <header className="sticky top-0 z-20 border-b border-zinc-800/60 bg-zinc-950/80 backdrop-blur-xl">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3">
          {/* Logo */}
          <button
            onClick={() => setTab('overview')}
            className="flex items-center gap-3"
          >
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-blue-600 to-blue-800 text-sm font-bold text-white shadow-lg shadow-blue-900/20">
              N
            </div>
            <div className="hidden sm:block">
              <h1 className="text-sm font-bold tracking-tight text-zinc-100">NEXUS</h1>
              <p className="text-[10px] text-zinc-600">AI Platform</p>
            </div>
          </button>

          {/* Center: search trigger */}
          <button
            onClick={() => setPaletteOpen(true)}
            className="flex items-center gap-2 rounded-lg border border-zinc-800 bg-zinc-900/50 px-3 py-1.5 text-xs text-zinc-600 transition hover:border-zinc-700 hover:text-zinc-400"
          >
            <span>⌘K</span>
            <span className="hidden sm:inline">Search…</span>
          </button>

          {/* Right: status */}
          <div className="flex items-center gap-3">
            <HealthBadge />
          </div>
        </div>

        {/* Tab navigation */}
        <div className="mx-auto max-w-6xl px-6">
          <TabNav active={tab} onChange={setTab} />
        </div>
      </header>

      {/* Main content */}
      <main className="mx-auto max-w-6xl px-6 py-6">
        {tab === 'overview' && (
          <TabContent>
            <Overview onNavigate={(t) => setTab(t as TabId)} />
          </TabContent>
        )}

        {tab === 'demo' && (
          <TabContent>
            <DemoPanel />
          </TabContent>
        )}

        {tab === 'inference' && (
          <TabContent>
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              <PredictPanel />
              <ImagePanel />
            </div>
          </TabContent>
        )}

        {tab === 'filter' && (
          <TabContent>
            <FilterPanel />
          </TabContent>
        )}

        {tab === 'guardrails' && (
          <TabContent>
            <GuardrailsPanel />
          </TabContent>
        )}

        {tab === 'stream' && (
          <TabContent>
            <LiveStreamPanel />
          </TabContent>
        )}

        {tab === 'review' && (
          <TabContent>
            <ReviewQueuePanel />
          </TabContent>
        )}

        {tab === 'business' && (
          <TabContent>
            <BusinessPanel />
          </TabContent>
        )}

        {tab === 'alerts' && (
          <TabContent>
            <AlertPanel />
          </TabContent>
        )}

        {tab === 'models' && (
          <TabContent>
            <ModelsPanel />
          </TabContent>
        )}

        {tab === 'experiments' && (
          <TabContent>
            <ExperimentsPanel />
          </TabContent>
        )}

        {tab === 'monitoring' && (
          <TabContent>
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              <DriftPanel />
              <CostPanel />
            </div>
          </TabContent>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-zinc-800/60 py-4 text-center text-xs text-zinc-700">
        NEXUS · End-to-End AI Platform · MLOps + AI PM Portfolio
      </footer>

      {/* Command palette */}
      <CommandPalette
        open={paletteOpen}
        onClose={() => setPaletteOpen(false)}
        onNavigate={(t) => setTab(t)}
      />
    </div>
  )
}

export default App
