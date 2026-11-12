import { useEffect, useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { ROLE_LABELS, ROLE_STATIONS } from '../../constants/enums';
import { metaApi } from '../../api/meta';
import { useAuthStore } from '../../stores/authStore';
import type { Overview } from '../../types/models';

const NAV = [
  { to: '/sources', label: '日志源', idx: '01', countKey: 'sources' },
  { to: '/templates', label: '模板库', idx: '02', countKey: 'templates' },
  { to: '/events', label: '事件与趋势', idx: '03', countKey: 'events' },
  { to: '/alerts', label: '告警台', idx: '04', countKey: 'alerts' },
  { to: '/import', label: '导入挖掘', idx: '05', countKey: 'pending' },
] as const;

export const StationShell = ({ children }: { children: React.ReactNode }) => {
  const user = useAuthStore((state) => state.user);
  const logout = useAuthStore((state) => state.logout);
  const navigate = useNavigate();
  const [overview, setOverview] = useState<Overview | null>(null);

  useEffect(() => {
    metaApi
      .overview()
      .then(setOverview)
      .catch(() => setOverview(null));
  }, []);

  const countOf = (key: string): string => {
    if (!overview) return '—';
    if (key === 'alerts') return String(overview.alerts.firing);
    if (key === 'pending') return String(overview.pending_events);
    if (key === 'events') return overview.events >= 10000 ? `${(overview.events / 10000).toFixed(1)}w` : String(overview.events);
    return String((overview as unknown as Record<string, number>)[key] ?? '—');
  };

  return (
    <div className="station">
      <aside className="rail">
        <div className="rail-brand">
          <span className="mark">
            log<em>mine</em>
          </span>
          <span className="sub">云栖 IDC · 日志观测站</span>
        </div>
        <nav className="rail-nav">
          {NAV.map((item) => (
            <NavLink key={item.to} to={item.to} className={({ isActive }) => `rail-link${isActive ? ' active' : ''}`}>
              <span className="idx">{item.idx}</span>
              <span>{item.label}</span>
              <span className="count">{countOf(item.countKey)}</span>
            </NavLink>
          ))}
        </nav>
        <div className="rail-foot">
          <div className="rail-user">
            <b>{user?.display_name ?? '未登录'}</b>
            {user?.email}
            <div className="rail-station-tag">{user ? ROLE_LABELS[user.role] : ''} · {user ? ROLE_STATIONS[user.role] : ''}</div>
          </div>
          <button
            type="button"
            className="btn small ghost"
            onClick={() => {
              logout();
              navigate('/login', { replace: true });
            }}
          >
            结束值班
          </button>
        </div>
      </aside>
      <main className="main">{children}</main>
    </div>
  );
};
