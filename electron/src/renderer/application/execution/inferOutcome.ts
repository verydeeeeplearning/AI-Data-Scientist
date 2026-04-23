import type { ExecutionToolEvent, Stage, StageOutcome } from '../../domain/execution/stage';

function countMatches(events: readonly ExecutionToolEvent[], pattern: RegExp): number {
  return events.reduce((count, event) => {
    const preview = event.outputPreview ?? '';
    return count + (pattern.test(preview) ? 1 : 0);
  }, 0);
}

function extractRowCount(preview: string): number | null {
  const match = preview.match(/(\d[\d,]*)\s+rows?/i);
  if (!match) {
    return null;
  }
  return Number.parseInt(match[1].replace(/,/g, ''), 10);
}

function summarizeDataLoading(events: readonly ExecutionToolEvent[]): StageOutcome {
  const files = events.length;
  const rows = events.reduce((sum, event) => sum + (extractRowCount(event.outputPreview ?? '') ?? 0), 0);
  if (rows > 0) {
    return { summary: `Loaded ${files} file(s) and scanned ${rows.toLocaleString()} rows.` };
  }
  return { summary: `Loaded ${files} file(s).` };
}

function summarizeSchemaDiagnosis(events: readonly ExecutionToolEvent[]): StageOutcome {
  const issueCount =
    countMatches(events, /\b(issue|warning|missing|duplicate|outlier|drift)\b/i);
  return {
    summary: issueCount > 0 ? `Detected ${issueCount} schema or quality issue(s).` : 'No major schema issues surfaced.',
  };
}

function summarizeEvaluation(events: readonly ExecutionToolEvent[]): StageOutcome {
  const metricMentions = countMatches(events, /\b(auc|rmse|mae|accuracy|f1|precision|recall)\b/i);
  return {
    summary: metricMentions > 0
      ? `Captured ${metricMentions} evaluation signal(s).`
      : `Evaluation completed across ${events.length} tool step(s).`,
  };
}

function summarizeExport(events: readonly ExecutionToolEvent[]): StageOutcome {
  return { summary: `Prepared ${events.length} export artifact(s).` };
}

export function inferOutcome(stage: Pick<Stage, 'key' | 'toolEvents'>): StageOutcome | undefined {
  if (stage.toolEvents.length === 0) {
    return undefined;
  }

  switch (stage.key) {
    case 'data_loading':
      return summarizeDataLoading(stage.toolEvents);
    case 'schema_diagnosis':
      return summarizeSchemaDiagnosis(stage.toolEvents);
    case 'eda':
      return { summary: `Completed ${stage.toolEvents.length} exploratory analysis step(s).` };
    case 'feature_engineering':
      return { summary: `Prepared ${stage.toolEvents.length} feature engineering step(s).` };
    case 'baseline_modeling':
      return { summary: `Built ${stage.toolEvents.length} baseline modeling step(s).` };
    case 'model_comparison':
      return { summary: `Compared ${stage.toolEvents.length} model candidate step(s).` };
    case 'evaluation':
      return summarizeEvaluation(stage.toolEvents);
    case 'reporting':
      return { summary: `Generated ${stage.toolEvents.length} reporting artifact step(s).` };
    case 'verification_certification':
      return { summary: `Ran ${stage.toolEvents.length} verification check(s).` };
    case 'export':
      return summarizeExport(stage.toolEvents);
    default:
      return undefined;
  }
}
