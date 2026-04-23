import assert from 'node:assert/strict';

import {
  buildModelProfile,
  buildModelProfiles,
} from '../../src/renderer/application/llm/buildModelProfiles';
import type {
  ModelCatalogEntry,
} from '../../src/renderer/domain/llm/modelCapability';

function baseEntry(overrides: Partial<ModelCatalogEntry> = {}): ModelCatalogEntry {
  return {
    id: 'anthropic/claude-sonnet-4-6',
    provider: 'anthropic',
    displayName: 'Claude Sonnet 4.6',
    maxContext: 1_000_000,
    maxOutput: 64_000,
    authType: 'api_key',
    legacy: false,
    ...overrides,
  };
}

function run(): void {
  // === backend metadata overrides heuristic when present ===
  {
    const entry = baseEntry({
      capabilityGroup: 'cost_optimized',
      capabilityBadges: ['cheap', 'fast'],
      recommendedFor: ['budget_sensitive'],
      providerLabelLegacy: 'Previously: Anthropic Claude Sonnet 4.6 (anthropic/claude-sonnet-4-6)',
    });
    const profile = buildModelProfile(entry);
    assert.equal(profile.capabilityGroup, 'cost_optimized');
    assert.deepEqual(profile.badges, ['cheap', 'fast']);
    assert.deepEqual(profile.recommendedFor, ['budget_sensitive']);
    assert.equal(
      profile.providerLabelLegacy,
      'Previously: Anthropic Claude Sonnet 4.6 (anthropic/claude-sonnet-4-6)',
    );
  }

  // === heuristic fallback when backend metadata absent ===
  {
    const entry = baseEntry();
    const profile = buildModelProfile(entry);
    assert.ok(profile.capabilityGroup, 'capabilityGroup must be set by heuristic');
    assert.ok(profile.badges.length >= 1, 'badges must be inferred when missing');
    assert.ok(profile.recommendedFor.length >= 1, 'recommendedFor must be inferred when missing');
  }

  // === heuristic anthropic opus -> best_quality ===
  {
    const entry = baseEntry({
      id: 'anthropic/claude-opus-4-6',
      displayName: 'Claude Opus 4.6',
    });
    const profile = buildModelProfile(entry);
    assert.equal(profile.capabilityGroup, 'best_quality');
  }

  // === heuristic local provider -> offline_capable ===
  {
    const entry = baseEntry({
      id: 'ollama/llama3-8b',
      provider: 'ollama',
      displayName: 'Llama 3 8B',
      maxContext: 8_000,
      maxOutput: 4_000,
      authType: 'local',
    });
    const profile = buildModelProfile(entry);
    assert.equal(profile.capabilityGroup, 'offline_capable');
    assert.ok(profile.badges.includes('offline'));
  }

  // === backend metadata partially present -> still uses backend group, heuristic badges only if missing ===
  {
    const entry = baseEntry({
      id: 'anthropic/claude-haiku-4-5',
      displayName: 'Claude Haiku 4.5',
      capabilityGroup: 'fast_start',
      // intentionally omit capabilityBadges + recommendedFor + providerLabelLegacy
    });
    const profile = buildModelProfile(entry);
    assert.equal(profile.capabilityGroup, 'fast_start');
    assert.ok(profile.badges.length >= 1, 'heuristic must fill missing badges');
  }

  // === buildModelProfiles preserves backend metadata for entire batch ===
  {
    const entries: ModelCatalogEntry[] = [
      baseEntry({
        id: 'anthropic/claude-opus-4-6',
        displayName: 'Claude Opus 4.6',
        capabilityGroup: 'best_quality',
        capabilityBadges: ['strong_reasoning', 'multimodal'],
        recommendedFor: ['deep_analysis'],
      }),
      baseEntry({
        id: 'codex/gpt-5.4',
        provider: 'codex',
        displayName: 'GPT-5.4 (Codex)',
        authType: 'oauth',
        capabilityGroup: 'fast_start',
        capabilityBadges: ['fast', 'strong_reasoning'],
        recommendedFor: ['first_run'],
      }),
    ];
    const profiles = buildModelProfiles(entries);
    assert.equal(profiles.length, 2);
    const opus = profiles.find((p) => p.id === 'anthropic/claude-opus-4-6');
    const codex = profiles.find((p) => p.id === 'codex/gpt-5.4');
    assert.ok(opus);
    assert.ok(codex);
    assert.equal(opus!.capabilityGroup, 'best_quality');
    assert.equal(codex!.capabilityGroup, 'fast_start');
  }

  // === providerLabelLegacy survives untouched when supplied by backend ===
  {
    const entry = baseEntry({
      providerLabelLegacy: 'Previously: Anthropic Claude Sonnet 4.6 (anthropic/claude-sonnet-4-6)',
    });
    const profile = buildModelProfile(entry);
    assert.equal(
      profile.providerLabelLegacy,
      'Previously: Anthropic Claude Sonnet 4.6 (anthropic/claude-sonnet-4-6)',
    );
  }

  // === invalid backend group falls back to heuristic ===
  {
    const entry = baseEntry({
      id: 'anthropic/claude-opus-4-6',
      displayName: 'Claude Opus 4.6',
      capabilityGroup: 'not_a_real_group' as never,
    });
    const profile = buildModelProfile(entry);
    assert.equal(profile.capabilityGroup, 'best_quality');
  }

  console.log('buildModelProfiles.spec.ts: all assertions passed');
}

run();
