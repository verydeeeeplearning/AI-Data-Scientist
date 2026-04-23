"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const audienceView_1 = require("../../src/renderer/domain/workspace/audienceView");
const cardEmphasisAdopter_1 = require("../../src/renderer/application/workspace/cardEmphasisAdopter");
const audienceCardState_1 = require("../../src/renderer/components/cards/audienceCardState");
const cardPresentation_1 = require("../../src/renderer/components/cards/cardPresentation");
function run() {
    let cases = 0;
    // === userExpanded wins regardless of audience ===
    {
        for (const view of ['ds', 'exec', 'ml']) {
            strict_1.default.equal((0, cardEmphasisAdopter_1.resolveCardDisplayMode)({ userExpanded: true }, view), 'expanded', `userExpanded=true must win for audience ${view}`);
            cases += 1;
        }
        for (const view of ['ds', 'exec', 'ml']) {
            strict_1.default.equal((0, cardEmphasisAdopter_1.resolveCardDisplayMode)({ userExpanded: false }, view), 'collapsed', `userExpanded=false must win for audience ${view}`);
            cases += 1;
        }
        // userExpanded beats workspace-level forceExpanded / forceCollapsed both ways.
        strict_1.default.equal((0, cardEmphasisAdopter_1.resolveCardDisplayMode)({ userExpanded: false, forceExpanded: true }, 'ds'), 'collapsed');
        cases += 1;
        strict_1.default.equal((0, cardEmphasisAdopter_1.resolveCardDisplayMode)({ userExpanded: true, forceCollapsed: true }, 'exec'), 'expanded');
        cases += 1;
    }
    // === forceExpanded wins over audience emphasis (when no userExpanded) ===
    {
        strict_1.default.equal((0, cardEmphasisAdopter_1.resolveCardDisplayMode)({ forceExpanded: true }, 'exec'), 'expanded', 'forceExpanded must override Exec collapsed default');
        cases += 1;
        strict_1.default.equal((0, cardEmphasisAdopter_1.resolveCardDisplayMode)({ forceExpanded: true }, 'ds'), 'expanded');
        cases += 1;
    }
    // === forceCollapsed wins over audience emphasis (when no userExpanded) ===
    {
        strict_1.default.equal((0, cardEmphasisAdopter_1.resolveCardDisplayMode)({ forceCollapsed: true }, 'ds'), 'collapsed', 'forceCollapsed must override DS expanded default');
        cases += 1;
        strict_1.default.equal((0, cardEmphasisAdopter_1.resolveCardDisplayMode)({ forceCollapsed: true }, 'ml'), 'collapsed');
        cases += 1;
        // forceExpanded beats forceCollapsed when both set (matches applyAudienceViewToCard).
        strict_1.default.equal((0, cardEmphasisAdopter_1.resolveCardDisplayMode)({ forceExpanded: true, forceCollapsed: true }, 'exec'), 'expanded');
        cases += 1;
    }
    // === No overrides: each audience uses its profile emphasis ===
    {
        strict_1.default.equal((0, cardEmphasisAdopter_1.resolveCardDisplayMode)({}, 'ds'), 'expanded', 'DS audience defaults to expanded');
        cases += 1;
        strict_1.default.equal((0, cardEmphasisAdopter_1.resolveCardDisplayMode)({}, 'exec'), 'collapsed', 'Exec audience defaults to collapsed');
        cases += 1;
        strict_1.default.equal((0, cardEmphasisAdopter_1.resolveCardDisplayMode)({}, 'ml'), 'expanded', 'ML audience defaults to expanded');
        cases += 1;
    }
    // === useAudienceView profile lookup matches getAudienceViewProfile ===
    // The hook is a thin facade over getAudienceViewProfile + zustand selectors.
    // Contract tests cannot import React, so verify the underlying lookup the
    // hook delegates to returns the same instance as the lookup table.
    {
        for (const view of ['ds', 'exec', 'ml']) {
            strict_1.default.equal((0, audienceView_1.getAudienceViewProfile)(view), audienceView_1.AUDIENCE_VIEW_PROFILES[view], `getAudienceViewProfile(${view}) must return the AUDIENCE_VIEW_PROFILES entry`);
            cases += 1;
        }
    }
    // === first-toggle override and reset semantics stay audience-driven ===
    {
        const execOverride = (0, audienceCardState_1.getNextUserExpandedOverride)(undefined, 'collapsed');
        strict_1.default.equal(execOverride, true);
        strict_1.default.equal((0, cardEmphasisAdopter_1.resolveCardDisplayMode)({ userExpanded: execOverride }, 'exec'), 'expanded');
        strict_1.default.equal((0, cardEmphasisAdopter_1.resolveCardDisplayMode)({ userExpanded: undefined }, 'exec'), 'collapsed');
        cases += 3;
        const dsOverride = (0, audienceCardState_1.getNextUserExpandedOverride)(undefined, 'expanded');
        strict_1.default.equal(dsOverride, false);
        strict_1.default.equal((0, cardEmphasisAdopter_1.resolveCardDisplayMode)({ userExpanded: dsOverride }, 'ds'), 'collapsed');
        strict_1.default.equal((0, cardEmphasisAdopter_1.resolveCardDisplayMode)({ userExpanded: undefined }, 'ds'), 'expanded');
        cases += 3;
        strict_1.default.equal((0, audienceCardState_1.getNextUserExpandedOverride)(execOverride, 'expanded'), false);
        cases += 1;
    }
    // === getCardEmphasisProfile only flips to rendered content for Exec / ML ===
    {
        const cardTypes = ['insight', 'experiment', 'risk', 'artifact', 'other'];
        for (const cardType of cardTypes) {
            const dsProfile = (0, cardPresentation_1.getCardEmphasisProfile)(cardType, 'ds');
            strict_1.default.equal(dsProfile.summarySource, 'original');
            strict_1.default.equal(dsProfile.bodySource, 'original');
            strict_1.default.equal(dsProfile.sectionDensity, 'none');
            cases += 3;
            const execProfile = (0, cardPresentation_1.getCardEmphasisProfile)(cardType, 'exec');
            strict_1.default.equal(execProfile.summarySource, 'rendered');
            strict_1.default.equal(execProfile.bodySource, 'rendered');
            strict_1.default.equal(execProfile.sectionDensity, 'compact');
            cases += 3;
        }
        const mlInsight = (0, cardPresentation_1.getCardEmphasisProfile)('insight', 'ml');
        strict_1.default.equal(mlInsight.sectionDensity, 'full');
        cases += 1;
        const mlArtifact = (0, cardPresentation_1.getCardEmphasisProfile)('artifact', 'ml');
        strict_1.default.equal(mlArtifact.sectionDensity, 'compact');
        cases += 1;
    }
    console.log(`[contract] PASS card-emphasis-adopter (${cases} cases)`);
}
run();
