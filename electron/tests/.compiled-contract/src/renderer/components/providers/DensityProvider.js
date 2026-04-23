"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.DensityProvider = DensityProvider;
const jsx_runtime_1 = require("react/jsx-runtime");
const react_1 = require("react");
const applyDensityScale_1 = require("../../application/layout/applyDensityScale");
const configStore_1 = require("../../stores/configStore");
function applyToDocument(mode) {
    if (typeof document === 'undefined') {
        return;
    }
    document.documentElement.setAttribute('data-density', mode);
    const overrides = (0, applyDensityScale_1.applyDensityScale)(mode);
    for (const [variable, value] of Object.entries(overrides)) {
        document.documentElement.style.setProperty(variable, value);
    }
}
function DensityProvider({ children }) {
    const density = (0, configStore_1.useConfigStore)((state) => state.density);
    (0, react_1.useEffect)(() => {
        applyToDocument(density);
    }, [density]);
    return (0, jsx_runtime_1.jsx)(jsx_runtime_1.Fragment, { children: children });
}
