"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const BranchRunDialog_1 = require("../../src/renderer/components/runtime/BranchRunDialog");
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
    container.appendChild(doc.createElement('textarea'));
    container.appendChild(doc.createElement('select'));
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
    // === branch dialog exposes stable aria ids for title + description wiring ===
    {
        strict_1.default.equal(BranchRunDialog_1.BRANCH_RUN_DIALOG_IDS.shell, 'run-branch-dialog-shell');
        strict_1.default.equal(BranchRunDialog_1.BRANCH_RUN_DIALOG_IDS.title, 'run-branch-dialog-title');
        strict_1.default.equal(BranchRunDialog_1.BRANCH_RUN_DIALOG_IDS.description, 'run-branch-dialog-description');
    }
    // === blank branch prompts are rejected before submit ===
    {
        strict_1.default.equal((0, BranchRunDialog_1.validateBranchRunDraft)({ message: '   ', model: null }), 'message_required');
        strict_1.default.equal((0, BranchRunDialog_1.validateBranchRunDraft)({ message: 'explore alternative model', model: 'm1' }), null);
    }
    // === tab cycles within the branch dialog controls ===
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
        const backward = createKeyEvent('Tab', true);
        strict_1.default.equal(controller.handleKeyDown(backward), 'tab');
        strict_1.default.equal(doc.activeElement, container.children[0]);
    }
    // === escape is surfaced so the drawer can close the branch dialog ===
    {
        const doc = new FakeDocument();
        const controller = (0, runtimeDialogA11y_1.createRuntimeDialogA11yController)(createDialogContainer(doc), { document: doc });
        controller.activate();
        const escape = createKeyEvent('Escape');
        strict_1.default.equal(controller.handleKeyDown(escape), 'escape');
        strict_1.default.equal(escape.prevented, true);
    }
    console.log('[contract] PASS dialog-branch-a11y (4 cases)');
}
run();
