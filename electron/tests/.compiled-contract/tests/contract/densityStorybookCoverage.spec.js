"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const node_fs_1 = __importDefault(require("node:fs"));
const node_path_1 = __importDefault(require("node:path"));
// __dirname resolves inside `tests/.compiled-contract/tests/contract/`; climb 4 levels to electron/.
const ELECTRON_ROOT = node_path_1.default.resolve(__dirname, '..', '..', '..', '..');
const PRIMITIVES_DIR = node_path_1.default.join(ELECTRON_ROOT, 'src', 'renderer', 'design-system', 'primitives');
const REQUIRED_PRIMITIVES = ['Button', 'Card', 'DialogShell', 'Input', 'Tabs'];
const REQUIRED_DENSITY_STORIES = [
    'CompactDensity',
    'ComfortableDensity',
    'SpaciousDensity',
];
const REQUIRED_DATA_DENSITY_VALUES = ['compact', 'comfortable', 'spacious'];
function readStoryFile(primitive) {
    const file = node_path_1.default.join(PRIMITIVES_DIR, `${primitive}.stories.tsx`);
    return node_fs_1.default.readFileSync(file, 'utf8');
}
function exportedConsts(content) {
    return [...content.matchAll(/^export const (\w+)/gm)].map((match) => match[1]);
}
function run() {
    let totalChecks = 0;
    for (const primitive of REQUIRED_PRIMITIVES) {
        const content = readStoryFile(primitive);
        const exports = exportedConsts(content);
        for (const story of REQUIRED_DENSITY_STORIES) {
            strict_1.default.ok(exports.includes(story), `${primitive}.stories.tsx must export "${story}" story`);
            totalChecks += 1;
        }
        strict_1.default.match(content, /applyDensityScale/, `${primitive}.stories.tsx must import applyDensityScale to scope CSS variables`);
        totalChecks += 1;
        strict_1.default.match(content, /data-density=\{mode\}/, `${primitive}.stories.tsx must wrap density showcases in [data-density={mode}]`);
        totalChecks += 1;
        for (const value of REQUIRED_DATA_DENSITY_VALUES) {
            const pattern = new RegExp(`mode=["']${value}["']`);
            strict_1.default.match(content, pattern, `${primitive}.stories.tsx must invoke a density showcase with mode="${value}"`);
            totalChecks += 1;
        }
    }
    console.log(`[contract] PASS density-storybook-coverage (${totalChecks} cases)`);
}
run();
