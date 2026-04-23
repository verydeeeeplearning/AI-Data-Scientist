import assert from 'node:assert/strict';

import {
  BRANCH_RUN_DIALOG_IDS,
  validateBranchRunDraft,
} from '../../src/renderer/components/runtime/BranchRunDialog';
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
  container.appendChild(doc.createElement('textarea'));
  container.appendChild(doc.createElement('select'));
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
  // === branch dialog exposes stable aria ids for title + description wiring ===
  {
    assert.equal(BRANCH_RUN_DIALOG_IDS.shell, 'run-branch-dialog-shell');
    assert.equal(BRANCH_RUN_DIALOG_IDS.title, 'run-branch-dialog-title');
    assert.equal(BRANCH_RUN_DIALOG_IDS.description, 'run-branch-dialog-description');
  }

  // === blank branch prompts are rejected before submit ===
  {
    assert.equal(
      validateBranchRunDraft({ message: '   ', model: null }),
      'message_required',
    );
    assert.equal(
      validateBranchRunDraft({ message: 'explore alternative model', model: 'm1' }),
      null,
    );
  }

  // === tab cycles within the branch dialog controls ===
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

    const backward = createKeyEvent('Tab', true);
    assert.equal(controller.handleKeyDown(backward), 'tab');
    assert.equal(doc.activeElement, container.children[0]);
  }

  // === escape is surfaced so the drawer can close the branch dialog ===
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

  console.log('[contract] PASS dialog-branch-a11y (4 cases)');
}

run();
