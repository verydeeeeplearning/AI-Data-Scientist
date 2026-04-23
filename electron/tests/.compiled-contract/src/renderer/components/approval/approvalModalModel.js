"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.mergeApprovalDetails = mergeApprovalDetails;
exports.buildApprovalModalViewModel = buildApprovalModalViewModel;
const AFFECTED_SCOPE_ORDER = [
    'network',
    'filesystem',
    'secret',
    'subprocess',
];
const APPROVAL_SCOPE_OPTIONS = [
    {
        id: 'once',
        label: 'Allow once',
        description: 'Approve only this blocked step. Recommended while the richer policy flow is still rolling out.',
        recommended: true,
    },
    {
        id: 'session',
        label: 'Allow for session',
        description: 'Record the operator intent for this session so nearby follow-up work can stay unblocked.',
    },
    {
        id: 'workspace',
        label: 'Allow for workspace',
        description: 'Record the operator intent at the workspace level for future runs that need the same approval.',
    },
];
const IMPACT_COPY = {
    network: {
        id: 'network',
        label: 'Network',
        description: 'The agent may call an external service or fetch remote content.',
    },
    filesystem: {
        id: 'filesystem',
        label: 'Filesystem',
        description: 'The action can read, write, move, or delete files on disk.',
    },
    secret: {
        id: 'secret',
        label: 'Secrets',
        description: 'The request may expose API keys, tokens, or credential-bearing files.',
    },
    subprocess: {
        id: 'subprocess',
        label: 'Subprocess',
        description: 'The agent may spawn code or shell execution outside the normal safe tool path.',
    },
};
const BINARY_APPROVE_OPTIONS = new Set([
    'allow',
    'allowed',
    'approve',
    'approved',
    'accept',
    'accepted',
    'proceed',
    'continue',
    'yes',
    'y',
]);
const BINARY_DENY_OPTIONS = new Set([
    'deny',
    'denied',
    'reject',
    'rejected',
    'decline',
    'cancel',
    'stop',
    'no',
    'n',
]);
function mergeApprovalDetails(approval, raw = null) {
    const payload = isRecord(raw) ? raw : null;
    const metadata = toRecord(payload?.metadata) ?? approval.metadata;
    return {
        approvalId: readString(payload, 'approvalId') ?? approval.approvalId,
        sessionId: readString(payload, 'sessionId') ?? approval.sessionId,
        runId: readNullableString(payload, 'runId') ?? approval.runId ?? null,
        surface: readString(payload, 'surface') ?? approval.surface,
        question: readString(payload, 'question') ?? approval.question,
        kind: readString(payload, 'kind') ?? approval.kind,
        metadata,
        options: readStringArray(payload, 'options') ?? approval.options,
        default: readNullableString(payload, 'default') ?? approval.default ?? null,
        status: readString(payload, 'status') ?? approval.status,
        response: readNullableString(payload, 'response') ?? approval.response ?? null,
        source: readNullableString(payload, 'source') ?? approval.source ?? null,
        actor: readNullableString(payload, 'actor') ?? approval.actor ?? null,
        createdAt: readNumber(payload, 'createdAt') ?? approval.createdAt,
        updatedAt: readNumber(payload, 'updatedAt') ?? approval.updatedAt,
        resolvedAt: readNullableNumber(payload, 'resolvedAt') ?? approval.resolvedAt ?? null,
        workspaceId: readNullableString(payload, 'workspaceId'),
        triggeredBy: toRecord(payload?.triggeredBy) ?? null,
        riskCode: readString(payload, 'riskCode') ?? readString(metadata, 'riskCode') ?? undefined,
        patternMatches: normalizePatternMatches(payload?.patternMatches ?? metadata.patternMatches ?? metadata.pattern_matches),
        affectedScopes: normalizeAffectedScopes(payload?.affectedScopes ?? metadata.affectedScopes ?? metadata.affected_scopes),
        recommendedAlternative: readNullableString(payload, 'recommendedAlternative')
            ?? readNullableString(metadata, 'recommendedAlternative')
            ?? readNullableString(metadata, 'recommended_alternative')
            ?? null,
        expiresAt: readNullableNumber(payload, 'expiresAt')
            ?? readNullableNumber(metadata, 'expiresAt')
            ?? readNullableNumber(metadata, 'expires_at')
            ?? null,
    };
}
function buildApprovalModalViewModel(details) {
    const impactItems = details.affectedScopes.map((scope) => IMPACT_COPY[scope]);
    const severity = deriveSeverity(details);
    const patternCards = details.patternMatches.map((match) => ({
        id: match.patternId || match.description,
        title: match.description || match.patternId || 'Policy match',
        highlights: match.highlightedLines.map((item) => `Line ${item.line}: ${item.reason}`),
    }));
    return {
        title: buildTitle(details),
        severity,
        severityLabel: severityLabel(severity),
        summary: details.question,
        explanation: buildExplanation(details, impactItems),
        responseOptions: filterResponseOptions(details.options),
        scopeOptions: APPROVAL_SCOPE_OPTIONS.map((item) => ({ ...item })),
        impactItems,
        recommendedAlternative: details.recommendedAlternative ?? undefined,
        infoRows: buildInfoRows(details),
        patternCards,
        codePreview: buildCodePreview(details),
    };
}
function buildTitle(details) {
    if (details.kind === 'semantic_proposal') {
        return 'Semantic proposal approval';
    }
    if (details.affectedScopes.includes('secret')) {
        return 'Secret access approval';
    }
    if (details.affectedScopes.includes('network')) {
        return 'Network access approval';
    }
    if (details.affectedScopes.includes('filesystem')) {
        return 'Filesystem approval';
    }
    if (details.affectedScopes.includes('subprocess')) {
        return 'Execution approval';
    }
    if (details.kind.startsWith('PAT_')) {
        return 'Policy exception approval';
    }
    return 'Operator approval required';
}
function buildExplanation(details, impactItems) {
    if (details.patternMatches.length > 0) {
        return details.patternMatches[0].description;
    }
    if (details.kind === 'semantic_proposal') {
        return 'The agent wants approval to review or apply a semantic-memory proposal that can affect future query behavior.';
    }
    if (impactItems.length > 0) {
        const labels = impactItems.map((item) => item.label.toLowerCase());
        return `This request can affect ${joinWithAnd(labels)}. Review the requested persistence scope before allowing it.`;
    }
    return 'The agent paused because it needs an explicit operator decision before continuing this workflow.';
}
function deriveSeverity(details) {
    if (details.affectedScopes.includes('secret')
        || details.affectedScopes.includes('subprocess')
        || details.patternMatches.length > 1
        || details.kind.startsWith('PAT_')) {
        return 'high';
    }
    if (details.affectedScopes.includes('network')
        || details.affectedScopes.includes('filesystem')
        || details.kind === 'semantic_proposal') {
        return 'medium';
    }
    return 'low';
}
function severityLabel(value) {
    if (value === 'high')
        return 'Higher-risk request';
    if (value === 'medium')
        return 'Review recommended';
    return 'Operator confirmation';
}
function filterResponseOptions(options) {
    const deduped = Array.from(new Map(options
        .map((item) => item.trim())
        .filter((item) => item.length > 0)
        .map((item) => [item.toLowerCase(), item])).values());
    if (deduped.length === 0) {
        return [];
    }
    const normalized = deduped.map((item) => item.toLowerCase());
    const hasApprove = normalized.some((item) => BINARY_APPROVE_OPTIONS.has(item));
    const hasDeny = normalized.some((item) => BINARY_DENY_OPTIONS.has(item));
    if (deduped.length <= 2 && hasApprove && hasDeny) {
        return [];
    }
    return deduped;
}
function buildInfoRows(details) {
    const rows = [];
    const metadata = details.metadata;
    pushRow(rows, 'Kind', humanizeLabel(details.kind));
    pushRow(rows, 'Surface', humanizeLabel(details.surface));
    pushRow(rows, 'Run', details.runId ?? undefined);
    pushRow(rows, 'Workspace', details.workspaceId ?? undefined);
    pushRow(rows, 'Request', details.approvalId);
    const proposalType = readNullableString(metadata, 'proposalType');
    const targetId = readNullableString(metadata, 'targetId');
    const risk = readNullableString(metadata, 'risk');
    const confidence = readNumber(metadata, 'confidence');
    const autoApply = metadata.autoApplyEligible === true ? 'Eligible' : undefined;
    const toolCallId = readNullableString(details.triggeredBy, 'toolCallId');
    pushRow(rows, 'Proposal', proposalType ? humanizeLabel(proposalType) : undefined);
    pushRow(rows, 'Target', targetId ?? undefined);
    pushRow(rows, 'Risk', risk ? humanizeLabel(risk) : undefined);
    pushRow(rows, 'Confidence', confidence !== undefined ? `${Math.round(confidence * 100)}%` : undefined);
    pushRow(rows, 'Auto-apply', autoApply);
    pushRow(rows, 'Tool call', toolCallId ?? undefined);
    if (details.expiresAt) {
        pushRow(rows, 'Expires', formatTimestamp(details.expiresAt));
    }
    return rows.slice(0, 8);
}
function pushRow(rows, label, value) {
    if (!value)
        return;
    rows.push({ label, value });
}
function buildCodePreview(details) {
    const snippet = extractSnippet(details.metadata);
    if (!snippet) {
        return undefined;
    }
    const lines = snippet.value.replace(/\r\n/g, '\n').split('\n');
    const reasonByLine = new Map();
    for (const match of details.patternMatches) {
        for (const item of match.highlightedLines) {
            if (!reasonByLine.has(item.line)) {
                reasonByLine.set(item.line, item.reason);
            }
        }
    }
    const windowed = choosePreviewWindow(lines.length, Array.from(reasonByLine.keys()));
    return {
        label: snippet.label,
        language: snippet.language,
        truncated: windowed.start > 1 || windowed.end < lines.length,
        lines: lines.slice(windowed.start - 1, windowed.end).map((text, index) => {
            const lineNumber = windowed.start + index;
            return {
                number: lineNumber,
                text,
                reason: reasonByLine.get(lineNumber),
            };
        }),
    };
}
function choosePreviewWindow(totalLines, highlightedLines) {
    if (totalLines <= 12) {
        return { start: 1, end: totalLines };
    }
    const firstHighlight = highlightedLines.length > 0 ? Math.min(...highlightedLines) : 1;
    const start = clamp(firstHighlight - 3, 1, Math.max(1, totalLines - 11));
    const end = Math.min(totalLines, start + 11);
    return { start, end };
}
function extractSnippet(metadata) {
    const explicitLanguage = readNullableString(metadata, 'language')
        ?? readNullableString(metadata, 'codeLanguage');
    const candidates = [
        { key: 'codeSnippet', label: 'Code preview', language: explicitLanguage ?? 'python' },
        { key: 'snippet', label: 'Code preview', language: explicitLanguage ?? 'python' },
        { key: 'proposedCode', label: 'Proposed code', language: explicitLanguage ?? 'python' },
        { key: 'sql', label: 'SQL preview', language: 'sql' },
        { key: 'query', label: 'Query preview', language: explicitLanguage ?? 'sql' },
        { key: 'command', label: 'Command preview', language: 'bash' },
        { key: 'script', label: 'Script preview', language: explicitLanguage ?? 'python' },
    ];
    for (const candidate of candidates) {
        const value = readNullableString(metadata, candidate.key);
        if (value) {
            return {
                label: candidate.label,
                language: candidate.language,
                value,
            };
        }
    }
    return undefined;
}
function normalizePatternMatches(value) {
    if (!Array.isArray(value)) {
        return [];
    }
    const matches = [];
    for (const item of value) {
        if (!isRecord(item))
            continue;
        matches.push({
            patternId: readString(item, 'patternId')
                ?? readString(item, 'pattern_id')
                ?? readString(item, 'id')
                ?? '',
            description: readString(item, 'description')
                ?? readString(item, 'detail')
                ?? readString(item, 'patternId')
                ?? 'Policy match',
            highlightedLines: normalizePatternHighlights(item.highlightedLines ?? item.highlighted_lines ?? item.lines),
        });
    }
    return matches;
}
function normalizePatternHighlights(value) {
    if (!Array.isArray(value)) {
        return [];
    }
    const highlights = [];
    for (const item of value) {
        if (isRecord(item)) {
            const line = readNumber(item, 'line');
            const reason = readString(item, 'reason');
            if (line !== undefined && reason) {
                highlights.push({ line, reason });
            }
            continue;
        }
        if (Array.isArray(item) && item.length >= 2) {
            const line = typeof item[0] === 'number' ? item[0] : Number(item[0]);
            const reason = typeof item[1] === 'string' ? item[1] : String(item[1] ?? '');
            if (Number.isFinite(line) && reason.trim().length > 0) {
                highlights.push({ line, reason });
            }
        }
    }
    return highlights;
}
function normalizeAffectedScopes(value) {
    if (!Array.isArray(value)) {
        return [];
    }
    const set = new Set();
    for (const item of value) {
        if (typeof item !== 'string')
            continue;
        const normalized = item.trim().toLowerCase();
        if (AFFECTED_SCOPE_ORDER.includes(normalized)) {
            set.add(normalized);
        }
    }
    return AFFECTED_SCOPE_ORDER.filter((item) => set.has(item));
}
function readString(payload, key) {
    if (!payload)
        return undefined;
    const value = payload[key];
    return typeof value === 'string' && value.trim().length > 0 ? value.trim() : undefined;
}
function readNullableString(payload, key) {
    if (!payload)
        return undefined;
    const value = payload[key];
    if (value === null)
        return null;
    return typeof value === 'string' ? value : undefined;
}
function readNumber(payload, key) {
    if (!payload)
        return undefined;
    const value = payload[key];
    return typeof value === 'number' && Number.isFinite(value) ? value : undefined;
}
function readNullableNumber(payload, key) {
    if (!payload)
        return undefined;
    const value = payload[key];
    if (value === null)
        return null;
    return typeof value === 'number' && Number.isFinite(value) ? value : undefined;
}
function readStringArray(payload, key) {
    if (!payload)
        return undefined;
    const value = payload[key];
    if (!Array.isArray(value)) {
        return undefined;
    }
    return value.filter((item) => typeof item === 'string');
}
function toRecord(value) {
    return isRecord(value) ? value : null;
}
function isRecord(value) {
    return typeof value === 'object' && value !== null;
}
function humanizeLabel(value) {
    return value
        .replace(/[_-]+/g, ' ')
        .replace(/\s+/g, ' ')
        .trim()
        .replace(/\b\w/g, (match) => match.toUpperCase());
}
function joinWithAnd(values) {
    if (values.length <= 1) {
        return values[0] ?? '';
    }
    if (values.length === 2) {
        return `${values[0]} and ${values[1]}`;
    }
    return `${values.slice(0, -1).join(', ')}, and ${values[values.length - 1]}`;
}
function formatTimestamp(value) {
    const epochMs = value > 1000000000000 ? value : value * 1000;
    return new Date(epochMs).toISOString().replace('T', ' ').slice(0, 16) + ' UTC';
}
function clamp(value, min, max) {
    return Math.min(Math.max(value, min), max);
}
