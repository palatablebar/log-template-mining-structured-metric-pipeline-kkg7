import { useEffect, useMemo } from 'react';
import { templateApi } from '../api/template';
import { EmptyState } from '../components/common/EmptyState';
import { GaugeMeter } from '../components/common/GaugeMeter';
import { StatusPill } from '../components/common/StatusPill';
import { TemplateTokenStrip } from '../components/common/TemplateTokenStrip';
import { SLOT_LABELS, TEMPLATE_STATUSES, TEMPLATE_STATUS_LABELS } from '../constants/enums';
import { useAuthStore } from '../stores/authStore';
import { useTemplateStore } from '../stores/templateStore';
import { metaApi } from '../api/meta';
import type { Overview, SlotType } from '../types/models';
import { errorMessage } from '../utils/errorMessage';
import { formatCount, formatPercent } from '../utils/formatCount';
import { formatTime } from '../utils/formatTime';
import { slotClass } from '../utils/slotColor';
import { useState } from 'react';

export const TemplatesPage = () => {
  const { templates, selected, filter, loading, error, load, select, setFilter } = useTemplateStore();
  const can = useAuthStore((state) => state.can);
  const [notice, setNotice] = useState('');
  const [overview, setOverview] = useState<Overview | null>(null);

  useEffect(() => {
    void load();
  }, [load, filter.status]);

  useEffect(() => {
    metaApi
      .overview()
      .then(setOverview)
      .catch(() => setOverview(null));
  }, [loading]);

  const slotSummary = useMemo(() => {
    const counts = new Map<string, number>();
    templates.forEach((template) => {
      (template.slot_types as string[]).forEach((slot) => {
        if (slot === 'static' || !slot) return;
        counts.set(slot, (counts.get(slot) ?? 0) + 1);
      });
    });
    return [...counts.entries()].sort((left, right) => right[1] - left[1]);
  }, [templates]);

  const totalFrequency = templates.reduce((acc, item) => acc + item.frequency, 0);
  const tentative = templates.filter((item) => item.status === 'tentative').length;
  const maxFrequency = Math.max(1, ...templates.map((item) => item.frequency));

  const act = async (action: 'confirm' | 'noise') => {
    if (!selected) return;
    setNotice('');
    try {
      const response = action === 'confirm' ? await templateApi.confirm(selected.id) : await templateApi.markNoise(selected.id);
      setNotice(response.message);
      await load();
    } catch (caught) {
      setNotice(errorMessage(caught, '操作失败'));
    }
  };

  return (
    <>
      <header className="pagehead">
        <div>
          <div className="kicker">02 / TEMPLATE REGISTRY · 模板库</div>
          <h1>模板与槽位</h1>
          <p className="lede">
            每个模板是一条被 Drain 抽象出来的日志骨架：固定 token 保留原文，变量位替换成 <code className="mono">&lt;*&gt;</code>{' '}
            并按数字 / IP / UUID / 路径 / hex / 时间戳归成槽位。频次来自真实事件计数。
          </p>
        </div>
        <aside>
          <span>{formatCount(totalFrequency)} 行被模板覆盖</span>
          <span>待确认 {tentative} 个</span>
        </aside>
      </header>
      <div className="pagebody">
        <div className="observation">
          <GaugeMeter label="模板总数" value={String(templates.length)} unit="个" sub="已挖掘 + 已确认" />
          <GaugeMeter
            label="事件覆盖率"
            value={overview ? overview.coverage_percent.toFixed(1) : '—'}
            unit="%"
            sub={overview ? `${formatCount(overview.covered_events)} / ${formatCount(overview.events)} 行` : '加载中'}
          />
          <GaugeMeter label="槽位种类" value={String(slotSummary.length)} unit="类" sub="num/ip/uuid/path/hex/ts/str" />
          <GaugeMeter
            label="最大频次模板"
            value={formatCount(maxFrequency)}
            unit="行"
            sub={templates[0]?.service ?? '—'}
            accent
          />
        </div>
        {error ? <div className="banner">{error}</div> : null}
        {notice ? <div className="banner ok">{notice}</div> : null}

        <div className="toolbar">
          <div className="field">
            <label>状态筛选</label>
            <select
              className="select"
              value={filter.status}
              onChange={(event) => setFilter({ status: event.target.value })}
            >
              <option value="">全部状态</option>
              {TEMPLATE_STATUSES.map((status) => (
                <option key={status} value={status}>
                  {TEMPLATE_STATUS_LABELS[status]}
                </option>
              ))}
            </select>
          </div>
          <div className="field" style={{ minWidth: 260 }}>
            <label>模板串搜索</label>
            <input
              className="input mono"
              value={filter.search}
              onChange={(event) => setFilter({ search: event.target.value })}
              placeholder="order-svc / retry / status="
            />
          </div>
          <span className="spacer" />
          <button className="btn ghost" type="button" onClick={() => void load()}>
            {loading ? '刷新中…' : '刷新模板'}
          </button>
        </div>

        <div className="split-asym">
          <section className="panel">
            <div className="panel-head">
              <h2>模板清单</h2>
              <span className="meta">{templates.length} 条 · 按频次降序</span>
            </div>
            <div className="panel-body flush">
              {templates.length === 0 ? (
                <EmptyState title="还没有匹配的模板" hint="到「导入挖掘」上传一份新格式样本，Drain 会挖出模板。" />
              ) : (
                <table className="ruled">
                  <thead>
                    <tr>
                      <th>模板（槽位高亮）</th>
                      <th>token</th>
                      <th>频次</th>
                      <th>状态</th>
                    </tr>
                  </thead>
                  <tbody>
                    {templates.map((template) => (
                      <tr
                        key={template.id}
                        className={selected?.id === template.id ? 'selected' : undefined}
                        onClick={() => select(template)}
                        style={{ cursor: 'pointer' }}
                      >
                        <td>
                          <TemplateTokenStrip
                            templateStr={template.template_str}
                            slotTypes={template.slot_types}
                            slotNames={template.slot_names}
                          />
                          <div className="mono" style={{ color: 'var(--ink-dim)', marginTop: 4 }}>
                            {template.service} · 首次 {formatTime(template.first_seen_at)} · {template.origin}
                          </div>
                        </td>
                        <td className="num">{template.token_count}</td>
                        <td className="num">{formatCount(template.frequency)}</td>
                        <td>
                          <StatusPill status={template.status} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </section>

          <section className="panel">
            <div className="panel-head">
              <h3>模板详情</h3>
              <span className="meta">SLOTS / {selected ? selected.token_count : '—'} tokens</span>
            </div>
            <div className="panel-body">
              {selected ? (
                <>
                  <div className="token-strip" style={{ marginBottom: 4 }}>
                    {(selected.slot_types as SlotType[]).map((slot, index) => (
                      <span
                        key={`${selected.id}-${index}`}
                        className={slot === 'static' ? 'token' : slotClass(slot)}
                        title={`位置 ${index + 1}`}
                      >
                        {slot === 'static' ? '·' : SLOT_LABELS[slot] ?? slot}
                        {selected.slot_names[index] ? `:${selected.slot_names[index]}` : ''}
                      </span>
                    ))}
                  </div>
                  <div className="field">
                    <label>样例原始行</label>
                    <textarea className="textarea" readOnly value={selected.sample_line} rows={3} />
                  </div>
                  <div className="observation">
                    <div className="metric">
                      <div className="metric-label">槽位数</div>
                      <div className="metric-value">{selected.slot_count}</div>
                    </div>
                    <div className="metric">
                      <div className="metric-label">级别倾向</div>
                      <div className="metric-value" style={{ fontSize: 'var(--step-2)' }}>
                        {selected.level_hint.toUpperCase()}
                      </div>
                    </div>
                  </div>
                  <div className="toolbar">
                    <button className="btn" type="button" disabled={!can('templates:write')} onClick={() => void act('confirm')}>
                      确认模板
                    </button>
                    <button className="btn danger" type="button" disabled={!can('templates:write')} onClick={() => void act('noise')}>
                      标记噪声
                    </button>
                  </div>
                  {!can('templates:write') ? <p className="hint">当前角色只读，确认动作由 admin 执行。</p> : null}
                </>
              ) : (
                <EmptyState title="选择左侧模板" hint="查看槽位分布、样例行与确认动作。" />
              )}
            </div>
          </section>
        </div>
      </div>
    </>
  );
};
