import { LayoutGrid, FileText, Key, Cpu, Users } from 'lucide-react';
import { clearSession, storedUser } from './auth';
import { useNavigate } from 'react-router-dom';

interface NavItem {
  to: string;
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  adminOnly?: boolean;
}

/* dashboard nav — Sidebar renders it, Header reuses it for its tabs */
export const navItems: NavItem[] = [
  { to: '/dashboard', icon: LayoutGrid, label: 'Overview' },
  { to: '/dashboard/logs', icon: FileText, label: 'Logs' },
  { to: '/dashboard/models', icon: Cpu, label: 'Models' },
  { to: '/dashboard/settings', icon: Key, label: 'Settings' },
  { to: '/dashboard/users', icon: Users, label: 'Users', adminOnly: true },
];

/* members manage their own BYOK keys + password; only Users is admin-only */
export function visibleNavItems(): NavItem[] {
  const admin = storedUser()?.role === 'admin';
  return navItems.filter((i) => !i.adminOnly || admin);
}

export function useSignOut() {
  const navigate = useNavigate();
  return () => {
    clearSession();
    navigate('/');
  };
}

export function signOut() {
  clearSession();
  if (typeof window !== 'undefined') window.location.href = '/';
}
