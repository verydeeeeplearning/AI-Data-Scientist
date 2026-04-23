import assert from 'node:assert/strict';

import {
  PROMOTE_DIALOG_IDS,
  validatePromoteDialogDraft,
} from '../../src/renderer/components/runtime/PromoteDialog';
import { createRuntimeDialogA11yController } from '../../src/renderer/components/runtime/runtimeDialogA11y';

class FakeElement {
  tagName: string;
  attributes: Map<string, string> = new Map();
  children: FakeElement[] = [];
  parent: FakeElement | null = null;
  ownerDocument: FakeDocument;

  constructor(tagName: string, ownerDocument: FakeDocument) {
    this.tagName = tagName.toUpperCase();
    this.ownerDocument = ownerDocument;
  }

  appendChild(child: FakeElement): void {
    this.children.push(child);
    child.parent = this;
  }

  focus(): void {
    this.ownerDocument.activeElement = this;
  }

  hasAttribute(name: string): boolean {
    return this.attributes.has(name);
  }

  getAttribute(name: string): string | null {
    return this.attributes.has(name) ? this.attributes.get(name)! : null;
  }

  setAttribute(name: string, value: string): void {
    this.attributes.set(name, value);
  }

  querySelectorAll(_selector: string): FakeElement[] {
    const out: FakeElement[] = [];
    walk(this, (node) => {
      if (node !== this) out.push(node);
    });
    return out;
  }
}

class FakeDocument {
  body: FakeElement;
  activeElement: FakeElement | null = null;

  constructor() {
    this.body = new FakeElement('body', this);
  }

  createElement(tag: string): FakeElement {
    return new FakeElement(tag, this);
  }
}

function walk(root: FakeElement, visit: (node: FakeElement) => void): void {
  visit(root);
  for (const child of root.children) {
    walk(child, visit);
  }
}

function createDialogContainer(doc: FakeDocument): FakeElement {
  const container = doc.createElement('div');
  container.appendChild(doc.createElement('input'));
  container.appendChild(doc.createElement('input'));
  container.appendChild(doc.createElement('input'));
  container.appendChild(doc.createElement('button'));
  doc.body.appendChild(container);
  return container;
}

function createKeyEvent(key: string, shiftKey = false): {
  key: string;
  shiftKey: boolean;
  prevented: boolean;
  preventDefault(): void;
} {
  return {
    key,
    shiftKey,
    prevented: false,
    preventDefault() {
      this.prevented = true;
    },
  };
}

function run(): void {
  // === promote dialog exposes stable aria ids for title + description wiring ===
  {
    assert.equal(PROMOTE_DIALOG_IDS.title, 'cards-promote-dialog-title');
    assert.equal(PROMOTE_DIALOG_IDS.description, 'cards-promote-dialog-description');
  }

  // === only the supported audiences are accepted ===
  {
    assert.equal(
      validatePromoteDialogDraft({ audience: 'board', title: 'Q2 brief' }),
      'audience_required',
    );
    assert.equal(
      validatePromoteDialogDraft({ audience: 'exec', title: 'Q2 brief' }),
      null,
    );
  }

  // === focus trap activates and cycles across the radio/input controls ===
  {
    const doc = new FakeDocument();
    const container = createDialogContainer(doc);
    const controller = createRuntimeDialogA11yController(
      container as unknown as HTMLElement,
      { document: doc as unknown as Document },
    );

    controller.activate();
    assert.equal(doc.activeElement, container.children[0]);

    const tab = createKeyEvent('Tab');
    assert.equal(controller.handleKeyDown(tab), 'tab');
    assert.equal(tab.prevented, true);
    assert.equal(doc.activeElement, container.children[1]);
  }

  // === escape is surfaced so ESC closes the promote dialog ===
  {
    const doc = new FakeDocument();
    const controller = createRuntimeDialogA11yController(
      createDialogContainer(doc) as unknown as HTMLElement,
      { document: doc as unknown as Document },
    );

    controller.activate();
    const escape = createKeyEvent('Escape');
    assert.equal(controller.handleKeyDown(escape), 'escape');
    assert.equal(escape.prevented, true);
  }

  console.log('[contract] PASS dialog-promote-a11y (4 cases)');
}

run();
