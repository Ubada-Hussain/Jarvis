const { app, BrowserWindow } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const net = require('net');

let mainWindow;
let backendProcess;

const BACKEND_PORT = 8000;
const FRONTEND_PORT = 5173;
const IS_DEV = !app.isPackaged;

function waitForPort(port, timeout = 30000) {
  return new Promise((resolve, reject) => {
    const startTime = Date.now();
    const check = () => {
      const client = new net.Socket();
      client.once('connect', () => {
        client.destroy();
        resolve();
      });
      client.once('error', () => {
        client.destroy();
        if (Date.now() - startTime > timeout) {
          reject(new Error(`Timeout waiting for port ${port}`));
        } else {
          setTimeout(check, 500);
        }
      });
      client.connect(port, '127.0.0.1');
    };
    check();
  });
}

function startBackend() {
  // Determine python executable
  const pythonCmd = process.platform === 'win32' ? 'python' : 'python3';
  const projectRoot = IS_DEV
    ? path.resolve(__dirname, '..', '..')  // jarvis-ui/electron/main.cjs -> Jarvis/
    : path.resolve(process.resourcesPath, 'backend');

  console.log(`[Electron] Starting backend from: ${projectRoot}`);

  backendProcess = spawn(
    pythonCmd,
    ['-m', 'uvicorn', 'api_server:app', '--host', '0.0.0.0', '--port', String(BACKEND_PORT)],
    {
      cwd: projectRoot,
      stdio: ['ignore', 'pipe', 'pipe'],
      env: { ...process.env, PYTHONUNBUFFERED: '1' },
    }
  );

  backendProcess.stdout.on('data', (data) => {
    console.log(`[Backend] ${data.toString().trim()}`);
  });
  backendProcess.stderr.on('data', (data) => {
    console.error(`[Backend ERR] ${data.toString().trim()}`);
  });
  backendProcess.on('close', (code) => {
    console.log(`[Backend] Process exited with code ${code}`);
  });
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1100,
    minHeight: 700,
    title: 'JARVIS',
    icon: path.join(__dirname, '..', 'public', 'jarvis-icon.png'),
    backgroundColor: '#07070b',
    frame: true,
    autoHideMenuBar: true,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
    },
  });

  if (IS_DEV) {
    mainWindow.loadURL(`http://localhost:${FRONTEND_PORT}`);
    // mainWindow.webContents.openDevTools();
  } else {
    // In production, serve the built frontend
    mainWindow.loadFile(path.join(__dirname, '..', 'dist', 'index.html'));
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

app.whenReady().then(async () => {
  // Start the Python backend
  startBackend();

  // Wait for backend to be ready
  console.log('[Electron] Waiting for backend to start...');
  try {
    await waitForPort(BACKEND_PORT, 30000);
    console.log('[Electron] Backend is ready!');
  } catch (err) {
    console.error('[Electron] Backend failed to start:', err.message);
  }

  // In dev mode, also wait for Vite
  if (IS_DEV) {
    console.log('[Electron] Waiting for Vite dev server...');
    try {
      await waitForPort(FRONTEND_PORT, 15000);
      console.log('[Electron] Vite is ready!');
    } catch (err) {
      console.error('[Electron] Vite not detected. Make sure npm run dev is running.');
    }
  }

  createWindow();
});

app.on('window-all-closed', () => {
  // Kill backend when window closes
  if (backendProcess) {
    console.log('[Electron] Shutting down backend...');
    backendProcess.kill();
  }
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});

// Ensure backend is cleaned up on quit
app.on('before-quit', () => {
  if (backendProcess && !backendProcess.killed) {
    backendProcess.kill();
  }
});
