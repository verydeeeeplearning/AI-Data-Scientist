"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.ADMIN_SECTION_DESCRIPTORS = exports.AREA_DESCRIPTORS = exports.DEFAULT_AREA_PATH = void 0;
exports.isAreaId = isAreaId;
exports.isAdminSectionId = isAdminSectionId;
exports.getAreaDescriptor = getAreaDescriptor;
exports.getAdminSectionDescriptor = getAdminSectionDescriptor;
exports.DEFAULT_AREA_PATH = '/mission';
exports.AREA_DESCRIPTORS = [
    {
        id: 'mission',
        labelKey: 'area.mission.label',
        descriptionKey: 'area.mission.description',
        defaultPath: '/mission',
        shortcut: 'mod+1',
    },
    {
        id: 'runs',
        labelKey: 'area.runs.label',
        descriptionKey: 'area.runs.description',
        defaultPath: '/runs',
        shortcut: 'mod+2',
    },
    {
        id: 'artifacts',
        labelKey: 'area.artifacts.label',
        descriptionKey: 'area.artifacts.description',
        defaultPath: '/artifacts/files',
        shortcut: 'mod+3',
    },
    {
        id: 'governance',
        labelKey: 'area.governance.label',
        descriptionKey: 'area.governance.description',
        defaultPath: '/governance/review',
        shortcut: 'mod+4',
    },
    {
        id: 'memory',
        labelKey: 'area.memory.label',
        descriptionKey: 'area.memory.description',
        defaultPath: '/memory/learning',
        shortcut: 'mod+5',
    },
    {
        id: 'admin',
        labelKey: 'area.admin.label',
        descriptionKey: 'area.admin.description',
        defaultPath: '/admin/models',
        shortcut: 'mod+,',
    },
];
exports.ADMIN_SECTION_DESCRIPTORS = [
    { id: 'models', labelKey: 'area.admin.models', defaultPath: '/admin/models' },
    { id: 'connectors', labelKey: 'area.admin.connectors', defaultPath: '/admin/connectors' },
    { id: 'policies', labelKey: 'area.admin.policies', defaultPath: '/admin/policies' },
    { id: 'settings', labelKey: 'area.admin.settings', defaultPath: '/admin/settings' },
];
function isAreaId(value) {
    return exports.AREA_DESCRIPTORS.some((descriptor) => descriptor.id === value);
}
function isAdminSectionId(value) {
    return exports.ADMIN_SECTION_DESCRIPTORS.some((descriptor) => descriptor.id === value);
}
function getAreaDescriptor(areaId) {
    return (exports.AREA_DESCRIPTORS.find((descriptor) => descriptor.id === areaId) ?? exports.AREA_DESCRIPTORS[0]);
}
function getAdminSectionDescriptor(sectionId) {
    return (exports.ADMIN_SECTION_DESCRIPTORS.find((descriptor) => descriptor.id === sectionId) ??
        exports.ADMIN_SECTION_DESCRIPTORS[0]);
}
