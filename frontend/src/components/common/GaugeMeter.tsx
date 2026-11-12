interface GaugeMeterProps {
  label: string;
  value: string;
  unit?: string;
  sub?: string;
  accent?: boolean;
}

/** 大号数值仪表：细刻度 + Archivo Narrow 数字，右上角留一个琥珀标记位。 */
export const GaugeMeter = ({ label, value, unit, sub, accent }: GaugeMeterProps) => (
  <div className={`metric${accent ? ' accent' : ''}`}>
    <div className="metric-label">
      <span>{label}</span>
      <span aria-hidden="true">{accent ? '◆' : '·'}</span>
    </div>
    <div className="metric-value">
      {value}
      {unit ? <small>{unit}</small> : null}
    </div>
    {sub ? <div className="metric-sub">{sub}</div> : null}
  </div>
);
