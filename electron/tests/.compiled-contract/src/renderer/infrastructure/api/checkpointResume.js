"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.buildCheckpointResumePrompt = buildCheckpointResumePrompt;
exports.copyCheckpointResumePrompt = copyCheckpointResumePrompt;
function buildCheckpointResumePrompt(options) {
    const references = [
        options.sessionLabel?.trim() ? `Session label: ${options.sessionLabel.trim()}.` : null,
        options.runId?.trim() ? `Latest reference run: ${options.runId.trim()}.` : null,
        options.taskId?.trim() ? `Linked task: ${options.taskId.trim()}.` : null,
    ].filter((value) => value !== null);
    return [
        `Resume session ${options.sessionId} from the latest available checkpoint if one exists.`,
        'Treat the existing session history as the source of truth.',
        ...references,
        'First summarize what is already complete, identify the next incomplete step, and continue from there.',
        'Do not invent branch lineage or restart already confirmed work unless verification shows it is necessary.',
    ].join(' ');
}
async function copyCheckpointResumePrompt(prompt) {
    if (typeof navigator === 'undefined' || !navigator.clipboard?.writeText) {
        return false;
    }
    try {
        await navigator.clipboard.writeText(prompt);
        return true;
    }
    catch {
        return false;
    }
}
