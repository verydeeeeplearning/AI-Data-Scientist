"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.cn = cn;
exports.joinIds = joinIds;
exports.isAriaInvalid = isAriaInvalid;
function cn(...values) {
    return values.filter(Boolean).join(' ');
}
function joinIds(...values) {
    const ids = values.filter((value) => Boolean(value));
    return ids.length > 0 ? ids.join(' ') : undefined;
}
function isAriaInvalid(value) {
    return value !== undefined && value !== false && value !== 'false';
}
