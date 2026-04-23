import { useEffect, useMemo, useRef } from 'react';
import { ReviewTab } from '../../components/workflow/ReviewTab';
import { ApprovalPanel } from '../../components/workflow/ApprovalPanel';
import { CertificationBoard } from '../../components/runtime/CertificationBoard';
import { PolicyPanel } from '../../components/runtime/PolicyPanel';
import {
  buildGovernanceSectionPath,
  resolveGovernanceLanding,
  type GovernanceDetailKind,
  type GovernanceLandingDetail,
  type GovernanceSectionId,
} from '../../application/navigation/resolveGovernanceLanding';
import type { AreaSelection } from '../../domain/navigation/area';
import { useI18n } from '../../stores/i18nStore';

interface Props {
  selection: AreaSelection;
  onNavigate: (path: string) => void;
}

const GOVERNANCE_SECTIONS: readonly { id: GovernanceSectionId; label: string }[] = [
  { id: 'review', label: 'Review' },
  { id: 'certification', label: 'Certification' },
  { id: 'policy', label: 'Policy' },
  { id: 'approvals', label: 'Approvals' },
] as const;

const DETAIL_LABELS: Readonly<Record<GovernanceDetailKind, string>> = Object.freeze({
  verifier: 'Verifier result',
  lineage: 'Lineage trace',
  'fallback-log': 'Fallback log',
  approval: 'Approval request',
  drift: 'Drift status',
  certification: 'Certification target',
  policy: 'Policy detail',
});

function sectionClassName(active: boolean): string {
  return [
    'rounded-2xl border bg-ds-surface/70 transition-colors',
    active ? 'border-ds-accent/50 ring-1 ring-ds-accent/20' : 'border-ds-border',
  ].join(' ');
}

function describeLandingDetail(detail: GovernanceLandingDetail | null): {
  label: string;
  id: string | null;
} | null {
  if (!detail) {
    return null;
  }
  return {
    label: DETAIL_LABELS[detail.kind],
    id: detail.id,
  };
}

export function GovernancePage({ selection, onNavigate }: Props) {
  const { t } = useI18n();
  const landing = useMemo(() => resolveGovernanceLanding(selection), [selection]);
  const detail = useMemo(() => describeLandingDetail(landing.detail), [landing.detail]);
  const sectionRefs = useRef<Record<GovernanceSectionId, HTMLElement | null>>({
    review: null,
    certification: null,
    policy: null,
    approvals: null,
  });

  useEffect(() => {
    const target = sectionRefs.current[landing.sectionId];
    if (!target) {
      return;
    }
    target.scrollIntoView({ block: 'start', behavior: 'smooth' });
    try {
      target.focus({ preventScroll: true });
    } catch {
      // Best-effort focus restore for keyboard users after route-driven landings.
    }
  }, [landing.detail?.id, landing.detail?.kind, landing.sectionId]);

  return (
    <div className="flex h-full min-w-0 flex-col overflow-hidden">
      <div className="border-b border-ds-border px-6 py-4">
        <h1 className="text-lg font-semibold text-ds-text">{t('area.governance.label')}</h1>
        <p className="mt-1 text-sm text-ds-muted">{t('area.governance.description')}</p>

        <div className="mt-4 flex flex-wrap gap-2">
          {GOVERNANCE_SECTIONS.map((section) => (
            <button
              key={section.id}
              type="button"
              onClick={() => onNavigate(buildGovernanceSectionPath(section.id))}
              aria-current={landing.sectionId === section.id ? 'page' : undefined}
              className={`rounded-full border px-3 py-1.5 text-xs transition-colors ${
                landing.sectionId === section.id
                  ? 'border-ds-accent bg-ds-accent/10 text-ds-accent'
                  : 'border-ds-border bg-ds-surface text-ds-muted hover:text-ds-text'
              }`}
            >
              {section.label}
            </button>
          ))}
        </div>

        {detail && (
          <div className="mt-4 rounded-2xl border border-ds-accent/30 bg-ds-accent/5 px-4 py-3">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-ds-accent">
              Governance deep link
            </div>
            <div className="mt-1 text-sm text-ds-text">{detail.label}</div>
            {detail.id && <div className="mt-1 text-xs font-mono text-ds-muted">{detail.id}</div>}
          </div>
        )}
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        <div className="space-y-4">
          <section
            ref={(node) => {
              sectionRefs.current.review = node;
            }}
            id="ds-governance-review"
            tabIndex={-1}
            className={sectionClassName(landing.sectionId === 'review')}
          >
            <ReviewTab />
          </section>

          <div className="grid gap-4 xl:grid-cols-2">
            <section
              ref={(node) => {
                sectionRefs.current.certification = node;
              }}
              id="ds-governance-certification"
              tabIndex={-1}
              className={sectionClassName(landing.sectionId === 'certification')}
            >
              <CertificationBoard />
            </section>

            <section
              ref={(node) => {
                sectionRefs.current.policy = node;
              }}
              id="ds-governance-policy"
              tabIndex={-1}
              className={sectionClassName(landing.sectionId === 'policy')}
            >
              <PolicyPanel />
            </section>

            <section
              ref={(node) => {
                sectionRefs.current.approvals = node;
              }}
              id="ds-governance-approvals"
              tabIndex={-1}
              className={`${sectionClassName(landing.sectionId === 'approvals')} xl:col-span-2`}
            >
              <ApprovalPanel />
            </section>
          </div>
        </div>
      </div>
    </div>
  );
}
