import { redirect } from 'react-router-dom';
import { tokenStore } from '../api/client';

/** 路由 loader：没有 token 直接回登录页（不发请求，避免闪一下 401）。 */
export const requireAuth = () => {
  if (!tokenStore.get()) return redirect('/login');
  return null;
};
