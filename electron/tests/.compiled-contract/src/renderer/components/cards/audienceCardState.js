"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.getNextUserExpandedOverride = getNextUserExpandedOverride;
exports.hasRenderedCardBodyContent = hasRenderedCardBodyContent;
function getNextUserExpandedOverride(currentUserExpanded, displayMode) {
    if (currentUserExpanded === undefined) {
        return displayMode !== 'expanded';
    }
    return !currentUserExpanded;
}
function hasRenderedCardBodyContent(renderedCard) {
    if (!renderedCard) {
        return false;
    }
    if (typeof renderedCard.body === 'string' && renderedCard.body.trim().length > 0) {
        return true;
    }
    return renderedCard.sections.length > 0;
}
