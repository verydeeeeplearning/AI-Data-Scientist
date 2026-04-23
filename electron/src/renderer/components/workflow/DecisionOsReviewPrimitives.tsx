import { Card } from '../../design-system/primitives';

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
    <Card
      data-testid={testId}
      className="space-y-ds-1 border-ds-border/70 bg-ds-surface/60 px-ds-3 py-ds-2"
    >
      <div className="text-[10px] text-ds-muted">{label}</div>
      <div className="mt-1 text-sm font-mono text-ds-text">{value}</div>
    </Card>
  );
}

export function StatusLine({ label, value }: StatusLineProps) {
  return (
    <Card className="space-y-ds-1 border-ds-border/70 bg-ds-surface/60 px-ds-3 py-ds-2 text-[10px]">
      <div className="text-ds-muted">{label}</div>
      <div className="mt-1 text-ds-text">{value}</div>
    </Card>
  );
}

export function InlineError({ message }: InlineErrorProps) {
  return (
    <Card
      role="alert"
      tone="danger"
      className="border-ds-error/40 px-ds-3 py-ds-3 text-ds-xs text-ds-error"
    >
      {message}
    </Card>
  );
}
