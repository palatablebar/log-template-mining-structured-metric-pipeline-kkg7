import { LEVEL_LABELS } from '../../constants/enums';
import type { EventLevel } from '../../types/models';

export const LevelBadge = ({ level }: { level: EventLevel | string }) => (
  <span className={`level ${level}`}>{LEVEL_LABELS[level as EventLevel] ?? String(level).toUpperCase()}</span>
);
