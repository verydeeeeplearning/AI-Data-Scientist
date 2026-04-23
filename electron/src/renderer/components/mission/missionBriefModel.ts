import type {
  DeliveryRenderResultView,
  TaskContractErrorDetailView,
} from '../../types/taskContract';

export const DEFAULT_DELIVERY_TENANT = 'default';

export type MissionArtifactGateIssueKind =
  | 'unavailable'
  | 'unmapped'
  | 'contract_missing'
  | 'delivery_missing';

export interface MissionArtifactGateIssue {
  kind: MissionArtifactGateIssueKind;
  label: string;
  artifacts: string[];
}

export interface MissionArtifactGateStatus {
  missionName: string | null;
  requiredArtifacts: string[];
  transitionTarget: string | null;
  failure: string | null;
  ready: boolean;
  issues: MissionArtifactGateIssue[];
}

export function normalizeDeliveryTenant(value: string | null | undefined): string {
  const normalized = typeof value === 'string' ? value.trim() : '';
  return normalized || DEFAULT_DELIVERY_TENANT;
}

export function resolveThemeId(
  globalContext: Record<string, string> | null | undefined,
): string {
  const raw = globalContext?.theme_id;
  return typeof raw === 'string' ? raw.trim() : '';
}

export function buildDeliveryGlobalContext(
  globalContext: Record<string, string> | null | undefined,
  themeId: string,
): Record<string, string> {
  const next = { ...(globalContext ?? {}) };
  const normalizedThemeId = themeId.trim();
  if (normalizedThemeId) {
    next.theme_id = normalizedThemeId;
    return next;
  }
  delete next.theme_id;
  return next;
}

export function resolveProviderBackedRenderOptions(
  providerBacked: boolean,
  model: string,
): {
  providerBacked: boolean;
  model?: string;
} {
  if (!providerBacked) {
    return { providerBacked: false };
  }
  const normalizedModel = model.trim();
  return normalizedModel
    ? { providerBacked: true, model: normalizedModel }
    : { providerBacked: true };
}

export function formatRenderResultNotice(result: DeliveryRenderResultView): string {
  let notice = `Rendered ${result.artifact_id} (${result.format}) to ${result.output_path}.`;
  if (!result.renderer_mode) {
    return notice;
  }
  notice += ` Renderer: ${result.renderer_mode}`;
  if (result.renderer_model) {
    notice += ` | Model: ${result.renderer_model}`;
  }
  return `${notice}.`;
}

export function parseMissionArtifactGate(
  dodSummary: readonly string[],
): MissionArtifactGateStatus | null {
  let missionName: string | null = null;
  let requiredArtifacts: string[] = [];
  let ready = false;
  const issues: MissionArtifactGateIssue[] = [];

  for (const line of dodSummary) {
    const unavailableMatch = line.match(/^Mission artifacts \[(.+?)\]: mission pack unavailable$/);
    if (unavailableMatch) {
      missionName = unavailableMatch[1];
      issues.push({
        kind: 'unavailable',
        label: 'Mission pack unavailable',
        artifacts: [],
      });
      continue;
    }

    const requiredMatch = line.match(/^Mission artifacts \[(.+?)\]: required=(.+)$/);
    if (requiredMatch) {
      missionName = requiredMatch[1];
      requiredArtifacts = splitArtifactList(requiredMatch[2]);
      continue;
    }

    if (line === 'Mission artifacts gate: ready') {
      ready = true;
      continue;
    }

    const gateMatch = line.match(
      /^Mission artifacts gate: (unmapped|contract_missing|delivery_missing)=(.+)$/,
    );
    if (!gateMatch) {
      continue;
    }
    const kind = gateMatch[1] as Exclude<MissionArtifactGateIssueKind, 'unavailable'>;
    issues.push({
      kind,
      label: {
        unmapped: 'Unmapped artifact families',
        contract_missing: 'Missing in contract',
        delivery_missing: 'Missing in delivered outputs',
      }[kind],
      artifacts: splitArtifactList(gateMatch[2]),
    });
  }

  if (missionName === null && requiredArtifacts.length === 0 && issues.length === 0 && !ready) {
    return null;
  }

  return {
    missionName,
    requiredArtifacts,
    transitionTarget: null,
    failure: null,
    ready: ready && issues.length === 0,
    issues,
  };
}

export function parseMissionArtifactGateError(
  detail: TaskContractErrorDetailView | null | undefined,
): MissionArtifactGateStatus | null {
  if (!detail?.metadata || detail.metadata.kind !== 'mission_artifact_gate') {
    return null;
  }

  const metadata = detail.metadata as Record<string, unknown>;
  const transitionTarget = typeof metadata.transition_target === 'string'
    ? metadata.transition_target
    : null;
  const failure = typeof metadata.failure === 'string' ? metadata.failure : null;

  return {
    missionName: typeof metadata.mission_name === 'string' ? metadata.mission_name : null,
    requiredArtifacts: readStringList(metadata.required_artifacts),
    transitionTarget,
    failure,
    ready: false,
    issues: [
      buildMissionArtifactGateIssue('unmapped', metadata.unmapped_required_artifacts),
      buildMissionArtifactGateIssue('contract_missing', metadata.missing_contract_artifacts),
      buildMissionArtifactGateIssue('delivery_missing', metadata.missing_delivery_artifacts),
      failure === 'mission_pack_unavailable'
        ? {
            kind: 'unavailable',
            label: 'Mission pack unavailable',
            artifacts: [],
          }
        : null,
    ].filter((issue): issue is MissionArtifactGateIssue => issue !== null),
  };
}

function splitArtifactList(value: string): string[] {
  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);
}

function readStringList(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
    : [];
}

function buildMissionArtifactGateIssue(
  kind: Exclude<MissionArtifactGateIssueKind, 'unavailable'>,
  value: unknown,
): MissionArtifactGateIssue | null {
  const artifacts = readStringList(value);
  if (artifacts.length === 0) {
    return null;
  }
  return {
    kind,
    label: {
      unmapped: 'Unmapped artifact families',
      contract_missing: 'Missing in contract',
      delivery_missing: 'Missing in delivered outputs',
    }[kind],
    artifacts,
  };
}

// ---------------------------------------------------------------------------
// Mission Check Gate
// ---------------------------------------------------------------------------

export interface MissionCheckGateStatus {
  missionName: string | null;
  transitionTarget: string | null;
  requiredChecks: string[];
  failed: string[];
  unmapped: string[];
  checkResults: Record<string, string>;
}

/**
 * Parse dod_summary lines for the mission required-checks gate.
 * Returns null when no check-gate data is present.
 */
export function parseMissionCheckGate(
  dodSummary: readonly string[],
): MissionCheckGateStatus | null {
  let missionName: string | null = null;
  let requiredChecks: string[] = [];
  let failed: string[] = [];
  let unmapped: string[] = [];
  let hasGateLine = false;

  for (const line of dodSummary) {
    const requiredMatch = line.match(/^Mission checks \[(.+?)\]: required=(.+)$/);
    if (requiredMatch) {
      missionName = requiredMatch[1] ?? null;
      const raw = requiredMatch[2] ?? '';
      requiredChecks = raw === 'none' ? [] : splitArtifactList(raw);
      continue;
    }

    const unavailableMatch = line.match(/^Mission checks \[(.+?)\]: mission pack unavailable$/);
    if (unavailableMatch) {
      missionName = unavailableMatch[1] ?? null;
      hasGateLine = true;
      continue;
    }

    const failedMatch = line.match(/^Mission checks gate: failed=(.+)$/);
    if (failedMatch) {
      failed = splitArtifactList(failedMatch[1] ?? '');
      hasGateLine = true;
      continue;
    }

    const unmappedMatch = line.match(/^Mission checks gate: unmapped=(.+)$/);
    if (unmappedMatch) {
      unmapped = splitArtifactList(unmappedMatch[1] ?? '');
      hasGateLine = true;
      continue;
    }

    if (line === 'Mission checks gate: ready') {
      hasGateLine = true;
      continue;
    }
  }

  if (missionName === null && !hasGateLine) {
    return null;
  }

  return {
    missionName,
    transitionTarget: null,
    requiredChecks,
    failed,
    unmapped,
    checkResults: {},
  };
}

/**
 * Parse a TaskContractErrorDetailView for a mission_check_gate error.
 * Returns null when the error is not a check gate failure.
 */
export function parseMissionCheckGateError(
  detail: TaskContractErrorDetailView | null | undefined,
): MissionCheckGateStatus | null {
  if (!detail?.metadata || detail.metadata['kind'] !== 'mission_check_gate') {
    return null;
  }

  const metadata = detail.metadata as Record<string, unknown>;
  const rawResults = metadata['required_check_results'];
  const checkResults: Record<string, string> =
    rawResults !== null &&
    typeof rawResults === 'object' &&
    !Array.isArray(rawResults)
      ? (rawResults as Record<string, string>)
      : {};

  return {
    missionName: typeof metadata['mission_name'] === 'string' ? metadata['mission_name'] : null,
    transitionTarget:
      typeof metadata['transition_target'] === 'string' ? metadata['transition_target'] : null,
    requiredChecks: readStringList(metadata['required_checks']),
    failed: readStringList(metadata['required_check_failures']),
    unmapped: readStringList(metadata['unmapped_required_checks']),
    checkResults,
  };
}

// ---------------------------------------------------------------------------
// Mission Delivery Channel Gate
// ---------------------------------------------------------------------------

export interface MissionChannelGateStatus {
  missionName: string | null;
  transitionTarget: string | null;
  requiredChannels: string[];
  missing: string[];
  satisfied: string[];
  unmapped: string[];
  dispatchLogAvailable: boolean;
}

/**
 * Parse dod_summary lines for the mission required-delivery-channels gate.
 * Returns null when no channel-gate data is present.
 */
export function parseMissionChannelGate(
  dodSummary: readonly string[],
): MissionChannelGateStatus | null {
  let missionName: string | null = null;
  let requiredChannels: string[] = [];
  let missing: string[] = [];
  let satisfied: string[] = [];
  let unmapped: string[] = [];
  let hasGateLine = false;

  for (const line of dodSummary) {
    const requiredMatch = line.match(/^Mission delivery channels \[(.+?)\]: required=(.+)$/);
    if (requiredMatch) {
      missionName = requiredMatch[1] ?? null;
      const raw = requiredMatch[2] ?? '';
      requiredChannels = raw === 'none' ? [] : splitArtifactList(raw);
      continue;
    }

    const unavailableMatch = line.match(
      /^Mission delivery channels \[(.+?)\]: mission pack unavailable$/,
    );
    if (unavailableMatch) {
      missionName = unavailableMatch[1] ?? null;
      hasGateLine = true;
      continue;
    }

    const dispatchUnavailableMatch = line.match(
      /^Mission delivery channels \[(.+?)\]: dispatch log unavailable$/,
    );
    if (dispatchUnavailableMatch) {
      missionName = dispatchUnavailableMatch[1] ?? null;
      hasGateLine = true;
      continue;
    }

    const satisfiedMatch = line.match(/^Mission delivery channels gate: satisfied=(.+)$/);
    if (satisfiedMatch) {
      satisfied = splitArtifactList(satisfiedMatch[1] ?? '');
      hasGateLine = true;
      continue;
    }

    const unmappedMatch = line.match(/^Mission delivery channels gate: unmapped=(.+)$/);
    if (unmappedMatch) {
      unmapped = splitArtifactList(unmappedMatch[1] ?? '');
      hasGateLine = true;
      continue;
    }

    const missingMatch = line.match(/^Mission delivery channels gate: delivery_missing=(.+)$/);
    if (missingMatch) {
      missing = splitArtifactList(missingMatch[1] ?? '');
      hasGateLine = true;
      continue;
    }

    if (line === 'Mission delivery channels gate: ready') {
      hasGateLine = true;
      continue;
    }
  }

  if (missionName === null && !hasGateLine) {
    return null;
  }

  return {
    missionName,
    transitionTarget: null,
    requiredChannels,
    missing,
    satisfied,
    unmapped,
    dispatchLogAvailable: true,
  };
}

/**
 * Parse a TaskContractErrorDetailView for a mission_delivery_channel_gate error.
 * Returns null when the error is not a channel gate failure.
 */
export function parseMissionChannelGateError(
  detail: TaskContractErrorDetailView | null | undefined,
): MissionChannelGateStatus | null {
  if (!detail?.metadata || detail.metadata['kind'] !== 'mission_delivery_channel_gate') {
    return null;
  }

  const metadata = detail.metadata as Record<string, unknown>;
  return {
    missionName: typeof metadata['mission_name'] === 'string' ? metadata['mission_name'] : null,
    transitionTarget:
      typeof metadata['transition_target'] === 'string' ? metadata['transition_target'] : null,
    requiredChannels: readStringList(metadata['required_delivery_channels']),
    missing: readStringList(metadata['missing_delivery_channels']),
    satisfied: readStringList(metadata['satisfied_delivery_channels']),
    unmapped: readStringList(metadata['unmapped_required_delivery_channels']),
    dispatchLogAvailable:
      typeof metadata['dispatch_log_available'] === 'boolean'
        ? metadata['dispatch_log_available']
        : true,
  };
}

