import { useEffect, useMemo, useState } from 'react';
import { alertApi } from '../api/alert';
import { eventApi } from '../api/event';
import { EmptyState } from '../components/common/EmptyState';
import { GaugeMeter } from '../components/common/GaugeMeter';
import { LevelBadge } from '../components/common/LevelBadge';
import { StatusPill } from '../components/common/StatusPill';
import { TrendChart } from '../components/common/TrendChart';
import { ALERT_STATUS_LABELS, TRIGGER_REASON_LABELS } from '../constants/enums';
import { useTrendSeries } from '../hooks/useTrendSeries';
import { useAlertStore } from '../stores/alertStore';
import { useAuthStore } from '../stores/authStore';
import type { TrendPayload } from '../types/models';
import { errorMessage } from '../utils/errorMessage';
import { formatCount, formatFixed, formatPercent } from '../utils/formatCount';
import { formatTime } from '../utils/formatTime';

const SCAN_NOTE = 'z = 0.6745 × (x - median) / MAD · 基线取前 12 个 5min 桶 · MAD=0 时用 1 兜底';

export const AlertsPage = () => {
  const { rules, alerts, stats, lastScan, loading, error, load, scan } = useAlertStore();
  const can = useAuthStore((state) => state.can);
  const [notice, setNotice] = useState('');
  const [actionError, setActionError] = useState('');
  const [trend, setTrend] = useState<TrendPayload | null>(null);
  const view = useTrendSeries(trend, 3);

  useEffect(() => {
    void load();
    eventApi.trend(24).then(setTrend).catch(() => setTrend(null));
  }, [load]);

  const firing = useMemo(() => alerts.filter((item) => item.status === 'firing'), [alerts]);

  const runScan = async () => {
    setActionError('');
    setNotice('');
    try {
      const result = await scan();
      setNotice(`${result.message}：新生成 ${result.created} 条告警，扫描模板 ${result.templates_scanned} 个，历史不足 ${result.insufficient_history} 个。`);
      const refreshed = await eventApi.trend(24);
      setTrend(refreshed);
    } catch (caught) {
      setActionError(errorMessage(caught, '扫描失败'));
    }
  };

  const acknowledge = async (alertId: number, silence = false) => {
    setActionError('');
    setNotice('');
    try {
      const response = silence
        ? await alertApi.silence(alertId, { minutes: 30, note: '值班确认：同模板 30 分钟内去抖' })
        : await alertApi.ack(alertId, { note: '值班工程师已确认为真实尖峰' });
      setNotice(`${response.message} · ${response.item.template_str.split(' ').slice(2, 5).join(' ')}`);
      await load();
    } catch (caught) {
      setActionError(errorMessage(caught, '告警操作失败'));
    }
  };

  return (
    <>
      <header className="pagehead">
        <div>
          <div className="kicker">04 / ALERT DESK · 基线异常判定</div>
          <h1>告警规则与触发记录</h1>
          <p className="lede">
            每条告警都带完整判定快照：窗口计数、基线中位数、MAD、z 分数与 error 占比。确认和静默都会写审计日志，
            静默后同模板 30 分钟内不再重复触发。
          </p>
        </div>
        <aside>
          <span>{SCAN_NOTE}</span>
          <span>触发中 {stats.firing} 条</span>
        </aside>
      </header>
      <div className="pagebody">
        <div className="observation">
          <GaugeMeter label="触发中" value={String(stats.firing)} unit="条" sub="firing · 待确认" accent />
          <GaugeMeter label="已确认" value={String(stats.acknowledged)} unit="条" sub="acknowledged" />
          <GaugeMeter label="静默中" value={String(stats.silenced)} unit="条" sub="30min 去抖" />
          <GaugeMeter label="历史告警" value={String(stats.total)} unit="条" sub={`规则 ${rules.length} 条`} />
        </div>
        {error ? <div className="banner">{error}</div> : null}
        {actionError ? <div className="banner">{actionError}</div> : null}
        {notice ? <div className="banner ok">{notice}</div> : null}

        <div className="toolbar">
          <button className="btn primary" type="button" onClick={() => void runScan()} disabled={!can('scan:run') || loading}>
            {loading ? '扫描中…' : '运行异常扫描'}
          </button>
          {lastScan ? (
            <span className="hint">
              最近扫描桶 {formatTime(lastScan.bucket)} · 模板 {lastScan.templates_scanned} · 新告警 {lastScan.created} · 历史不足{' '}
              {lastScan.insufficient_history}
            </span>
          ) : null}
          <span className="spacer" />
          <button className="btn ghost" type="button" onClick={() => void load()}>
            刷新
          </button>
        </div>

        <section className="panel">
          <div className="panel-head">
            <h2>窗口趋势（mini）</h2>
            <span className="meta">最近 {trend?.buckets.length ?? 0} 桶 · 前 3 个模板</span>
          </div>
          <div className="panel-body">
            {view.series.length ? (
              <TrendChart series={view.series} buckets={view.buckets} height={172} mini animationKey={trend?.anchor ?? 'na'} />
            ) : (
              <EmptyState title="还没有可画的趋势" hint="先在「导入挖掘」把模板应用到事件。" />
            )}
          </div>
        </section>

        <section className="panel">
          <div className="panel-head">
            <h2>触发记录</h2>
            <span className="meta">{alerts.length} 条 · 按触发时间降序</span>
          </div>
          <div className="panel-body flush">
            {alerts.length === 0 ? (
              <EmptyState title="还没有告警" hint="点击「运行异常扫描」，用 12 桶基线比对当前桶。" />
            ) : (
              <table className="ruled">
                <thead>
                  <tr>
                    <th>触发时刻 / 模板</th>
                    <th>计数</th>
                    <th>基线 median / MAD</th>
                    <th>z</th>
                    <th>error 占比</th>
                    <th>原因</th>
                    <th>状态</th>
                    <th>动作</th>
                  </tr>
                </thead>
                <tbody>
                  {alerts.map((alert) => (
                    <tr key={alert.id}>
                      <td>
                        <div className="mono">{formatTime(alert.triggered_at)}</div>
                        <div className="mono truncate" style={{ color: 'var(--ink-dim)' }} title={alert.template_str}>
                          #{alert.template_id} {alert.service}
                        </div>
                      </td>
                      <td className="num">
                        {alert.count_in_bucket}
                        <div className="mono" style={{ color: 'var(--ink-dim)' }}>
                          {formatTime(alert.bucket_start).slice(11, 16)}
                        </div>
                      </td>
                      <td className="num">
                        {formatFixed(alert.baseline_median, 1)} / {formatFixed(alert.baseline_mad, 3)}
                      </td>
                      <td className="num" style={{ color: alert.z_score > 3.5 ? 'var(--brick)' : 'inherit' }}>
                        {formatFixed(alert.z_score, 3)}
                      </td>
                      <td className="num">
                        {formatPercent(alert.error_ratio)}
                        <div className="mono" style={{ color: 'var(--ink-dim)' }}>
                          基线 {formatPercent(alert.baseline_error_ratio)}
                        </div>
                      </td>
                      <td>
                        <span className="pill">{TRIGGER_REASON_LABELS[alert.reason] ?? alert.reason}</span>
                        <div style={{ marginTop: 4 }}>
                          <LevelBadge level={alert.level} />
                        </div>
                      </td>
                      <td>
                        <StatusPill status={alert.status} kind="alert" />
                        <div className="mono" style={{ color: 'var(--ink-dim)', marginTop: 4 }}>
                          {alert.silenced_until ? `静默至 ${formatTime(alert.silenced_until).slice(11, 16)}` : '—'}
                          {alert.acknowledged_by ? <div>by {alert.acknowledged_by}</div> : null}
                        </div>
                      </td>
                      <td>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                          <button
                            className="btn small"
                            type="button"
                            disabled={!can('alerts:ack') || alert.status !== 'firing'}
                            onClick={() => void acknowledge(alert.id)}
                          >
                            确认
                          </button>
                          <button
                            className="btn small ghost"
                            type="button"
                            disabled={!can('alerts:silence') || alert.status === 'resolved'}
                            onClick={() => void acknowledge(alert.id, true)}
                          >
                            静默 30min
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </section>

        <div className="split-asym">
          <section className="panel">
            <div className="panel-head">
              <h2>告警规则</h2>
              <span className="meta">{rules.length} 条 · admin 可建</span>
            </div>
            <div className="panel-body flush">
              <table className="ruled">
                <thead>
                  <tr>
                    <th>规则</th>
                    <th>作用模板</th>
                    <th>口径</th>
                    <th>静默</th>
                    <th>状态</th>
                  </tr>
                </thead>
                <tbody>
                  {rules.map((rule) => (
                    <tr key={rule.id}>
                      <td>
                        {rule.name}
                        <div className="mono" style={{ color: 'var(--ink-dim)' }}>{rule.metric}</div>
                      </td>
                      <td className="mono">{rule.template_id ? `#${rule.template_id}` : '全部模板'}</td>
                      <td className="mono">
                        z&gt;{formatFixed(rule.z_threshold, 1)} · 占比 {formatPercent(rule.error_ratio_low, 0)}→
                        {formatPercent(rule.error_ratio_high, 0)}
                      </td>
                      <td className="num">{rule.silence_minutes}min</td>
                      <td>
                        <span className={`pill ${rule.enabled ? 'confirmed' : 'noise'}`}>{rule.enabled ? '启用' : '停用'}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
          <section className="panel">
            <div className="panel-head">
              <h3>判定口径</h3>
              <span className="meta">FORMULA</span>
            </div>
            <div className="panel-body">
              <ul style={{ margin: 0, paddingLeft: 18, lineHeight: 1.8, color: 'var(--ink-soft)' }}>
                <li>桶宽 5 分钟，按 (template_id, 桶) 计数。</li>
                <li>基线 = 当前桶之前 12 个桶的计数，缺失桶补 0。</li>
                <li>z = 0.6745 × (x − median) / MAD；MAD = 0 时用 1 兜底。</li>
                <li>z &gt; 3.5 判尖峰；error 占比 &lt;5% → &gt;25% 也触发。</li>
                <li>历史桶 &lt; 3 时标 insufficient_history，不判异常。</li>
                <li>同模板 30 分钟去抖，确认/静默写审计。</li>
              </ul>
              <div className="observation">
                <div className="metric">
                  <div className="metric-label">当前触发中</div>
                  <div className="metric-value">{formatCount(firing.length)}</div>
                  <div className="metric-sub">firing</div>
                </div>
                <div className="metric">
                  <div className="metric-label">告警状态枚举</div>
                  <div className="metric-sub">{Object.values(ALERT_STATUS_LABELS).join(' / ')}</div>
                </div>
              </div>
            </div>
          </section>
        </div>
      </div>
    </>
  );
};
