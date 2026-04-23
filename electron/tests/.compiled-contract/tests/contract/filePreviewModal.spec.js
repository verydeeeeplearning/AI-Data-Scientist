"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const FilePreviewModal_1 = require("../../src/renderer/components/sidebar/FilePreviewModal");
function run() {
    strict_1.default.equal((0, FilePreviewModal_1.clampHeaderRow)('3'), 3);
    strict_1.default.equal((0, FilePreviewModal_1.clampHeaderRow)('0'), 1);
    strict_1.default.equal((0, FilePreviewModal_1.clampHeaderRow)('99'), 50);
    strict_1.default.equal((0, FilePreviewModal_1.clampHeaderRow)('abc'), 1);
    strict_1.default.deepEqual((0, FilePreviewModal_1.buildPreviewRequest)('workspace/data.csv', 2, null), {
        path: 'workspace/data.csv',
        rows: 50,
        headerRow: 2,
    });
    strict_1.default.deepEqual((0, FilePreviewModal_1.buildPreviewRequest)('workspace/book.xlsx', 4, 'Revenue'), {
        path: 'workspace/book.xlsx',
        rows: 50,
        headerRow: 4,
        sheetName: 'Revenue',
    });
    console.log('[contract] PASS file-preview-modal (2 cases)');
}
run();
