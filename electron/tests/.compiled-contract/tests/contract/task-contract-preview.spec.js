"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const promises_1 = __importDefault(require("node:fs/promises"));
const node_os_1 = __importDefault(require("node:os"));
const node_path_1 = __importDefault(require("node:path"));
const task_contract_preview_1 = require("../../src/main/task-contract-preview");
async function run() {
    const fixtureDir = await promises_1.default.mkdtemp(node_path_1.default.join(node_os_1.default.tmpdir(), 'ds-agent-delivery-preview-'));
    try {
        const markdownPath = node_path_1.default.join(fixtureDir, 'exec-brief.md');
        await promises_1.default.writeFile(markdownPath, '# Situation\nRevenue softened in Q2.\n## Finding\nRetention is stable.\n## Recommendation\nPrioritize reactivation.\n', 'utf-8');
        const markdownPreview = await (0, task_contract_preview_1.loadRenderedArtifactPreview)({
            renderedUri: markdownPath,
            format: 'markdown',
        });
        strict_1.default.equal(markdownPreview.kind, 'markdown');
        strict_1.default.equal(markdownPreview.sections[0], 'Situation');
        strict_1.default.equal(markdownPreview.sections[1], 'Finding');
        strict_1.default.equal(markdownPreview.sections[2], 'Recommendation');
        strict_1.default.equal(markdownPreview.lineCount, 7);
        strict_1.default.equal(markdownPreview.truncated, false);
        strict_1.default.equal(markdownPreview.fileUrl.startsWith('file://'), true);
        const notebookPath = node_path_1.default.join(fixtureDir, 'ds-note.ipynb');
        await promises_1.default.writeFile(notebookPath, JSON.stringify({
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
        }), 'utf-8');
        const notebookPreview = await (0, task_contract_preview_1.loadRenderedArtifactPreview)({
            renderedUri: notebookPath,
            format: 'ipynb',
        });
        strict_1.default.equal(notebookPreview.kind, 'ipynb');
        strict_1.default.equal(notebookPreview.cellCount, 2);
        strict_1.default.deepEqual(notebookPreview.markdownCells, ['# Overview\nNotebook preview contract test']);
        strict_1.default.deepEqual(notebookPreview.codeCells, ['print("hello")']);
        strict_1.default.deepEqual(notebookPreview.outputCells, ['hello']);
        const pdfPath = node_path_1.default.join(fixtureDir, 'audit.pdf');
        await promises_1.default.writeFile(pdfPath, Buffer.from('%PDF-1.4\nmock\n', 'utf-8'));
        const pdfPreview = await (0, task_contract_preview_1.loadRenderedArtifactPreview)({
            renderedUri: pdfPath,
            format: 'pdf',
        });
        strict_1.default.equal(pdfPreview.kind, 'pdf');
        strict_1.default.equal(pdfPreview.size > 0, true);
        strict_1.default.equal(pdfPreview.fileUrl.startsWith('file://'), true);
        const pptxPath = node_path_1.default.join(fixtureDir, 'exec-brief.pptx');
        await promises_1.default.writeFile(pptxPath, Buffer.from('mock-pptx', 'utf-8'));
        await promises_1.default.writeFile(node_path_1.default.join(fixtureDir, 'exec-brief.preview.json'), JSON.stringify({
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
        }), 'utf-8');
        const pptxPreview = await (0, task_contract_preview_1.loadRenderedArtifactPreview)({
            renderedUri: pptxPath,
            format: 'pptx',
        });
        strict_1.default.equal(pptxPreview.kind, 'pptx');
        strict_1.default.equal(pptxPreview.manifestFound, true);
        strict_1.default.equal(pptxPreview.slideCount, 2);
        strict_1.default.equal(pptxPreview.slides[0]?.title, 'Situation');
        strict_1.default.deepEqual(pptxPreview.slides[0]?.bullets, ['Revenue softened', 'North America lagged']);
        const fallbackPptxPath = node_path_1.default.join(fixtureDir, 'exec-brief-fallback.pptx');
        await promises_1.default.writeFile(fallbackPptxPath, Buffer.from('mock-pptx-fallback', 'utf-8'));
        const fallbackPreview = await (0, task_contract_preview_1.loadRenderedArtifactPreview)({
            renderedUri: fallbackPptxPath,
            format: 'pptx',
        });
        strict_1.default.equal(fallbackPreview.kind, 'pptx');
        strict_1.default.equal(fallbackPreview.manifestFound, false);
        strict_1.default.equal(fallbackPreview.slideCount, 0);
        strict_1.default.deepEqual(fallbackPreview.slides, []);
        const unavailablePreview = await (0, task_contract_preview_1.loadRenderedArtifactPreview)({
            renderedUri: markdownPath,
            format: 'docx',
        });
        strict_1.default.equal(unavailablePreview.kind, 'unavailable');
        strict_1.default.equal(unavailablePreview.message, 'Inline preview is not available for docx.');
        console.log('[contract] PASS delivery preview loader');
    }
    finally {
        await promises_1.default.rm(fixtureDir, { recursive: true, force: true });
    }
}
void run();
