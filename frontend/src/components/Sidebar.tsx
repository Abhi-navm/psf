'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useState } from 'react';
import { 
  LayoutDashboard, Upload, History, Settings, HelpCircle, 
  ChevronLeft, ChevronRight, Sparkles, Users, Plus, Check
} from 'lucide-react';
import { useUser } from '@/lib/UserContext';

const navItems = [
  { name: 'Dashboard', href: '/', icon: LayoutDashboard },
  { name: 'Upload', href: '/upload', icon: Upload },
  { name: 'History', href: '/history', icon: History },
  { name: 'Settings', href: '/settings', icon: Settings },
  { name: 'Help', href: '/help', icon: HelpCircle },
];

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const [collapsed, setCollapsed] = useState(false);
  const { userId, setUserId } = useUser();
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [newUser, setNewUser] = useState('');

  const presetUsers = ['default', 'userA', 'userB', 'userC'];

  const handleSwitchUser = (id: string) => {
    setUserId(id);
    setShowUserMenu(false);
    router.refresh();
    window.location.reload();
  };

  const handleAddUser = () => {
    const trimmed = newUser.trim();
    if (trimmed && !presetUsers.includes(trimmed)) {
      handleSwitchUser(trimmed);
      setNewUser('');
    }
  };

  return (
    <aside className={`${collapsed ? 'w-16' : 'w-64'} bg-white border-r border-slate-200 flex flex-col transition-all duration-300`}>
      {/* Logo */}
      <div className="p-4 flex items-center gap-2 border-b border-slate-100">
        <div className="w-8 h-8 bg-indigo-500 rounded-lg flex items-center justify-center flex-shrink-0">
          <Sparkles className="w-5 h-5 text-white" />
        </div>
        {!collapsed && <span className="font-bold text-slate-800">AI Pitch Analyzer</span>}
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-3 space-y-1">
        {navItems.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.name}
              href={item.href}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-indigo-50 text-indigo-600'
                  : 'text-slate-600 hover:bg-slate-50 hover:text-slate-800'
              }`}
            >
              <item.icon className={`w-5 h-5 flex-shrink-0 ${isActive ? 'text-indigo-500' : ''}`} />
              {!collapsed && <span>{item.name}</span>}
            </Link>
          );
        })}
      </nav>

      {/* Collapse toggle */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="p-3 border-t border-slate-100 flex items-center justify-center text-slate-400 hover:text-slate-600"
      >
        {collapsed ? <ChevronRight className="w-5 h-5" /> : <ChevronLeft className="w-5 h-5" />}
      </button>

      {/* User selector */}
      <div className="relative border-t border-slate-100 p-3">
        <button
          onClick={() => setShowUserMenu(!showUserMenu)}
          className="flex items-center gap-2 w-full px-3 py-2 rounded-lg text-sm font-medium text-slate-600 hover:bg-slate-50 transition-colors"
        >
          <div className="w-7 h-7 bg-indigo-100 rounded-full flex items-center justify-center flex-shrink-0">
            <Users className="w-4 h-4 text-indigo-600" />
          </div>
          {!collapsed && (
            <span className="truncate">{userId}</span>
          )}
        </button>

        {showUserMenu && !collapsed && (
          <div className="absolute bottom-full left-3 right-3 mb-1 bg-white border border-slate-200 rounded-lg shadow-lg py-1 z-50">
            <div className="px-3 py-1.5 text-xs font-semibold text-slate-400 uppercase">Switch User</div>
            {presetUsers.map((u) => (
              <button
                key={u}
                onClick={() => handleSwitchUser(u)}
                className={`flex items-center gap-2 w-full px-3 py-2 text-sm hover:bg-slate-50 ${
                  userId === u ? 'text-indigo-600 font-medium' : 'text-slate-600'
                }`}
              >
                {userId === u && <Check className="w-3.5 h-3.5" />}
                <span className={userId === u ? '' : 'ml-5'}>{u}</span>
              </button>
            ))}
            <div className="border-t border-slate-100 mt-1 pt-1 px-3 pb-2">
              <div className="flex gap-1">
                <input
                  type="text"
                  value={newUser}
                  onChange={(e) => setNewUser(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleAddUser()}
                  placeholder="Custom ID..."
                  className="flex-1 text-sm px-2 py-1 border border-slate-200 rounded focus:outline-none focus:border-indigo-300"
                />
                <button
                  onClick={handleAddUser}
                  className="p-1 text-indigo-500 hover:text-indigo-700"
                >
                  <Plus className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}
