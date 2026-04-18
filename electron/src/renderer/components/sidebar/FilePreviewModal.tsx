/**
 * FilePreviewModal renders the payload returned by the `files.preview` RPC.
 *
 * Supports:
 * - table: tabular previews with summary stats and column profiles
 * - text: truncated markdown / txt / json etc.
 * - binary/unknown: metadata only
 */

import { useEffect, useMemo, useState } from 'react';
import { File, FileCode, FileSpreadsheet, FileText, X } from 'lucide-react';
import { useWs } from '../../hooks/WsProvider';

interface ColumnProfile {
  name: string;
  dtype: string;
  nullCount: number;
  uniqueCount: number;
  sampleValues: string[];
}

type PreviewPayload =
  | {
      kind: 'table';
      path: string;
      name: string;
      size: number;
      columns: string[];
      rows: string[][];
      previewRows: number;
      totalRows: number | null;
      rowCount?: number | null;
      fileSizeMb?: number | null;
      encodingDetected?: string | null;
      selectedSheet?: string | null;
      sheetNames?: string[];
      headerRow?: number | null;
      columnProfiles?: ColumnProfile[];
    }
  | {
      kind: 'text';
      path: string;
      name: string;
      size: number;
      content: string;
      truncated: boolean;
    }
  | {
      kind: 'binary' | 'unknown';
      path: string;
      name: string;
      size: number;
      type: string;
      message?: string;
    }
  | {
      kind: 'error';
      path: string;
      name: string;
      error: string;
    };

interface Props {
  path: string;
  onClose: () => void;
}

const PREVIEW_ROWS = 50;

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function iconFor(name: string) {
  const ext = name.split('.').pop()?.toLowerCase() ?? '';
  if (['csv', 'tsv', 'xlsx', 'xls', 'parquet', 'pq'].includes(ext)) return FileSpreadsheet;
  if (['json', 'py', 'yaml', 'yml', 'toml'].includes(ext)) return FileCode;
  if (['md', 'txt', 'log', 'ini'].includes(ext)) return FileText;
  return File;
}

function clampHeaderRow(value: string): number {
  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed) || Number.isNaN(parsed)) {
    return 1;
  }
  return Math.min(Math.max(parsed, 1), 50);
}

export function FilePreviewModal({ path, onClose }: Props) {
  const { rpc } = useWs();
  const [payload, setPayload] = useState<PreviewPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedSheet, setSelectedSheet] = useState('');
  const [headerRowDraft, setHeaderRowDraft] = useState('1');
  const [appliedSheet, setAppliedSheet] = useState<string | null>(null);
  const [appliedHeaderRow, setAppliedHeaderRow] = useState(1);

  const ext = useMemo(() => path.split('.').pop()?.toLowerCase() ?? '', [path]);
  const isExcel = ext === 'xlsx' || ext === 'xls';

  useEffect(() => {
    setPayload(null);
    setError(null);
    setSelectedSheet('');
    setHeaderRowDraft('1');
    setAppliedSheet(null);
    setAppliedHeaderRow(1);
  }, [path]);

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [onClose]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    const params: Record<string, unknown> = {
      path,
      rows: PREVIEW_ROWS,
      headerRow: appliedHeaderRow,
    };
    if (appliedSheet) {
      params.sheetName = appliedSheet;
    }

    rpc('files.preview', params)
      .then((data) => {
        if (!cancelled) {
          setPayload(data as PreviewPayload);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(String(err?.message ?? err));
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [appliedHeaderRow, appliedSheet, path, rpc]);

  useEffect(() => {
    if (payload?.kind !== 'table') {
      return;
    }
    if (payload.selectedSheet) {
      setSelectedSheet(payload.selectedSheet);
    }
    if (appliedSheet === null && payload.selectedSheet) {
      setAppliedSheet(payload.selectedSheet);
    }
    setHeaderRowDraft(String(payload.headerRow ?? 1));
  }, [appliedSheet, payload]);

  const Icon = iconFor(path.split('/').pop() ?? path);
  const effectiveSelectedSheet =
    selectedSheet || (payload?.kind === 'table' ? payload.selectedSheet ?? '' : '');
  const canApplyWizard =
    !loading
    && (effectiveSelectedSheet !== (appliedSheet ?? '') || clampHeaderRow(headerRowDraft) !== appliedHeaderRow);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="file-preview-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70"
      onClick={onClose}
    >
      <div
        className="relative flex max-h-[85vh] w-[min(92vw,1100px)] flex-col overflow-hidden rounded-lg border border-ds-border bg-ds-surface shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-2 border-b border-ds-border px-4 py-2">
          <Icon size={16} className="text-ds-muted" />
          <span id="file-preview-title" className="flex-1 truncate text-sm font-medium text-ds-text">{path}</span>
          {payload && 'size' in payload && (
            <span className="text-[11px] text-ds-muted/70">{formatSize(payload.size)}</span>
          )}
          <button
            onClick={onClose}
            aria-label="Close preview"
            className="rounded p-1 text-ds-muted hover:bg-ds-bg hover:text-ds-text"
          >
            <X size={16} />
          </button>
        </div>

        <div className="flex-1 overflow-auto p-4">
          {loading && <div className="text-sm text-ds-muted">Loading preview...</div>}
          {error && <div className="text-sm text-red-400">Failed to load: {error}</div>}

          {!loading && !error && payload?.kind === 'table' && (
            <TablePreview
              payload={payload}
              isExcel={isExcel}
              selectedSheet={selectedSheet}
              onSelectSheet={setSelectedSheet}
              headerRowDraft={headerRowDraft}
              onChangeHeaderRow={setHeaderRowDraft}
              onApply={() => {
                setAppliedSheet(selectedSheet || payload.selectedSheet || null);
                setAppliedHeaderRow(clampHeaderRow(headerRowDraft));
              }}
              canApplyWizard={canApplyWizard}
            />
          )}

          {!loading && !error && payload?.kind === 'text' && (
            <div>
              <pre className="whitespace-pre-wrap break-words font-mono text-[12px] text-ds-text/90">
                {payload.content}
              </pre>
              {payload.truncated && (
                <div className="mt-2 text-[11px] text-ds-muted">Truncated at 256 KB.</div>
              )}
            </div>
          )}

          {!loading && !error && (payload?.kind === 'binary' || payload?.kind === 'unknown') && (
            <div className="text-sm text-ds-muted">
              <p>Binary file - no inline preview.</p>
              {'message' in payload && payload.message && (
                <p className="mt-1 text-[11px]">{payload.message}</p>
              )}
            </div>
          )}

          {!loading && !error && payload?.kind === 'error' && (
            <div className="text-sm text-red-400">{payload.error}</div>
          )}
        </div>
      </div>
    </div>
  );
}

function TablePreview({
  payload,
  isExcel,
  selectedSheet,
  onSelectSheet,
  headerRowDraft,
  onChangeHeaderRow,
  onApply,
  canApplyWizard,
}: {
  payload: Extract<PreviewPayload, { kind: 'table' }>;
  isExcel: boolean;
  selectedSheet: string;
  onSelectSheet: (sheet: string) => void;
  headerRowDraft: string;
  onChangeHeaderRow: (headerRow: string) => void;
  onApply: () => void;
  canApplyWizard: boolean;
}) {
  const columnProfiles = payload.columnProfiles ?? [];
  const hasNulls = columnProfiles.some((column) => column.nullCount > 0);
  const showExcelWizard = isExcel && (payload.sheetNames?.length ?? 0) > 0;

  return (
    <div className="space-y-4">
      {showExcelWizard && (
        <div className="rounded-lg border border-ds-border bg-ds-bg p-3">
          <div className="text-[11px] font-medium uppercase tracking-wider text-ds-muted">
            Excel Preview
          </div>
          <div className="mt-3 grid gap-3 sm:grid-cols-[minmax(0,1fr)_120px_auto]">
            <label className="space-y-1">
              <span className="text-[10px] uppercase tracking-wider text-ds-muted">Sheet</span>
              <select
                value={selectedSheet || payload.selectedSheet || payload.sheetNames?.[0] || ''}
                onChange={(event) => onSelectSheet(event.target.value)}
                className="w-full rounded border border-ds-border bg-ds-surface px-3 py-2 text-xs text-ds-text focus:border-ds-accent focus:outline-none"
              >
                {(payload.sheetNames ?? []).map((sheetName) => (
                  <option key={sheetName} value={sheetName}>
                    {sheetName}
                  </option>
                ))}
              </select>
            </label>

            <label className="space-y-1">
              <span className="text-[10px] uppercase tracking-wider text-ds-muted">Header Row</span>
              <input
                type="number"
                min={1}
                max={50}
                value={headerRowDraft}
                onChange={(event) => onChangeHeaderRow(event.target.value)}
                className="w-full rounded border border-ds-border bg-ds-surface px-3 py-2 text-xs text-ds-text focus:border-ds-accent focus:outline-none"
              />
            </label>

            <div className="flex items-end">
              <button
                onClick={onApply}
                disabled={!canApplyWizard}
                className="rounded border border-ds-border px-3 py-2 text-xs font-medium text-ds-text transition-colors hover:border-ds-accent/50 hover:text-ds-accent disabled:cursor-not-allowed disabled:opacity-40"
              >
                Apply
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
        <SummaryCard
          label="Rows"
          value={
            payload.rowCount != null
              ? payload.rowCount.toLocaleString()
              : `${payload.previewRows.toLocaleString()} preview`
          }
        />
        <SummaryCard label="Columns" value={payload.columns.length.toString()} />
        <SummaryCard
          label="File Size"
          value={
            typeof payload.fileSizeMb === 'number'
              ? `${payload.fileSizeMb.toFixed(2)} MB`
              : formatSize(payload.size)
          }
        />
        <SummaryCard
          label={payload.selectedSheet ? 'Sheet' : 'Encoding'}
          value={payload.selectedSheet ?? payload.encodingDetected ?? 'Detected automatically'}
        />
      </div>

      {hasNulls && (
        <div className="rounded-lg border border-ds-accent/30 bg-ds-accent/10 px-3 py-2 text-[11px] text-ds-muted">
          Blank values were detected in this preview. The agent can still analyze the file, but it
          may clean or impute missing values during preparation.
        </div>
      )}

      {payload.selectedSheet && (payload.sheetNames?.length ?? 0) > 1 && (
        <div className="text-[11px] text-ds-muted">
          Previewing sheet <span className="font-medium text-ds-text">{payload.selectedSheet}</span>{' '}
          of {payload.sheetNames?.length} sheets.
        </div>
      )}

      <div className="overflow-auto rounded-lg border border-ds-border">
        <table className="w-full border-collapse text-[11px]">
          <thead className="sticky top-0 bg-ds-surface">
            <tr>
              {payload.columns.map((column) => (
                <th
                  key={column}
                  className="whitespace-nowrap border-b border-ds-border px-2 py-1 text-left font-medium text-ds-text"
                >
                  {column}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {payload.rows.map((row, rowIndex) => (
              <tr key={`${payload.path}-${rowIndex}`} className="hover:bg-ds-bg/50">
                {row.map((cell, cellIndex) => (
                  <td
                    key={`${payload.columns[cellIndex] ?? cellIndex}-${rowIndex}`}
                    className="whitespace-nowrap border-b border-ds-border/40 px-2 py-1 text-ds-text/80"
                  >
                    {cell || <span className="text-ds-muted/50">empty</span>}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {columnProfiles.length > 0 && (
        <div className="space-y-2">
          <div className="text-[11px] font-medium uppercase tracking-wider text-ds-muted">
            Column Profile
          </div>
          <div className="grid gap-2 lg:grid-cols-2">
            {columnProfiles.map((column) => (
              <div key={column.name} className="rounded-lg border border-ds-border bg-ds-bg p-3">
                <div className="flex items-center justify-between gap-2">
                  <div className="truncate text-xs font-medium text-ds-text">{column.name}</div>
                  <div className="text-[10px] uppercase tracking-wider text-ds-muted">
                    {column.dtype}
                  </div>
                </div>
                <div className="mt-2 flex flex-wrap gap-2 text-[10px] text-ds-muted">
                  <span>{column.nullCount} nulls</span>
                  <span>{column.uniqueCount} unique</span>
                </div>
                <div className="mt-2 text-[10px] text-ds-muted">
                  {column.sampleValues.length > 0 ? (
                    <>Samples: {column.sampleValues.join(', ')}</>
                  ) : (
                    'Samples: none in preview'
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="text-[11px] text-ds-muted">
        Showing {payload.previewRows}
        {payload.totalRows != null && ` of ${payload.totalRows}`} rows and {payload.columns.length}{' '}
        columns.
      </div>
    </div>
  );
}

function SummaryCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-ds-border bg-ds-bg px-3 py-2">
      <div className="text-[10px] uppercase tracking-wider text-ds-muted">{label}</div>
      <div className="mt-1 text-sm font-medium text-ds-text">{value}</div>
    </div>
  );
}
