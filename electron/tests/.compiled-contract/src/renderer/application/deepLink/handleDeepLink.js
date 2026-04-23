"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.__test__ = void 0;
exports.buildDeepLinkRoute = buildDeepLinkRoute;
exports.handleDeepLink = handleDeepLink;
const deepLink_1 = require("../../domain/deepLink/deepLink");
function buildDeepLinkRoute(link) {
    const base = `/workspace/${link.workspaceId}/${link.resourceType}/${link.resourceId}`;
    return link.action ? `${base}?action=${link.action}` : base;
}
async function handleDeepLink(rawUri, deps) {
    const result = deps.parseUri(rawUri);
    if (!result.ok) {
        deps.warnInvalid(result.error, rawUri);
        return;
    }
    const policy = deps.getReauthPolicy();
    if (policy === 'always' || (policy === 'once-per-session' && !deps.hasReauthedThisSession())) {
        const granted = await deps.requestReauth();
        if (!granted) {
            return;
        }
        if (policy === 'once-per-session') {
            deps.markSessionReauthed();
        }
    }
    deps.navigate(buildDeepLinkRoute(result.value));
}
exports.__test__ = { parseDeepLink: deepLink_1.parseDeepLink };
