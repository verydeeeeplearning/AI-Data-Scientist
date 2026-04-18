import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';

import { loadRenderedArtifactPreview } from '../../src/main/task-contract-preview';

async function run(): Promise<void> {
  const fixtureDir = await fs.mkdtemp(path.join(os.tmpdir(), 'ds-agent-delivery-preview-'));

  try {
    const markdownPath = path.join(fixtureDir, 'exec-brief.md');
    await fs.writeFile(
      markdownPath,
      '# Situation\nRevenue softened in Q2.\n## Finding\nRetention is stable.\n## Recommendation\nPrioritize reactivation.\n',
      'utf-8',
    );

    const markdownPreview = await loadRenderedArtifactPreview({
      renderedUri: markdownPath,
      format: 'markdown',
    });
    assert.equal(markdownPreview.kind, 'markdown');
    assert.equal(markdownPreview.sections[0], 'Situation');
    assert.equal(markdownPreview.sections[1], 'Finding');
    assert.equal(markdownPreview.sections[2], 'Recommendation');
    assert.equal(markdownPreview.lineCount, 7);
    assert.equal(markdownPreview.truncated, false);
    assert.equal(markdownPreview.fileUrl.startsWith('file://'), true);

    const notebookPath = path.join(fixtureDir, 'ds-note.ipynb');
    await fs.writeFile(
      notebookPath,
      JSON.stringify({
        cells: [
          {
            cell_type: 'markdown',
            source: ['# Overview\n', 'Notebook preview contract test'],
          },
          {
            cell_type: 'code',
            source: ['print("hello")\n'],
            outputs: [
              {
                output_type: 'stream',
                text: ['hello\n'],
              },
            ],
          },
        ],
      }),
      'utf-8',
    );

    const notebookPreview = await loadRenderedArtifactPreview({
      renderedUri: notebookPath,
      format: 'ipynb',
    });
    assert.equal(notebookPreview.kind, 'ipynb');
    assert.equal(notebookPreview.cellCount, 2);
    assert.deepEqual(notebookPreview.markdownCells, ['# Overview\nNotebook preview contract test']);
    assert.deepEqual(notebookPreview.codeCells, ['print("hello")']);
    assert.deepEqual(notebookPreview.outputCells, ['hello']);

    const pdfPath = path.join(fixtureDir, 'audit.pdf');
    await fs.writeFile(pdfPath, Buffer.from('%PDF-1.4\nmock\n', 'utf-8'));

    const pdfPreview = await loadRenderedArtifactPreview({
      renderedUri: pdfPath,
      format: 'pdf',
    });
    assert.equal(pdfPreview.kind, 'pdf');
    assert.equal(pdfPreview.size > 0, true);
    assert.equal(pdfPreview.fileUrl.startsWith('file://'), true);

    const pptxPath = path.join(fixtureDir, 'exec-brief.pptx');
    await fs.writeFile(pptxPath, Buffer.from('mock-pptx', 'utf-8'));
    await fs.writeFile(
      path.join(fixtureDir, 'exec-brief.preview.json'),
      JSON.stringify({
        slide_count: 2,
        slides: [
          {
            index: 1,
            section: 'situation',
            title: 'Situation',
            bullets: ['Revenue softened', 'North America lagged'],
            excerpt: 'Revenue softened in Q2 while retention stayed stable.',
            chart_count: 1,
          },
          {
            index: 2,
            section: 'recommendation',
            title: 'Recommendation',
            bullets: ['Prioritize reactivation'],
            excerpt: 'Focus next sprint on reactivation offers.',
            chart_count: 0,
          },
        ],
      }),
      'utf-8',
    );

    const pptxPreview = await loadRenderedArtifactPreview({
      renderedUri: pptxPath,
      format: 'pptx',
    });
    assert.equal(pptxPreview.kind, 'pptx');
    assert.equal(pptxPreview.manifestFound, true);
    assert.equal(pptxPreview.slideCount, 2);
    assert.equal(pptxPreview.slides[0]?.title, 'Situation');
    assert.deepEqual(pptxPreview.slides[0]?.bullets, ['Revenue softened', 'North America lagged']);

    const fallbackPptxPath = path.join(fixtureDir, 'exec-brief-fallback.pptx');
    await fs.writeFile(fallbackPptxPath, Buffer.from('mock-pptx-fallback', 'utf-8'));

    const fallbackPreview = await loadRenderedArtifactPreview({
      renderedUri: fallbackPptxPath,
      format: 'pptx',
    });
    assert.equal(fallbackPreview.kind, 'pptx');
    assert.equal(fallbackPreview.manifestFound, false);
    assert.equal(fallbackPreview.slideCount, 0);
    assert.deepEqual(fallbackPreview.slides, []);

    const unavailablePreview = await loadRenderedArtifactPreview({
      renderedUri: markdownPath,
      format: 'docx',
    });
    assert.equal(unavailablePreview.kind, 'unavailable');
    assert.equal(unavailablePreview.message, 'Inline preview is not available for docx.');

    console.log('[contract] PASS delivery preview loader');
  } finally {
    await fs.rm(fixtureDir, { recursive: true, force: true });
  }
}

void run();
