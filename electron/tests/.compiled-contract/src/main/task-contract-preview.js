"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.loadRenderedArtifactPreview = loadRenderedArtifactPreview;
const promises_1 = __importDefault(require("fs/promises"));
const path_1 = __importDefault(require("path"));
const url_1 = require("url");
const MAX_TEXT_CHARS = 24000;
const MAX_NOTEBOOK_CELL_PREVIEWS = 8;
const MAX_CELL_CHARS = 1600;
async function loadRenderedArtifactPreview(params) {
    const normalizedPath = path_1.default.normalize(params.renderedUri);
    const fileUrl = (0, url_1.pathToFileURL)(normalizedPath).toString();
    const stat = await promises_1.default.stat(normalizedPath);
    if (!stat.isFile()) {
        throw new Error(`Rendered artifact is not a file: ${normalizedPath}`);
    }
    const normalizedFormat = normalizePreviewFormat(params.format);
    if (normalizedFormat === 'markdown') {
        const rawContent = await promises_1.default.readFile(normalizedPath, 'utf-8');
        const { content, truncated } = truncateText(rawContent, MAX_TEXT_CHARS);
        return {
            kind: 'markdown',
            path: normalizedPath,
            fileUrl,
            content,
            truncated,
            sections: extractMarkdownSections(content),
            lineCount: rawContent.split(/\r?\n/).length,
        };
    }
    if (normalizedFormat === 'ipynb') {
        return loadNotebookPreview(normalizedPath, fileUrl);
    }
    if (normalizedFormat === 'pdf') {
        return {
            kind: 'pdf',
            path: normalizedPath,
            fileUrl,
            size: stat.size,
        };
    }
    if (normalizedFormat === 'pptx') {
        return loadPptxPreview(normalizedPath, fileUrl);
    }
    return {
        kind: 'unavailable',
        path: normalizedPath,
        fileUrl,
        message: `Inline preview is not available for ${params.format}.`,
    };
}
function normalizePreviewFormat(value) {
    const normalized = value.trim().toLowerCase();
    if (normalized === 'markdown' || normalized === 'md') {
        return 'markdown';
    }
    if (normalized === 'ipynb') {
        return 'ipynb';
    }
    if (normalized === 'pdf') {
        return 'pdf';
    }
    if (normalized === 'pptx') {
        return 'pptx';
    }
    return null;
}
async function loadNotebookPreview(filePath, fileUrl) {
    const rawContent = await promises_1.default.readFile(filePath, 'utf-8');
    const truncated = rawContent.length > MAX_TEXT_CHARS * 2;
    const parsed = JSON.parse(rawContent);
    const notebook = asRecord(parsed);
    const cells = Array.isArray(notebook?.cells) ? notebook.cells : [];
    const markdownCells = [];
    const codeCells = [];
    const outputCells = [];
    for (const cell of cells) {
        const record = asRecord(cell);
        if (!record) {
            continue;
        }
        const cellType = typeof record.cell_type === 'string' ? record.cell_type : '';
        const source = compactSnippet(stringOrJoin(record.source), MAX_CELL_CHARS);
        if (cellType === 'markdown' && source) {
            markdownCells.push(source);
            continue;
        }
        if (cellType === 'code') {
            if (source) {
                codeCells.push(source);
            }
            const outputs = Array.isArray(record.outputs) ? record.outputs : [];
            for (const output of outputs) {
                const text = compactSnippet(extractNotebookOutput(output), MAX_CELL_CHARS);
                if (text) {
                    outputCells.push(text);
                }
            }
        }
    }
    return {
        kind: 'ipynb',
        path: filePath,
        fileUrl,
        markdownCells: markdownCells.slice(0, MAX_NOTEBOOK_CELL_PREVIEWS),
        codeCells: codeCells.slice(0, MAX_NOTEBOOK_CELL_PREVIEWS),
        outputCells: outputCells.slice(0, MAX_NOTEBOOK_CELL_PREVIEWS),
        truncated,
        cellCount: cells.length,
    };
}
async function loadPptxPreview(filePath, fileUrl) {
    const manifestPath = filePath.replace(/\.pptx$/i, '.preview.json');
    try {
        const rawManifest = await promises_1.default.readFile(manifestPath, 'utf-8');
        const parsed = JSON.parse(rawManifest);
        const manifest = asRecord(parsed);
        const rawSlides = Array.isArray(manifest?.slides) ? manifest.slides : [];
        const slides = rawSlides.reduce((items, slide) => {
            const record = asRecord(slide);
            if (!record) {
                return items;
            }
            items.push({
                index: typeof record.index === 'number' ? record.index : 0,
                section: typeof record.section === 'string' ? record.section : null,
                title: typeof record.title === 'string' ? record.title : 'Untitled slide',
                bullets: asStringArray(record.bullets).slice(0, 4),
                excerpt: typeof record.excerpt === 'string' ? record.excerpt : '',
                chart_count: typeof record.chart_count === 'number' ? record.chart_count : 0,
            });
            return items;
        }, []);
        return {
            kind: 'pptx',
            path: filePath,
            fileUrl,
            slides,
            slideCount: typeof manifest?.slide_count === 'number' ? manifest.slide_count : slides.length,
            manifestFound: true,
        };
    }
    catch {
        return {
            kind: 'pptx',
            path: filePath,
            fileUrl,
            slides: [],
            slideCount: 0,
            manifestFound: false,
        };
    }
}
function extractMarkdownSections(content) {
    const sections = new Set();
    const matches = content.matchAll(/^#{1,6}\s+(.+)$/gm);
    for (const match of matches) {
        const heading = match[1]?.trim();
        if (heading) {
            sections.add(heading);
        }
    }
    return Array.from(sections).slice(0, 8);
}
function extractNotebookOutput(value) {
    const record = asRecord(value);
    if (!record) {
        return null;
    }
    const directText = stringOrJoin(record.text);
    if (directText) {
        return directText;
    }
    const traceback = stringOrJoin(record.traceback);
    if (traceback) {
        return traceback;
    }
    const data = asRecord(record.data);
    if (!data) {
        return null;
    }
    return (stringOrJoin(data['text/plain'])
        || stringOrJoin(data['text/html'])
        || stringOrJoin(data['application/json']));
}
function asRecord(value) {
    return value && typeof value === 'object' && !Array.isArray(value)
        ? value
        : null;
}
function asStringArray(value) {
    return Array.isArray(value) ? value.filter((item) => typeof item === 'string') : [];
}
function stringOrJoin(value) {
    if (typeof value === 'string') {
        return value;
    }
    if (Array.isArray(value)) {
        const parts = value.filter((item) => typeof item === 'string');
        return parts.length > 0 ? parts.join('') : null;
    }
    return null;
}
function compactSnippet(value, limit) {
    if (!value) {
        return null;
    }
    const compact = value.replace(/\n{3,}/g, '\n\n').trim();
    if (!compact) {
        return null;
    }
    return compact.length > limit ? `${compact.slice(0, limit)}...` : compact;
}
function truncateText(value, limit) {
    if (value.length <= limit) {
        return { content: value, truncated: false };
    }
    return {
        content: `${value.slice(0, limit)}\n...`,
        truncated: true,
    };
}
