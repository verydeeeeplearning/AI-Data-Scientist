"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.DEFAULT_DENSITY_MODE = exports.DENSITY_MODES = void 0;
exports.isDensityMode = isDensityMode;
exports.getDensityScale = getDensityScale;
exports.DENSITY_MODES = ['compact', 'comfortable', 'spacious'];
exports.DEFAULT_DENSITY_MODE = 'comfortable';
const SCALE_TABLE = {
    compact: { spacing: 0.75, font: 0.9 },
    comfortable: { spacing: 1, font: 1 },
    spacious: { spacing: 1.25, font: 1.1 },
};
function isDensityMode(value) {
    return typeof value === 'string'
        && exports.DENSITY_MODES.includes(value);
}
function getDensityScale(mode) {
    return SCALE_TABLE[mode];
}
