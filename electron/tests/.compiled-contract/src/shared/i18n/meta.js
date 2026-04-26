"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.ALL_I18N_NAMESPACES = exports.MOBILE_I18N_NAMESPACES = exports.DESKTOP_I18N_NAMESPACES = exports.SHARED_I18N_LOCALES = void 0;
exports.SHARED_I18N_LOCALES = ['ko', 'en', 'ja'];
exports.DESKTOP_I18N_NAMESPACES = [
    'common',
    'area',
    'mission',
    'workspace',
    'execution',
    'llm',
    'sidebar',
    'onboarding',
    'settings',
    'approval',
    'trust',
    'run',
    'cards',
    'chat',
    'cmd',
    'share',
    'session',
];
exports.MOBILE_I18N_NAMESPACES = ['mobile'];
exports.ALL_I18N_NAMESPACES = [
    ...exports.DESKTOP_I18N_NAMESPACES,
    ...exports.MOBILE_I18N_NAMESPACES,
];
