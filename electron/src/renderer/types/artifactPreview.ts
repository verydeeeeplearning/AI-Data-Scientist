export interface ArtifactPreviewBase {
  kind: string;
  path: string;
  name: string;
  size: number;
  modifiedAt: string;
}

export interface MarkdownArtifactPreview extends ArtifactPreviewBase {
  kind: 'markdown';
  content: string;
  truncated: boolean;
  headings: string[];
}

export interface NotebookCellPreview {
  kind: 'markdown' | 'code';
  excerpt: string;
  executionCount?: number | null;
}

export interface NotebookArtifactPreview extends ArtifactPreviewBase {
  kind: 'notebook';
  totalCells: number;
  markdownCells: number;
  codeCells: number;
  truncated: boolean;
  cellPreviews: NotebookCellPreview[];
}

export interface BinaryArtifactPreview extends ArtifactPreviewBase {
  kind: 'binary';
  message: string;
}

export interface PdfArtifactPreview extends ArtifactPreviewBase {
  kind: 'pdf';
  message: string;
}

export interface PptxArtifactPreview extends ArtifactPreviewBase {
  kind: 'pptx';
  message: string;
}

export interface MissingArtifactPreview {
  kind: 'missing';
  path: string;
  message: string;
}

export type ArtifactPreviewView =
  | MarkdownArtifactPreview
  | NotebookArtifactPreview
  | BinaryArtifactPreview
  | PdfArtifactPreview
  | PptxArtifactPreview
  | MissingArtifactPreview;
