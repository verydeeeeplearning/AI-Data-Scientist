import { ChevronDown, ChevronUp, ShieldCheck } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { StatusLine } from './DecisionOsReviewPrimitives';
import {
  EXPECTED_REVIEW_SKILLS,
  formatDate,
  ReviewArtifactRecord,
  ReviewRun,
  ReviewSkillName,
  reviewSkillLabel,
  runOptionLabel,
  severityClass,
} from './decisionOsReviewModel';

interface Props {
  runs: ReviewRun[];
}

export function SharedSkillReviewPanel({ runs }: Props) {
  const [artifactRunId, setArtifactRunId] = useState('');

  useEffect(() => {
    const runIds = new Set(runs.map((run) => run.run_id));
    if (!runIds.has(artifactRunId)) {
      setArtifactRunId(runs[0]?.run_id ?? '');
    }
  }, [artifactRunId, runs]);

  const selectedArtifactRun = useMemo(
    () => runs.find((run) => run.run_id === artifactRunId) ?? runs[0] ?? null,
    [artifactRunId, runs],
  );

  return (
    <section
      data-testid="decision-os-shared-skill-review"
      className="space-y-2 rounded-md border border-ds-border bg-ds-bg/70 p-3"
    >
      <div className="flex items-center gap-2 text-xs font-semibold text-ds-text">
        <ShieldCheck size={14} />
        Shared Skill Review
      </div>
      <select
        value={artifactRunId}
        onChange={(event) => setArtifactRunId(event.target.value)}
        aria-label="Run selected for shared skill review"
        data-testid="decision-os-artifact-run"
        className="w-full rounded border border-ds-border bg-ds-surface px-2 py-1.5 text-xs text-ds-text"
      >
        <option value="">Select run</option>
        {runs.map((run) => (
          <option key={run.run_id} value={run.run_id}>
            {runOptionLabel(run)}
          </option>
        ))}
      </select>
      {selectedArtifactRun === null ? (
        <div className="text-xs text-ds-muted">No runs available yet.</div>
      ) : (
        <div className="space-y-2">
          <div
            data-testid="decision-os-artifact-summary"
            className="rounded border border-ds-border/70 bg-ds-surface/60 p-2 text-[10px] text-ds-muted"
          >
            {selectedArtifactRun.run_id} / {selectedArtifactRun.review_artifacts.length} stored
            review artifacts
          </div>
          {EXPECTED_REVIEW_SKILLS.map((skill) => {
            const artifact =
              selectedArtifactRun.review_artifacts.find((item) => item.skill_name === skill) ??
              null;
            if (artifact === null) {
              return <MissingReviewCard key={skill} skill={skill} />;
            }
            return <ReviewArtifactCard key={artifact.artifact_id} artifact={artifact} />;
          })}
        </div>
      )}
    </section>
  );
}

function ReviewArtifactCard({ artifact }: { artifact: ReviewArtifactRecord }) {
  const [narrativeOpen, setNarrativeOpen] = useState(false);

  return (
    <article
      data-testid={`decision-os-artifact-${artifact.skill_name}`}
      className="space-y-2 rounded border border-ds-border/70 bg-ds-surface/60 p-2"
    >
      <div className="flex flex-wrap items-center gap-2 text-xs text-ds-text">
        <span className="font-medium">{reviewSkillLabel(artifact.skill_name)}</span>
        <span className="rounded border border-ds-border px-1.5 py-0.5 text-[10px] text-ds-muted">
          {formatDate(artifact.created_at)}
        </span>
        <span
          className={`rounded border px-1.5 py-0.5 text-[10px] ${
            artifact.artifact.artifact_type === 'causal-assumption-check'
              ? severityClass(artifact.artifact.is_causal ? 'pass' : 'warn')
              : artifact.artifact.artifact_type === 'retrain-vs-rollback'
                ? severityClass(
                    artifact.artifact.recommendation === 'rollback'
                      ? 'fail'
                      : artifact.artifact.recommendation === 'retrain'
                        ? 'warn'
                        : 'pass',
                  )
                : 'border-ds-border bg-ds-bg/70 text-ds-muted'
          }`}
        >
          {artifact.artifact.artifact_type}
        </span>
      </div>
      <div className="rounded border border-ds-border bg-ds-bg/70 px-2 py-1.5 text-xs text-ds-text">
        {artifact.summary}
      </div>
      <ReviewArtifactBody artifact={artifact} />
      {artifact.narrative ? (
        <div className="rounded border border-ds-border bg-ds-bg/70">
          <button
            onClick={() => setNarrativeOpen((current) => !current)}
            data-testid={`decision-os-artifact-toggle-${artifact.skill_name}`}
            className="flex w-full items-center justify-between px-2 py-1.5 text-left text-[10px] text-ds-muted hover:text-ds-text"
          >
            <span>{narrativeOpen ? 'Hide narrative' : 'Show narrative'}</span>
            {narrativeOpen ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
          </button>
          {narrativeOpen ? (
            <div
              data-testid={`decision-os-artifact-narrative-${artifact.skill_name}`}
              className="border-t border-ds-border px-2 py-2 text-[10px] leading-5 text-ds-muted"
            >
              {artifact.narrative}
            </div>
          ) : null}
        </div>
      ) : null}
    </article>
  );
}

function ReviewArtifactBody({ artifact }: { artifact: ReviewArtifactRecord }) {
  if (artifact.artifact.artifact_type === 'backtesting') {
    return (
      <div className="space-y-2">
        <StatusLine
          label="Consistency"
          value={artifact.artifact.consistency_score.toFixed(2)}
        />
        <div className="grid gap-2">
          {artifact.artifact.folds.map((fold) => (
            <div
              key={`${fold.fold_label}:${fold.metric}`}
              className="rounded border border-ds-border bg-ds-bg/70 px-2 py-1.5 text-[10px]"
            >
              <div className="flex items-center justify-between">
                <span className="text-ds-text">
                  {fold.fold_label} / {fold.metric}
                </span>
                <span className={`rounded border px-1.5 py-0.5 ${severityClass(fold.status)}`}>
                  {fold.status}
                </span>
              </div>
              <div className="mt-1 text-ds-muted">
                {fold.score.toFixed(3)}
                {fold.baseline_score !== undefined && fold.baseline_score !== null
                  ? ` vs baseline ${fold.baseline_score.toFixed(3)}`
                  : ''}
              </div>
            </div>
          ))}
        </div>
        {artifact.artifact.warnings.length > 0 ? (
          <StatusLine label="Warnings" value={artifact.artifact.warnings.join(' | ')} />
        ) : null}
      </div>
    );
  }

  if (artifact.artifact.artifact_type === 'causal-assumption-check') {
    return (
      <div className="space-y-2">
        <StatusLine
          label="Causal interpretation"
          value={artifact.artifact.is_causal ? 'Allowed' : 'Correlation only'}
        />
        {artifact.artifact.risks.map((risk) => (
          <div
            key={`${risk.assumption}:${risk.detail}`}
            className="rounded border border-ds-border bg-ds-bg/70 px-2 py-1.5 text-[10px]"
          >
            <div className="flex items-center justify-between">
              <span className="text-ds-text">{risk.assumption}</span>
              <span className={`rounded border px-1.5 py-0.5 ${severityClass(risk.severity)}`}>
                {risk.severity}
              </span>
            </div>
            <div className="mt-1 text-ds-muted">{risk.detail}</div>
          </div>
        ))}
        {artifact.artifact.confounders.length > 0 ? (
          <StatusLine label="Confounders" value={artifact.artifact.confounders.join(', ')} />
        ) : null}
      </div>
    );
  }

  if (artifact.artifact.artifact_type === 'uncertainty-quantification') {
    return (
      <div className="space-y-2">
        <StatusLine label="Methodology" value={artifact.artifact.methodology} />
        {artifact.artifact.intervals.map((interval) => (
          <div
            key={`${interval.metric}:${interval.lower}:${interval.upper}`}
            className="rounded border border-ds-border bg-ds-bg/70 px-2 py-1.5 text-[10px]"
          >
            <div className="text-ds-text">{interval.metric}</div>
            <div className="mt-1 text-ds-muted">
              [{interval.lower.toFixed(3)}, {interval.upper.toFixed(3)}]
              {interval.confidence_level !== undefined && interval.confidence_level !== null
                ? ` @ ${(interval.confidence_level * 100).toFixed(0)}%`
                : ''}
            </div>
          </div>
        ))}
        {artifact.artifact.warnings.length > 0 ? (
          <StatusLine label="Warnings" value={artifact.artifact.warnings.join(' | ')} />
        ) : null}
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <StatusLine label="Recommendation" value={artifact.artifact.recommendation} />
      <StatusLine label="Rationale" value={artifact.artifact.rationale} />
      {artifact.artifact.evidence.length > 0 ? (
        <StatusLine label="Evidence" value={artifact.artifact.evidence.join(' | ')} />
      ) : null}
    </div>
  );
}

function MissingReviewCard({ skill }: { skill: ReviewSkillName }) {
  return (
    <div className="rounded border border-dashed border-ds-border bg-ds-bg/60 p-2 text-[10px]">
      <div className="text-ds-text">{reviewSkillLabel(skill)}</div>
      <div className="mt-1 text-ds-muted">
        No structured artifact is stored yet. This card will fill automatically when the agent
        emits a hidden Decision OS review artifact for this run.
      </div>
    </div>
  );
}
