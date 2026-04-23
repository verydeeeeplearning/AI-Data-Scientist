"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const SaveCheckpointDialog_1 = require("../../src/renderer/components/runtime/SaveCheckpointDialog");
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
    const input = doc.createElement('input');
    const textarea = doc.createElement('textarea');
    const primary = doc.createElement('button');
    container.appendChild(input);
    container.appendChild(textarea);
    container.appendChild(primary);
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
    // === save dialog exposes stable aria ids for title + description wiring ===
    {
        strict_1.default.equal(SaveCheckpointDialog_1.SAVE_CHECKPOINT_DIALOG_IDS.title, 'run-save-checkpoint-title');
        strict_1.default.equal(SaveCheckpointDialog_1.SAVE_CHECKPOINT_DIALOG_IDS.description, 'run-save-checkpoint-description');
    }
    // === blank checkpoint names are rejected before submit ===
    {
        strict_1.default.equal((0, SaveCheckpointDialog_1.validateSaveCheckpointDraft)({ name: '   ', description: 'note' }), 'name_required');
        strict_1.default.equal((0, SaveCheckpointDialog_1.validateSaveCheckpointDraft)({ name: 'before fe', description: 'note' }), null);
    }
    // === focus trap activates, cycles, and restores focus on close ===
    {
        const doc = new FakeDocument();
        const opener = doc.createElement('button');
        doc.body.appendChild(opener);
        opener.focus();
        const container = createDialogContainer(doc);
        const controller = (0, runtimeDialogA11y_1.createRuntimeDialogA11yController)(container, { document: doc });
        controller.activate();
        strict_1.default.equal(doc.activeElement, container.children[0]);
        const tab = createKeyEvent('Tab');
        strict_1.default.equal(controller.handleKeyDown(tab), 'tab');
        strict_1.default.equal(tab.prevented, true);
        strict_1.default.equal(doc.activeElement, container.children[1]);
        controller.deactivate();
        strict_1.default.equal(doc.activeElement, opener);
    }
    // === escape is surfaced to the dialog so ESC=cancel remains possible ===
    {
        const doc = new FakeDocument();
        const controller = (0, runtimeDialogA11y_1.createRuntimeDialogA11yController)(createDialogContainer(doc), { document: doc });
        controller.activate();
        const escape = createKeyEvent('Escape');
        strict_1.default.equal(controller.handleKeyDown(escape), 'escape');
        strict_1.default.equal(escape.prevented, true);
    }
    console.log('[contract] PASS dialog-save-a11y (4 cases)');
}
run();
