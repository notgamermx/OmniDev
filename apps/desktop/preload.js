/**
 * OmniDev Desktop - Preload Script
 * Provides secure IPC bridge between renderer and main process
 */

const { contextBridge, ipcRenderer } = require('electron');

// Exposed API methods
const api = {
    // HTTP API requests
    request: (path, method = 'GET', body = null) =>
        ipcRenderer.invoke('api-request', { path, method, body }),

    // File operations
    read: (path) =>
        ipcRenderer.invoke('file-read', path),

    write: (path, content) =>
        ipcRenderer.invoke('file-write', path, content),

    list: (path = '.') =>
        ipcRenderer.invoke('file-list', path),

    // Terminal operations
    terminal: {
        create: (sessionId) =>
            ipcRenderer.invoke('terminal-create', sessionId),
        input: (sessionId, input) =>
            ipcRenderer.invoke('terminal-input', sessionId, input),
        destroy: (sessionId) =>
            ipcRenderer.invoke('terminal-destroy', sessionId)
    },

    // Dialog operations
    dialog: {
        showOpenDialog: (options) =>
            ipcRenderer.invoke('dialog-showOpenDialog', options),
        showSaveDialog: (options) =>
            ipcRenderer.invoke('dialog-showSaveDialog', options)
    },

    // App info
    getVersion: () =>
        ipcRenderer.invoke('app-getVersion'),
    getPath: (name) =>
        ipcRenderer.invoke('app-getPath', name),

    // Event listeners
    on: {
        terminalOutput: (callback) =>
            ipcRenderer.on('terminal-output', (_, ...args) => callback(...args)),
        terminalExit: (callback) =>
            ipcRenderer.on('terminal-exit', (_, ...args) => callback(...args)),
        removeAllListeners: () =>
            ipcRenderer.removeAllListeners()
    }
};

// Expose to renderer process
contextBridge.exposeInMainWorld('electronAPI', api);