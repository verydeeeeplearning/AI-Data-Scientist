import { useEffect, useMemo, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useI18n } from '../../stores/i18nStore';
import { resolveMainIpcErrorMessage } from '../../utils/mainIpcErrors';
import type {
  DeliveryArtifactView,
  PptxPreviewSlideView,
  RenderedArtifactPreviewView,
} from '../../types/taskContract';

interface Props {
  artifact: DeliveryArtifactView | null;
  renderedUri: string | null;
}

export function ArtifactInlinePreview({ artifact, renderedUri }: Props) {
  const { t } = useI18n();
  const [preview, setPreview] = useState<RenderedArtifactPreviewView | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!artifact || !renderedUri || !window.electronAPI?.taskContract?.previewRenderedArtifact) {
      setPreview(null);
      setError(null);
      setLoading(false);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    void window.electronAPI.taskContract.previewRenderedArtifact({
      renderedUri,
      format: artifact.format,
    })
      .then((result) => {
        if (cancelled) {
          return;
        }
        if (!result.ok) {
          setError(
            resolveMainIpcErrorMessage(result, 'common.mainIpc.taskContract.previewFailed'),
          );
          setPreview(null);
          return;
        }
        setPreview(result.preview);
      })
      .catch((err) => {
        if (cancelled) {
          return;
        }
        console.error('[ArtifactInlinePreview] preview failed:', err);
        setError(t('common.mainIpc.taskContract.previewFailed'));
        setPreview(null);
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [artifact, renderedUri, t]);

  const pptxFallbackSlides = useMemo(() => {
    if (!artifact) {
      return [];
    }
    return artifact.content_policy.structure.map((section, index) => ({
      index: index + 1,
      section,
      title: section.replace(/_/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase()),
      bullets: [],
      excerpt: 'Preview manifest not available yet. Open the deck to inspect the full slide content.',
      chart_count: 0,
    } satisfies PptxPreviewSlideView));
  }, [artifact]);

  if (!artifact || !renderedUri) {
    return null;
  }

  return (
    <div className="mt-3 rounded-lg border border-ds-border/70 bg-ds-bg/50 px-3 py-3">
      <div className="flex items-center justify-between gap-2">
        <div>
          <p className="text-[11px] uppercase tracking-wide text-ds-muted">Inline Preview</p>
          <p className="mt-1 text-[10px] text-ds-muted">{artifact.format}</p>
        </div>
        {preview && (
          <span className="text-[10px] text-ds-muted">
            {preview.kind}
          </span>
        )}
      </div>

      {loading && (
        <p className="mt-2 text-[11px] text-ds-muted">Loading rendered artifact preview...</p>
      )}

      {error && (
        <p className="mt-2 text-[11px] text-rose-300">{error}</p>
      )}

      {!loading && !error && preview?.kind === 'markdown' && (
        <div className="mt-3 grid gap-3 xl:grid-cols-[220px_minmax(0,1fr)]">
          <ArtifactStructureCard
            structure={artifact.content_policy.structure}
            sections={preview.sections}
            helper={`${preview.lineCount} lines rendered`}
          />
          <MarkdownPane content={preview.content} truncated={preview.truncated} />
        </div>
      )}

      {!loading && !error && preview?.kind === 'ipynb' && (
        <div className="mt-3 space-y-3">
          <div className="grid gap-2 sm:grid-cols-3">
            <PreviewMetric label="Cells" value={String(preview.cellCount)} />
            <PreviewMetric label="Markdown" value={String(preview.markdownCells.length)} />
            <PreviewMetric label="Code/Output" value={String(preview.codeCells.length + preview.outputCells.length)} />
          </div>
          <div className="grid gap-3 xl:grid-cols-2">
            <NotebookMarkdownPane cells={preview.markdownCells} />
            <NotebookCodePane codeCells={preview.codeCells} outputCells={preview.outputCells} />
          </div>
          {preview.truncated && (
            <p className="text-[10px] text-ds-muted">
              Showing the first notebook cells only.
            </p>
          )}
        </div>
      )}

      {!loading && !error && preview?.kind === 'pdf' && (
        <div className="mt-3 space-y-2">
          <div className="grid gap-2 sm:grid-cols-2">
            <PreviewMetric label="Viewer" value="Embedded PDF" />
            <PreviewMetric label="Size" value={formatSize(preview.size)} />
          </div>
          <div className="overflow-hidden rounded-lg border border-ds-border/70 bg-white">
            <iframe
              title={`${artifact.type} pdf preview`}
              src={`${preview.fileUrl}#toolbar=0&navpanes=0`}
              className="h-[30rem] w-full"
            />
          </div>
        </div>
      )}

      {!loading && !error && preview?.kind === 'pptx' && (
        <div className="mt-3 space-y-3">
          <div className="grid gap-2 sm:grid-cols-2">
            <PreviewMetric label="Slides" value={String(preview.slideCount || pptxFallbackSlides.length)} />
            <PreviewMetric
              label="Source"
              value={preview.manifestFound ? 'Exporter manifest' : 'Fallback structure'}
            />
          </div>
          <PptxSlideGallery slides={preview.slides.length > 0 ? preview.slides : pptxFallbackSlides} />
        </div>
      )}

      {!loading && !error && preview?.kind === 'unavailable' && (
        <div className="mt-3 rounded-lg border border-ds-border/70 bg-ds-surface px-3 py-3">
          <p className="text-xs text-ds-muted">{preview.message}</p>
        </div>
      )}
    </div>
  );
}

function ArtifactStructureCard({
  structure,
  sections,
  helper,
}: {
  structure: string[];
  sections: string[];
  helper: string;
}) {
  return (
    <div className="rounded-lg border border-ds-border/70 bg-ds-surface px-3 py-3">
      <p className="text-[11px] uppercase tracking-wide text-ds-muted">Skeleton</p>
      <div className="mt-3 space-y-2">
        {structure.map((section) => {
          const active = sections.some((item) => item.toLowerCase().includes(section.toLowerCase()));
          return (
            <div
              key={section}
              className={`rounded-lg border px-3 py-2 text-[11px] ${
                active
                  ? 'border-ds-accent/50 bg-ds-accent/10 text-ds-text'
                  : 'border-ds-border/70 bg-ds-bg/60 text-ds-muted'
              }`}
            >
              {section}
            </div>
          );
        })}
      </div>
      <p className="mt-3 text-[10px] text-ds-muted">{helper}</p>
    </div>
  );
}

function MarkdownPane({
  content,
  truncated,
}: {
  content: string;
  truncated: boolean;
}) {
  return (
    <div className="rounded-lg border border-ds-border/70 bg-ds-surface px-3 py-3">
      <p className="text-[11px] uppercase tracking-wide text-ds-muted">Rendered Result</p>
      <div className="prose prose-invert prose-sm mt-3 max-w-none overflow-auto rounded-lg border border-ds-border/70 bg-ds-bg/60 px-3 py-3 prose-headings:text-ds-text prose-p:text-ds-text prose-li:text-ds-text prose-code:text-ds-accent prose-strong:text-ds-text">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>
          {content}
        </ReactMarkdown>
      </div>
      {truncated && (
        <p className="mt-2 text-[10px] text-ds-muted">
          Preview truncated to keep the desktop view responsive.
        </p>
      )}
    </div>
  );
}

function NotebookMarkdownPane({ cells }: { cells: string[] }) {
  return (
    <div className="rounded-lg border border-ds-border/70 bg-ds-surface px-3 py-3">
      <p className="text-[11px] uppercase tracking-wide text-ds-muted">Markdown Cells</p>
      <div className="mt-3 space-y-3">
        {cells.length > 0 ? cells.map((cell, index) => (
          <div key={`markdown-${index}`} className="prose prose-invert prose-sm max-w-none rounded-lg border border-ds-border/70 bg-ds-bg/60 px-3 py-3 prose-headings:text-ds-text prose-p:text-ds-text prose-li:text-ds-text prose-code:text-ds-accent prose-strong:text-ds-text">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {cell}
            </ReactMarkdown>
          </div>
        )) : (
          <div className="rounded-lg border border-ds-border/70 bg-ds-bg/60 px-3 py-3 text-[11px] text-ds-muted">
            No markdown cells were found in the notebook preview.
          </div>
        )}
      </div>
    </div>
  );
}

function NotebookCodePane({
  codeCells,
  outputCells,
}: {
  codeCells: string[];
  outputCells: string[];
}) {
  return (
    <div className="rounded-lg border border-ds-border/70 bg-ds-surface px-3 py-3">
      <p className="text-[11px] uppercase tracking-wide text-ds-muted">Code + Output</p>
      <div className="mt-3 space-y-3">
        {codeCells.length > 0 ? codeCells.map((cell, index) => (
          <pre
            key={`code-${index}`}
            className="overflow-auto rounded-lg border border-ds-border/70 bg-ds-bg/60 px-3 py-3 font-mono text-[11px] text-ds-text"
          >
            {cell}
          </pre>
        )) : (
          <div className="rounded-lg border border-ds-border/70 bg-ds-bg/60 px-3 py-3 text-[11px] text-ds-muted">
            No code cells were found in the notebook preview.
          </div>
        )}
        {outputCells.length > 0 && (
          <div className="space-y-2">
            <p className="text-[10px] uppercase tracking-wide text-ds-muted">Captured Output</p>
            {outputCells.map((output, index) => (
              <pre
                key={`output-${index}`}
                className="overflow-auto rounded-lg border border-ds-border/70 bg-ds-bg/60 px-3 py-3 font-mono text-[11px] text-ds-text"
              >
                {output}
              </pre>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function PptxSlideGallery({ slides }: { slides: PptxPreviewSlideView[] }) {
  return (
    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
      {slides.map((slide) => (
        <div
          key={`${slide.index}-${slide.title}`}
          className="relative aspect-video overflow-hidden rounded-xl border border-ds-border/70 bg-ds-surface"
        >
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(59,130,246,0.18),transparent_45%),linear-gradient(135deg,rgba(15,23,42,0.94),rgba(30,41,59,0.92))]" />
          <div className="relative flex h-full flex-col justify-between p-3">
            <div className="flex items-start justify-between gap-2 text-[10px] text-ds-muted">
              <span>Slide {slide.index}</span>
              {slide.chart_count > 0 && <span>{slide.chart_count} chart</span>}
            </div>
            <div>
              <p className="line-clamp-2 text-sm font-semibold text-white">{slide.title}</p>
              {slide.section && (
                <p className="mt-1 text-[10px] uppercase tracking-wide text-slate-300">
                  {slide.section}
                </p>
              )}
            </div>
            <div className="space-y-1">
              {slide.bullets.length > 0 ? slide.bullets.map((bullet) => (
                <p key={bullet} className="line-clamp-1 text-[11px] text-slate-200">
                  - {bullet}
                </p>
              )) : (
                <p className="line-clamp-3 text-[11px] text-slate-200">{slide.excerpt}</p>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

function PreviewMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-ds-border/70 bg-ds-surface px-3 py-2">
      <p className="text-[10px] uppercase tracking-wide text-ds-muted">{label}</p>
      <p className="mt-1 text-sm font-medium text-ds-text">{value}</p>
    </div>
  );
}

function formatSize(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
