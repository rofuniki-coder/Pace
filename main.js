
const { app, BrowserWindow, ipcMain, screen, Menu, clipboard, shell, dialog, Tray } = require('electron');
const path = require('path');
const { spawn, execSync } = require('child_process');

let mainWindow;
let pythonProcess;
let tray = null;
let transcriptions = [];
let lastTranscriptionId = null;
let hideTimeout = null;
let currentModel = "tiny.en";

const VERSION = "1.0.0";
const GITHUB_REPO = "https://github.com/rofuniki-coder/Pace";
const WEBSITE_URL = "https://pacespeech.vercel.app/";

// --- Single Instance Lock ---
const gotTheLock = app.requestSingleInstanceLock();
if (!gotTheLock) {
  app.quit();
} else {
  app.on('second-instance', (event, commandLine, workingDirectory) => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    }
  });

  app.whenReady().then(createWindow);
}

function createWindow() {
  // Kill any previous python processes running engine.py before starting
  // Use windowsHide to prevent terminal flicker
  try {
    if (process.platform === 'win32') {
      const { spawnSync } = require('child_process');
      spawnSync('taskkill', ['/F', '/IM', 'python.exe', '/FI', 'WINDOWTITLE eq PaceEngine*', '/T'], { windowsHide: true });
      spawnSync('wmic', ['process', 'where', "commandline like '%engine.py%'", 'delete'], { windowsHide: true });
    }
  } catch (e) {}

  const { width, height } = screen.getPrimaryDisplay().workAreaSize;
  
  mainWindow = new BrowserWindow({
    width: 120,
    height: 36,
    x: Math.floor((width - 120) / 2),
    y: height - 50,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    resizable: false,
    skipTaskbar: true,
    icon: path.join(__dirname, 'image.png'),
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
    },
  });

  mainWindow.loadFile('index.html');
  mainWindow.setIgnoreMouseEvents(true, { forward: true });

  // Context Menu
  ipcMain.on('show-context-menu', (event) => {
    const historySubmenu = transcriptions.length > 0 
      ? transcriptions.map((text) => ({
          label: text.length > 40 ? text.substring(0, 37) + '...' : text,
          click: () => clipboard.writeText(text)
        }))
      : [{ label: 'No history yet', enabled: false }];

    const menu = Menu.buildFromTemplate([
      { label: 'Last 10 Transcriptions', submenu: historySubmenu },
      { type: 'separator' },
      {
        label: 'Whisper Model',
        submenu: [
          {
            label: 'Tiny (Fastest)',
            type: 'radio',
            checked: currentModel === 'tiny.en',
            click: () => switchModel('tiny.en')
          },
          {
            label: 'Medium (Accurate)',
            type: 'radio',
            checked: currentModel === 'medium.en',
            click: () => switchModel('medium.en')
          }
        ]
      },
      { type: 'separator' },
      { 
        label: 'Hide for 1 Hour', 
        click: () => {
          if (mainWindow) {
            mainWindow.hide();
            if (hideTimeout) clearTimeout(hideTimeout);
            hideTimeout = setTimeout(() => {
              if (mainWindow) mainWindow.show();
            }, 3600000); // 1 hour
          }
        }
      },
      {
        label: 'Check for Updates',
        click: () => {
          shell.openExternal(WEBSITE_URL);
          dialog.showMessageBox(mainWindow, {
            type: 'info',
            title: 'Update Check',
            message: `Current Version: v${VERSION}\nChecking for updates on the official website...`,
            buttons: ['OK']
          });
        }
      },
      { type: 'separator' },
      { label: 'Quit Pace', click: () => app.quit() }
    ]);
    menu.popup(BrowserWindow.fromWebContents(event.sender));
  });

  ipcMain.on('toggle-recording', () => {
    if (pythonProcess) pythonProcess.stdin.write('toggle\n');
  });

  function switchModel(size) {
    currentModel = size;
    if (pythonProcess) {
      pythonProcess.stdin.write(`model:${size}\n`);
    }
  }

  ipcMain.on('set-ignore-mouse-events', (event, ignore, options) => {
    if (mainWindow) mainWindow.setIgnoreMouseEvents(ignore, options);
  });

  createTray();
  startPythonEngine();
}

function createTray() {
  const iconPath = path.join(__dirname, 'image.png');
  tray = new Tray(iconPath);
  
  const contextMenu = Menu.buildFromTemplate([
    { label: 'Pace v' + VERSION, enabled: false },
    { type: 'separator' },
    {
      label: 'Whisper Model',
      submenu: [
        {
          label: 'Tiny (Fastest)',
          type: 'radio',
          checked: currentModel === 'tiny.en',
          click: () => switchModel('tiny.en')
        },
        {
          label: 'Medium (Accurate)',
          type: 'radio',
          checked: currentModel === 'medium.en',
          click: () => switchModel('medium.en')
        }
      ]
    },
    { type: 'separator' },
    { label: 'Show App', click: () => { if (mainWindow) mainWindow.show(); } },
    { label: 'Hide for 1 Hour', click: () => {
        if (mainWindow) {
          mainWindow.hide();
          if (hideTimeout) clearTimeout(hideTimeout);
          hideTimeout = setTimeout(() => {
            if (mainWindow) mainWindow.show();
          }, 3600000);
        }
    }},
    { type: 'separator' },
    { label: 'Check for Updates', click: () => shell.openExternal(`${GITHUB_REPO}/releases/latest`) },
    { label: 'Quit Pace', click: () => app.quit() }
  ]);

  tray.setToolTip('Pace - High Performance STT');
  tray.setContextMenu(contextMenu);

  tray.on('click', () => {
    if (mainWindow) {
      if (mainWindow.isVisible()) {
        mainWindow.hide();
      } else {
        mainWindow.show();
      }
    }
  });
}

function startPythonEngine() {
  if (pythonProcess) return;

  console.log('Spawning PaceEngine process...');
  
  // In packaged apps, we need to point to the unpacked version of engine.py
  // electron-builder moves asarUnpack files to 'app.asar.unpacked'
  let enginePath = path.join(__dirname, 'engine.py');
  if (app.isPackaged) {
    enginePath = enginePath.replace('app.asar', 'app.asar.unpacked');
  }

  console.log('Engine path:', enginePath);

  // Use windowsHide: true to prevent terminal window from popping up
  pythonProcess = spawn('python', [enginePath], {
    stdio: ['pipe', 'pipe', 'pipe'],
    windowsHide: true,
    env: { ...process.env, PYTHONIOENCODING: 'utf-8' }
  });

  pythonProcess.stderr.on('data', (data) => {
    console.error(`Python Engine Error: ${data}`);
  });

  pythonProcess.stdout.on('data', (data) => {
    data.toString().split('\n').forEach(line => {
      if (!line.trim()) return;
      try {
        const json = JSON.parse(line);
        
        // Prevent duplicates
        if (json.type === 'transcription') {
          if (json.id && json.id === lastTranscriptionId) return;
          lastTranscriptionId = json.id;
          transcriptions.unshift(json.text);
          if (transcriptions.length > 10) transcriptions.pop();
        }

        if (mainWindow) mainWindow.webContents.send('engine-msg', json);
      } catch (e) {}
    });
  });

  pythonProcess.on('error', (err) => {
    console.error('Failed to start Python engine:', err);
    if (mainWindow) {
      mainWindow.webContents.send('engine-msg', { 
        type: 'status', 
        text: 'Error: Python not found. Please install Python and add it to your PATH.' 
      });
    }
  });

  pythonProcess.on('exit', (code) => {
    console.log(`Python engine exited with code ${code}`);
    pythonProcess = null;
    if (!app.isQuitting) {
      // If it crashes too fast, wait longer before restarting to prevent spam
      const delay = 3000; 
      setTimeout(startPythonEngine, delay);
    }
  });
}

app.on('before-quit', () => {
  app.isQuitting = true;
  if (pythonProcess) pythonProcess.kill();
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
