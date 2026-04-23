/**
 * FilePreviewModal renders the payload returned by the `files.preview` RPC.
 *
 * Supports:
 * - table: tabular previews with summary stats and column profiles
 * - text: truncated markdown / txt / json etc.
 * - binary/unknown: metadata only
 */

import { useEffect, useId, useMemo, useRef, useState } from 'react';
import { File, FileCode, FileSpreadsheet, FileText, X } from 'lucide-react';
import {
  Badge,
  Button,
  Card,
  Input,
  Select,
  joinIds,
} from '../../design-system/primitives';
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
      sheetNames?: string[] | null;
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

function baseName(filePath: string): string {
  return filePath.split(/[/\\]/).pop() ?? filePath;
}

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

export function clampHeaderRow(value: string): number {
  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed) || Number.isNaN(parsed)) {
    return 1;
  }
  return Math.min(Math.max(parsed, 1), 50);
}

export function buildPreviewRequest(
  path: string,
  headerRow: number,
  sheetName: string | null,
): Record<string, unknown> {
  const request: Record<string, unknown> = {
    path,
    rows: PREVIEW_ROWS,
    headerRow,
  };
  if (sheetName) {
    request.sheetName = sheetName;
  }
  return request;
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
  const restoreFocusRef = useRef<HTMLElement | null>(null);

  const generatedId = useId().replace(/:/g, '');
  const dialogId = `file-preview-dialog-${generatedId}`;
  const titleId = `${dialogId}-title`;
  const descriptionId = `${dialogId}-description`;
  const statusId = `${dialogId}-status`;

  const fileName = useMemo(() => baseName(path), [path]);
  const ext = useMemo(() => fileName.split('.').pop()?.toLowerCase() ?? '', [fileName]);
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
    restoreFocusRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const frame = window.requestAnimationFrame(() => {
      const dialog = document.getElementById(dialogId);
      if (dialog instanceof HTMLElement) {
        dialog.focus();
      }
    });
    return () => {
      window.cancelAnimationFrame(frame);
      restoreFocusRef.current?.focus();
    };
  }, [dialogId]);

  useEffect(() => {
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [onClose]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    rpc('files.preview', buildPreviewRequest(path, appliedHeaderRow, appliedSheet))
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

  const Icon = iconFor(fileName);
  const effectiveSelectedSheet =
    selectedSheet || (payload?.kind === 'table' ? payload.selectedSheet ?? '' : '');
  const canApplyWizard =
    !loading
    && (effectiveSelectedSheet !== (appliedSheet ?? '') || clampHeaderRow(headerRowDraft) !== appliedHeaderRow);

  const payloadSize = payload && 'size' in payload ? payload.size : null;
  const description =
    payload?.kind === 'table'
      ? 'Preview the sampled rows, schema details, and spreadsheet controls before analysis.'
      : 'Preview file contents and metadata before analysis.';

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-ds-4"
      onClick={onClose}
    >
      <Card
        id={dialogId}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={joinIds(descriptionId, statusId)}
        tabIndex={-1}
        className="relative flex max-h-[85vh] w-[min(92vw,1100px)] flex-col overflow-hidden border-ds-border bg-ds-surface p-0 shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-center gap-ds-2 border-b border-ds-border px-ds-4 py-ds-3">
          <Icon size={16} className="text-ds-muted" aria-hidden="true" />
          <div className="min-w-0 flex-1">
            <div id={titleId} className="truncate text-ds-sm font-medium text-ds-text">
              {fileName}
            </div>
            <div id={descriptionId} className="mt-ds-1 text-ds-xs text-ds-muted">
              {description}
            </div>
          </div>
          {payloadSize != null ? (
            <Badge compact tone="neutral">
              {formatSize(payloadSize)}
            </Badge>
          ) : null}
          <Button
            variant="ghost"
            size="sm"
            aria-label="Close preview"
            className="h-8 min-h-8 w-8 rounded-ds-md px-0 shadow-none"
            onClick={onClose}
          >
            <X size={16} aria-hidden="true" />
          </Button>
        </div>

        <div className="flex-1 overflow-auto p-ds-4">
          <div id={statusId} className="sr-only" aria-live="polite">
            {loading
              ? 'Loading preview'
              : error
                ? `Preview failed: ${error}`
                : payload?.kind === 'table'
                  ? 'Tabular preview loaded'
                  : 'Preview loaded'}
          </div>

          {loading ? (
            <Card className="bg-ds-bg/40 text-ds-sm text-ds-muted shadow-none">
              Loading preview...
            </Card>
          ) : null}

          {error ? (
            <Card tone="danger" className="text-ds-sm shadow-none">
              Failed to load: {error}
            </Card>
          ) : null}

          {!loading && !error && payload?.kind === 'table' ? (
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
          ) : null}

          {!loading && !error && payload?.kind === 'text' ? (
            <Card className="space-y-ds-3 bg-ds-bg/30 shadow-none">
              <pre className="whitespace-pre-wrap break-words font-mono text-[12px] text-ds-text/90">
                {payload.content}
              </pre>
              {payload.truncated ? (
                <Badge compact tone="warning">
                  Truncated at 256 KB
                </Badge>
              ) : null}
            </Card>
          ) : null}

          {!loading && !error && (payload?.kind === 'binary' || payload?.kind === 'unknown') ? (
            <Card className="space-y-ds-2 bg-ds-bg/30 text-ds-sm text-ds-muted shadow-none">
              <div>Binary file. Inline preview is not available.</div>
              {'message' in payload && payload.message ? (
                <div className="text-ds-xs">{payload.message}</div>
              ) : null}
            </Card>
          ) : null}

          {!loading && !error && payload?.kind === 'error' ? (
            <Card tone="danger" className="text-ds-sm shadow-none">
              {payload.error}
            </Card>
          ) : null}
        </div>
      </Card>
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
    <div className="space-y-ds-4">
      {showExcelWizard ? (
        <Card className="space-y-ds-3 bg-ds-bg/40 shadow-none">
          <div className="text-[11px] font-medium uppercase tracking-wider text-ds-muted">
            Excel preview
          </div>
          <div className="grid gap-ds-3 sm:grid-cols-[minmax(0,1fr)_180px_auto]">
            <Select
              label="Sheet"
              options={(payload.sheetNames ?? []).map((sheetName) => ({
                value: sheetName,
                label: sheetName,
              }))}
              value={selectedSheet || payload.selectedSheet || payload.sheetNames?.[0] || ''}
              onChange={(event) => onSelectSheet(event.target.value)}
            />
            <Input
              label="Header row"
              type="number"
              min={1}
              max={50}
              value={headerRowDraft}
              onChange={(event) => onChangeHeaderRow(event.target.value)}
            />
            <div className="flex items-end">
              <Button
                variant="secondary"
                size="md"
                className="w-full rounded-ds-lg px-ds-4"
                disabled={!canApplyWizard}
                onClick={onApply}
              >
                Apply
              </Button>
            </div>
          </div>
        </Card>
      ) : null}

      <div className="grid gap-ds-2 sm:grid-cols-2 xl:grid-cols-4">
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
          label="File size"
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

      {hasNulls ? (
        <Card tone="accent" className="text-[11px] text-ds-muted shadow-none">
          Blank values were detected in this preview. The agent can still analyze the file, but it
          may clean or impute missing values during preparation.
        </Card>
      ) : null}

      {payload.selectedSheet && (payload.sheetNames?.length ?? 0) > 1 ? (
        <div className="text-[11px] text-ds-muted">
          Previewing sheet <span className="font-medium text-ds-text">{payload.selectedSheet}</span>{' '}
          of {payload.sheetNames?.length} sheets.
        </div>
      ) : null}

      <div className="overflow-auto rounded-ds-xl border border-ds-border">
        <table className="w-full border-collapse text-[11px]">
          <caption className="sr-only">
            Preview table for {payload.path} showing {payload.previewRows} rows.
          </caption>
          <thead className="sticky top-0 bg-ds-surface">
            <tr>
              {payload.columns.map((column) => (
                <th
                  key={column}
                  className="whitespace-nowrap border-b border-ds-border px-ds-2 py-ds-2 text-left font-medium text-ds-text"
                  scope="col"
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
                    className="whitespace-nowrap border-b border-ds-border/40 px-ds-2 py-ds-2 text-ds-text/80"
                  >
                    {cell || <span className="text-ds-muted/50">empty</span>}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {columnProfiles.length > 0 ? (
        <div className="space-y-ds-2">
          <div className="text-[11px] font-medium uppercase tracking-wider text-ds-muted">
            Column profile
          </div>
          <div className="grid gap-ds-2 lg:grid-cols-2">
            {columnProfiles.map((column) => (
              <Card key={column.name} className="bg-ds-bg/40 shadow-none">
                <div className="flex items-center justify-between gap-ds-2">
                  <div className="truncate text-xs font-medium text-ds-text">{column.name}</div>
                  <Badge compact tone="neutral">
                    {column.dtype}
                  </Badge>
                </div>
                <div className="mt-ds-2 flex flex-wrap gap-ds-2 text-[10px] text-ds-muted">
                  <span>{column.nullCount} nulls</span>
                  <span>{column.uniqueCount} unique</span>
                </div>
                <div className="mt-ds-2 text-[10px] text-ds-muted">
                  {column.sampleValues.length > 0 ? (
                    <>Samples: {column.sampleValues.join(', ')}</>
                  ) : (
                    'Samples: none in preview'
                  )}
                </div>
              </Card>
            ))}
          </div>
        </div>
      ) : null}

      <div className="text-[11px] text-ds-muted">
        Showing {payload.previewRows}
        {payload.totalRows != null ? ` of ${payload.totalRows}` : ''} rows and {payload.columns.length}{' '}
        columns.
      </div>
    </div>
  );
}

function SummaryCard({ label, value }: { label: string; value: string }) {
  return (
    <Card className="bg-ds-bg/40 px-ds-3 py-ds-3 shadow-none">
      <div className="text-[10px] uppercase tracking-wider text-ds-muted">{label}</div>
      <div className="mt-ds-1 text-ds-sm font-medium text-ds-text">{value}</div>
    </Card>
  );
}
