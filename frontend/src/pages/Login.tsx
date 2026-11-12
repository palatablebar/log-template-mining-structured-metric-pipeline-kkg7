import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore';
import { errorMessage } from '../utils/errorMessage';

const DEMO_HINT = 'admin@logmine.demo · engineer@logmine.demo · viewer@logmine.demo（密码 Demo@2026）';

export const LoginPage = () => {
  const navigate = useNavigate();
  const login = useAuthStore((state) => state.login);
  const loading = useAuthStore((state) => state.loading);
  const [email, setEmail] = useState('admin@logmine.demo');
  const [password, setPassword] = useState('Demo@2026');
  const [error, setError] = useState('');

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError('');
    try {
      await login(email.trim(), password);
      navigate('/sources', { replace: true });
    } catch (caught) {
      setError(errorMessage(caught, '登录失败'));
    }
  };

  return (
    <div className="gate">
      <section className="gate-left">
        <div className="gate-brand">
          log<em>mine</em>
        </div>
        <div>
          <h1 className="gate-title">
            从 1200 万行日志里，
            <span>只留下模板</span>。
          </h1>
          <p className="gate-note">
            云栖 IDC · SRE 团队每天被同一类日志刷屏：变量不同、模板相同。logmine 用 Drain
            把原始行压成模板与槽位，再按 (模板 × 5min) 桶做中位数 + MAD 基线，把「同一个模板突然变多」变成可确认的告警。
          </p>
        </div>
        <div className="gate-meters">
          <div className="cell">
            观测服务<b>40</b>
          </div>
          <div className="cell">
            日接入日志<b>1200w</b>
          </div>
          <div className="cell">
            基线窗口<b>12 桶</b>
          </div>
          <div className="cell">
            尖峰阈值<b>z &gt; 3.5</b>
          </div>
        </div>
      </section>
      <section className="gate-right">
        <form className="gate-form" onSubmit={submit}>
          <div className="kicker" style={{ letterSpacing: '0.2em' }}>
            OBSERVATION LOGIN / 值班登录
          </div>
          <h2>进入观测台</h2>
          <div className="field">
            <label htmlFor="email">邮箱</label>
            <input
              id="email"
              className="input"
              type="email"
              autoComplete="username"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
          </div>
          <div className="field">
            <label htmlFor="password">密码</label>
            <input
              id="password"
              className="input"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </div>
          {error ? <div className="banner">{error}</div> : null}
          <button className="btn primary" type="submit" disabled={loading}>
            {loading ? '正在签到…' : '签到并进入'}
          </button>
          <p className="hint">{DEMO_HINT}</p>
        </form>
      </section>
    </div>
  );
};
