"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const PromoteDialog_1 = require("../../src/renderer/components/runtime/PromoteDialog");
const runtimeDialogA11y_1 = require("../../src/renderer/components/runtime/runtimeDialogA11y");
class FakeElement {
    constructor(tagName, ownerDocument) {
        this.attributes = new Map();
        this.children = [];
        this.parent = null;
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
function createDialogContainer(doc) {
    const container = doc.createElement('div');
    container.appendChild(doc.createElement('input'));
    container.appendChild(doc.createElement('input'));
    container.appendChild(doc.createElement('input'));
    container.appendChild(doc.createElement('button'));
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
    // === promote dialog exposes stable aria ids for title + description wiring ===
    {
        strict_1.default.equal(PromoteDialog_1.PROMOTE_DIALOG_IDS.title, 'cards-promote-dialog-title');
        strict_1.default.equal(PromoteDialog_1.PROMOTE_DIALOG_IDS.description, 'cards-promote-dialog-description');
    }
    // === only the supported audiences are accepted ===
    {
        strict_1.default.equal((0, PromoteDialog_1.validatePromoteDialogDraft)({ audience: 'board', title: 'Q2 brief' }), 'audience_required');
        strict_1.default.equal((0, PromoteDialog_1.validatePromoteDialogDraft)({ audience: 'exec', title: 'Q2 brief' }), null);
    }
    // === focus trap activates and cycles across the radio/input controls ===
    {
        const doc = new FakeDocument();
        const container = createDialogContainer(doc);
        const controller = (0, runtimeDialogA11y_1.createRuntimeDialogA11yController)(container, { document: doc });
        controller.activate();
        strict_1.default.equal(doc.activeElement, container.children[0]);
        const tab = createKeyEvent('Tab');
        strict_1.default.equal(controller.handleKeyDown(tab), 'tab');
        strict_1.default.equal(tab.prevented, true);
        strict_1.default.equal(doc.activeElement, container.children[1]);
    }
    // === escape is surfaced so ESC closes the promote dialog ===
    {
        const doc = new FakeDocument();
        const controller = (0, runtimeDialogA11y_1.createRuntimeDialogA11yController)(createDialogContainer(doc), { document: doc });
        controller.activate();
        const escape = createKeyEvent('Escape');
        strict_1.default.equal(controller.handleKeyDown(escape), 'escape');
        strict_1.default.equal(escape.prevented, true);
    }
    console.log('[contract] PASS dialog-promote-a11y (4 cases)');
}
run();
