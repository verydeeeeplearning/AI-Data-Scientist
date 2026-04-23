import assert from 'node:assert/strict';

import { createApprovalModalA11yController } from '../../src/renderer/components/approval/approvalModalA11y';

class FakeElement {
  tagName: string;
  attributes: Map<string, string> = new Map();
  children: FakeElement[] = [];
  parent: FakeElement | null = null;
  ownerDocument: FakeDocument;
  disabled = false;

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

function createModalContainer(doc: FakeDocument): FakeElement {
  const container = doc.createElement('div');
  const primary = doc.createElement('button');
  const secondary = doc.createElement('button');
  container.appendChild(primary);
  container.appendChild(secondary);
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
  // === activate focuses the first interactive control ===
  {
    const doc = new FakeDocument();
    const opener = doc.createElement('button');
    doc.body.appendChild(opener);
    opener.focus();

    const container = createModalContainer(doc);
    const controller = createApprovalModalA11yController(
      container as unknown as HTMLElement,
      { document: doc as unknown as Document },
    );

    controller.activate();
    assert.equal(doc.activeElement, container.children[0]);
  }

  // === Tab moves within the modal instead of escaping it ===
  {
    const doc = new FakeDocument();
    const container = createModalContainer(doc);
    const controller = createApprovalModalA11yController(
      container as unknown as HTMLElement,
      { document: doc as unknown as Document },
    );

    controller.activate();
    const tab = createKeyEvent('Tab');
    const action = controller.handleKeyDown(tab);
    assert.equal(action, 'tab');
    assert.equal(tab.prevented, true);
    assert.equal(doc.activeElement, container.children[1]);
  }

  // === Shift+Tab wraps from the first control back to the last ===
  {
    const doc = new FakeDocument();
    const container = createModalContainer(doc);
    const controller = createApprovalModalA11yController(
      container as unknown as HTMLElement,
      { document: doc as unknown as Document },
    );

    controller.activate();
    const backward = createKeyEvent('Tab', true);
    const action = controller.handleKeyDown(backward);
    assert.equal(action, 'tab');
    assert.equal(backward.prevented, true);
    assert.equal(doc.activeElement, container.children[1]);
  }

  // === Escape is surfaced to the modal and default handling is suppressed ===
  {
    const doc = new FakeDocument();
    const container = createModalContainer(doc);
    const controller = createApprovalModalA11yController(
      container as unknown as HTMLElement,
      { document: doc as unknown as Document },
    );

    controller.activate();
    const escape = createKeyEvent('Escape');
    const action = controller.handleKeyDown(escape);
    assert.equal(action, 'escape');
    assert.equal(escape.prevented, true);
  }

  // === deactivate restores focus to the opener once the modal clears ===
  {
    const doc = new FakeDocument();
    const opener = doc.createElement('button');
    doc.body.appendChild(opener);
    opener.focus();

    const container = createModalContainer(doc);
    const controller = createApprovalModalA11yController(
      container as unknown as HTMLElement,
      { document: doc as unknown as Document },
    );

    controller.activate();
    controller.deactivate();
    assert.equal(doc.activeElement, opener);
  }

  console.log('[contract] PASS approval-modal-a11y (5 cases)');
}

run();
