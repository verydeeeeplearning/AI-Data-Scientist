"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const node_fs_1 = require("node:fs");
const node_os_1 = require("node:os");
const node_path_1 = require("node:path");
// Compiled path differs from source path: source is electron/tests/contract/x.ts,
// compiled is electron/tests/.compiled-contract/tests/contract/x.js. Resolve
// relative to compiled __dirname climbing back to electron/.
// eslint-disable-next-line @typescript-eslint/no-require-imports
const path = require('node:path');
const lintArchPath = path.resolve(__dirname, '..', '..', '..', '..', 'scripts', 'lintArchCore.cjs');
// eslint-disable-next-line @typescript-eslint/no-require-imports
const lintArch = require(lintArchPath);
const scanSourceFile = lintArch.scanSourceFile;
const scanProject = lintArch.scanProject;
function makeFixture() {
    const root = (0, node_fs_1.mkdtempSync)((0, node_path_1.join)((0, node_os_1.tmpdir)(), 'ds-arch-lint-'));
    const dirs = [
        (0, node_path_1.join)(root, 'src/renderer/domain/mission'),
        (0, node_path_1.join)(root, 'src/renderer/application/mission'),
        (0, node_path_1.join)(root, 'src/renderer/infrastructure/api'),
        (0, node_path_1.join)(root, 'src/renderer/components/mission'),
        (0, node_path_1.join)(root, 'src/renderer/stores'),
    ];
    for (const dir of dirs) {
        (0, node_fs_1.mkdirSync)(dir, { recursive: true });
    }
    return {
        root,
        cleanup: () => {
            (0, node_fs_1.rmSync)(root, { recursive: true, force: true });
        },
    };
}
function run() {
    // === Test 1: domain importing react -> violation ===
    {
        const f = makeFixture();
        try {
            (0, node_fs_1.writeFileSync)((0, node_path_1.join)(f.root, 'src/renderer/domain/mission/mission.ts'), "import { useState } from 'react';\nexport const Mission = {};\n");
            const violations = scanProject((0, node_path_1.join)(f.root, 'src/renderer'));
            strict_1.default.equal(violations.length, 1, 'expected 1 violation when domain imports react');
            strict_1.default.equal(violations[0].layer, 'domain');
            strict_1.default.match(violations[0].importedFrom, /react/);
        }
        finally {
            f.cleanup();
        }
    }
    // === Test 2: domain importing zustand -> violation ===
    {
        const f = makeFixture();
        try {
            (0, node_fs_1.writeFileSync)((0, node_path_1.join)(f.root, 'src/renderer/domain/mission/mission.ts'), "import { create } from 'zustand';\nexport const Mission = {};\n");
            const violations = scanProject((0, node_path_1.join)(f.root, 'src/renderer'));
            strict_1.default.equal(violations.length, 1);
            strict_1.default.match(violations[0].importedFrom, /zustand/);
        }
        finally {
            f.cleanup();
        }
    }
    // === Test 3: domain importing axios -> violation ===
    {
        const f = makeFixture();
        try {
            (0, node_fs_1.writeFileSync)((0, node_path_1.join)(f.root, 'src/renderer/domain/mission/mission.ts'), "import axios from 'axios';\nexport const Mission = {};\n");
            const violations = scanProject((0, node_path_1.join)(f.root, 'src/renderer'));
            strict_1.default.equal(violations.length, 1);
            strict_1.default.match(violations[0].importedFrom, /axios/);
        }
        finally {
            f.cleanup();
        }
    }
    // === Test 4: domain importing infrastructure -> violation ===
    {
        const f = makeFixture();
        try {
            (0, node_fs_1.writeFileSync)((0, node_path_1.join)(f.root, 'src/renderer/domain/mission/mission.ts'), "import { api } from '../../infrastructure/api/missionApi';\nexport const Mission = {};\n");
            const violations = scanProject((0, node_path_1.join)(f.root, 'src/renderer'));
            strict_1.default.equal(violations.length, 1);
            strict_1.default.match(violations[0].importedFrom, /infrastructure/);
        }
        finally {
            f.cleanup();
        }
    }
    // === Test 5: domain importing components -> violation ===
    {
        const f = makeFixture();
        try {
            (0, node_fs_1.writeFileSync)((0, node_path_1.join)(f.root, 'src/renderer/domain/mission/mission.ts'), "import { MissionView } from '../../components/mission/MissionView';\nexport const Mission = {};\n");
            const violations = scanProject((0, node_path_1.join)(f.root, 'src/renderer'));
            strict_1.default.equal(violations.length, 1);
            strict_1.default.match(violations[0].importedFrom, /components/);
        }
        finally {
            f.cleanup();
        }
    }
    // === Test 6: pure domain (stdlib + relative within domain) -> OK ===
    {
        const f = makeFixture();
        try {
            (0, node_fs_1.writeFileSync)((0, node_path_1.join)(f.root, 'src/renderer/domain/mission/mission.ts'), "import { Goal } from './goal';\nexport const Mission = { goal: Goal };\n");
            (0, node_fs_1.writeFileSync)((0, node_path_1.join)(f.root, 'src/renderer/domain/mission/goal.ts'), "export const Goal = {};\n");
            const violations = scanProject((0, node_path_1.join)(f.root, 'src/renderer'));
            strict_1.default.equal(violations.length, 0, 'pure domain with intra-domain import should pass');
        }
        finally {
            f.cleanup();
        }
    }
    // === Test 7: application importing infrastructure directly -> violation ===
    {
        const f = makeFixture();
        try {
            (0, node_fs_1.writeFileSync)((0, node_path_1.join)(f.root, 'src/renderer/application/mission/getMissionContext.ts'), "import { fetchMission } from '../../infrastructure/api/missionApi';\nexport const usecase = () => fetchMission();\n");
            const violations = scanProject((0, node_path_1.join)(f.root, 'src/renderer'));
            strict_1.default.equal(violations.length, 1);
            strict_1.default.equal(violations[0].layer, 'application');
            strict_1.default.match(violations[0].importedFrom, /infrastructure/);
        }
        finally {
            f.cleanup();
        }
    }
    // === Test 8: application importing components -> violation ===
    {
        const f = makeFixture();
        try {
            (0, node_fs_1.writeFileSync)((0, node_path_1.join)(f.root, 'src/renderer/application/mission/getMissionContext.ts'), "import { MissionView } from '../../components/mission/MissionView';\nexport const usecase = () => MissionView;\n");
            const violations = scanProject((0, node_path_1.join)(f.root, 'src/renderer'));
            strict_1.default.equal(violations.length, 1);
            strict_1.default.equal(violations[0].layer, 'application');
        }
        finally {
            f.cleanup();
        }
    }
    // === Test 9: application importing react -> violation ===
    {
        const f = makeFixture();
        try {
            (0, node_fs_1.writeFileSync)((0, node_path_1.join)(f.root, 'src/renderer/application/mission/getMissionContext.ts'), "import { useState } from 'react';\nexport const usecase = useState;\n");
            const violations = scanProject((0, node_path_1.join)(f.root, 'src/renderer'));
            strict_1.default.equal(violations.length, 1);
            strict_1.default.match(violations[0].importedFrom, /react/);
        }
        finally {
            f.cleanup();
        }
    }
    // === Test 10: application importing domain -> OK ===
    {
        const f = makeFixture();
        try {
            (0, node_fs_1.writeFileSync)((0, node_path_1.join)(f.root, 'src/renderer/application/mission/getMissionContext.ts'), "import { Mission } from '../../domain/mission/mission';\nexport const usecase = () => Mission;\n");
            (0, node_fs_1.writeFileSync)((0, node_path_1.join)(f.root, 'src/renderer/domain/mission/mission.ts'), "export const Mission = {};\n");
            const violations = scanProject((0, node_path_1.join)(f.root, 'src/renderer'));
            strict_1.default.equal(violations.length, 0);
        }
        finally {
            f.cleanup();
        }
    }
    // === Test 11: components importing infrastructure -> violation ===
    {
        const f = makeFixture();
        try {
            (0, node_fs_1.writeFileSync)((0, node_path_1.join)(f.root, 'src/renderer/components/mission/MissionView.tsx'), "import { fetchMission } from '../../infrastructure/api/missionApi';\nexport const View = () => null;\n");
            const violations = scanProject((0, node_path_1.join)(f.root, 'src/renderer'));
            strict_1.default.equal(violations.length, 1);
            strict_1.default.equal(violations[0].layer, 'components');
            strict_1.default.match(violations[0].importedFrom, /infrastructure/);
        }
        finally {
            f.cleanup();
        }
    }
    // === Test 12: scanSourceFile recognizes both single+double quote imports ===
    {
        const single = scanSourceFile('src/renderer/domain/mission/mission.ts', "import { useState } from 'react';\n");
        const double = scanSourceFile('src/renderer/domain/mission/mission.ts', 'import { useState } from "react";\n');
        strict_1.default.equal(single.length, 1);
        strict_1.default.equal(double.length, 1);
    }
    // === Test 13: dynamic import() also detected ===
    {
        const violations = scanSourceFile('src/renderer/domain/mission/mission.ts', "const r = await import('react');\nexport const x = r;\n");
        strict_1.default.equal(violations.length, 1);
        strict_1.default.match(violations[0].importedFrom, /react/);
    }
    // === Test 14: violations include file path + line number ===
    {
        const violations = scanSourceFile('src/renderer/domain/mission/mission.ts', "// header comment\nimport { useState } from 'react';\nexport const x = useState;\n");
        strict_1.default.equal(violations.length, 1);
        strict_1.default.equal(violations[0].file, 'src/renderer/domain/mission/mission.ts');
        strict_1.default.equal(violations[0].line, 2);
    }
    console.log('[contract] PASS eslint-arch-rule (14 cases)');
}
run();
