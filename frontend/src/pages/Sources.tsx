import { useEffect, useState } from 'react';
import { sourceApi } from '../api/source';
import { EmptyState } from '../components/common/EmptyState';
import { SourceCard } from '../components/common/SourceCard';
import { StatusPill } from '../components/common/StatusPill';
import { ROLE_LABELS } from '../constants/enums';
import { useAuthStore } from '../stores/authStore';
import { useSourceStore } from '../stores/sourceStore';
import type { Source } from '../types/models';
import { errorMessage } from '../utils/errorMessage';
import { formatCount } from '../utils/formatCount';
import { formatTime } from '../utils/formatTime';

export const SourcesPage = () => {
  const { sources, rules, selectedId, loading, error, load, loadRules, select } = useSourceStore();
  const user = useAuthStore((state) => state.user);
  const can = useAuthStore((state) => state.can);
  const [editing, setEditing] = useState<{ name: string; pattern: string; field_names: string[]; priority: number }>({
    name: '',
    pattern: '',
    field_names: [],
    priority: 100,
  });
  const [notice, setNotice] = useState('');
  const [formError, setFormError] = useState('');

  useEffect(() => {
    void load();
    void loadRules();
  }, [load, loadRules]);

  const selected = sources.find((item) => item.id === selectedId) ?? null;

  const submitRule = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!selected) return;
    setFormError('');
    setNotice('');
    try {
      const fields = [...editing.pattern.matchAll(/\(\?P<([A-Za-z_][A-Za-z0-9_]*)>/g)].map((match) => match[1]);
      const response = await sourceApi.createRule(selected.id, { ...editing, field_names: fields });
      setNotice(response.message);
      setEditing({ name: '', pattern: '', field_names: [], priority: 100 });
      await loadRules(selected.id);
    } catch (caught) {
      setFormError(errorMessage(caught, '解析规则创建失败'));
    }
  };

  return (
    <>
      <header className="pagehead">
        <div>
          <div className="kicker">01 / SOURCE STATIONS · {sources.length} 个采集站</div>
          <h1>日志源与解析规则</h1>
          <p className="lede">
            Filebeat 按服务上报，每个源带一种采集格式与一组正则解析规则。格式未知的新服务先以
            plain 接入，模板由 Drain 从样本里挖出来，不用等人写正则。
          </p>
        </div>
        <aside>
          <span>当前值班：{user ? ROLE_LABELS[user.role] : '—'}</span>
          <span>写权限：{can('sources:write') ? '可建源/建规则' : '只读'}</span>
        </aside>
      </header>
      <div className="pagebody">
        {error ? <div className="banner">{error}</div> : null}
        {notice ? <div className="banner ok">{notice}</div> : null}
        <div className="split-asym">
          <section className="panel">
            <div className="panel-head">
              <h2>采集站列表</h2>
              <span className="meta">按服务 · {loading ? 'LOADING' : 'READY'}</span>
            </div>
            {sources.length === 0 ? (
              <EmptyState title="还没有日志源" hint="admin 可以在下方表单里接入第一个服务。" />
            ) : (
              <div className="side-list">
                {sources.map((source: Source) => (
                  <SourceCard
                    key={source.id}
                    source={source}
                    active={source.id === selectedId}
                    onSelect={(item) => select(item.id)}
                  />
                ))}
              </div>
            )}
          </section>
          <section className="panel">
            <div className="panel-head">
              <h3>选中的站台</h3>
              <span className="meta">{selected ? selected.name : '—'}</span>
            </div>
            <div className="panel-body">
              {selected ? (
                <>
                  <div className="observation">
                    <div className="metric">
                      <div className="metric-label">接入速率</div>
                      <div className="metric-value">
                        {formatCount(selected.rate_per_min)}
                        <small>/min</small>
                      </div>
                      <div className="metric-sub">{selected.log_format} · {selected.host_group}</div>
                    </div>
                    <div className="metric">
                      <div className="metric-label">待归类行</div>
                      <div className="metric-value">
                        {formatCount(selected.pending_count)}
                        <small>行</small>
                      </div>
                      <div className="metric-sub">等 Drain 挖掘</div>
                    </div>
                    <div className="metric accent">
                      <div className="metric-label">模板数</div>
                      <div className="metric-value">{formatCount(selected.template_count)}</div>
                      <div className="metric-sub">已归类 {formatCount(selected.event_count)} 行</div>
                    </div>
                  </div>
                  <p style={{ margin: 0, color: 'var(--ink-soft)', lineHeight: 1.6 }}>{selected.description}</p>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--ink-dim)' }}>
                    采集状态 <StatusPill status={selected.collect_status} kind="collect" /> · 最近上报{' '}
                    {formatTime(selected.last_collected_at)} · 规则 {selected.rule_count}
                  </div>
                </>
              ) : (
                <EmptyState title="左侧选择一个站台" hint="选中后这里显示速率、待归类行与规则清单。" />
              )}
            </div>
          </section>
        </div>

        <div className="split-asym reverse">
          <section className="panel">
            <div className="panel-head">
              <h2>解析规则</h2>
              <span className="meta">{selected ? `${rules.length} 条生效` : '未选中站台'}</span>
            </div>
            <div className="panel-body flush">
              {rules.length === 0 ? (
                <EmptyState title="该站台还没有解析规则" hint="解析规则只补字段，不影响模板挖掘。" />
              ) : (
                <table className="ruled">
                  <thead>
                    <tr>
                      <th>规则 / 优先级</th>
                      <th>正则</th>
                      <th>字段</th>
                      <th>命中</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rules.map((rule) => (
                      <tr key={rule.id}>
                        <td>
                          {rule.name}
                          <div className="mono" style={{ color: 'var(--ink-dim)' }}>
                            P{rule.priority} · {rule.enabled ? '启用' : '停用'}
                          </div>
                        </td>
                        <td>
                          <code className="mono truncate" style={{ display: 'block', maxWidth: '34ch' }}>
                            {rule.pattern}
                          </code>
                        </td>
                        <td className="mono">{rule.field_names.join(', ') || '—'}</td>
                        <td className="num">{formatCount(rule.hit_count)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </section>
          <section className="panel">
            <div className="panel-head">
              <h3>新增解析规则</h3>
              <span className="meta">{can('parse_rules:write') ? 'ADMIN' : 'VIEWER READONLY'}</span>
            </div>
            <form className="panel-body" onSubmit={submitRule}>
              <div className="field">
                <label>规则名</label>
                <input
                  className="input"
                  value={editing.name}
                  onChange={(event) => setEditing({ ...editing, name: event.target.value })}
                  placeholder="例如：订单号提取"
                  disabled={!can('parse_rules:write')}
                  required
                />
              </div>
              <div className="field">
                <label>正则（命名分组）</label>
                <input
                  className="input mono"
                  value={editing.pattern}
                  onChange={(event) => setEditing({ ...editing, pattern: event.target.value })}
                  placeholder="order_id=ORD-(?P<order_id>\\d+)"
                  disabled={!can('parse_rules:write')}
                  required
                />
              </div>
              <button className="btn primary" type="submit" disabled={!can('parse_rules:write') || !selected}>
                写入规则
              </button>
              {formError ? <div className="banner">{formError}</div> : null}
              {!can('parse_rules:write') ? (
                <p className="hint">当前角色只读：写接口会返回 403，页面直接禁用输入。</p>
              ) : null}
            </form>
          </section>
        </div>
      </div>
    </>
  );
};
