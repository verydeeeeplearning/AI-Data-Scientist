import type { LucideIcon } from 'lucide-react';
import {
  AlertTriangle,
  Beaker,
  FileBox,
  Lightbulb,
  Sparkles,
} from 'lucide-react';
import type { AudienceView } from '../../domain/workspace/audienceView';
import type { ResultCardRecord } from '../../stores/chatStore';
import type {
  ResultCardActionDescriptor,
  ResultCardActionId,
} from './types';

export interface CardTone {
  badgeClassName: string;
  panelClassName: string;
}

export interface CardMeta {
  icon: LucideIcon;
  label: string;
  tone: CardTone;
}

export type CardContentSource = 'original' | 'rendered';
export type CardSectionDensity = 'none' | 'compact' | 'full';

export interface CardEmphasisProfile {
  readonly audience: AudienceView;
  readonly summarySource: CardContentSource;
  readonly bodySource: CardContentSource;
  readonly sectionDensity: CardSectionDensity;
}

const DEFAULT_TONE: CardTone = {
  badgeClassName: 'border-ds-border bg-ds-surface text-ds-muted',
  panelClassName: 'border-ds-border bg-ds-surface/80 text-ds-text',
};

const CARD_META: Record<ResultCardRecord['type'], CardMeta> = {
  insight: {
    icon: Lightbulb,
    label: 'Insight',
    tone: {
      badgeClassName: 'border-sky-400/30 bg-sky-400/10 text-sky-200',
      panelClassName: 'border-sky-400/20 bg-sky-400/5 text-sky-100',
    },
  },
  experiment: {
    icon: Beaker,
    label: 'Experiment',
    tone: {
      badgeClassName: 'border-emerald-400/30 bg-emerald-400/10 text-emerald-200',
      panelClassName: 'border-emerald-400/20 bg-emerald-400/5 text-emerald-100',
    },
  },
  risk: {
    icon: AlertTriangle,
    label: 'Risk',
    tone: {
      badgeClassName: 'border-amber-400/30 bg-amber-400/10 text-amber-200',
      panelClassName: 'border-amber-400/20 bg-amber-400/5 text-amber-100',
    },
  },
  artifact: {
    icon: FileBox,
    label: 'Artifact',
    tone: {
      badgeClassName: 'border-violet-400/30 bg-violet-400/10 text-violet-200',
      panelClassName: 'border-violet-400/20 bg-violet-400/5 text-violet-100',
    },
  },
  other: {
    icon: Sparkles,
    label: 'Result',
    tone: DEFAULT_TONE,
  },
};

const CARD_EMPHASIS_PROFILES: Record<
  AudienceView,
  Record<ResultCardRecord['type'], CardEmphasisProfile>
> = {
  ds: {
    insight: {
      audience: 'ds',
      summarySource: 'original',
      bodySource: 'original',
      sectionDensity: 'none',
    },
    experiment: {
      audience: 'ds',
      summarySource: 'original',
      bodySource: 'original',
      sectionDensity: 'none',
    },
    risk: {
      audience: 'ds',
      summarySource: 'original',
      bodySource: 'original',
      sectionDensity: 'none',
    },
    artifact: {
      audience: 'ds',
      summarySource: 'original',
      bodySource: 'original',
      sectionDensity: 'none',
    },
    other: {
      audience: 'ds',
      summarySource: 'original',
      bodySource: 'original',
      sectionDensity: 'none',
    },
  },
  exec: {
    insight: {
      audience: 'exec',
      summarySource: 'rendered',
      bodySource: 'rendered',
      sectionDensity: 'compact',
    },
    experiment: {
      audience: 'exec',
      summarySource: 'rendered',
      bodySource: 'rendered',
      sectionDensity: 'compact',
    },
    risk: {
      audience: 'exec',
      summarySource: 'rendered',
      bodySource: 'rendered',
      sectionDensity: 'compact',
    },
    artifact: {
      audience: 'exec',
      summarySource: 'rendered',
      bodySource: 'rendered',
      sectionDensity: 'compact',
    },
    other: {
      audience: 'exec',
      summarySource: 'rendered',
      bodySource: 'rendered',
      sectionDensity: 'compact',
    },
  },
  ml: {
    insight: {
      audience: 'ml',
      summarySource: 'rendered',
      bodySource: 'rendered',
      sectionDensity: 'full',
    },
    experiment: {
      audience: 'ml',
      summarySource: 'rendered',
      bodySource: 'rendered',
      sectionDensity: 'full',
    },
    risk: {
      audience: 'ml',
      summarySource: 'rendered',
      bodySource: 'rendered',
      sectionDensity: 'full',
    },
    artifact: {
      audience: 'ml',
      summarySource: 'rendered',
      bodySource: 'rendered',
      sectionDensity: 'compact',
    },
    other: {
      audience: 'ml',
      summarySource: 'rendered',
      bodySource: 'rendered',
      sectionDensity: 'full',
    },
  },
};

export function getCardMeta(card: ResultCardRecord): CardMeta {
  return CARD_META[card.type] ?? CARD_META.other;
}

export function getCardEmphasisProfile(
  cardType: ResultCardRecord['type'],
  audience: AudienceView,
): CardEmphasisProfile {
  return CARD_EMPHASIS_PROFILES[audience]?.[cardType] ?? CARD_EMPHASIS_PROFILES.ds.other;
}

export function getString(value: unknown): string | null {
  if (typeof value !== 'string') {
    return null;
  }
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

export function getNumber(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === 'string' && value.trim().length > 0) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

export function getRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === 'object' && value !== null ? value as Record<string, unknown> : null;
}

export function getStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((item) => getString(item))
    .filter((item): item is string => item !== null);
}

export function formatCardTimestamp(createdAt: number): string {
  const timestamp = createdAt > 1_000_000_000_000 ? createdAt : createdAt * 1000;
  if (!Number.isFinite(timestamp)) {
    return 'Unknown time';
  }

  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) {
    return 'Unknown time';
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date);
}

export function formatMetricValue(value: unknown): string | null {
  if (typeof value === 'number' && Number.isFinite(value)) {
    if (Math.abs(value) >= 1000) {
      return value.toLocaleString(undefined, {
        maximumFractionDigits: 2,
      });
    }
    return value.toLocaleString(undefined, {
      maximumFractionDigits: 4,
    });
  }
  return getString(value);
}

export function formatDelta(value: unknown): string | null {
  const numeric = getNumber(value);
  if (numeric === null) {
    return null;
  }
  const sign = numeric > 0 ? '+' : '';
  return `${sign}${numeric.toLocaleString(undefined, {
    maximumFractionDigits: 4,
  })}`;
}

export function getCardTitle(card: ResultCardRecord): string {
  const explicitTitle = getString(card.title);
  if (explicitTitle) {
    return explicitTitle;
  }

  if (card.type === 'experiment') {
    return getString(card.modelLabel) ?? 'Experiment result';
  }

  if (card.type === 'artifact') {
    return getString(card.fileRef) ?? 'Generated artifact';
  }

  if (card.type === 'risk') {
    return 'Risk detected';
  }

  if (card.type === 'insight') {
    return 'Key insight';
  }

  return 'Additional result';
}

export function getCardSummary(card: ResultCardRecord): string | null {
  if (card.type === 'insight') {
    const keyMetric = getRecord(card.keyMetric);
    const label = getString(keyMetric?.label);
    const value = formatMetricValue(keyMetric?.value);
    return label && value ? `${label}: ${value}` : null;
  }

  if (card.type === 'experiment') {
    const metric = getRecord(card.primaryMetric);
    const metricName = getString(metric?.name);
    const metricValue = formatMetricValue(metric?.value);
    if (metricName && metricValue) {
      return `${metricName}: ${metricValue}`;
    }
    return getString(card.dataVersion);
  }

  if (card.type === 'risk') {
    const severity = getString(card.severity);
    const category = getString(card.category);
    return [severity, category].filter(Boolean).join(' / ') || null;
  }

  if (card.type === 'artifact') {
    return [getString(card.artifactKind), getString(card.generatedByTool)]
      .filter(Boolean)
      .join(' / ') || null;
  }

  return null;
}

export function getCardActionDescriptors(card: ResultCardRecord): ResultCardActionDescriptor[] {
  const ordered = new Map<ResultCardActionId, ResultCardActionDescriptor>();

  ordered.set('pin', {
    id: 'pin',
    label: card.pinned ? 'Pinned' : 'Pin',
  });

  for (const action of getStringArray(card.quickActions)) {
    if (action === 'export_report') {
      ordered.set(action, { id: action, label: 'Export' });
    }
    if (action === 'compare_run') {
      ordered.set(action, { id: action, label: 'Compare' });
    }
    if (action === 'rerun') {
      ordered.set(action, { id: action, label: 'Re-run' });
    }
    if (action === 'request_review') {
      ordered.set(action, { id: action, label: 'Request review' });
    }
  }

  if (card.type === 'artifact' && getString(card.fileRef)) {
    ordered.set('open_artifact', {
      id: 'open_artifact',
      label: 'Open artifact',
    });
  }

  return [...ordered.values()];
}

export function getSeverityTone(value: unknown): CardTone {
  const severity = getString(value);
  if (severity === 'high') {
    return {
      badgeClassName: 'border-rose-400/30 bg-rose-400/10 text-rose-200',
      panelClassName: 'border-rose-400/20 bg-rose-400/5 text-rose-100',
    };
  }
  if (severity === 'medium') {
    return {
      badgeClassName: 'border-amber-400/30 bg-amber-400/10 text-amber-200',
      panelClassName: 'border-amber-400/20 bg-amber-400/5 text-amber-100',
    };
  }
  if (severity === 'low') {
    return {
      badgeClassName: 'border-emerald-400/30 bg-emerald-400/10 text-emerald-200',
      panelClassName: 'border-emerald-400/20 bg-emerald-400/5 text-emerald-100',
    };
  }
  return DEFAULT_TONE;
}
