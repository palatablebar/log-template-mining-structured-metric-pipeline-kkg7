import { StatusPill } from './StatusPill';
import { formatCount } from '../../utils/formatCount';
import { formatTime } from '../../utils/formatTime';
import type { Source } from '../../types/models';

interface SourceCardProps {
  source: Source;
  active?: boolean;
  onSelect?: (source: Source) => void;
  compact?: boolean;
}

/** 业务共享组件：/sources 左栏与 /import 的「待归类归属源」都用它。 */
export const SourceCard = ({ source, active, onSelect, compact }: SourceCardProps) => (
  <button type="button" className={`side-item${active ? ' active' : ''}`} onClick={() => onSelect?.(source)}>
    <span className="title">
      {source.name} <span className="mono" style={{ color: 'var(--ink-dim)' }}>/ {source.log_format}</span>
    </span>
    <span className="sub">
      {source.host_group || '未分组'} · {source.rate_per_min}/min · {formatCount(source.event_count)} 行
    </span>
    {compact ? null : (
      <>
        <span className="sub">
          规则 {source.rule_count} · 模板 {source.template_count} · 待归类 <b>{source.pending_count}</b>
        </span>
        <span className="sub">
          <StatusPill status={source.collect_status} kind="collect" /> <span>{formatTime(source.last_collected_at)}</span>
        </span>
      </>
    )}
  </button>
);
