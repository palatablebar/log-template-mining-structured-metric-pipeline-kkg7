interface EmptyStateProps {
  title: string;
  hint?: string;
  action?: React.ReactNode;
}

export const EmptyState = ({ title, hint, action }: EmptyStateProps) => (
  <div className="empty">
    <b>{title}</b>
    {hint ? <span>{hint}</span> : null}
    {action ? <div style={{ marginTop: 12 }}>{action}</div> : null}
  </div>
);
