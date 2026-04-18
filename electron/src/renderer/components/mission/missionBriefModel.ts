import type { DeliveryRenderResultView } from '../../types/taskContract';

export const DEFAULT_DELIVERY_TENANT = 'default';

export function normalizeDeliveryTenant(value: string | null | undefined): string {
  const normalized = typeof value === 'string' ? value.trim() : '';
  return normalized || DEFAULT_DELIVERY_TENANT;
}

export function resolveThemeId(
  globalContext: Record<string, string> | null | undefined,
): string {
  const raw = globalContext?.theme_id;
  return typeof raw === 'string' ? raw.trim() : '';
}

export function buildDeliveryGlobalContext(
  globalContext: Record<string, string> | null | undefined,
  themeId: string,
): Record<string, string> {
  const next = { ...(globalContext ?? {}) };
  const normalizedThemeId = themeId.trim();
  if (normalizedThemeId) {
    next.theme_id = normalizedThemeId;
    return next;
  }
  delete next.theme_id;
  return next;
}

export function resolveProviderBackedRenderOptions(
  providerBacked: boolean,
  model: string,
): {
  providerBacked: boolean;
  model?: string;
} {
  if (!providerBacked) {
    return { providerBacked: false };
  }
  const normalizedModel = model.trim();
  return normalizedModel
    ? { providerBacked: true, model: normalizedModel }
    : { providerBacked: true };
}

export function formatRenderResultNotice(result: DeliveryRenderResultView): string {
  let notice = `Rendered ${result.artifact_id} (${result.format}) to ${result.output_path}.`;
  if (!result.renderer_mode) {
    return notice;
  }
  notice += ` Renderer: ${result.renderer_mode}`;
  if (result.renderer_model) {
    notice += ` | Model: ${result.renderer_model}`;
  }
  return `${notice}.`;
}
