"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.ThemeProvider = ThemeProvider;
const jsx_runtime_1 = require("react/jsx-runtime");
const react_1 = require("react");
const themes_1 = require("../../design-system/themes");
const configStore_1 = require("../../stores/configStore");
function ThemeProvider({ children }) {
    const theme = (0, configStore_1.useConfigStore)((state) => state.theme);
    (0, react_1.useEffect)(() => {
        (0, themes_1.applyThemeToDocument)(theme);
    }, [theme]);
    return (0, jsx_runtime_1.jsx)(jsx_runtime_1.Fragment, { children: children });
}
