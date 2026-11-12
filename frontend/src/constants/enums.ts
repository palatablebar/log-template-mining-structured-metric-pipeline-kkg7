/**
 * 共享枚举（前端唯一来源，必须与 backend/src/constants/enums.py 逐项一致）。
 * 出现位置：constants/enums.ts、stores/*、components/common/LevelBadge.tsx、
 * components/common/TemplateTokenStrip.tsx、pages/{Templates,Events,Alerts}.tsx
 */
import type { AlertStatus, EventLevel, Role, SlotType, TemplateStatus } from '../types/models';

export const ROLES: Role[] = ['admin', 'engineer', 'viewer'];

export const ROLE_LABELS: Record<Role, string> = {
  admin: 'SRE 负责人',
  engineer: '值班工程师',
  viewer: '只读观察者',
};

export const ROLE_STATIONS: Record<Role, string> = {
  admin: '全部站台 · 可写',
  engineer: '检索/告警站台 · 可确认',
  viewer: '趋势站台 · 只读',
};

export const EVENT_LEVELS: EventLevel[] = ['debug', 'info', 'warn', 'error', 'fatal'];

export const LEVEL_LABELS: Record<EventLevel, string> = {
  debug: 'DEBUG',
  info: 'INFO',
  warn: 'WARN',
  error: 'ERROR',
  fatal: 'FATAL',
};

export const TEMPLATE_STATUSES: TemplateStatus[] = ['mined', 'tentative', 'confirmed', 'noise'];

export const TEMPLATE_STATUS_LABELS: Record<TemplateStatus, string> = {
  mined: '已挖掘',
  tentative: '待确认',
  confirmed: '已确认',
  noise: '噪声',
};

export const ALERT_STATUSES: AlertStatus[] = ['firing', 'acknowledged', 'silenced', 'resolved'];

export const ALERT_STATUS_LABELS: Record<AlertStatus, string> = {
  firing: '触发中',
  acknowledged: '已确认',
  silenced: '静默中',
  resolved: '已恢复',
};

export const TRIGGER_REASON_LABELS: Record<string, string> = {
  spike_zscore: 'z 分数尖峰',
  error_ratio_jump: '错误占比突升',
  spike_and_error_ratio: '尖峰 + 占比突升',
};

export const SLOT_LABELS: Record<SlotType, string> = {
  num: '数字',
  ip: 'IP',
  uuid: 'UUID',
  path: '路径',
  hex: 'hex',
  ts: '时间戳',
  str: '字符串',
  unknown: '未定',
  static: '固定',
};

export type Permission =
  | 'sources:write'
  | 'parse_rules:write'
  | 'templates:write'
  | 'events:import'
  | 'alerts:write'
  | 'alerts:ack'
  | 'alerts:silence'
  | 'scan:run';

export const PERMISSION_MATRIX: Record<Role, Permission[]> = {
  admin: [
    'sources:write',
    'parse_rules:write',
    'templates:write',
    'events:import',
    'alerts:write',
    'alerts:ack',
    'alerts:silence',
    'scan:run',
  ],
  engineer: ['alerts:ack', 'alerts:silence', 'scan:run'],
  viewer: [],
};
