export const formatTime = (text: string | null | undefined): string => {
  if (!text) return '—';
  return text.replace('T', ' ').slice(0, 19);
};

export const formatClock = (text: string | null | undefined): string => {
  if (!text) return '—';
  const normalized = text.replace('T', ' ');
  return normalized.slice(11, 16) || normalized;
};

export const formatBucket = (text: string | null | undefined): string => {
  if (!text) return '—';
  return text.replace('T', ' ').slice(11, 16);
};

export const relativeAgo = (text: string | null | undefined): string => {
  if (!text) return '—';
  return text.replace('T', ' ').slice(5, 16);
};
