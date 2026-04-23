"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const buildWorkspaceExportCandidates_1 = require("../../src/renderer/application/workspace/buildWorkspaceExportCandidates");
function run() {
    const snapshot = {
        files: [
            {
                name: 'report.md',
                path: 'reports/report.md',
                type: 'md',
            },
            {
                name: 'metrics.csv',
                path: 'tables/metrics.csv',
                type: 'csv',
            },
            {
                name: 'plot.png',
                path: 'plots/plot.png',
                type: 'png',
            },
            {
                name: 'ignored.bin',
                path: 'misc/ignored.bin',
                type: 'bin',
            },
        ],
        plots: [
            {
                name: 'chart.svg',
                path: 'charts/chart.svg',
            },
            {
                name: 'plot.png',
                path: 'plots/plot.png',
            },
        ],
    };
    const candidates = (0, buildWorkspaceExportCandidates_1.buildWorkspaceExportCandidates)(snapshot);
    strict_1.default.deepEqual(candidates.map((candidate) => ({
        id: candidate.id,
        name: candidate.name,
        path: candidate.path,
        type: candidate.type,
        formats: [...candidate.formats],
        sourceKind: candidate.sourceKind,
    })), [
        {
            id: 'charts/chart.svg',
            name: 'chart.svg',
            path: 'charts/chart.svg',
            type: 'svg',
            formats: ['svg'],
            sourceKind: 'plot',
        },
        {
            id: 'plots/plot.png',
            name: 'plot.png',
            path: 'plots/plot.png',
            type: 'png',
            formats: ['png'],
            sourceKind: 'file',
        },
        {
            id: 'reports/report.md',
            name: 'report.md',
            path: 'reports/report.md',
            type: 'md',
            formats: ['docx', 'html', 'pdf'],
            sourceKind: 'file',
        },
        {
            id: 'tables/metrics.csv',
            name: 'metrics.csv',
            path: 'tables/metrics.csv',
            type: 'csv',
            formats: ['html', 'xlsx'],
            sourceKind: 'file',
        },
    ]);
    console.log('[contract] PASS workspace-export-candidates (4 cases)');
}
run();
