/**
 * Shared model/provider auth interpretation for Electron surfaces.
 */

import type { ModelEntry } from '../hooks/useModels';
import type { OAuthAccountStatus } from '../stores/authStore';

export const PROVIDER_LABELS: Record<string, string> = {
  anthropic: 'Anthropic',
  openai: 'OpenAI',
  groq: 'Groq',
  deepseek: 'DeepSeek',
  minimax: 'MiniMax',
  qwen: 'Qwen',
  zhipu: 'Zhipu',
  moonshot: 'Moonshot',
  codex: 'ChatGPT (Codex)',
  gemini: 'Google Gemini',
  ollama: 'Ollama',
};

const AUTH_TYPE_LABELS: Record<ModelEntry['authType'], string> = {
  oauth: 'OAuth',
  free_api_key: 'Free API Key',
  api_key: 'API Key',
  local: 'Local',
};

export interface ModelAccessSummary {
  provider: string;
  providerLabel: string;
  authType: ModelEntry['authType'];
  authTypeLabel: string;
  providerStatus: string;
  ready: boolean;
  shortLabel: string;
  detail: string;
  tone: 'success' | 'warning' | 'muted';
}

export function inferProviderFromModel(modelId: string): string {
  const prefix = modelId.split('/')[0];
  return prefix || modelId;
}

export function inferAuthTypeFromProvider(provider: string): ModelEntry['authType'] {
  if (provider === 'codex' || provider === 'gemini') {
    return 'oauth';
  }
  if (provider === 'ollama') {
    return 'local';
  }
  if (provider === 'groq') {
    return 'free_api_key';
  }
  return 'api_key';
}

function defaultProviderLabel(provider: string): string {
  if (provider in PROVIDER_LABELS) {
    return PROVIDER_LABELS[provider];
  }
  return provider.charAt(0).toUpperCase() + provider.slice(1);
}

export function describeModelAccess({
  modelId,
  modelEntry,
  providerStatuses,
  oauthStatuses,
}: {
  modelId: string;
  modelEntry?: ModelEntry | null;
  providerStatuses?: Record<string, string>;
  oauthStatuses?: Record<string, OAuthAccountStatus>;
}): ModelAccessSummary {
  const provider = modelEntry?.provider ?? inferProviderFromModel(modelId);
  const authType = modelEntry?.authType ?? inferAuthTypeFromProvider(provider);
  const providerStatus = providerStatuses?.[provider] ?? (authType === 'local' ? 'local' : 'unknown');
  const oauth = oauthStatuses?.[provider];
  const providerLabel = defaultProviderLabel(provider);
  const authTypeLabel = AUTH_TYPE_LABELS[authType];

  if (authType === 'local') {
    return {
      provider,
      providerLabel,
      authType,
      authTypeLabel,
      providerStatus,
      ready: true,
      shortLabel: 'Local',
      detail: 'Uses a local runtime. No external authentication is required.',
      tone: 'success',
    };
  }

  if (authType === 'oauth') {
    if (providerStatus === 'unknown') {
      return {
        provider,
        providerLabel,
        authType,
        authTypeLabel,
        providerStatus,
        ready: false,
        shortLabel: 'Checking auth',
        detail: `Checking ${providerLabel} authentication state.`,
        tone: 'muted',
      };
    }

    if (oauth?.authenticated) {
      return {
        provider,
        providerLabel,
        authType,
        authTypeLabel,
        providerStatus,
        ready: true,
        shortLabel: 'Connected',
        detail: oauth.email
          ? `${providerLabel} account connected as ${oauth.email}.`
          : `${providerLabel} account is connected.`,
        tone: 'success',
      };
    }

    if (provider === 'gemini' && providerStatus === 'active') {
      return {
        provider,
        providerLabel,
        authType,
        authTypeLabel,
        providerStatus,
        ready: true,
        shortLabel: 'Ready via key',
        detail: 'Gemini is currently usable through a configured API key.',
        tone: 'success',
      };
    }

    return {
      provider,
      providerLabel,
      authType,
      authTypeLabel,
      providerStatus,
      ready: false,
      shortLabel: 'Login required',
      detail: `Sign in with ${providerLabel} before using this model.`,
      tone: 'warning',
    };
  }

  if (providerStatus === 'unknown') {
    return {
      provider,
      providerLabel,
      authType,
      authTypeLabel,
      providerStatus,
      ready: false,
      shortLabel: 'Checking auth',
      detail: `Checking whether ${providerLabel} credentials are configured.`,
      tone: 'muted',
    };
  }

  if (providerStatus === 'active') {
    return {
      provider,
      providerLabel,
      authType,
      authTypeLabel,
      providerStatus,
      ready: true,
      shortLabel: 'Ready',
      detail: `${providerLabel} credentials are configured for this model.`,
      tone: 'success',
    };
  }

  const needsFreeKey = authType === 'free_api_key';
  return {
    provider,
    providerLabel,
    authType,
    authTypeLabel,
    providerStatus,
    ready: false,
    shortLabel: 'Key required',
    detail: needsFreeKey
      ? `Add a ${providerLabel} API key to enable this free-tier provider.`
      : `Add a ${providerLabel} API key before using this model.`,
    tone: 'warning',
  };
}
