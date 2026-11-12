import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore';

/** 未登录跳 /login；已登录但用户信息未加载时补一次 /auth/me。 */
export const useAuthGuard = (): void => {
  const navigate = useNavigate();
  const user = useAuthStore((state) => state.user);
  const loadMe = useAuthStore((state) => state.loadMe);

  useEffect(() => {
    if (user) return;
    void loadMe().then((loaded) => {
      if (!loaded) navigate('/login', { replace: true });
    });
  }, [user, loadMe, navigate]);
};
