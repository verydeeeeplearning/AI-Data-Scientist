"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.DEFAULT_DELIVERY_TENANT = void 0;
exports.normalizeDeliveryTenant = normalizeDeliveryTenant;
exports.resolveThemeId = resolveThemeId;
exports.buildDeliveryGlobalContext = buildDeliveryGlobalContext;
exports.resolveProviderBackedRenderOptions = resolveProviderBackedRenderOptions;
exports.formatRenderResultNotice = formatRenderResultNotice;
exports.DEFAULT_DELIVERY_TENANT = 'default';
function normalizeDeliveryTenant(value) {
    const normalized = typeof value === 'string' ? value.trim() : '';
    return normalized || exports.DEFAULT_DELIVERY_TENANT;
}
function resolveThemeId(globalContext) {
    const raw = globalContext?.theme_id;
    return typeof raw === 'string' ? raw.trim() : '';
}
function buildDeliveryGlobalContext(globalContext, themeId) {
    const next = { ...(globalContext ?? {}) };
    const normalizedThemeId = themeId.trim();
    if (normalizedThemeId) {
        next.theme_id = normalizedThemeId;
        return next;
    }
    delete next.theme_id;
    return next;
}
function resolveProviderBackedRenderOptions(providerBacked, model) {
    if (!providerBacked) {
        return { providerBacked: false };
    }
    const normalizedModel = model.trim();
    return normalizedModel
        ? { providerBacked: true, model: normalizedModel }
        : { providerBacked: true };
}
function formatRenderResultNotice(result) {
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
