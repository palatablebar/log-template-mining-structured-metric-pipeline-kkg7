import type { ReactNode } from 'react';
import { useAuthStore } from '../../stores/authStore';
import type { Role } from '../../types/models';
import { EmptyState } from './EmptyState';

interface RequireRoleProps {
  roles: Role[];
  message: string;
  children: ReactNode;
}

/** 页面级角色门禁：角色不符时给出可恢复的空态，而不是白屏。 */
export const RequireRole = ({ roles, message, children }: RequireRoleProps) => {
  const user = useAuthStore((state) => state.user);
  if (!user) return null;
  if (!roles.includes(user.role)) {
    return <EmptyState title="当前账号没有该站台权限" hint={message} />;
  }
  return <>{children}</>;
};
