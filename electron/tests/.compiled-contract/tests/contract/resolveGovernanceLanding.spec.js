"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const resolveGovernanceLanding_1 = require("../../src/renderer/application/navigation/resolveGovernanceLanding");
function run() {
    {
        const landing = (0, resolveGovernanceLanding_1.resolveGovernanceLanding)({ subPath: undefined });
        strict_1.default.equal(landing.sectionId, 'review');
        strict_1.default.equal(landing.sectionPath, '/governance/review');
        strict_1.default.equal(landing.detail, null);
    }
    {
        const landing = (0, resolveGovernanceLanding_1.resolveGovernanceLanding)({ subPath: 'verifier/result-42' });
        strict_1.default.equal(landing.sectionId, 'review');
        strict_1.default.equal(landing.sectionPath, '/governance/review');
        strict_1.default.equal(landing.detail?.kind, 'verifier');
        strict_1.default.equal(landing.detail?.id, 'result-42');
    }
    {
        const landing = (0, resolveGovernanceLanding_1.resolveGovernanceLanding)({ subPath: 'lineage/run-9/result-42' });
        strict_1.default.equal(landing.sectionId, 'review');
        strict_1.default.equal(landing.detail?.kind, 'lineage');
        strict_1.default.equal(landing.detail?.id, 'run-9/result-42');
    }
    {
        const landing = (0, resolveGovernanceLanding_1.resolveGovernanceLanding)({ subPath: 'fallback-log' });
        strict_1.default.equal(landing.sectionId, 'review');
        strict_1.default.equal(landing.detail?.kind, 'fallback-log');
        strict_1.default.equal(landing.detail?.id, null);
    }
    {
        const landing = (0, resolveGovernanceLanding_1.resolveGovernanceLanding)({ subPath: 'approvals/appr-7' });
        strict_1.default.equal(landing.sectionId, 'approvals');
        strict_1.default.equal(landing.sectionPath, '/governance/approvals');
        strict_1.default.equal(landing.detail?.kind, 'approval');
        strict_1.default.equal(landing.detail?.id, 'appr-7');
    }
    {
        const landing = (0, resolveGovernanceLanding_1.resolveGovernanceLanding)({ subPath: 'policies/runtime-profile' });
        strict_1.default.equal(landing.sectionId, 'policy');
        strict_1.default.equal(landing.sectionPath, '/governance/policy');
        strict_1.default.equal(landing.detail?.kind, 'policy');
        strict_1.default.equal(landing.detail?.id, 'runtime-profile');
    }
    {
        const landing = (0, resolveGovernanceLanding_1.resolveGovernanceLanding)({ subPath: 'certification/mission-alpha' });
        strict_1.default.equal(landing.sectionId, 'certification');
        strict_1.default.equal(landing.detail?.kind, 'certification');
        strict_1.default.equal(landing.detail?.id, 'mission-alpha');
    }
    {
        const landing = (0, resolveGovernanceLanding_1.resolveGovernanceLanding)({ subPath: 'unknown/route' });
        strict_1.default.equal(landing.sectionId, 'review');
        strict_1.default.equal(landing.detail, null);
    }
    console.log('[contract] PASS resolve-governance-landing (8 cases)');
}
run();
