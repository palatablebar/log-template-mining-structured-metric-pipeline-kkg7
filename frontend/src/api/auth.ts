import { api } from './client';
import type { User } from '../types/models';

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: User;
  message: string;
}

export const authApi = {
  login: (email: string, password: string) =>
    api.post<LoginResponse>('/auth/login', { email, password }),
  me: () => api.get<User>('/auth/me'),
  quota: () => api.get<{ used: number; limit: number; remaining: number; date: string }>('/auth/quota'),
};
