"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const approvalModalA11y_1 = require("../../src/renderer/components/approval/approvalModalA11y");
class FakeElement {
    constructor(tagName, ownerDocument) {
        this.attributes = new Map();
        this.children = [];
        this.parent = null;
        this.disabled = false;
        this.tagName = tagName.toUpperCase();
        this.ownerDocument = ownerDocument;
    }
    appendChild(child) {
        this.children.push(child);
        child.parent = this;
    }
    focus() {
        this.ownerDocument.activeElement = this;
    }
    hasAttribute(name) {
        return this.attributes.has(name);
    }
    getAttribute(name) {
        return this.attributes.has(name) ? this.attributes.get(name) : null;
    }
    setAttribute(name, value) {
        this.attributes.set(name, value);
    }
    querySelectorAll(_selector) {
        const out = [];
        walk(this, (node) => {
            if (node !== this)
                out.push(node);
        });
        return out;
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
function walk(root, visit) {
    visit(root);
    for (const child of root.children) {
        walk(child, visit);
    }
}
function createModalContainer(doc) {
    const container = doc.createElement('div');
    const primary = doc.createElement('button');
    const secondary = doc.createElement('button');
    container.appendChild(primary);
    container.appendChild(secondary);
    doc.body.appendChild(container);
    return container;
}
function createKeyEvent(key, shiftKey = false) {
    return {
        key,
        shiftKey,
        prevented: false,
        preventDefault() {
            this.prevented = true;
        },
    };
}
function run() {
    // === activate focuses the first interactive control ===
    {
        const doc = new FakeDocument();
        const opener = doc.createElement('button');
        doc.body.appendChild(opener);
        opener.focus();
        const container = createModalContainer(doc);
        const controller = (0, approvalModalA11y_1.createApprovalModalA11yController)(container, { document: doc });
        controller.activate();
        strict_1.default.equal(doc.activeElement, container.children[0]);
    }
    // === Tab moves within the modal instead of escaping it ===
    {
        const doc = new FakeDocument();
        const container = createModalContainer(doc);
        const controller = (0, approvalModalA11y_1.createApprovalModalA11yController)(container, { document: doc });
        controller.activate();
        const tab = createKeyEvent('Tab');
        const action = controller.handleKeyDown(tab);
        strict_1.default.equal(action, 'tab');
        strict_1.default.equal(tab.prevented, true);
        strict_1.default.equal(doc.activeElement, container.children[1]);
    }
    // === Shift+Tab wraps from the first control back to the last ===
    {
        const doc = new FakeDocument();
        const container = createModalContainer(doc);
        const controller = (0, approvalModalA11y_1.createApprovalModalA11yController)(container, { document: doc });
        controller.activate();
        const backward = createKeyEvent('Tab', true);
        const action = controller.handleKeyDown(backward);
        strict_1.default.equal(action, 'tab');
        strict_1.default.equal(backward.prevented, true);
        strict_1.default.equal(doc.activeElement, container.children[1]);
    }
    // === Escape is surfaced to the modal and default handling is suppressed ===
    {
        const doc = new FakeDocument();
        const container = createModalContainer(doc);
        const controller = (0, approvalModalA11y_1.createApprovalModalA11yController)(container, { document: doc });
        controller.activate();
        const escape = createKeyEvent('Escape');
        const action = controller.handleKeyDown(escape);
        strict_1.default.equal(action, 'escape');
        strict_1.default.equal(escape.prevented, true);
    }
    // === deactivate restores focus to the opener once the modal clears ===
    {
        const doc = new FakeDocument();
        const opener = doc.createElement('button');
        doc.body.appendChild(opener);
        opener.focus();
        const container = createModalContainer(doc);
        const controller = (0, approvalModalA11y_1.createApprovalModalA11yController)(container, { document: doc });
        controller.activate();
        controller.deactivate();
        strict_1.default.equal(doc.activeElement, opener);
    }
    console.log('[contract] PASS approval-modal-a11y (5 cases)');
}
run();
