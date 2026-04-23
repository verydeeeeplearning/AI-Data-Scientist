import assert from 'node:assert/strict';

import { matchesShortcut } from '../../src/renderer/utils/keyboardShortcut';

function run(): void {
  // Ctrl+Shift+M toggles collapse on Windows/Linux.
  {
    const event = {
      key: 'M',
      ctrlKey: true,
      shiftKey: true,
      metaKey: false,
      altKey: false,
    };
    assert.equal(matchesShortcut(event, 'ctrl+shift+m'), true);
  }

  // Meta+Shift+M toggles collapse on macOS.
  {
    const event = {
      key: 'm',
      ctrlKey: false,
      shiftKey: true,
      metaKey: true,
      altKey: false,
    };
    assert.equal(matchesShortcut(event, 'meta+shift+m'), true);
  }

  // Plain Ctrl+M does not match (shift required).
  {
    const event = {
      key: 'm',
      ctrlKey: true,
      shiftKey: false,
      metaKey: false,
      altKey: false,
    };
    assert.equal(matchesShortcut(event, 'ctrl+shift+m'), false);
  }

  // Escape closes details.
  {
    const event = {
      key: 'Escape',
      ctrlKey: false,
      shiftKey: false,
      metaKey: false,
      altKey: false,
    };
    assert.equal(matchesShortcut(event, 'escape'), true);
  }

  // Other keys are inert.
  {
    const event = {
      key: 'a',
      ctrlKey: true,
      shiftKey: true,
      metaKey: false,
      altKey: false,
    };
    assert.equal(matchesShortcut(event, 'ctrl+shift+m'), false);
  }

  // Alt modifier mismatch breaks the binding.
  {
    const event = {
      key: 'm',
      ctrlKey: true,
      shiftKey: true,
      metaKey: false,
      altKey: true,
    };
    assert.equal(matchesShortcut(event, 'ctrl+shift+m'), false);
  }

  console.log('[contract] PASS mission-header-shortcut (6 cases)');
}

run();
