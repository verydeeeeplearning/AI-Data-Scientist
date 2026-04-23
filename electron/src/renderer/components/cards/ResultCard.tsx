import { useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  ArrowUpRight,
  ChevronDown,
  ChevronRight,
  Pin,
  ShieldAlert,
} from 'lucide-react';
import { buildCardAnchorId } from '../../application/execution/resolveStageJumpTarget';
import { promoteToArtifact } from '../../application/run/promoteToArtifact';
import type { PromoteAudience } from '../../application/run/promoteToArtifactPort';
import { prefersReducedMotion } from '../../application/a11y/reducedMotion';
import { resolveCardDisplayMode } from '../../application/workspace/cardEmphasisAdopter';
import { useAudienceRenderedCard } from '../../hooks/useAudienceRenderedCard';
import { useAudienceView } from '../../hooks/useAudienceView';
import { usePromoteToArtifact } from '../../hooks/usePromoteToArtifact';
import { useI18n } from '../../stores/i18nStore';
import type { ResultCardRecord } from '../../stores/chatStore';
import { Button } from '../../design-system/primitives';
import {
  ResultCardActionButton,
  ResultCardDetailBlock,
  ResultCardFooter,
  ResultCardIconFrame,
  ResultCardMetaRow,
  ResultCardMetricPanel,
  ResultCardPill,
  ResultCardPillButton,
  ResultCardSectionPanel,
  ResultCardSectionTitle,
  ResultCardShell,
} from '../../design-system/composites';
import { PromoteDialog } from '../runtime/PromoteDialog';
import { PromotedArtifactBadge } from './PromotedArtifactBadge';
import {
  getNextUserExpandedOverride,
  hasRenderedCardBodyContent,
} from './audienceCardState';
import {
  formatCardTimestamp,
  formatDelta,
  formatMetricValue,
  getCardActionDescriptors,
  getCardMeta,
  getCardEmphasisProfile,
  getCardSummary,
  getCardTitle,
  getRecord,
  getSeverityTone,
  getString,
  getStringArray,
} from './cardPresentation';
import type { AudienceRenderedCard } from '../../application/cards/renderCardForAudiencePort';
import type { ResultCardViewProps } from './types';

interface ResultCardListProps {
  cards: ResultCardRecord[];
  onAction?: ResultCardViewProps['onAction'];
  renderTrustStrip?: ResultCardViewProps['renderTrustStrip'];
  forceExpanded?: boolean;
  forceCollapsed?: boolean;
}

export function ResultCardList({
  cards,
  onAction,
  renderTrustStrip,
  forceExpanded,
  forceCollapsed,
}: ResultCardListProps) {
  if (cards.length === 0) {
    return null;
  }

  return (
    <section
      aria-label="Result cards"
      className="mt-4 space-y-3"
      data-testid="result-card-list"
    >
      {cards.map((card) => (
        <ResultCard
          key={card.cardId}
          card={card}
          onAction={onAction}
          renderTrustStrip={renderTrustStrip}
          forceExpanded={forceExpanded}
          forceCollapsed={forceCollapsed}
        />
      ))}
    </section>
  );
}

export interface ResultCardProps extends ResultCardViewProps {
  /** Workspace-level "always expand" override — wins over audience emphasis. */
  forceExpanded?: boolean;
  /** Workspace-level "always collapse" override — wins over audience emphasis. */
  forceCollapsed?: boolean;
}

export function ResultCard({
  card,
  onAction,
  renderTrustStrip,
  forceExpanded,
  forceCollapsed,
}: ResultCardProps) {
  const meta = getCardMeta(card);
  const title = getCardTitle(card);
  const titleId = `${buildCardAnchorId(card.cardId)}-title`;
  const trustNode = renderTrustStrip?.({
    card,
    cardId: card.cardId,
    resultId: card.resultId,
    messageId: card.source.messageId,
  });
  const actions = getCardActionDescriptors(card);
  const actionHandler = onAction;
  const showActions = actionHandler !== undefined && actions.length > 0;
  const showPromoteAction = Boolean(card.source.runId);
  const Icon = meta.icon;

  const { view: audienceView } = useAudienceView();
  const emphasisProfile = getCardEmphasisProfile(card.type, audienceView);
  const audienceRendered = useAudienceRenderedCard(card);
  const { t } = useI18n();
  const reduceMotion = prefersReducedMotion();
  // `undefined` means "follow audience emphasis"; once the user clicks the
  // toggle, lock to their explicit choice (true/false).
  const [userExpanded, setUserExpanded] = useState<boolean | undefined>(undefined);
  const [promotionRefreshToken, setPromotionRefreshToken] = useState(0);
  const [isAudienceTransitioning, setAudienceTransitioning] = useState(false);
  const previousAudienceView = useRef(audienceView);

  const displayMode = resolveCardDisplayMode(
    { forceExpanded, forceCollapsed, userExpanded },
    audienceView,
  );
  const expanded = displayMode === 'expanded';
  const renderStatus = audienceRendered.status;
  const renderedCard = renderStatus === 'rendered' ? audienceRendered.renderedCard : null;
  const summary = renderedCard?.summary ?? getCardSummary(card);
  const bodySource = hasRenderedCardBodyContent(renderedCard) ? renderedCard : null;
  const motionClassName = reduceMotion
    ? ''
    : `transition-[opacity,transform] duration-200 ${
      isAudienceTransitioning ? 'opacity-80 translate-y-0.5' : 'opacity-100 translate-y-0'
    }`;

  // The DS audience defaults to fully expanded cards. Surface a hint badge
  // when the audience switch has changed the displayed mode away from the
  // DS default, AND no user override is currently in play. This communicates
  // why the card is dense / sparse without burying the cause in the UI.
  const dsBaselineExpanded = true;
  const audienceShiftedFromDsDefault =
    audienceView !== 'ds'
    && userExpanded === undefined
    && !forceExpanded
    && !forceCollapsed
    && expanded !== dsBaselineExpanded;
  const userOverrideActive = userExpanded !== undefined;
  const audienceHintKey: 'execCollapsed' | 'dsExpanded' | 'mlExpanded' =
    audienceView === 'exec'
      ? 'execCollapsed'
      : audienceView === 'ml'
        ? 'mlExpanded'
        : 'dsExpanded';

  useEffect(() => {
    if (previousAudienceView.current === audienceView) {
      return;
    }
    previousAudienceView.current = audienceView;
    if (reduceMotion) {
      setAudienceTransitioning(false);
      return;
    }
    setAudienceTransitioning(true);
    const timer = window.setTimeout(() => {
      setAudienceTransitioning(false);
    }, 240);
    return () => {
      window.clearTimeout(timer);
    };
  }, [audienceView, reduceMotion]);

  function handleToggle() {
    setUserExpanded((prev) => getNextUserExpandedOverride(prev, displayMode));
  }

  return (
    <ResultCardShell
      id={buildCardAnchorId(card.cardId)}
      aria-labelledby={titleId}
      className={reduceMotion ? '' : 'transition-[opacity,transform] duration-200'}
      data-card-id={card.cardId}
      data-result-id={card.resultId}
      data-audience-view={audienceView}
      data-display-mode={displayMode}
      data-render-source={renderStatus === 'rendered' ? 'backend' : 'original'}
      data-audience-transition={isAudienceTransitioning ? 'true' : 'false'}
      data-testid={`result-card-${card.cardId}`}
    >
      <header className={`flex items-start justify-between gap-ds-3 ${motionClassName}`}>
        <div className="min-w-0">
          <ResultCardMetaRow className="text-[11px] uppercase tracking-[0.18em]">
            <ResultCardPill className={`${meta.tone.badgeClassName} uppercase tracking-[0.18em]`}>
              {meta.label}
            </ResultCardPill>
            {card.pinned && (
              <ResultCardPill className="border-ds-accent/30 bg-ds-accent/10 text-ds-accent">
                Pinned
              </ResultCardPill>
            )}
            {card.archived && <ResultCardPill>Archived</ResultCardPill>}
            <span>{formatCardTimestamp(card.createdAt)}</span>
            {renderStatus === 'loading-fallback' && (
              <ResultCardPill
                data-testid={`result-card-${card.cardId}-render-loading`}
              >
                {t('workspace:audienceView.cardHint.loading')}
              </ResultCardPill>
            )}
            {renderStatus === 'error-fallback' && (
              <ResultCardPill
                className="border-amber-400/30 bg-amber-400/10 text-amber-200"
                data-testid={`result-card-${card.cardId}-render-error`}
                title={audienceRendered.error ?? undefined}
              >
                {t('workspace:audienceView.cardHint.renderFailed')}
              </ResultCardPill>
            )}
            {renderStatus === 'rendered' && renderedCard && (
              <ResultCardPill
                className="border-ds-accent/30 bg-ds-accent/10 text-ds-accent"
                data-testid={`result-card-${card.cardId}-rendered`}
              >
                {t('workspace:audienceView.cardHint.rendered', {
                  audience: t(`workspace:audienceView.option.${audienceView}`),
                })}
              </ResultCardPill>
            )}
            {audienceShiftedFromDsDefault && (
              <ResultCardPill
                className="border-amber-400/30 bg-amber-400/10 text-amber-200"
                data-testid={`result-card-${card.cardId}-audience-hint`}
              >
                {t(`workspace:audienceView.cardHint.${audienceHintKey}`)}
              </ResultCardPill>
            )}
            {userOverrideActive && (
              <ResultCardPill
                data-testid={`result-card-${card.cardId}-user-override`}
              >
                {t('workspace:audienceView.cardHint.userOverride')}
              </ResultCardPill>
            )}
            {userOverrideActive && (
              <ResultCardPillButton
                onClick={() => setUserExpanded(undefined)}
                data-testid={`result-card-${card.cardId}-reset-override`}
              >
                {t('workspace:audienceView.cardHint.resetOverride')}
              </ResultCardPillButton>
            )}
          </ResultCardMetaRow>
          <h3 id={titleId} className="mt-ds-2 text-ds-sm font-semibold text-ds-text">
            {title}
          </h3>
          {summary && (
            <p className={`mt-ds-1 text-ds-xs text-ds-muted ${motionClassName}`}>
              {summary}
            </p>
          )}
        </div>

        <div className="flex items-center gap-ds-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={handleToggle}
            aria-expanded={expanded}
            aria-controls={`${buildCardAnchorId(card.cardId)}-body`}
            className="min-h-0 rounded-ds-pill border border-ds-border bg-ds-bg/40 p-ds-2 text-ds-muted hover:border-ds-accent/40 hover:text-ds-accent"
            data-testid={`result-card-${card.cardId}-toggle`}
          >
            {expanded ? (
              <ChevronDown size={14} aria-hidden="true" />
            ) : (
              <ChevronRight size={14} aria-hidden="true" />
            )}
            <span className="sr-only">
              {expanded
                ? t('workspace:audienceView.cardHint.collapseAction')
                : t('workspace:audienceView.cardHint.expandAction')}
            </span>
          </Button>
          <ResultCardIconFrame className={meta.tone.panelClassName}>
            <Icon size={16} aria-hidden="true" />
          </ResultCardIconFrame>
        </div>
      </header>

      {expanded && (
        <div className={`mt-ds-4 ${motionClassName}`} id={`${buildCardAnchorId(card.cardId)}-body`}>
          {bodySource ? (
            <AudienceRenderedCardBody
              renderedCard={bodySource}
              density={emphasisProfile.sectionDensity}
            />
          ) : (
            <OriginalCardBody card={card} />
          )}
        </div>
      )}

      {expanded && (trustNode || showActions || card.source.toolCallId || showPromoteAction) && (
        <ResultCardFooter>
          <PromotedArtifactBadge
            runId={card.source.runId}
            cardId={card.cardId}
            refreshToken={promotionRefreshToken}
          />

          {trustNode && <ResultCardSectionPanel>{trustNode}</ResultCardSectionPanel>}

          <ResultCardMetaRow>
            <span className="font-medium text-ds-text">Run</span>
            <ResultCardPill>{card.source.runId}</ResultCardPill>
            {card.source.toolCallId && (
              <>
                <span className="font-medium text-ds-text">Tool</span>
                <ResultCardPill>{card.source.toolCallId}</ResultCardPill>
              </>
            )}
          </ResultCardMetaRow>

          {showActions && (
            <div className="flex flex-wrap gap-ds-2">
              {actions.map((action) => {
                const disabled = action.id === 'pin' && card.archived;
                return (
                  <ResultCardActionButton
                    key={action.id}
                    disabled={disabled}
                    leadingIcon={
                      action.id === 'request_review' ? (
                        <ShieldAlert size={13} aria-hidden="true" />
                      ) : action.id === 'pin' ? (
                        <Pin size={13} aria-hidden="true" />
                      ) : (
                        <ArrowUpRight size={13} aria-hidden="true" />
                      )
                    }
                    onClick={() => actionHandler?.(action.id, card)}
                  >
                    {action.label}
                  </ResultCardActionButton>
                );
              })}
            </div>
          )}

          <PromoteCardAction
            card={card}
            onPromoted={() => {
              setPromotionRefreshToken((current) => current + 1);
            }}
          />
        </ResultCardFooter>
      )}
    </ResultCardShell>
  );
}

interface PromoteCardActionProps {
  card: ResultCardRecord;
  onPromoted?: () => void;
}

function PromoteCardAction({ card, onPromoted }: PromoteCardActionProps) {
  const port = usePromoteToArtifact();
  const { t } = useI18n();
  const [busy, setBusy] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [status, setStatus] = useState<{
    tone: 'success' | 'error';
    message: string;
  } | null>(null);

  const runId = card.source.runId;

  const handlePromote = async ({
    audience,
    title,
  }: {
    audience: PromoteAudience;
    title: string;
  }) => {
    setStatus(null);
    setBusy(true);
    try {
      const result = await promoteToArtifact(port, {
        runId,
        cardId: card.cardId,
        audience,
        title: title.trim() || null,
      });
      setStatus({
        tone: 'success',
        message: t('cards:promoteDialog.status.success', {
          audience: t(`cards:promoteDialog.audience.${result.audience}`),
          artifactId: result.artifactId,
        }),
      });
      setDialogOpen(false);
      onPromoted?.();
    } catch (err) {
      const detail = err instanceof Error ? err.message : String(err);
      setStatus({
        tone: 'error',
        message: t('cards:promoteDialog.status.failed', { reason: detail }),
      });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-2">
      <ResultCardActionButton
        tone="accent"
        onClick={() => {
          setStatus(null);
          setDialogOpen(true);
        }}
        disabled={busy || !runId}
        title={
          runId
            ? 'Promote this card to a delivery-pack artifact for the chosen audience.'
            : 'Card is missing a run id; promote unavailable.'
        }
        data-testid={`result-card-${card.cardId}-promote`}
      >
        {busy ? t('cards:promoteDialog.confirmBusy') : t('cards:promoteDialog.confirm')}
      </ResultCardActionButton>
      {status && (
        <span
          className={`text-[11px] ${
            status.tone === 'error' ? 'text-rose-300' : 'text-emerald-300'
          }`}
          role="status"
          aria-live="polite"
        >
          {status.message}
        </span>
      )}
      <PromoteDialog
        open={dialogOpen}
        busy={busy}
        error={status?.tone === 'error' ? status.message : null}
        onClose={() => {
          if (!busy) {
            setDialogOpen(false);
          }
        }}
        onSubmit={(draft) => void handlePromote(draft)}
      />
    </div>
  );
}

function AudienceRenderedCardBody({
  renderedCard,
  density,
}: {
  renderedCard: AudienceRenderedCard;
  density: 'compact' | 'full' | 'none';
}) {
  const body = renderedCard.body;
  const sections = renderedCard.sections;
  const sectionGridClassName =
    density === 'compact'
      ? 'grid gap-3 md:grid-cols-2'
      : 'grid gap-3 lg:grid-cols-2';

  return (
    <div className="space-y-4">
      {body && (
        <div className="prose prose-invert prose-sm max-w-none
          prose-headings:text-ds-text prose-p:text-ds-text prose-li:text-ds-text
          prose-code:text-ds-accent prose-strong:text-ds-text prose-a:text-ds-accent
          prose-a:no-underline hover:prose-a:underline">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {body}
          </ReactMarkdown>
        </div>
      )}

      {sections.length > 0 && density !== 'none' && (
        <section className={sectionGridClassName}>
          {sections.map((section) => (
            <ResultCardSectionPanel
              key={section.id}
              className="bg-ds-bg/60"
            >
              <ResultCardSectionTitle>{section.title}</ResultCardSectionTitle>
              <div className="mt-2 text-sm text-ds-text whitespace-pre-line">
                {section.body}
              </div>
            </ResultCardSectionPanel>
          ))}
        </section>
      )}
    </div>
  );
}

function OriginalCardBody({ card }: { card: ResultCardRecord }) {
  if (card.type === 'insight') {
    return <InsightCardBody card={card} />;
  }
  if (card.type === 'experiment') {
    return <ExperimentCardBody card={card} />;
  }
  if (card.type === 'risk') {
    return <RiskCardBody card={card} />;
  }
  if (card.type === 'artifact') {
    return <ArtifactCardBody card={card} />;
  }
  return <OtherCardBody card={card} />;
}

function InsightCardBody({ card }: { card: ResultCardRecord }) {
  const keyMetric = getRecord(card.keyMetric);
  const metricLabel = getString(keyMetric?.label);
  const metricValue = formatMetricValue(keyMetric?.value);
  const metricDelta = getString(keyMetric?.delta);
  const evidence = getStringArray(card.evidence);
  const trustStatus = getString(card.trustStatus);

  return (
    <div className="space-y-3">
      {(metricLabel || metricValue) && (
        <ResultCardMetricPanel
          label={metricLabel ?? 'Key metric'}
          value={metricValue ?? 'Unknown'}
          hint={metricDelta ?? undefined}
        />
      )}

      {evidence.length > 0 && (
        <section>
          <ResultCardSectionTitle>Evidence</ResultCardSectionTitle>
          <ul className="mt-2 space-y-2 text-sm text-ds-text">
            {evidence.map((item) => (
              <li key={item}>
                <ResultCardSectionPanel className="px-ds-3 py-ds-2">
                  {item}
                </ResultCardSectionPanel>
              </li>
            ))}
          </ul>
        </section>
      )}

      {trustStatus && (
        <ResultCardPill className="border-ds-accent/30 bg-ds-accent/10 text-ds-accent">
          {`Trust ${trustStatus}`}
        </ResultCardPill>
      )}
    </div>
  );
}

function ExperimentCardBody({ card }: { card: ResultCardRecord }) {
  const primaryMetric = getRecord(card.primaryMetric);
  const metricName = getString(primaryMetric?.name) ?? 'Primary metric';
  const metricValue = formatMetricValue(primaryMetric?.value);
  const metricDelta = formatDelta(primaryMetric?.deltaVsBaseline);
  const artifactRefs = Array.isArray(card.artifactRefs) ? card.artifactRefs : [];

  return (
    <div className="space-y-3">
      {metricValue && (
        <ResultCardMetricPanel
          label={metricName}
          value={metricValue}
          hint={metricDelta ? `${metricDelta} vs baseline` : undefined}
        />
      )}

      <div className="grid gap-3 md:grid-cols-2">
        <ResultCardDetailBlock label="Model" value={getString(card.modelLabel) ?? 'Unknown'} />
        <ResultCardDetailBlock label="Data version" value={getString(card.dataVersion) ?? 'Unknown'} />
      </div>

      {artifactRefs.length > 0 && (
        <section>
          <ResultCardSectionTitle>Linked artifacts</ResultCardSectionTitle>
          <div className="mt-2 flex flex-wrap gap-2">
            {artifactRefs.map((ref, index) => {
              const record = getRecord(ref);
              const label = getString(record?.label)
                ?? getString(record?.title)
                ?? getString(record?.id)
                ?? `Artifact ${index + 1}`;
              return (
                <ResultCardPill key={`${label}-${index}`}>
                  {label}
                </ResultCardPill>
              );
            })}
          </div>
        </section>
      )}
    </div>
  );
}

function RiskCardBody({ card }: { card: ResultCardRecord }) {
  const severity = getString(card.severity);
  const severityTone = getSeverityTone(card.severity);
  const category = getString(card.category);
  const target = getString(card.target);
  const impact = getString(card.impact);
  const recommendation = getString(card.recommendation);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        {severity && (
          <ResultCardPill className={severityTone.badgeClassName}>
            {`Severity ${severity}`}
          </ResultCardPill>
        )}
        {category && (
          <ResultCardPill className="border-ds-border bg-ds-surface text-ds-muted">
            {category.replace(/_/g, ' ')}
          </ResultCardPill>
        )}
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <ResultCardDetailBlock label="Target" value={target ?? 'Not specified'} />
        <ResultCardDetailBlock label="Impact" value={impact ?? 'Not specified'} />
      </div>

      {recommendation && (
        <ResultCardSectionPanel>
          <ResultCardSectionTitle>Recommendation</ResultCardSectionTitle>
          <p className="mt-2 text-sm text-ds-text">
            {recommendation}
          </p>
        </ResultCardSectionPanel>
      )}
    </div>
  );
}

function ArtifactCardBody({ card }: { card: ResultCardRecord }) {
  const thumbnailUrl = getString(card.thumbnailUrl);
  const fileRef = getString(card.fileRef);
  const generatedByTool = getString(card.generatedByTool);
  const sourceExperimentRunId = getString(card.sourceExperimentRunId);

  return (
    <div className="space-y-3">
      {thumbnailUrl && (
        <div className="overflow-hidden rounded-ds-lg border border-ds-border/70 bg-ds-bg/60">
          <img
            src={thumbnailUrl}
            alt={getCardTitle(card)}
            className="max-h-64 w-full object-cover"
          />
        </div>
      )}

      <div className="grid gap-3 md:grid-cols-2">
        <ResultCardDetailBlock label="Artifact kind" value={getString(card.artifactKind) ?? 'Unknown'} />
        <ResultCardDetailBlock label="File" value={fileRef ?? 'Unknown'} />
        <ResultCardDetailBlock label="Generated by" value={generatedByTool ?? 'Unknown'} />
        {sourceExperimentRunId && (
          <ResultCardDetailBlock label="Experiment run" value={sourceExperimentRunId} />
        )}
      </div>
    </div>
  );
}

function OtherCardBody({ card }: { card: ResultCardRecord }) {
  const body = getString(card.body);
  if (!body) {
    return (
      <p className="text-sm text-ds-muted">
        No structured card body was provided.
      </p>
    );
  }

  return (
    <div className="prose prose-invert prose-sm max-w-none
      prose-headings:text-ds-text prose-p:text-ds-text prose-li:text-ds-text
      prose-code:text-ds-accent prose-strong:text-ds-text prose-a:text-ds-accent
      prose-a:no-underline hover:prose-a:underline">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>
        {body}
      </ReactMarkdown>
    </div>
  );
}
