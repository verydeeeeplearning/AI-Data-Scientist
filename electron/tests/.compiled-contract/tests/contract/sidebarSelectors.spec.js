"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const react_1 = require("react");
const server_1 = require("react-dom/server");
const ModeSelector_1 = require("../../src/renderer/components/sidebar/ModeSelector");
const ModelSelector_1 = require("../../src/renderer/components/sidebar/ModelSelector");
const GROUPS = [
    {
        id: 'best_quality',
        order: 1,
        titleKey: 'llm.group.best_quality.title',
        descriptionKey: 'llm.group.best_quality.description',
        emptyTitleKey: 'llm.group.best_quality.emptyTitle',
        emptyDescriptionKey: 'llm.group.best_quality.emptyDescription',
        models: [
            {
                id: 'anthropic/claude-sonnet-4-6',
                provider: 'anthropic',
                displayName: 'Claude Sonnet 4.6',
                maxContext: 200000,
                maxOutput: 64000,
                authType: 'api_key',
                providerCategory: 'api_key',
                legacy: false,
                capabilityGroup: 'best_quality',
                badges: ['strong_reasoning', 'strong_korean'],
                recommendedFor: ['data_analysis'],
            },
        ],
    },
];
function run() {
    const modeHtml = (0, server_1.renderToStaticMarkup)((0, react_1.createElement)(ModeSelector_1.ModeSelector, {
        onChange: () => undefined,
    }));
    strict_1.default.match(modeHtml, /<fieldset[^>]*aria-label="Execution mode"/);
    strict_1.default.match(modeHtml, /name="sidebar-execution-mode"/);
    strict_1.default.equal((modeHtml.match(/type="radio"/g) ?? []).length, 3);
    strict_1.default.match(modeHtml, /Supervised/);
    const modelHtml = (0, server_1.renderToStaticMarkup)((0, react_1.createElement)(ModelSelector_1.ModelSelector, {
        onChangeModel: () => undefined,
        onChangeQualityPreset: () => undefined,
        groups: GROUPS,
    }));
    strict_1.default.match(modelHtml, /aria-haspopup="dialog"/);
    strict_1.default.match(modelHtml, /aria-expanded="false"/);
    strict_1.default.match(modelHtml, /aria-controls="sidebar-model-selector-panel-[^"]+"/);
    strict_1.default.match(modelHtml, /type="button"/);
    console.log('[contract] PASS sidebar-selectors (2 cases)');
}
run();
