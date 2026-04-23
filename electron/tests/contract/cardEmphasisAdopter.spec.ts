import assert from 'node:assert/strict';

import {
  AUDIENCE_VIEW_PROFILES,
  getAudienceViewProfile,
  type AudienceView,
} from '../../src/renderer/domain/workspace/audienceView';
import { resolveCardDisplayMode } from '../../src/renderer/application/workspace/cardEmphasisAdopter';
import { getNextUserExpandedOverride } from '../../src/renderer/components/cards/audienceCardState';
import { getCardEmphasisProfile } from '../../src/renderer/components/cards/cardPresentation';

function run(): void {
  let cases = 0;

  // === userExpanded wins regardless of audience ===
  {
    for (const view of ['ds', 'exec', 'ml'] as AudienceView[]) {
      assert.equal(
        resolveCardDisplayMode({ userExpanded: true }, view),
        'expanded',
        `userExpanded=true must win for audience ${view}`,
      );
      cases += 1;
    }
    for (const view of ['ds', 'exec', 'ml'] as AudienceView[]) {
      assert.equal(
        resolveCardDisplayMode({ userExpanded: false }, view),
        'collapsed',
        `userExpanded=false must win for audience ${view}`,
      );
      cases += 1;
    }
    // userExpanded beats workspace-level forceExpanded / forceCollapsed both ways.
    assert.equal(
      resolveCardDisplayMode({ userExpanded: false, forceExpanded: true }, 'ds'),
      'collapsed',
    );
    cases += 1;
    assert.equal(
      resolveCardDisplayMode({ userExpanded: true, forceCollapsed: true }, 'exec'),
      'expanded',
    );
    cases += 1;
  }

  // === forceExpanded wins over audience emphasis (when no userExpanded) ===
  {
    assert.equal(
      resolveCardDisplayMode({ forceExpanded: true }, 'exec'),
      'expanded',
      'forceExpanded must override Exec collapsed default',
    );
    cases += 1;
    assert.equal(
      resolveCardDisplayMode({ forceExpanded: true }, 'ds'),
      'expanded',
    );
    cases += 1;
  }

  // === forceCollapsed wins over audience emphasis (when no userExpanded) ===
  {
    assert.equal(
      resolveCardDisplayMode({ forceCollapsed: true }, 'ds'),
      'collapsed',
      'forceCollapsed must override DS expanded default',
    );
    cases += 1;
    assert.equal(
      resolveCardDisplayMode({ forceCollapsed: true }, 'ml'),
      'collapsed',
    );
    cases += 1;
    // forceExpanded beats forceCollapsed when both set (matches applyAudienceViewToCard).
    assert.equal(
      resolveCardDisplayMode({ forceExpanded: true, forceCollapsed: true }, 'exec'),
      'expanded',
    );
    cases += 1;
  }

  // === No overrides: each audience uses its profile emphasis ===
  {
    assert.equal(
      resolveCardDisplayMode({}, 'ds'),
      'expanded',
      'DS audience defaults to expanded',
    );
    cases += 1;
    assert.equal(
      resolveCardDisplayMode({}, 'exec'),
      'collapsed',
      'Exec audience defaults to collapsed',
    );
    cases += 1;
    assert.equal(
      resolveCardDisplayMode({}, 'ml'),
      'expanded',
      'ML audience defaults to expanded',
    );
    cases += 1;
  }

  // === useAudienceView profile lookup matches getAudienceViewProfile ===
  // The hook is a thin facade over getAudienceViewProfile + zustand selectors.
  // Contract tests cannot import React, so verify the underlying lookup the
  // hook delegates to returns the same instance as the lookup table.
  {
    for (const view of ['ds', 'exec', 'ml'] as AudienceView[]) {
      assert.equal(
        getAudienceViewProfile(view),
        AUDIENCE_VIEW_PROFILES[view],
        `getAudienceViewProfile(${view}) must return the AUDIENCE_VIEW_PROFILES entry`,
      );
      cases += 1;
    }
  }

  // === first-toggle override and reset semantics stay audience-driven ===
  {
    const execOverride = getNextUserExpandedOverride(undefined, 'collapsed');
    assert.equal(execOverride, true);
    assert.equal(resolveCardDisplayMode({ userExpanded: execOverride }, 'exec'), 'expanded');
    assert.equal(resolveCardDisplayMode({ userExpanded: undefined }, 'exec'), 'collapsed');
    cases += 3;

    const dsOverride = getNextUserExpandedOverride(undefined, 'expanded');
    assert.equal(dsOverride, false);
    assert.equal(resolveCardDisplayMode({ userExpanded: dsOverride }, 'ds'), 'collapsed');
    assert.equal(resolveCardDisplayMode({ userExpanded: undefined }, 'ds'), 'expanded');
    cases += 3;

    assert.equal(getNextUserExpandedOverride(execOverride, 'expanded'), false);
    cases += 1;
  }

  // === getCardEmphasisProfile only flips to rendered content for Exec / ML ===
  {
    const cardTypes = ['insight', 'experiment', 'risk', 'artifact', 'other'] as const;
    for (const cardType of cardTypes) {
      const dsProfile = getCardEmphasisProfile(cardType, 'ds');
      assert.equal(dsProfile.summarySource, 'original');
      assert.equal(dsProfile.bodySource, 'original');
      assert.equal(dsProfile.sectionDensity, 'none');
      cases += 3;

      const execProfile = getCardEmphasisProfile(cardType, 'exec');
      assert.equal(execProfile.summarySource, 'rendered');
      assert.equal(execProfile.bodySource, 'rendered');
      assert.equal(execProfile.sectionDensity, 'compact');
      cases += 3;
    }

    const mlInsight = getCardEmphasisProfile('insight', 'ml');
    assert.equal(mlInsight.sectionDensity, 'full');
    cases += 1;

    const mlArtifact = getCardEmphasisProfile('artifact', 'ml');
    assert.equal(mlArtifact.sectionDensity, 'compact');
    cases += 1;
  }

  console.log(`[contract] PASS card-emphasis-adopter (${cases} cases)`);
}

run();
