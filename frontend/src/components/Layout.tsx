import { ReactNode } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { Zap, Bell, Sun, Moon, Settings, Calendar, ChevronDown } from 'lucide-react'
import { useState } from 'react'

interface LayoutProps {
  children: ReactNode
}

export function Layout({ children }: LayoutProps) {
  const [isDark, setIsDark] = useState(true)
  const location = useLocation()
  const navigate = useNavigate()

  return (
    <div className={`min-h-screen ${isDark ? 'bg-slate-900' : 'bg-gray-50'}`}>
      {/* Header */}
      <header className={`${isDark ? 'bg-slate-800 border-slate-700' : 'bg-white border-gray-200'} border-b px-6 py-4`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link to="/mission-control" className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-purple-500 to-blue-600 flex items-center justify-center">
                <Zap size={24} className="text-white" />
              </div>
              <div>
                <h1 className={`text-xl font-bold ${isDark ? 'text-white' : 'text-gray-900'}`}>AP Agent</h1>
                <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-gray-500'}`}>Mission Control</p>
              </div>
            </Link>

            <div className={`ml-8 px-4 py-2 rounded-lg ${isDark ? 'bg-slate-800/50 hover:bg-slate-700' : 'bg-gray-100 hover:bg-gray-200'} flex items-center gap-2 cursor-pointer`}>
              <Calendar size={16} className={isDark ? 'text-slate-400' : 'text-gray-500'} />
              <span className={isDark ? 'text-white' : 'text-gray-900'}>November 2025</span>
              <ChevronDown size={16} className={isDark ? 'text-slate-400' : 'text-gray-500'} />
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-emerald-500/10">
              <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              <span className="text-sm text-emerald-400">Live</span>
            </div>
            <button className={`p-2 rounded-lg ${isDark ? 'hover:bg-slate-700' : 'hover:bg-gray-100'} relative`}>
              <Bell size={20} className={isDark ? 'text-slate-400' : 'text-gray-500'} />
              <span className="absolute -top-1 -right-1 w-5 h-5 bg-amber-500 rounded-full text-[10px] text-white flex items-center justify-center font-bold">12</span>
            </button>
            <button 
              onClick={() => setIsDark(!isDark)} 
              className={`p-2 rounded-lg ${isDark ? 'hover:bg-slate-700' : 'hover:bg-gray-100'}`}
            >
              {isDark ? <Sun size={20} className="text-slate-400" /> : <Moon size={20} className="text-gray-500" />}
            </button>
            <button 
              onClick={() => navigate('/settings')}
              className={`p-2 rounded-lg ${isDark ? 'hover:bg-slate-700' : 'hover:bg-gray-100'} ${location.pathname === '/settings' ? 'bg-slate-700' : ''}`}
            >
              <Settings size={20} className={location.pathname === '/settings' ? 'text-purple-400' : isDark ? 'text-slate-400' : 'text-gray-500'} />
            </button>
          </div>
        </div>

        {/* Breadcrumb */}
        {location.pathname !== '/mission-control' && (
          <div className={`mt-3 pt-3 border-t ${isDark ? 'border-slate-700' : 'border-gray-200'}`}>
            <nav className="flex items-center gap-2 text-sm">
              <Link 
                to="/mission-control" 
                className={`${isDark ? 'text-slate-400 hover:text-white' : 'text-gray-500 hover:text-gray-900'}`}
              >
                Mission Control
              </Link>
              <span className={isDark ? 'text-slate-600' : 'text-gray-400'}>/</span>
              <span className={isDark ? 'text-white' : 'text-gray-900'}>
                {location.pathname.split('/').pop()}
              </span>
            </nav>
          </div>
        )}
      </header>

      {/* Main Content */}
      <main className="p-6">
        {children}
      </main>
    </div>
  )
}
