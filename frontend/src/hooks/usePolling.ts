import { useEffect, useRef } from 'react';

/** 简单轮询（页面可见时才跑），供 /alerts 与 /events 用。 */
export const usePolling = (callback: () => void, intervalMs: number, enabled = true): void => {
  const saved = useRef(callback);
  saved.current = callback;

  useEffect(() => {
    if (!enabled) return;
    const timer = window.setInterval(() => {
      if (document.visibilityState === 'visible') saved.current();
    }, intervalMs);
    return () => window.clearInterval(timer);
  }, [intervalMs, enabled]);
};
