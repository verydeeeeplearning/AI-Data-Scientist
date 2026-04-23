"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.setDensity = setDensity;
function setDensity(port, mode) {
    port.persist(mode);
    port.applyToDocument(mode);
    return mode;
}
