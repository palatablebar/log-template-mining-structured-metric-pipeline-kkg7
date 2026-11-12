import { ApiError } from '../types/api';

export const errorMessage = (error: unknown, fallback = '操作失败，请稍后重试'): string => {
  if (error instanceof ApiError) {
    return error.detail ? `${error.message}（${error.detail}）` : error.message;
  }
  if (error instanceof Error) return error.message;
  return fallback;
};

export const errorCode = (error: unknown): string => (error instanceof ApiError ? error.code : 'UNKNOWN');
