import assert from 'node:assert/strict';

import {
  findFocusableElements,
  isFocusable,
  createFocusTrap,
  captureFocus,
  restoreFocus,
  type FocusTrap,
  type FocusToken,
} from '../../src/renderer/application/a11y/focusManagement';

class FakeElement {
  tagName: string;
  attributes: Map<string, string> = new Map();
  children: FakeElement[] = [];
  parent: FakeElement | null = null;
  hidden = false;
  disabled = false;
  focusedAt: number | null = null;
  isConnected = true;
  ownerDocument: FakeDocument;

  constructor(tagName: string, doc: FakeDocument) {
    this.tagName = tagName.toUpperCase();
    this.ownerDocument = doc;
  }
  getAttribute(name: string): string | null {
    return this.attributes.has(name) ? this.attributes.get(name)! : null;
  }
  setAttribute(name: string, value: string): void {
    this.attributes.set(name, String(value));
  }
  hasAttribute(name: string): boolean {
    return this.attributes.has(name);
  }
  appendChild(child: FakeElement): void {
    this.children.push(child);
    child.parent = this;
  }
  focus(): void {
    this.ownerDocument.activeElement = this;
    this.focusedAt = Date.now();
  }
  matches(selector: string): boolean {
    if (selector === ':not([disabled])') return !this.disabled;
    return false;
  }
  querySelectorAll(_selector: string): FakeElement[] {
    const out: FakeElement[] = [];
    walk(this, (el) => {
      if (el !== this) out.push(el);
    });
    return out;
  }
  contains(other: FakeElement): boolean {
    let current: FakeElement | null = other;
    while (current) {
      if (current === this) return true;
      current = current.parent;
    }
    return false;
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

function walk(root: FakeElement, fn: (el: FakeElement) => void): void {
  fn(root);
  for (const c of root.children) walk(c, fn);
}

function buildContainer(doc: FakeDocument, items: Array<{ tag: string; opts?: Record<string, string | boolean> }>): FakeElement {
  const container = doc.createElement('div');
  for (const item of items) {
    const el = doc.createElement(item.tag);
    if (item.opts) {
      for (const [k, v] of Object.entries(item.opts)) {
        if (v === true) {
          el.setAttribute(k, '');
        } else if (v === false) {
          // skip
        } else {
          el.setAttribute(k, String(v));
        }
        if (k === 'disabled' && v) el.disabled = true;
      }
    }
    container.appendChild(el);
  }
  doc.body.appendChild(container);
  return container;
}

function run(): void {
  // === isFocusable: button is focusable ===
  {
    const doc = new FakeDocument();
    const btn = doc.createElement('button');
    assert.equal(isFocusable(btn as unknown as HTMLElement), true);
  }

  // === isFocusable: disabled button is not focusable ===
  {
    const doc = new FakeDocument();
    const btn = doc.createElement('button');
    btn.disabled = true;
    btn.setAttribute('disabled', '');
    assert.equal(isFocusable(btn as unknown as HTMLElement), false);
  }

  // === isFocusable: tabindex=-1 is not focusable for tab cycle ===
  {
    const doc = new FakeDocument();
    const div = doc.createElement('div');
    div.setAttribute('tabindex', '-1');
    assert.equal(isFocusable(div as unknown as HTMLElement), false);
  }

  // === isFocusable: input/select/textarea/a[href] are focusable ===
  {
    const doc = new FakeDocument();
    const input = doc.createElement('input');
    const select = doc.createElement('select');
    const textarea = doc.createElement('textarea');
    const a = doc.createElement('a');
    a.setAttribute('href', '#x');
    assert.equal(isFocusable(input as unknown as HTMLElement), true);
    assert.equal(isFocusable(select as unknown as HTMLElement), true);
    assert.equal(isFocusable(textarea as unknown as HTMLElement), true);
    assert.equal(isFocusable(a as unknown as HTMLElement), true);
  }

  // === findFocusableElements: lists in DOM order ===
  {
    const doc = new FakeDocument();
    const c = buildContainer(doc, [
      { tag: 'button' },
      { tag: 'input' },
      { tag: 'div' }, // not focusable
      { tag: 'a', opts: { href: '#' } },
    ]);
    const list = findFocusableElements(c as unknown as HTMLElement);
    assert.equal(list.length, 3);
  }

  // === captureFocus + restoreFocus ===
  {
    const doc = new FakeDocument();
    const a = doc.createElement('button');
    const b = doc.createElement('button');
    doc.body.appendChild(a);
    doc.body.appendChild(b);
    a.focus();
    const token: FocusToken = captureFocus({ document: doc as unknown as Document });
    b.focus();
    assert.equal(doc.activeElement, b);
    restoreFocus(token);
    assert.equal(doc.activeElement, a);
  }

  // === captureFocus when nothing focused returns null token ===
  {
    const doc = new FakeDocument();
    const token = captureFocus({ document: doc as unknown as Document });
    // restoreFocus on null token is a no-op
    restoreFocus(token);
    assert.equal(doc.activeElement, null);
  }

  // === createFocusTrap focuses first focusable on activate ===
  {
    const doc = new FakeDocument();
    const c = buildContainer(doc, [{ tag: 'button' }, { tag: 'input' }]);
    const trap: FocusTrap = createFocusTrap(c as unknown as HTMLElement, {
      document: doc as unknown as Document,
    });
    trap.activate();
    assert.equal(doc.activeElement, c.children[0]);
    trap.deactivate();
  }

  // === createFocusTrap restores prior focus on deactivate ===
  {
    const doc = new FakeDocument();
    const outerBtn = doc.createElement('button');
    doc.body.appendChild(outerBtn);
    outerBtn.focus();

    const c = buildContainer(doc, [{ tag: 'button' }]);
    const trap = createFocusTrap(c as unknown as HTMLElement, {
      document: doc as unknown as Document,
    });
    trap.activate();
    assert.notEqual(doc.activeElement, outerBtn);
    trap.deactivate();
    assert.equal(doc.activeElement, outerBtn);
  }

  // === createFocusTrap.cycle: Tab from last wraps to first ===
  {
    const doc = new FakeDocument();
    const c = buildContainer(doc, [{ tag: 'button' }, { tag: 'button' }]);
    const trap = createFocusTrap(c as unknown as HTMLElement, {
      document: doc as unknown as Document,
    });
    trap.activate();
    // simulate tab from the last
    const last = c.children[1];
    last.focus();
    const next = trap.cycle('forward');
    assert.equal(next, c.children[0]);
    assert.equal(doc.activeElement, c.children[0]);
    trap.deactivate();
  }

  // === createFocusTrap.cycle: Shift+Tab from first wraps to last ===
  {
    const doc = new FakeDocument();
    const c = buildContainer(doc, [{ tag: 'button' }, { tag: 'button' }]);
    const trap = createFocusTrap(c as unknown as HTMLElement, {
      document: doc as unknown as Document,
    });
    trap.activate();
    const first = c.children[0];
    first.focus();
    const next = trap.cycle('backward');
    assert.equal(next, c.children[1]);
    trap.deactivate();
  }

  console.log('[contract] PASS focus-management (10 cases)');
}

run();
