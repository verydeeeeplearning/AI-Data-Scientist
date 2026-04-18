"use strict";
/**
 * Preload script — secure IPC bridge between main and renderer.
 *
 * Exposes minimal API to the renderer via contextBridge.
 * The renderer communicates with Python backend directly via WebSocket,
 * so this preload only handles Electron-specific features.
 */
Object.defineProperty(exports, "__esModule", { value: true });
const electron_1 = require("electron");
electron_1.contextBridge.exposeInMainWorld('electronAPI', {
    // Platform info
    platform: process.platform,
    // Window controls (for custom title bar if needed)
    minimize: () => electron_1.ipcRenderer.send('window:minimize'),
    maximize: () => electron_1.ipcRenderer.send('window:maximize'),
    close: () => electron_1.ipcRenderer.send('window:close'),
    // File dialog
    openFileDialog: () => electron_1.ipcRenderer.invoke('dialog:openFile'),
});
//# sourceMappingURL=index.js.map