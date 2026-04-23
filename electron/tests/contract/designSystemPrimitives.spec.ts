import assert from 'node:assert/strict';

import {
  Accordion,
  Checkbox,
  Chip,
  DialogShell,
  DrawerShell,
  Input,
  Popover,
  Radio,
  Skeleton,
  Spinner,
  Tabs,
  Textarea,
  Toast,
  ToastViewport,
  Tooltip,
} from '../../src/renderer/design-system/primitives';

function run(): void {
  assert.equal(typeof Accordion, 'function');
  assert.equal(typeof Checkbox, 'function');
  assert.equal(typeof Chip, 'function');
  assert.equal(typeof Input, 'function');
  assert.equal(typeof Radio, 'function');
  assert.equal(typeof Textarea, 'function');
  assert.equal(typeof Spinner, 'function');
  assert.equal(typeof Skeleton, 'function');
  assert.equal(typeof DialogShell, 'function');
  assert.equal(typeof DrawerShell, 'function');
  assert.equal(typeof Tabs, 'function');
  assert.equal(typeof Tooltip, 'function');
  assert.equal(typeof Popover, 'function');
  assert.equal(typeof Toast, 'function');
  assert.equal(typeof ToastViewport, 'function');

  console.log('[contract] PASS design-system-primitives (15 exports)');
}

run();
