import { ALERT_STATUS_LABELS, TEMPLATE_STATUS_LABELS } from '../../constants/enums';
import type { AlertStatus, TemplateStatus } from '../../types/models';

export const StatusPill = ({ status, kind = 'template' }: { status: string; kind?: 'template' | 'alert' | 'collect' }) => {
  const label =
    kind === 'alert'
      ? ALERT_STATUS_LABELS[status as AlertStatus] ?? status
      : kind === 'collect'
        ? ({ active: '采集中', paused: '已暂停', error: '采集异常' } as Record<string, string>)[status] ?? status
        : TEMPLATE_STATUS_LABELS[status as TemplateStatus] ?? status;
  return (
    <span className={`pill ${status}`}>
      <i className="dot" />
      {label}
    </span>
  );
};
