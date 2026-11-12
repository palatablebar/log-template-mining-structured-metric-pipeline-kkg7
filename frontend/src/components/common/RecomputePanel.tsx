import { useEffect, useMemo, useState } from 'react';
import { alertApi, type RecomputePayload } from '../../api/alert';
import { EmptyState } from '../common/EmptyState';
import { StatusPill } from '../common/StatusPill';
import { ALERT_STATUS_LABELS, RECOMPUTE_ACTION_LABELS } from '../../constants/enums';
import type { RecomputeJob, RecomputePreview } from '../../types/models';
import { errorMessage } from '../../utils/errorMessage';
import { formatFixed, formatPercent } from '../../utils/formatCount';
import { formatClock, formatTime } from '../../utils/formatTime';

const ACTION_COLORS: Record<string, string> = {
  created: 'var(--brick)',
  updated: 'var(--amber-deep)',
  resolved: 'var(--teal, var(--ink-dim))',
  unchanged: 'var(--ink-dim)',
  skipped: 'var(--ink-dim)',
};

export const RecomputePanel = ({ canScan, onChanged }: { canScan: boolean; onChanged: () => void }) => {
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [preview, setPreview] = useState<RecomputePreview | null>(null);
  const [jobs, setJobs] = useState<RecomputeJob[]>([]);
  const [activeJob, setActiveJob] = useState<RecomputeJob | null>(null);
  const [bucketFilter, setBucketFilter] = useState('');
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');

  const loadJobs = async () => {
    try {
      const response = await alertApi.recomputeJobs();
      setJobs(response.items);
    } catch (caught) {
      setError(errorMessage(caught, '补算批次加载失败'));
    }
  };

  useEffect(() => {
    void loadJobs();
  }, []);

  const payload = useMemo<RecomputePayload>(() => {
    const data: RecomputePayload = {};
    if (start) data.start = start.replace('T', ' ');
    if (end) data.end = end.replace('T', ' ');
    return data;
  }, [start, end]);

  const runPreview = async () => {
    setError('');
    setNotice('');
    setBusy(true);
    try {
      setPreview(await alertApi.recomputePreview(payload));
    } catch (caught) {
      setError(errorMessage(caught, '补算范围解析失败'));
    } finally {
      setBusy(false);
    }
  };

  const runRecompute = async () => {
    setError('');
    setNotice('');
    setBusy(true);
    try {
      const result = await alertApi.recompute({
        ...payload,
        note: '值班补传后手动补算',
      });
      setNotice(
        result.deduplicated
          ? `#${result.id} 同范围补算已执行过，未重复新增告警（幂等返回）。`
          : `#${result.id} 补算完成：新补 ${result.created} · 更新 ${result.updated} · 恢复 ${result.resolved} · 未变 ${result.unchanged} · 跳过 ${result.skipped}。`,
      );
      setPreview(null);
      await loadJobs();
      const detail = await alertApi.recomputeJob(result.id);
      setActiveJob(detail);
      setBucketFilter('');
      onChanged();
    } catch (caught) {
      setError(errorMessage(caught, '补算失败'));
    } finally {
      setBusy(false);
    }
  };

  const openJob = async (jobId: number) => {
    setError('');
    try {
      const detail = await alertApi.recomputeJob(jobId);
      setActiveJob(detail);
      setBucketFilter('');
    } catch (caught) {
      setError(errorMessage(caught, '补算明细加载失败'));
    }
  };

  const filteredDetails = useMemo(() => {
    if (!activeJob?.details) return [];
    if (!bucketFilter) return activeJob.details;
    return activeJob.details.filter((item) => item.bucket_start === bucketFilter);
  }, [activeJob, bucketFilter]);

  return (
    <section className="panel">
      <div className="panel-head">
        <h2>补传补算（只重算受影响模板 × 时间桶）</h2>
        <span className="meta">补日志后在此重判，重复投递幂等</span>
      </div>
      <div className="panel-body">
        {error ? <div className="banner">{error}</div> : null}
        {notice ? <div className="banner ok">{notice}</div> : null}

        <div className="toolbar" style={{ marginBottom: 12 }}>
          <div className="field">
            <label htmlFor="rc-start">开始时间（留空自动取补传范围）</label>
            <input
              id="rc-start"
              className="input"
              type="datetime-local"
              step="300"
              value={start}
              onChange={(event) => setStart(event.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="rc-end">结束时间</label>
            <input
              id="rc-end"
              className="input"
              type="datetime-local"
              step="300"
              value={end}
              onChange={(event) => setEnd(event.target.value)}
            />
          </div>
          <button className="btn ghost" type="button" disabled={!canScan || busy} onClick={() => void runPreview()}>
            预览受影响范围
          </button>
          <button className="btn primary" type="button" disabled={!canScan || busy} onClick={() => void runRecompute()}>
            {busy ? '补算中…' : '发起补算'}
          </button>
        </div>

        {preview ? (
          <div className="banner info" style={{ marginBottom: 12 }}>
            {preview.pair_count === 0 ? (
              preview.message
            ) : (
              <>
                范围 {formatTime(preview.range_start)} ~ {formatTime(preview.range_end)}
                {preview.auto ? '（自动按补传事件圈定）' : ''} · 受影响模板 {preview.template_count} 个 · 时间桶{' '}
                {preview.bucket_count} 个 · 待重算 (模板×桶) {preview.pair_count} 个；基线窗口另向前取 12 桶，下游再扩展 12 桶。
              </>
            )}
          </div>
        ) : null}

        <div className="split-asym" style={{ alignItems: 'flex-start' }}>
          <div>
            <h3 style={{ margin: '0 0 8px' }}>补算批次</h3>
            {jobs.length === 0 ? (
              <EmptyState title="还没有补算批次" hint="补传日志并应用模板后，选择时间范围发起补算。" />
            ) : (
              <table className="ruled">
                <thead>
                  <tr>
                    <th>批次</th>
                    <th>范围</th>
                    <th>新补/更新/恢复</th>
                    <th>桶 / 模板</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {jobs.map((job) => (
                    <tr key={job.id} className={activeJob?.id === job.id ? 'selected' : undefined}>
                      <td>
                        <div className="mono">#{job.id}</div>
                        <div className="mono" style={{ color: 'var(--ink-dim)' }}>
                          {formatClock(job.finished_at)}
                        </div>
                      </td>
                      <td className="mono" style={{ fontSize: 11 }}>
                        {formatTime(job.range_start).slice(5)}
                        <br />~ {formatTime(job.range_end).slice(5)}
                      </td>
                      <td className="num">
                        <span style={{ color: 'var(--brick)' }}>{job.created}</span> / {job.updated} /{' '}
                        <span style={{ color: 'var(--teal, var(--ink-dim))' }}>{job.resolved}</span>
                      </td>
                      <td className="num">
                        {job.affected_bucket_count} / {job.affected_template_count}
                      </td>
                      <td>
                        <button className="btn small" type="button" onClick={() => void openJob(job.id)}>
                          查看明细
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {activeJob ? (
            <div>
              <h3 style={{ margin: '0 0 8px' }}>
                #{activeJob.id} 按时间桶查看重算前后
                {activeJob.deduplicated ? '（幂等复用）' : ''}
              </h3>
              {activeJob.buckets && activeJob.buckets.length > 0 ? (
                <table className="ruled" style={{ marginBottom: 12 }}>
                  <thead>
                    <tr>
                      <th>时间桶</th>
                      <th>重算前触发</th>
                      <th>重算后触发</th>
                      <th>新补</th>
                      <th>更新</th>
                      <th>恢复</th>
                      <th>未变/跳过</th>
                    </tr>
                  </thead>
                  <tbody>
                    {activeJob.buckets.map((bucket) => (
                      <tr
                        key={bucket.bucket_start}
                        className={bucketFilter === bucket.bucket_start ? 'selected' : undefined}
                        style={{ cursor: 'pointer' }}
                        onClick={() =>
                          setBucketFilter(bucketFilter === bucket.bucket_start ? '' : bucket.bucket_start)
                        }
                      >
                        <td className="mono">{formatClock(bucket.bucket_start)}</td>
                        <td className="num">{bucket.before_firing}</td>
                        <td className="num" style={{ color: bucket.after_firing ? 'var(--brick)' : 'inherit' }}>
                          {bucket.after_firing}
                        </td>
                        <td className="num">{bucket.created}</td>
                        <td className="num">{bucket.updated}</td>
                        <td className="num">{bucket.resolved}</td>
                        <td className="num">
                          {bucket.unchanged} / {bucket.skipped}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : null}

              <div className="toolbar" style={{ marginBottom: 8 }}>
                <span className="hint">
                  {bucketFilter
                    ? `已筛选桶 ${formatClock(bucketFilter)}，共 ${filteredDetails.length} 条；点击桶行可取消筛选`
                    : `共 ${filteredDetails.length} 个 (模板 × 桶) 判定`}
                </span>
              </div>
              <table className="ruled">
                <thead>
                  <tr>
                    <th>桶 / 模板</th>
                    <th>动作</th>
                    <th>状态：前 → 后</th>
                    <th>计数：前 → 后</th>
                    <th>z：前 → 后</th>
                    <th>error 占比：前 → 后</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredDetails.map((detail) => (
                    <tr key={detail.id}>
                      <td>
                        <div className="mono">{formatClock(detail.bucket_start)}</div>
                        <div className="mono truncate" style={{ color: 'var(--ink-dim)' }} title={detail.template_str}>
                          #{detail.template_id} {detail.service}
                        </div>
                      </td>
                      <td>
                        <span className="pill" style={{ color: ACTION_COLORS[detail.action] }}>
                          {RECOMPUTE_ACTION_LABELS[detail.action] ?? detail.action}
                        </span>
                        {detail.note ? (
                          <div className="mono" style={{ color: 'var(--ink-dim)', marginTop: 4, fontSize: 10 }}>
                            {detail.note}
                          </div>
                        ) : null}
                      </td>
                      <td className="mono" style={{ fontSize: 11 }}>
                        {detail.before_status ? <StatusPill status={detail.before_status} kind="alert" /> : '—'}
                        <span style={{ margin: '0 4px' }}>→</span>
                        {detail.after_status ? (
                          <StatusPill status={detail.after_status} kind="alert" />
                        ) : (
                          <span className="mono" style={{ color: 'var(--ink-dim)' }}>
                            无告警
                          </span>
                        )}
                        <div style={{ marginTop: 4, color: 'var(--ink-dim)' }}>
                          {detail.before_status ? ALERT_STATUS_LABELS[detail.before_status] ?? detail.before_status : '无'}
                        </div>
                      </td>
                      <td className="num">
                        {detail.before_count ?? '—'} → <strong>{detail.after_count ?? '—'}</strong>
                      </td>
                      <td className="num">
                        {detail.before_z_score === null ? '—' : formatFixed(detail.before_z_score, 2)} →{' '}
                        {detail.after_z_score === null ? (
                          '—'
                        ) : (
                          <strong style={{ color: detail.after_z_score > 3.5 ? 'var(--brick)' : 'inherit' }}>
                            {formatFixed(detail.after_z_score, 2)}
                          </strong>
                        )}
                      </td>
                      <td className="num">
                        {detail.before_error_ratio === null ? '—' : formatPercent(detail.before_error_ratio)} →{' '}
                        {detail.after_error_ratio === null ? '—' : formatPercent(detail.after_error_ratio)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState title="选择一个批次查看明细" hint="明细按时间桶展示重算前后的状态、计数与判定数据。" />
          )}
        </div>
      </div>
    </section>
  );
};
