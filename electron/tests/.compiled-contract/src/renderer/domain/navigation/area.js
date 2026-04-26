"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.PRIMARY_AREAS_V3 = exports.ADMIN_SECTION_DESCRIPTORS = exports.AREA_DESCRIPTORS = exports.DEFAULT_AREA_PATH_V3 = exports.DEFAULT_AREA_PATH = void 0;
exports.isAreaId = isAreaId;
exports.isAdminSectionId = isAdminSectionId;
exports.getAreaDescriptor = getAreaDescriptor;
exports.getAdminSectionDescriptor = getAdminSectionDescriptor;
exports.isLegacyV3AreaId = isLegacyV3AreaId;
exports.DEFAULT_AREA_PATH = '/mission';
/** v3 default landing — Artifacts is where data scientists actually start. */
exports.DEFAULT_AREA_PATH_V3 = '/artifacts/files';
exports.AREA_DESCRIPTORS = [
    {
        id: 'mission',
        labelKey: 'area.mission.label',
        descriptionKey: 'area.mission.description',
        defaultPath: '/mission',
        shortcut: 'mod+1',
        ring: 'primary',
        legacyInV3: true,
    },
    {
        id: 'runs',
        labelKey: 'area.runs.label',
        descriptionKey: 'area.runs.description',
        defaultPath: '/runs',
        shortcut: 'mod+2',
        ring: 'primary',
    },
    {
        id: 'artifacts',
        labelKey: 'area.artifacts.label',
        descriptionKey: 'area.artifacts.description',
        defaultPath: '/artifacts/files',
        shortcut: 'mod+3',
        ring: 'primary',
    },
    {
        id: 'governance',
        labelKey: 'area.governance.label',
        descriptionKey: 'area.governance.description',
        defaultPath: '/governance/review',
        shortcut: 'mod+4',
        ring: 'primary',
    },
    {
        id: 'memory',
        labelKey: 'area.memory.label',
        descriptionKey: 'area.memory.description',
        defaultPath: '/memory/learning',
        shortcut: 'mod+5',
        ring: 'primary',
        legacyInV3: true,
    },
    {
        id: 'admin',
        labelKey: 'area.admin.label',
        descriptionKey: 'area.admin.description',
        defaultPath: '/admin/models',
        shortcut: 'mod+,',
        ring: 'admin',
    },
];
exports.ADMIN_SECTION_DESCRIPTORS = [
    { id: 'models', labelKey: 'area.admin.models', defaultPath: '/admin/models' },
    { id: 'connectors', labelKey: 'area.admin.connectors', defaultPath: '/admin/connectors' },
    { id: 'policies', labelKey: 'area.admin.policies', defaultPath: '/admin/policies' },
    { id: 'notifications', labelKey: 'area.admin.notifications', defaultPath: '/admin/notifications' },
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
/**
 * Areas shown in the v3 sidebar primary group, in display order.
 * Excludes `mission` and `memory` (replaced by MissionContextBar + FloatingChat
 * and folded into Admin respectively).
 */
exports.PRIMARY_AREAS_V3 = exports.AREA_DESCRIPTORS.filter((d) => d.ring === 'primary' && !d.legacyInV3);
/** Returns true when an area id exists but should be hidden/redirected in v3. */
function isLegacyV3AreaId(value) {
    return exports.AREA_DESCRIPTORS.find((d) => d.id === value)?.legacyInV3 === true;
}
