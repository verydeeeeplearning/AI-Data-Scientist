import type { CapabilityBadge as CapabilityBadgeId } from '../../domain/llm/modelCapability';
import { useI18n } from '../../stores/i18nStore';

interface Props {
  badge: CapabilityBadgeId;
}

function badgeClasses(badge: CapabilityBadgeId): string {
  if (badge === 'strong_reasoning' || badge === 'strong_coding') {
    return 'border-ds-accent/30 bg-ds-accent/10 text-ds-accent';
  }
  if (badge === 'offline') {
    return 'border-emerald-400/20 bg-emerald-500/10 text-emerald-300';
  }
  if (badge === 'cheap' || badge === 'fast') {
    return 'border-amber-400/20 bg-amber-400/10 text-amber-200';
  }
  return 'border-ds-border/70 bg-ds-surface text-ds-muted';
}

export function CapabilityBadge({ badge }: Props) {
  const { t } = useI18n();

  return (
    <span
      className={`rounded-full border px-2 py-0.5 text-[10px] font-medium ${badgeClasses(badge)}`}
    >
      {t(`llm.badge.${badge}`)}
    </span>
  );
}
