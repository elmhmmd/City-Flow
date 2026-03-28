import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../AuthContext'
import { Map, BarChart2, LogOut } from 'lucide-react'

export default function Layout() {
  const { user, logout } = useAuth()

  return (
    <div className="flex h-screen bg-gray-950 text-white">
      {/* Sidebar */}
      <aside className="w-56 bg-gray-900 border-r border-gray-800 flex flex-col">
        <div className="px-5 py-4 border-b border-gray-800">
          <h1 className="text-lg font-bold">CityFlow</h1>
          <p className="text-xs text-gray-400 mt-0.5">{user?.username} · {user?.role}</p>
        </div>

        <nav className="flex-1 p-3 space-y-1">
          <NavLink
            to="/map"
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                isActive ? 'bg-blue-600 text-white' : 'text-gray-400 hover:bg-gray-800 hover:text-white'
              }`
            }
          >
            <Map size={16} /> Demand Map
          </NavLink>
          <NavLink
            to="/performance"
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                isActive ? 'bg-blue-600 text-white' : 'text-gray-400 hover:bg-gray-800 hover:text-white'
              }`
            }
          >
            <BarChart2 size={16} /> Performance
          </NavLink>
        </nav>

        <div className="p-3 border-t border-gray-800">
          <button
            onClick={logout}
            className="flex items-center gap-3 px-3 py-2 w-full rounded-lg text-sm text-gray-400 hover:bg-gray-800 hover:text-white transition-colors"
          >
            <LogOut size={16} /> Sign out
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  )
}
