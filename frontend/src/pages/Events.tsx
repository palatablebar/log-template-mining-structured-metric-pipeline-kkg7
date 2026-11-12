import { useEffect, useMemo } from 'react';
import { EmptyState } from '../components/common/EmptyState';
import { GaugeMeter } from '../components/common/GaugeMeter';
import { LevelBadge } from '../components/common/LevelBadge';
import { TrendChart } from '../components/common/TrendChart';
import { EVENT_LEVELS, LEVEL_LABELS } from '../constants/enums';
import { useTrendSeries } from '../hooks/useTrendSeries';
import { useEventStore } from '../stores/eventStore';
import { formatCount, formatPercent } from '../utils/formatCount';
import { formatTime } from '../utils/formatTime';

export const EventsPage = () => {
  const { page, trend, aggregate, filters, loading, error, loadPage, loadTrend, loadAggregate, setFilters } =
    useEventStore();
  const view = useTrendSeries(trend, 5);

  useEffect(() => {
    void loadPage(1);
    void loadTrend();
    void loadAggregate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const totals = useMemo(() => {
    if (!trend) return { count: 0, error: 0, peak: 0 };
    const count = trend.series.reduce((acc, item) => acc + item.total, 0);
    const errors = trend.series.reduce((acc, item) => acc + item.error_series.reduce((sum, value) => sum + value, 0), 0);
    const peak = trend.series.reduce((acc, item) => Math.max(acc, item.peak), 0);
    return { count, error: errors, peak };
  }, [trend]);

  return (
    <>
      <header className="pagehead">
        <div>
          <div className="kicker">03 / EVENT TREND · {trend?.anchor ? `观测时刻 ${formatTime(trend.anchor)}` : '等待数据'}</div>
          <h1>事件检索与模板趋势</h1>
          <p className="lede">
            事件按 (模板 × 5 分钟) 桶聚合。曲线是每个模板的桶内计数，砖色柱是同桶里的 error/fatal
            行数——尖峰检测正是拿这两列做基线比较。
          </p>
        </div>
        <aside>
          <span>窗口 {filters.buckets} 桶 × 5min = {(filters.buckets * 5) / 60} 小时</span>
          <span>当前筛选 {filters.templateId ? `模板 #${filters.templateId}` : '全部模板'}</span>
        </aside>
      </header>
      <div className="pagebody">
        <div className="observation">
          <GaugeMeter label="窗口内事件" value={formatCount(totals.count)} unit="行" sub="按模板归类后" />
          <GaugeMeter label="窗口内 error" value={formatCount(totals.error)} unit="行" sub={formatPercent(totals.count ? totals.error / totals.count : 0)} />
          <GaugeMeter label="单桶峰值" value={formatCount(totals.peak)} unit="行" sub="5 分钟桶" />
          <GaugeMeter label="命中模板" value={String(trend?.series.length ?? 0)} unit="个" sub="按窗口计数降序" accent />
        </div>
        {error ? <div className="banner">{error}</div> : null}

        <section className="panel">
          <div className="panel-head">
            <h2>按模板聚合趋势</h2>
            <span className="meta">{trend?.bucket_minutes ?? 5} 分钟 / 桶 · 前 5 个模板</span>
          </div>
          <div className="panel-body">
            {view.series.length ? (
              <TrendChart series={view.series} buckets={view.buckets} height={260} animationKey={trend?.anchor ?? 'na'} />
            ) : (
              <EmptyState title="窗口内还没有归类事件" hint="先到「导入挖掘」跑一次 Drain，把待归类行变成模板事件。" />
            )}
          </div>
        </section>

        <div className="split-asym reverse">
          <section className="panel">
            <div className="panel-head">
              <h2>模板聚合排行</h2>
              <span className="meta">TOP {aggregate.length}</span>
            </div>
            <div className="panel-body flush">
              <table className="ruled">
                <thead>
                  <tr>
                    <th>模板</th>
                    <th>事件数</th>
                    <th>error</th>
                    <th>占比</th>
                  </tr>
                </thead>
                <tbody>
                  {aggregate.map((item) => (
                    <tr key={item.template_id} onClick={() => setFilters({ templateId: item.template_id })} style={{ cursor: 'pointer' }}>
                      <td>
                        <span className="mono">#{item.template_id}</span> {item.service}
                        <div className="mono truncate" style={{ color: 'var(--ink-dim)' }}>
                          {item.template_str}
                        </div>
                      </td>
                      <td className="num">{formatCount(item.event_count)}</td>
                      <td className="num">{formatCount(item.error_count)}</td>
                      <td className="num" style={{ color: item.error_ratio > 0.25 ? 'var(--brick)' : 'inherit' }}>
                        {formatPercent(item.error_ratio)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="panel">
            <div className="panel-head">
              <h3>事件检索</h3>
              <span className="meta">{page ? `${formatCount(page.total)} 行` : '—'}</span>
            </div>
            <div className="panel-body flush">
              <div className="toolbar" style={{ padding: '12px 12px 0' }}>
                <div className="field">
                  <label>级别</label>
                  <select className="select" value={filters.level} onChange={(event) => setFilters({ level: event.target.value })}>
                    <option value="">全部</option>
                    {EVENT_LEVELS.map((level) => (
                      <option key={level} value={level}>
                        {LEVEL_LABELS[level]}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="field" style={{ minWidth: 150 }}>
                  <label>关键字</label>
                  <input
                    className="input mono"
                    value={filters.search}
                    onChange={(event) => setFilters({ search: event.target.value })}
                    placeholder="retry / timeout"
                  />
                </div>
                <label className="hint" style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                  <input
                    type="checkbox"
                    checked={filters.pendingOnly}
                    onChange={(event) => setFilters({ pendingOnly: event.target.checked })}
                  />
                  只看待归类
                </label>
              </div>
              {page && page.items.length ? (
                <>
                  <table className="ruled">
                    <thead>
                      <tr>
                        <th>时间</th>
                        <th>级别</th>
                        <th>模板</th>
                        <th>原始行</th>
                      </tr>
                    </thead>
                    <tbody>
                      {page.items.map((event) => (
                        <tr key={event.id}>
                          <td className="mono" style={{ whiteSpace: 'nowrap' }}>
                            {formatTime(event.event_time).slice(5)}
                          </td>
                          <td>
                            <LevelBadge level={event.level} />
                          </td>
                          <td className="mono">{event.template_id ? `#${event.template_id}` : '—'}</td>
                          <td>
                            <div className="mono truncate" title={event.raw_line}>
                              {event.raw_line}
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <div className="toolbar" style={{ padding: '10px 12px' }}>
                    <button className="btn small ghost" type="button" disabled={page.page <= 1 || loading} onClick={() => void loadPage(page.page - 1)}>
                      上一页
                    </button>
                    <span className="hint">
                      {page.page} / {page.pages}
                    </span>
                    <button
                      className="btn small ghost"
                      type="button"
                      disabled={page.page >= page.pages || loading}
                      onClick={() => void loadPage(page.page + 1)}
                    >
                      下一页
                    </button>
                  </div>
                </>
              ) : (
                <EmptyState title="没有匹配的事件" hint="放宽级别或关键字筛选，或先导入一份样本。" />
              )}
            </div>
          </section>
        </div>
      </div>
    </>
  );
};
