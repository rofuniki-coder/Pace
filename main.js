const { app, BrowserWindow, screen, ipcMain, Menu, Tray, dialog } = require('electron');
const path = require('path');

// Set UserData to local directory to avoid sandbox permission issues
app.setPath('userData', path.join(__dirname, 'UserData'));

const { spawn } = require('child_process');
const { autoUpdater } = require('electron-updater');

// Single Instance Lock
const gotTheLock = app.requestSingleInstanceLock();

// Protocol Handler Removed

if (!gotTheLock) {
    app.quit();
} else {
    app.on('second-instance', (event, commandLine, workingDirectory) => {
        // Someone tried to run a second instance, we should focus our window.
        if (mainWindow) {
            if (mainWindow.isMinimized()) mainWindow.restore();
            mainWindow.show();
            mainWindow.focus();
            
        }
    });

    // Continue with app initialization...
    app.whenReady().then(() => {
        startBackend();
        createWindows();
        setTimeout(() => {
            syncConfig();
            checkForUpdates();
        }, 2000);
    });
}

let mainWindow;
let overlayWindow;
let backendProcess;
let currentModelSize = 'tiny.en'; // Default to match server
let currentLanguage = 'auto';
let currentTargetLanguage = 'none';
let soundEnabled = true;
let formattingMode = 'standard';
let inputDeviceIndex = null;
let history = [];
let inputDevices = [];
let isPinned = true;
let tray = null; // Global tray
let updateReminderTimestamp = 0;

// Define getMenuTemplate BEFORE usage to avoid any hoisting edge cases
function getMenuTemplate() {
    // Dynamic History Items
    const historyItems = history.length > 0 ? history.map((item, index) => {
        const text = typeof item === 'string' ? item : item.text;
        return {
            label: (text.length > 30 ? text.substring(0, 30) + '...' : text),
            click: () => {
                const { clipboard } = require('electron');
                clipboard.writeText(text);
            }
        };
    }) : [{ label: '(No History)', enabled: false }];

    // Dynamic Device Items
    const deviceItems = inputDevices.length > 0 ? inputDevices.map(d => ({
        label: d.name,
        type: 'radio',
        checked: inputDeviceIndex === d.index,
        click: () => { inputDeviceIndex = d.index; setConfig({ input_device_index: d.index }); }
    })) : [{ label: 'Default Device', type: 'radio', checked: true }];

    return [
        {
            label: 'Paste Last Transcription',
            accelerator: 'Ctrl+Shift+P',
            click: () => triggerPaste()
        },
        {
            label: 'Recent History',
            submenu: historyItems
        },
        { type: 'separator' },
        {
            label: 'Open UI',
            click: () => {
                if (mainWindow) {
                    mainWindow.show();
                    mainWindow.focus();
                }
            }
        },
        { type: 'separator' },
        {
            label: 'Always on Top (Pin)',
            type: 'checkbox',
            checked: isPinned,
            click: () => {
                isPinned = !isPinned;
                if (overlayWindow) overlayWindow.setAlwaysOnTop(isPinned, "screen-saver");
            }
        },
        {
            label: 'Hide for 30 minutes',
            click: () => {
                if (overlayWindow) {
                    overlayWindow.hide();
                    setTimeout(() => {
                        if (overlayWindow) overlayWindow.show();
                    }, 30 * 60 * 1000);
                }
            }
        },
        { type: 'separator' },
        {
            label: 'Sound Effects',
            type: 'checkbox',
            checked: soundEnabled,
            click: () => { 
                soundEnabled = !soundEnabled; 
                setConfig({ sound_enabled: soundEnabled }); 
            }
        },
        {
            label: 'Formatting Mode',
            submenu: [
                {
                    label: 'Standard (Punctuation & Caps)',
                    type: 'radio',
                    checked: formattingMode === 'standard',
                    click: () => { formattingMode = 'standard'; setConfig({ formatting_mode: 'standard' }); }
                },
                {
                    label: 'Raw / Chat (lowercase, no dots)',
                    type: 'radio',
                    checked: formattingMode === 'raw',
                    click: () => { formattingMode = 'raw'; setConfig({ formatting_mode: 'raw' }); }
                }
            ]
        },
        {
            label: 'Microphone',
            submenu: deviceItems
        },
        { type: 'separator' },
        {
            label: 'Change Language',
            submenu: [
                { 
                    label: 'Auto Detect (Default)', 
                    type: 'radio', 
                    checked: currentLanguage === 'auto',
                    click: () => { currentLanguage = 'auto'; setConfig({ source_language: 'auto' }); }
                },
                { 
                    label: 'English', 
                    type: 'radio',
                    checked: currentLanguage === 'en',
                    click: () => { currentLanguage = 'en'; setConfig({ source_language: 'en' }); }
                },
                { 
                    label: 'Spanish', 
                    type: 'radio',
                    checked: currentLanguage === 'es',
                    click: () => { currentLanguage = 'es'; setConfig({ source_language: 'es' }); }
                },
                { 
                    label: 'French', 
                    type: 'radio',
                    checked: currentLanguage === 'fr',
                    click: () => { currentLanguage = 'fr'; setConfig({ source_language: 'fr' }); }
                },
                { 
                    label: 'Japanese', 
                    type: 'radio',
                    checked: currentLanguage === 'ja',
                    click: () => { currentLanguage = 'ja'; setConfig({ source_language: 'ja' }); }
                }
            ]
        },
        {
            label: 'Translate to...',
            submenu: [
                { 
                    label: 'None (Default)', 
                    type: 'radio', 
                    checked: currentTargetLanguage === 'none',
                    click: () => { currentTargetLanguage = 'none'; setConfig({ target_language: 'none' }); }
                },
                { 
                    label: 'English', 
                    type: 'radio',
                    checked: currentTargetLanguage === 'en',
                    click: () => { currentTargetLanguage = 'en'; setConfig({ target_language: 'en' }); }
                },
                { 
                    label: 'Spanish', 
                    type: 'radio',
                    checked: currentTargetLanguage === 'es',
                    click: () => { currentTargetLanguage = 'es'; setConfig({ target_language: 'es' }); }
                },
                { 
                    label: 'French', 
                    type: 'radio',
                    checked: currentTargetLanguage === 'fr',
                    click: () => { currentTargetLanguage = 'fr'; setConfig({ target_language: 'fr' }); }
                },
                { 
                    label: 'Japanese', 
                    type: 'radio',
                    checked: currentTargetLanguage === 'ja',
                    click: () => { currentTargetLanguage = 'ja'; setConfig({ target_language: 'ja' }); }
                },
                 { 
                    label: 'German', 
                    type: 'radio',
                    checked: currentTargetLanguage === 'de',
                    click: () => { currentTargetLanguage = 'de'; setConfig({ target_language: 'de' }); }
                }
            ]
        },
        {
            label: 'Model',
            submenu: [
                { 
                    label: 'Tiny (Fastest)', 
                    type: 'radio', 
                    checked: currentModelSize === 'tiny.en',
                    click: () => { currentModelSize = 'tiny.en'; setConfig({ model_size: 'tiny.en' }); }
                },
                { 
                    label: 'Medium (Balanced)', 
                    type: 'radio', 
                    checked: currentModelSize === 'medium',
                    click: () => { currentModelSize = 'medium'; setConfig({ model_size: 'medium' }); }
                },
                { 
                    label: 'Large-v3 (Download Req. - 3GB)', 
                    type: 'radio', 
                    checked: currentModelSize === 'large-v3',
                    click: () => { currentModelSize = 'large-v3'; setConfig({ model_size: 'large-v3' }); }
                }
            ]
        },
        { type: 'separator' },
        { role: 'quit' }
    ];
}

function getTrayMenu() {
    return [
        {
            label: 'Show Pace',
            click: () => {
                if (mainWindow) {
                    mainWindow.show();
                    mainWindow.focus();
                }
            }
        },
        { type: 'separator' },
        ...getMenuTemplate()
    ];
}

function getIconPath() {
    if (app.isPackaged) {
        return path.join(process.resourcesPath, 'icon.ico');
    }
    return path.join(__dirname, 'icon.ico');
}

function createWindows() {
    const { width, height } = screen.getPrimaryDisplay().workAreaSize;
    const iconPath = getIconPath();

    // 1. Main UI Window
    mainWindow = new BrowserWindow({
        width: 1000,
        height: 720,
        show: false,
        frame: false,
        transparent: true,
        backgroundColor: '#00000000',
        icon: iconPath, // Explicitly set icon for taskbar
        webPreferences: {
            nodeIntegration: true,
            contextIsolation: false
        }
    });
    mainWindow.loadFile('dashboard/dashboard.html');
    
    // Deep link check removed
    
    // 2. Floating Overlay Window
    overlayWindow = new BrowserWindow({
        width: 300,
        height: 100,
        x: (width / 2) - 150,
        y: height - 120,
        frame: false,
        transparent: true,
        backgroundColor: '#00000000',
        alwaysOnTop: true,
        skipTaskbar: true,
        resizable: false,
        hasShadow: false,
        icon: iconPath,
        webPreferences: {
            nodeIntegration: true,
            contextIsolation: false
        }
    });
    
    overlayWindow.setAlwaysOnTop(true, "screen-saver");
    overlayWindow.setIgnoreMouseEvents(true, { forward: true });
    
    ipcMain.on('set-ignore-mouse-events', (event, ignore, options) => {
        const win = BrowserWindow.fromWebContents(event.sender);
        win.setIgnoreMouseEvents(ignore, options);
    });

    // Window Controls
    ipcMain.on('minimize-window', () => mainWindow.minimize());
    ipcMain.on('maximize-window', () => {
        if (mainWindow.isMaximized()) mainWindow.unmaximize();
        else mainWindow.maximize();
    });
    ipcMain.on('close-window', () => mainWindow.hide()); // Hide instead of close to keep app running

    overlayWindow.loadURL(`file://${__dirname}/index.html?mode=overlay`);

    // 3. Tray Icon
    if (!tray) {
        try {
            tray = new Tray(iconPath);
            tray.setToolTip('Pace - AI Transcription');
            tray.setContextMenu(Menu.buildFromTemplate(getTrayMenu()));
            
            // Toggle window on tray click
            tray.on('click', () => {
                if (mainWindow) {
                    if (mainWindow.isVisible()) {
                        mainWindow.hide();
                    } else {
                        mainWindow.show();
                        mainWindow.focus();
                    }
                }
            });
        } catch (e) {
            console.log("Tray icon failed load:", e);
        }
    }
}

const axios = require('axios');

function triggerPaste() {
    const http = require('http');
    const req = http.request({
        hostname: '127.0.0.1',
        port: 5000,
        path: '/paste',
        method: 'POST'
    }, (res) => {});
    req.on('error', (e) => console.error(e));
    req.end();
}

ipcMain.on('show-context-menu', (event) => {
    const menu = Menu.buildFromTemplate(getMenuTemplate());
    menu.popup({ window: BrowserWindow.fromWebContents(event.sender) });
});

function setConfig(config) {
    const http = require('http');
    const data = JSON.stringify(config);
    
    const req = http.request({
        hostname: '127.0.0.1',
        port: 5000,
        path: '/config',
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Content-Length': data.length
        }
    }, (res) => {
        console.log(`Config updated: ${JSON.stringify(config)}`);
    });
    
    req.on('error', (error) => {
        console.error(error);
    });
    
    req.write(data);
    req.end();
}

function startBackend() {
    const userDataPath = app.getPath('userData');
    console.log("UserData Path:", userDataPath);

    let executable;
    let args = ['--data-dir', userDataPath];

    if (app.isPackaged) {
        // Production: Use bundled executable
        // We will configure electron-builder to put server folder in resources
        executable = path.join(process.resourcesPath, 'server', 'server.exe');
    } else {
        // Development: Use python from venv
        executable = path.join(__dirname, 'venv', 'Scripts', 'python.exe');
        args.unshift('server.py');
    }
    
    console.log(`Starting backend: ${executable} ${args.join(' ')}`);
    backendProcess = spawn(executable, args);
    
    backendProcess.stdout.on('data', (data) => {
        console.log(`Backend: ${data}`);
        const strData = data.toString();
        
        if (strData.includes("Model loaded")) {
            if (mainWindow) mainWindow.webContents.send('model-loaded');
            if (overlayWindow) overlayWindow.webContents.send('model-loaded');
        }
        
        // Sync config (and history) when transcription finishes
        if (strData.includes("Transcription finished")) {
            setTimeout(syncConfig, 500); // Small delay to ensure backend state is ready
        }
    });
    
    backendProcess.stderr.on('data', (data) => console.error(`Backend Error: ${data}`));
}

function syncConfig() {
    const http = require('http');
    
    http.get('http://127.0.0.1:5000/config', (res) => {
        let data = '';
        res.on('data', (chunk) => { data += chunk; });
        res.on('end', () => {
            try {
                const config = JSON.parse(data);
                console.log("Synced Config:", config);
                
                if (config.model_size) currentModelSize = config.model_size;
                if (config.source_language) currentLanguage = config.source_language;
                if (config.target_language) currentTargetLanguage = config.target_language;
                if (config.sound_enabled !== undefined) soundEnabled = config.sound_enabled;
                if (config.formatting_mode) formattingMode = config.formatting_mode;
                if (config.history) history = config.history;
                if (config.update_reminder_ts) updateReminderTimestamp = config.update_reminder_ts;
                
                // Update menu immediately
                if(tray) tray.setContextMenu(Menu.buildFromTemplate(getTrayMenu()));

                if (mainWindow) mainWindow.webContents.send('config-updated', config);

                fetchDevices();
                
            } catch (e) {
                console.error("Error parsing config:", e);
            }
        });
    }).on('error', (err) => {
        console.log("Waiting for backend...");
        setTimeout(syncConfig, 1000);
    });
}

function checkForUpdates() {
    if (!app.isPackaged) return; // Don't check in dev mode

    autoUpdater.autoDownload = false;
    autoUpdater.checkForUpdates();

    autoUpdater.on('update-available', (info) => {
        // Check if reminder is active (24h)
        const now = Date.now();
        if (now < updateReminderTimestamp) {
            console.log("Update available but reminded for tomorrow.");
            return;
        }

        dialog.showMessageBox({
            type: 'info',
            title: 'Update Available',
            message: `A new version (${info.version}) of Pace is available.`,
            buttons: ['Update Now', 'Remind Me Tomorrow', 'Cancel'],
            defaultId: 0
        }).then(result => {
            if (result.response === 0) {
                // Update Now
                autoUpdater.downloadUpdate();
            } else if (result.response === 1) {
                // Remind Me Tomorrow (24h)
                const tomorrow = Date.now() + (24 * 60 * 60 * 1000);
                setConfig({ update_reminder_ts: tomorrow });
            }
        });
    });

    autoUpdater.on('update-downloaded', () => {
        dialog.showMessageBox({
            type: 'info',
            title: 'Update Ready',
            message: 'Update downloaded. Restart now to install?',
            buttons: ['Restart', 'Later']
        }).then(result => {
            if (result.response === 0) {
                autoUpdater.quitAndInstall();
            }
        });
    });
    
    autoUpdater.on('error', (err) => {
        console.log("Update error:", err);
    });
}

function fetchDevices() {
    const http = require('http');
    http.get('http://127.0.0.1:5000/devices', (res) => {
        let data = '';
        res.on('data', (chunk) => { data += chunk; });
        res.on('end', () => {
            try {
                inputDevices = JSON.parse(data);
                if(tray) tray.setContextMenu(Menu.buildFromTemplate(getMenuTemplate()));
                if (mainWindow) mainWindow.webContents.send('update-devices', inputDevices);
            } catch (e) {
                console.error("Error parsing devices:", e);
            }
        });
    }).on('error', (err) => console.error("Device fetch error:", err));
}

// app.whenReady is now handled inside the lock check block above
// app.whenReady().then(() => {
//     startBackend();
//     createWindows();
//     setTimeout(syncConfig, 2000);
// });

app.on('will-quit', () => {
    if (backendProcess) backendProcess.kill();
});

// handleDeepLink removed
