interface OverviewStatProps {
  label: string;
  value: number;
  testId?: string;
}

interface StatusLineProps {
  label: string;
  value: string;
}

interface InlineErrorProps {
  message: string;
}

export function OverviewStat({ label, value, testId }: OverviewStatProps) {
  return (
    <div
      data-testid={testId}
      className="rounded border border-ds-border/70 bg-ds-surface/60 px-2 py-1.5"
    >
      <div className="text-[10px] text-ds-muted">{label}</div>
      <div className="mt-1 text-sm font-mono text-ds-text">{value}</div>
    </div>
  );
}

export function StatusLine({ label, value }: StatusLineProps) {
  return (
    <div className="rounded border border-ds-border/70 bg-ds-surface/60 px-2 py-1.5 text-[10px]">
      <div className="text-ds-muted">{label}</div>
      <div className="mt-1 text-ds-text">{value}</div>
    </div>
  );
}

export function InlineError({ message }: InlineErrorProps) {
  return (
    <div className="rounded border border-ds-error/40 bg-ds-error/10 px-2 py-2 text-xs text-ds-error">
      {message}
    </div>
  );
}
