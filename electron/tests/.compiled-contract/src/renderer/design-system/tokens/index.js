"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.DESIGN_SYSTEM_BASE_TOKENS = void 0;
const motion_1 = require("./motion");
const radius_1 = require("./radius");
const shadow_1 = require("./shadow");
const spacing_1 = require("./spacing");
const typography_1 = require("./typography");
exports.DESIGN_SYSTEM_BASE_TOKENS = {
    ...spacing_1.SPACING_TOKENS,
    ...typography_1.TYPOGRAPHY_TOKENS,
    ...radius_1.RADIUS_TOKENS,
    ...shadow_1.SHADOW_TOKENS,
    ...motion_1.MOTION_TOKENS,
};
