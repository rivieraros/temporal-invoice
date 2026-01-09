import { useState } from 'react'
import {
  Calendar,
  Bell,
  Settings,
  Moon,
  Sun,
  RefreshCw,
  Wifi,
} from 'lucide-react'

interface HeaderProps {
  period: string
  lastSync: string
  onPeriodChange?: (period: string) => void
}

// Generate period options (last 6 months)
function getPeriodOptions(): { value: string; label: string }[] {
  const options: { value: string; label: string }[] = []
  const now = new Date()
  for (let i = 0; i < 6; i++) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1)
    const value = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
    const label = d.toLocaleDateString('en-US', { month: 'long', year: 'numeric' })
    options.push({ value, label })
  }
  return options
}

export function Header({ period, lastSync, onPeriodChange }: HeaderProps) {
  const [isDark, setIsDark] = useState(true)
  const [showSettings, setShowSettings] = useState(false)
  const [isLive, setIsLive] = useState(true)

  const periodOptions = getPeriodOptions()

  return (
    <div className="flex items-center justify-between mb-6">
      {/* Left: Title & Period Selector */}
      <div className="flex items-center gap-6">
        <h1 className="text-2xl font-bold text-white">Mission Control</h1>
        
        {/* Period Selector */}
        <div className="relative">
          <select
            value={period}
            onChange={(e) => onPeriodChange?.(e.target.value)}
            className="appearance-none bg-slate-800 border border-slate-700 rounded-lg px-4 py-2 pr-10 text-white text-sm focus:outline-none focus:ring-2 focus:ring-purple-500 cursor-pointer"
          >
            {periodOptions.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
          <Calendar
            size={16}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none"
          />
        </div>

        {/* Live Badge */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => setIsLive(!isLive)}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-semibold transition-all ${
              isLive
                ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40'
                : 'bg-slate-700/50 text-slate-400 border border-slate-600'
            }`}
          >
            <Wifi size={12} className={isLive ? 'animate-pulse' : ''} />
            {isLive ? 'LIVE' : 'PAUSED'}
          </button>
        </div>
      </div>

      {/* Right: Actions */}
      <div className="flex items-center gap-4">
        {/* Last Sync */}
        <div className="flex items-center gap-2 text-sm text-slate-400">
          <RefreshCw size={14} />
          <span>Synced {lastSync}</span>
        </div>

        {/* Notifications */}
        <button className="relative p-2 rounded-lg bg-slate-800 border border-slate-700 hover:bg-slate-700 transition-colors">
          <Bell size={18} className="text-slate-400" />
          <span className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-red-500 text-white text-[10px] flex items-center justify-center font-bold">
            3
          </span>
        </button>

        {/* Theme Toggle */}
        <button
          onClick={() => setIsDark(!isDark)}
          className="p-2 rounded-lg bg-slate-800 border border-slate-700 hover:bg-slate-700 transition-colors"
        >
          {isDark ? (
            <Moon size={18} className="text-slate-400" />
          ) : (
            <Sun size={18} className="text-amber-400" />
          )}
        </button>

        {/* Settings */}
        <button
          onClick={() => setShowSettings(!showSettings)}
          className="p-2 rounded-lg bg-slate-800 border border-slate-700 hover:bg-slate-700 transition-colors"
        >
          <Settings size={18} className="text-slate-400" />
        </button>
      </div>
    </div>
  )
}
