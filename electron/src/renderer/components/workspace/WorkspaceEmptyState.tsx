import { useId, type ReactNode } from 'react';
import { Card } from '../../design-system/primitives';

interface Props {
  title: string;
  description: string;
  action?: ReactNode;
}

export function WorkspaceEmptyState({ title, description, action }: Props) {
  const titleId = useId();
  const descriptionId = `${titleId}-description`;

  return (
    <Card
      role="region"
      aria-labelledby={titleId}
      aria-describedby={descriptionId}
      className="border-dashed bg-ds-bg/50 px-ds-6 py-10 text-center shadow-none"
    >
      <h3 id={titleId} className="text-base font-semibold text-ds-text">
        {title}
      </h3>
      <p id={descriptionId} className="mx-auto mt-ds-2 max-w-xl text-sm leading-6 text-ds-muted">
        {description}
      </p>
      {action ? <div className="mt-ds-4 flex justify-center">{action}</div> : null}
    </Card>
  );
}
