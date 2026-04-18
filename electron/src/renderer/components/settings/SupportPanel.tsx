import { useState } from 'react';
import { ExternalLink, FolderOpen, Loader2, ShieldCheck } from 'lucide-react';

function supportDefaultName(): string {
  return `ds-agent-support-${new Date().toISOString().replace(/[:.]/g, '-')}.zip`;
}

export function SupportPanel() {
  const [exporting, setExporting] = useState(false);
  const [exportPath, setExportPath] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleExport = async () => {
    if (!window.electronAPI?.exportSupportBundle) {
      setErrorMessage('Desktop support export is unavailable in this environment.');
      return;
    }
    setExporting(true);
    try {
      const result = await window.electronAPI.exportSupportBundle(supportDefaultName());
      if (result.canceled) {
        return;
      }
      if (result.error) {
        setErrorMessage(result.error);
        return;
      }
      setExportPath(result.path);
      setErrorMessage(null);
    } finally {
      setExporting(false);
    }
  };

  const handleReveal = async () => {
    if (!exportPath || !window.electronAPI?.revealPath) {
      return;
    }
    const result = await window.electronAPI.revealPath(exportPath);
    if (!result.ok) {
      setErrorMessage(result.error ?? 'Unable to reveal the exported bundle.');
    }
  };

  return (
    <div className="rounded-xl border border-ds-border bg-ds-surface p-4">
      <div className="flex items-start gap-3">
        <div className="rounded-lg bg-ds-accent/15 p-2 text-ds-accent">
          <ShieldCheck size={16} />
        </div>
        <div className="flex-1">
          <h4 className="text-sm font-semibold text-ds-text">Support Bundle</h4>
          <p className="mt-1 text-[11px] text-ds-muted">
            Export a redacted ZIP bundle with configuration, runtime events, audit logs, and system
            diagnostics. API keys, OAuth tokens, and bot secrets are automatically removed.
          </p>
        </div>
      </div>

      {errorMessage && (
        <div className="mt-3 rounded-lg border border-red-500/40 bg-red-500/10 px-3 py-2 text-[11px] text-red-200">
          {errorMessage}
        </div>
      )}

      {exportPath && (
        <div className="mt-3 rounded-lg border border-ds-accent/30 bg-ds-accent/10 px-3 py-2 text-[11px] text-ds-text">
          Saved to: {exportPath}
        </div>
      )}

      <div className="mt-4 flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <button
          onClick={() => void handleExport()}
          disabled={exporting}
          className="inline-flex items-center justify-center gap-2 rounded-lg bg-ds-accent px-3 py-2 text-xs font-medium text-white transition-colors hover:bg-ds-accent-hover disabled:opacity-40"
        >
          {exporting ? <Loader2 size={12} className="animate-spin" /> : <ShieldCheck size={12} />}
          {exporting ? 'Collecting...' : 'Export Support Bundle'}
        </button>

        <div className="flex gap-2">
          <button
            onClick={() => void handleReveal()}
            disabled={!exportPath}
            className="inline-flex items-center gap-2 rounded-lg border border-ds-border bg-ds-bg px-3 py-2 text-xs font-medium text-ds-text transition-colors hover:border-ds-accent/50 disabled:opacity-40"
          >
            <FolderOpen size={12} />
            Reveal Bundle
          </button>
          <a
            href="https://github.com/org/ds-agent/issues"
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-2 rounded-lg border border-ds-border bg-ds-bg px-3 py-2 text-xs font-medium text-ds-text transition-colors hover:border-ds-accent/50"
          >
            <ExternalLink size={12} />
            GitHub Issues
          </a>
        </div>
      </div>
    </div>
  );
}
