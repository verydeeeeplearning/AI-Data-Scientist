import assert from 'node:assert/strict';

import { classifyUploadError } from '../../src/renderer/application/workspace/classifyUploadError';

function run(): void {
  // Network error variants
  {
    const info = classifyUploadError(new TypeError('Failed to fetch'));
    assert.equal(info.kind, 'network');
    assert.match(info.message, /fetch/i);
  }
  {
    const info = classifyUploadError(new Error('NetworkError when attempting to fetch resource.'));
    assert.equal(info.kind, 'network');
  }
  {
    const info = classifyUploadError(new Error('Request timed out'));
    assert.equal(info.kind, 'network');
  }

  // tooLarge
  {
    const info = classifyUploadError(
      new Error('File too large: 200000000 bytes (max 100MB)'),
    );
    assert.equal(info.kind, 'tooLarge');
  }
  {
    const info = classifyUploadError(new Error('Upload failed with status 413'));
    assert.equal(info.kind, 'tooLarge');
  }

  // unsupported
  {
    const info = classifyUploadError(new Error('File type not allowed: .exe'));
    assert.equal(info.kind, 'unsupported');
  }

  // malformed (signature mismatch / parse error)
  {
    const info = classifyUploadError(
      new Error('File signature does not match the declared Excel format'),
    );
    assert.equal(info.kind, 'malformed');
  }
  {
    const info = classifyUploadError(new Error('Unable to parse CSV preview: ParserError: ...'));
    assert.equal(info.kind, 'malformed');
  }

  // unknown fallback
  {
    const info = classifyUploadError(new Error('Backend exploded for unknown reasons'));
    assert.equal(info.kind, 'unknown');
    assert.equal(info.message, 'Backend exploded for unknown reasons');
  }

  // empty / non-error inputs
  {
    const info = classifyUploadError(undefined);
    assert.equal(info.kind, 'unknown');
    assert.equal(info.message, 'Upload failed');
  }
  {
    const info = classifyUploadError('');
    assert.equal(info.kind, 'unknown');
    assert.equal(info.message, 'Upload failed');
  }

  // fileName context preserved
  {
    const info = classifyUploadError(new Error('File too large'), { fileName: 'big.csv' });
    assert.equal(info.kind, 'tooLarge');
    assert.equal(info.fileName, 'big.csv');
  }
}

run();
console.log('uploadErrorStates contract — OK');
