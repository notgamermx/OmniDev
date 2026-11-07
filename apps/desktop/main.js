/**
 * OmniDev Desktop - Electron Main Process
 * Main entry point for the desktop application
 */

const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs');

// Configuration
const API_HOST = process.env.API_HOST || 'localhost';
const API_PORT = process.env.API_PORT || 8000;
const API_URL = `http://${API_HOST}:${API_PORT}`;

// Window management
let mainWindow;
let terminalWindows = new Map();
const terminalProcesses = new Map();

function createWindow() {
    mainWindow = new BrowserWindow({
        width: 1400,
        height: 900,
        webPreferences: {
            preload: path.join(__dirname, 'preload.js'),
            contextIsolation: true,
            nodeIntegration: false
        },
        title: 'OmniDev - AI Development Environment'
    });

    // Load the React app
    const indexPath = path.join(__dirname, 'renderer', 'index.html');
    if (fs.existsSync(indexPath)) {
        mainWindow.loadFile(indexPath);
    } else {
        // Fallback to local dev server
        mainWindow.loadURL('http://localhost:3000');
    }

    // Open dev tools in development
    if (!app.isPackaged) {
        mainWindow.webContents.openDevTools();
    }

    mainWindow.on('closed', () => {
        mainWindow = null;
    });
}

// App lifecycle
app.whenReady().then(() => {
    createWindow();

    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) {
            createWindow();
        }
    });
});

app.on('window-all-closed', () => {
    // Quit when all windows are closed, except on macOS
    if (process.platform !== 'darwin') {
        app.quit();
    }
});

// ==========================================
// IPC Handlers for API Proxy
// ==========================================

ipcMain.handle('api-request', async (event, options) => {
    try {
        const response = await fetch(`${API_URL}${options.path}`, {
            method: options.method || 'GET',
            headers: { 'Content-Type': 'application/json' },
            body: options.body ? JSON.stringify(options.body) : undefined
        });
        return await response.json();
    } catch (error) {
        return { error: error.message };
    }
});

// ==========================================
// IPC Handlers for File Operations
// ==========================================

ipcMain.handle('file-read', async (event, filePath) => {
    try {
        const absolutePath = path.resolve(process.cwd(), filePath);
        const content = fs.readFileSync(absolutePath, 'utf8');
        return { content, path: absolutePath };
    } catch (error) {
        return { error: error.message };
    }
});

ipcMain.handle('file-write', async (event, filePath, content) => {
    try {
        const absolutePath = path.resolve(process.cwd(), filePath);
        const dir = path.dirname(absolutePath);

        // Create directory if it doesn't exist
        if (!fs.existsSync(dir)) {
            fs.mkdirSync(dir, { recursive: true });
        }

        fs.writeFileSync(absolutePath, content, 'utf8');
        return { success: true, path: absolutePath };
    } catch (error) {
        return { error: error.message };
    }
});

ipcMain.handle('file-list', async (event, dirPath = '.') => {
    try {
        const absolutePath = path.resolve(process.cwd(), dirPath);
        const items = fs.readdirSync(absolutePath, { withFileTypes: true });

        return {
            items: items.map(item => ({
                name: item.name,
                isDirectory: item.isDirectory(),
                path: path.join(absolutePath, item.name)
            })),
            path: absolutePath
        };
    } catch (error) {
        return { error: error.message };
    }
});

// ==========================================
// IPC Handlers for Terminal
// ==========================================

ipcMain.handle('terminal-create', async (event, sessionId) => {
    try {
        const term = spawn('cmd.exe' || 'bash', [], {
            cwd: process.cwd(),
            env: process.env
        });

        terminalProcesses.set(sessionId, term);

        term.stdout.on('data', (data) => {
            mainWindow?.webContents?.send('terminal-output', sessionId, { type: 'stdout', data: data.toString() });
        });

        term.stderr.on('data', (data) => {
            mainWindow?.webContents?.send('terminal-output', sessionId, { type: 'stderr', data: data.toString() });
        });

        term.on('exit', (code) => {
            mainWindow?.webContents?.send('terminal-exit', sessionId, { code });
            terminalProcesses.delete(sessionId);
        });

        return { success: true, sessionId };
    } catch (error) {
        return { error: error.message };
    }
});

ipcMain.handle('terminal-input', async (event, sessionId, input) => {
    try {
        const term = terminalProcesses.get(sessionId);
        if (!term) {
            return { error: 'Terminal session not found' };
        }
        term.stdin.write(input);
        return { success: true };
    } catch (error) {
        return { error: error.message };
    }
});

ipcMain.handle('terminal-destroy', async (event, sessionId) => {
    try {
        const term = terminalProcesses.get(sessionId);
        if (term) {
            term.kill();
            terminalProcesses.delete(sessionId);
        }
        return { success: true };
    } catch (error) {
        return { error: error.message };
    }
});

// ==========================================
// IPC Handlers for File Dialog
// ==========================================

ipcMain.handle('dialog-showOpenDialog', async (event, options) => {
    const result = await dialog.showOpenDialog(mainWindow, options);
    return result;
});

ipcMain.handle('dialog-showSaveDialog', async (event, options) => {
    const result = await dialog.showSaveDialog(mainWindow, options);
    return result;
});

// ==========================================
// App Info
// ==========================================

ipcMain.handle('app-getVersion', async () => {
    return app.getVersion();
});

ipcMain.handle('app-getPath', async (event, name) => {
    return app.getPath(name);
});