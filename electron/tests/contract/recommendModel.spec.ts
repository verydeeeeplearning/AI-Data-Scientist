import assert from 'node:assert/strict';

import { recommendModel } from '../../src/renderer/application/llm/recommendModel';
import type {
  CapabilityBadge,
  CapabilityGroup,
  ModelProfile,
} from '../../src/renderer/domain/llm/modelCapability';

function makeProfile(overrides: Partial<ModelProfile> = {}): ModelProfile {
  return {
    id: 'anthropic/claude-sonnet-4-6',
    provider: 'anthropic',
    displayName: 'Claude Sonnet 4.6',
    maxContext: 1_000_000,
    maxOutput: 64_000,
    authType: 'api_key',
    legacy: false,
    providerCategory: 'api_key',
    capabilityGroup: 'best_quality' as CapabilityGroup,
    badges: ['strong_reasoning', 'long_context'] as CapabilityBadge[],
    recommendedFor: ['deep_analysis'],
    ...overrides,
  };
}

function run(): void {
  // === korean preference picks strong_korean badge over equally scored model ===
  {
    const koreanModel = makeProfile({
      id: 'qwen/qwen3.5-plus',
      provider: 'qwen',
      displayName: 'Qwen 3.5 Plus',
      capabilityGroup: 'privacy_first',
      badges: ['strong_korean', 'long_context'],
    });
    const englishModel = makeProfile({
      id: 'openai/gpt-5.4',
      provider: 'openai',
      displayName: 'GPT-5.4',
      badges: ['strong_reasoning', 'multimodal'],
    });
    const result = recommendModel([koreanModel, englishModel], { locale: 'ko' });
    assert.ok(result, 'recommendation must exist');
    assert.equal(result!.model.id, 'qwen/qwen3.5-plus');
    assert.ok(result!.reasons.includes('korean'));
  }

  // === ready model wins over higher-quality unready model ===
  {
    const ready = makeProfile({ id: 'anthropic/claude-haiku-4-5', capabilityGroup: 'fast_start', badges: ['fast', 'cheap'] });
    const unready = makeProfile({ id: 'openai/gpt-5.4' });
    const result = recommendModel([ready, unready], {
      locale: 'en',
      readyModelIds: new Set(['anthropic/claude-haiku-4-5']),
    });
    assert.ok(result);
    assert.equal(result!.model.id, 'anthropic/claude-haiku-4-5');
    assert.ok(result!.reasons.includes('ready'));
  }

  // === best_quality preset boosts best_quality group ===
  {
    const opus = makeProfile({ id: 'anthropic/claude-opus-4-6', capabilityGroup: 'best_quality' });
    const haiku = makeProfile({
      id: 'anthropic/claude-haiku-4-5',
      capabilityGroup: 'fast_start',
      badges: ['fast', 'cheap'],
    });
    const result = recommendModel([opus, haiku], {
      locale: 'en',
      qualityPreset: 'best_quality',
    });
    assert.ok(result);
    assert.equal(result!.model.id, 'anthropic/claude-opus-4-6');
    assert.ok(result!.reasons.includes('quality'));
  }

  // === local preset surfaces offline_capable group strongly ===
  {
    const offline = makeProfile({
      id: 'ollama/llama3-8b',
      provider: 'ollama',
      authType: 'local',
      capabilityGroup: 'offline_capable',
      badges: ['offline'],
      recommendedFor: ['offline'],
    });
    const cloud = makeProfile({ id: 'openai/gpt-5.4' });
    const result = recommendModel([offline, cloud], {
      locale: 'en',
      qualityPreset: 'local',
    });
    assert.ok(result);
    assert.equal(result!.model.id, 'ollama/llama3-8b');
    assert.ok(result!.reasons.includes('offline'));
  }

  // === legacy models are penalized vs current ones ===
  {
    const legacy = makeProfile({
      id: 'anthropic/claude-opus-4',
      legacy: true,
      capabilityGroup: 'best_quality',
    });
    const current = makeProfile({
      id: 'anthropic/claude-opus-4-6',
      capabilityGroup: 'best_quality',
    });
    const result = recommendModel([legacy, current], { locale: 'en' });
    assert.ok(result);
    assert.equal(result!.model.id, 'anthropic/claude-opus-4-6');
  }

  // === reasons capped at 2 to keep UI compact ===
  {
    const koreanReady = makeProfile({
      id: 'qwen/qwen3.5-plus',
      provider: 'qwen',
      capabilityGroup: 'privacy_first',
      badges: ['strong_korean', 'long_context', 'strong_reasoning'],
    });
    const result = recommendModel([koreanReady], {
      locale: 'ko',
      qualityPreset: 'fast',
      readyModelIds: new Set(['qwen/qwen3.5-plus']),
    });
    assert.ok(result);
    assert.ok(result!.reasons.length <= 2, `expected <=2 reasons, got ${result!.reasons.length}`);
  }

  // === empty model list returns undefined ===
  {
    const result = recommendModel([], { locale: 'en' });
    assert.equal(result, undefined);
  }

  // === coding task type promotes strong_coding badge ===
  {
    const coder = makeProfile({
      id: 'codex/gpt-5.3-codex',
      provider: 'codex',
      authType: 'oauth',
      capabilityGroup: 'fast_start',
      badges: ['strong_coding', 'fast'],
    });
    const generalist = makeProfile({ id: 'openai/gpt-5.4', badges: ['strong_reasoning'] });
    const result = recommendModel([coder, generalist], {
      locale: 'en',
      taskType: 'coding',
    });
    assert.ok(result);
    assert.equal(result!.model.id, 'codex/gpt-5.3-codex');
    assert.ok(result!.reasons.includes('coding'));
  }

  console.log('recommendModel.spec.ts: all assertions passed');
}

run();
