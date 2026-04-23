"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.MOBILE_TABS = void 0;
exports.MobileRouter = MobileRouter;
const jsx_runtime_1 = require("react/jsx-runtime");
const react_1 = require("react");
const MobileShell_1 = require("./components/MobileShell");
const MissionPage_1 = require("./pages/MissionPage");
const RunsPage_1 = require("./pages/RunsPage");
const ArtifactsPage_1 = require("./pages/ArtifactsPage");
const ApprovalsPage_1 = require("./pages/ApprovalsPage");
const SettingsPage_1 = require("./pages/SettingsPage");
exports.MOBILE_TABS = [
    'mission',
    'runs',
    'artifacts',
    'approvals',
    'settings',
];
function renderPage(tab) {
    switch (tab) {
        case 'mission':
            return (0, jsx_runtime_1.jsx)(MissionPage_1.MissionPage, {});
        case 'runs':
            return (0, jsx_runtime_1.jsx)(RunsPage_1.RunsPage, {});
        case 'artifacts':
            return (0, jsx_runtime_1.jsx)(ArtifactsPage_1.ArtifactsPage, {});
        case 'approvals':
            return (0, jsx_runtime_1.jsx)(ApprovalsPage_1.ApprovalsPage, {});
        case 'settings':
            return (0, jsx_runtime_1.jsx)(SettingsPage_1.SettingsPage, {});
    }
}
function MobileRouter() {
    const [activeTab, setActiveTab] = (0, react_1.useState)('mission');
    return ((0, jsx_runtime_1.jsx)(MobileShell_1.MobileShell, { activeTab: activeTab, onTabChange: setActiveTab, children: renderPage(activeTab) }));
}
