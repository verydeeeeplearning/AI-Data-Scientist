import type { LucideIcon } from 'lucide-react';
import { Tooltip } from '../../design-system/primitives';

interface Props {
  icon: LucideIcon;
  label: string;
  active?: boolean;
  collapsed: boolean;
  onClick: () => void;
  dataTestId?: string;
}

export function SidebarItem({
  icon: Icon,
  label,
  active = false,
  collapsed,
  onClick,
  dataTestId,
}: Props) {
  const button = (
    <button
      onClick={onClick}
      data-testid={dataTestId}
      aria-label={label}
      title={collapsed ? undefined : label}
      className={`group relative flex w-full items-center rounded-lg px-2 py-2 text-left transition-colors ${
        collapsed ? 'justify-center' : 'justify-start gap-2'
      } ${
        active
          ? 'bg-ds-accent/10 text-ds-accent'
          : 'text-ds-muted hover:bg-ds-bg hover:text-ds-text'
      } focus:outline-none focus-visible:ring-2 focus-visible:ring-ds-accent/50`}
    >
      <Icon size={16} className="shrink-0" />
      {!collapsed && <span className="truncate text-xs font-medium">{label}</span>}
    </button>
  );

  if (!collapsed) {
    return button;
  }

  return (
    <Tooltip content={label} placement="right">
      {button}
    </Tooltip>
  );
}
