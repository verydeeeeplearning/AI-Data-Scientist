import type { Command } from '../../domain/command/command';

interface Props {
  readonly command: Command;
  readonly selected: boolean;
  readonly index: number;
  readonly totalCount: number;
  readonly onPointerEnter: () => void;
  readonly onSelect: () => void;
}

function categoryBadgeClass(category: Command['category']): string {
  if (category === 'navigation') {
    return 'border-sky-400/30 bg-sky-400/10 text-sky-200';
  }
  if (category === 'run') {
    return 'border-emerald-400/30 bg-emerald-400/10 text-emerald-200';
  }
  if (category === 'model') {
    return 'border-violet-400/30 bg-violet-400/10 text-violet-200';
  }
  return 'border-amber-400/30 bg-amber-400/10 text-amber-200';
}

export function CommandRow({
  command,
  selected,
  index,
  totalCount,
  onPointerEnter,
  onSelect,
}: Props) {
  return (
    <button
      id={`command-palette-option-${index}`}
      type="button"
      role="option"
      aria-posinset={index + 1}
      aria-selected={selected}
      aria-setsize={totalCount}
      onMouseEnter={onPointerEnter}
      onClick={onSelect}
      tabIndex={selected ? 0 : -1}
      className={`flex w-full items-start justify-between gap-3 rounded-2xl border px-3 py-3 text-left transition ${
        selected
          ? 'border-ds-accent bg-ds-accent/10'
          : 'border-ds-border bg-ds-bg/40 hover:border-ds-accent/40'
      }`}
    >
      <div className="min-w-0">
        <div className="text-sm font-medium text-ds-text">{command.title}</div>
        {command.subtitle && (
          <div className="mt-1 text-xs leading-5 text-ds-muted">{command.subtitle}</div>
        )}
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <span className={`rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-wider ${categoryBadgeClass(command.category)}`}>
          {command.category}
        </span>
        {command.shortcut && (
          <span className="rounded-full border border-ds-border px-2 py-0.5 text-[10px] text-ds-muted">
            {command.shortcut}
          </span>
        )}
      </div>
    </button>
  );
}
