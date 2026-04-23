"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const classifyUploadError_1 = require("../../src/renderer/application/workspace/classifyUploadError");
function run() {
    // Network error variants
    {
        const info = (0, classifyUploadError_1.classifyUploadError)(new TypeError('Failed to fetch'));
        strict_1.default.equal(info.kind, 'network');
        strict_1.default.match(info.message, /fetch/i);
    }
    {
        const info = (0, classifyUploadError_1.classifyUploadError)(new Error('NetworkError when attempting to fetch resource.'));
        strict_1.default.equal(info.kind, 'network');
    }
    {
        const info = (0, classifyUploadError_1.classifyUploadError)(new Error('Request timed out'));
        strict_1.default.equal(info.kind, 'network');
    }
    // tooLarge
    {
        const info = (0, classifyUploadError_1.classifyUploadError)(new Error('File too large: 200000000 bytes (max 100MB)'));
        strict_1.default.equal(info.kind, 'tooLarge');
    }
    {
        const info = (0, classifyUploadError_1.classifyUploadError)(new Error('Upload failed with status 413'));
        strict_1.default.equal(info.kind, 'tooLarge');
    }
    // unsupported
    {
        const info = (0, classifyUploadError_1.classifyUploadError)(new Error('File type not allowed: .exe'));
        strict_1.default.equal(info.kind, 'unsupported');
    }
    // malformed (signature mismatch / parse error)
    {
        const info = (0, classifyUploadError_1.classifyUploadError)(new Error('File signature does not match the declared Excel format'));
        strict_1.default.equal(info.kind, 'malformed');
    }
    {
        const info = (0, classifyUploadError_1.classifyUploadError)(new Error('Unable to parse CSV preview: ParserError: ...'));
        strict_1.default.equal(info.kind, 'malformed');
    }
    // unknown fallback
    {
        const info = (0, classifyUploadError_1.classifyUploadError)(new Error('Backend exploded for unknown reasons'));
        strict_1.default.equal(info.kind, 'unknown');
        strict_1.default.equal(info.message, 'Backend exploded for unknown reasons');
    }
    // empty / non-error inputs
    {
        const info = (0, classifyUploadError_1.classifyUploadError)(undefined);
        strict_1.default.equal(info.kind, 'unknown');
        strict_1.default.equal(info.message, 'Upload failed');
    }
    {
        const info = (0, classifyUploadError_1.classifyUploadError)('');
        strict_1.default.equal(info.kind, 'unknown');
        strict_1.default.equal(info.message, 'Upload failed');
    }
    // fileName context preserved
    {
        const info = (0, classifyUploadError_1.classifyUploadError)(new Error('File too large'), { fileName: 'big.csv' });
        strict_1.default.equal(info.kind, 'tooLarge');
        strict_1.default.equal(info.fileName, 'big.csv');
    }
}
run();
console.log('uploadErrorStates contract — OK');
