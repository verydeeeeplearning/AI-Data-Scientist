"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const focusManagement_1 = require("../../src/renderer/application/a11y/focusManagement");
class FakeElement {
    constructor(tagName, doc) {
        this.attributes = new Map();
        this.children = [];
        this.parent = null;
        this.hidden = false;
        this.disabled = false;
        this.focusedAt = null;
        this.isConnected = true;
        this.tagName = tagName.toUpperCase();
        this.ownerDocument = doc;
    }
    getAttribute(name) {
        return this.attributes.has(name) ? this.attributes.get(name) : null;
    }
    setAttribute(name, value) {
        this.attributes.set(name, String(value));
    }
    hasAttribute(name) {
        return this.attributes.has(name);
    }
    appendChild(child) {
        this.children.push(child);
        child.parent = this;
    }
    focus() {
        this.ownerDocument.activeElement = this;
        this.focusedAt = Date.now();
    }
    matches(selector) {
        if (selector === ':not([disabled])')
            return !this.disabled;
        return false;
    }
    querySelectorAll(_selector) {
        const out = [];
        walk(this, (el) => {
            if (el !== this)
                out.push(el);
        });
        return out;
    }
    contains(other) {
        let current = other;
        while (current) {
            if (current === this)
                return true;
            current = current.parent;
        }
        return false;
    }
}
class FakeDocument {
    constructor() {
        this.activeElement = null;
        this.body = new FakeElement('body', this);
    }
    createElement(tag) {
        return new FakeElement(tag, this);
    }
}
function walk(root, fn) {
    fn(root);
    for (const c of root.children)
        walk(c, fn);
}
function buildContainer(doc, items) {
    const container = doc.createElement('div');
    for (const item of items) {
        const el = doc.createElement(item.tag);
        if (item.opts) {
            for (const [k, v] of Object.entries(item.opts)) {
                if (v === true) {
                    el.setAttribute(k, '');
                }
                else if (v === false) {
                    // skip
                }
                else {
                    el.setAttribute(k, String(v));
                }
                if (k === 'disabled' && v)
                    el.disabled = true;
            }
        }
        container.appendChild(el);
    }
    doc.body.appendChild(container);
    return container;
}
function run() {
    // === isFocusable: button is focusable ===
    {
        const doc = new FakeDocument();
        const btn = doc.createElement('button');
        strict_1.default.equal((0, focusManagement_1.isFocusable)(btn), true);
    }
    // === isFocusable: disabled button is not focusable ===
    {
        const doc = new FakeDocument();
        const btn = doc.createElement('button');
        btn.disabled = true;
        btn.setAttribute('disabled', '');
        strict_1.default.equal((0, focusManagement_1.isFocusable)(btn), false);
    }
    // === isFocusable: tabindex=-1 is not focusable for tab cycle ===
    {
        const doc = new FakeDocument();
        const div = doc.createElement('div');
        div.setAttribute('tabindex', '-1');
        strict_1.default.equal((0, focusManagement_1.isFocusable)(div), false);
    }
    // === isFocusable: input/select/textarea/a[href] are focusable ===
    {
        const doc = new FakeDocument();
        const input = doc.createElement('input');
        const select = doc.createElement('select');
        const textarea = doc.createElement('textarea');
        const a = doc.createElement('a');
        a.setAttribute('href', '#x');
        strict_1.default.equal((0, focusManagement_1.isFocusable)(input), true);
        strict_1.default.equal((0, focusManagement_1.isFocusable)(select), true);
        strict_1.default.equal((0, focusManagement_1.isFocusable)(textarea), true);
        strict_1.default.equal((0, focusManagement_1.isFocusable)(a), true);
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
        const list = (0, focusManagement_1.findFocusableElements)(c);
        strict_1.default.equal(list.length, 3);
    }
    // === captureFocus + restoreFocus ===
    {
        const doc = new FakeDocument();
        const a = doc.createElement('button');
        const b = doc.createElement('button');
        doc.body.appendChild(a);
        doc.body.appendChild(b);
        a.focus();
        const token = (0, focusManagement_1.captureFocus)({ document: doc });
        b.focus();
        strict_1.default.equal(doc.activeElement, b);
        (0, focusManagement_1.restoreFocus)(token);
        strict_1.default.equal(doc.activeElement, a);
    }
    // === captureFocus when nothing focused returns null token ===
    {
        const doc = new FakeDocument();
        const token = (0, focusManagement_1.captureFocus)({ document: doc });
        // restoreFocus on null token is a no-op
        (0, focusManagement_1.restoreFocus)(token);
        strict_1.default.equal(doc.activeElement, null);
    }
    // === createFocusTrap focuses first focusable on activate ===
    {
        const doc = new FakeDocument();
        const c = buildContainer(doc, [{ tag: 'button' }, { tag: 'input' }]);
        const trap = (0, focusManagement_1.createFocusTrap)(c, {
            document: doc,
        });
        trap.activate();
        strict_1.default.equal(doc.activeElement, c.children[0]);
        trap.deactivate();
    }
    // === createFocusTrap restores prior focus on deactivate ===
    {
        const doc = new FakeDocument();
        const outerBtn = doc.createElement('button');
        doc.body.appendChild(outerBtn);
        outerBtn.focus();
        const c = buildContainer(doc, [{ tag: 'button' }]);
        const trap = (0, focusManagement_1.createFocusTrap)(c, {
            document: doc,
        });
        trap.activate();
        strict_1.default.notEqual(doc.activeElement, outerBtn);
        trap.deactivate();
        strict_1.default.equal(doc.activeElement, outerBtn);
    }
    // === createFocusTrap.cycle: Tab from last wraps to first ===
    {
        const doc = new FakeDocument();
        const c = buildContainer(doc, [{ tag: 'button' }, { tag: 'button' }]);
        const trap = (0, focusManagement_1.createFocusTrap)(c, {
            document: doc,
        });
        trap.activate();
        // simulate tab from the last
        const last = c.children[1];
        last.focus();
        const next = trap.cycle('forward');
        strict_1.default.equal(next, c.children[0]);
        strict_1.default.equal(doc.activeElement, c.children[0]);
        trap.deactivate();
    }
    // === createFocusTrap.cycle: Shift+Tab from first wraps to last ===
    {
        const doc = new FakeDocument();
        const c = buildContainer(doc, [{ tag: 'button' }, { tag: 'button' }]);
        const trap = (0, focusManagement_1.createFocusTrap)(c, {
            document: doc,
        });
        trap.activate();
        const first = c.children[0];
        first.focus();
        const next = trap.cycle('backward');
        strict_1.default.equal(next, c.children[1]);
        trap.deactivate();
    }
    console.log('[contract] PASS focus-management (10 cases)');
}
run();
