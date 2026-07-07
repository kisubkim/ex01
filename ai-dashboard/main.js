const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const { Client } = require('ssh2');
const net = require('net');
const fs = require('fs');

let mainWindow;
let sshClient;
let localServer;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      webviewTag: true, // Required for <webview>
      contextIsolation: true,
      nodeIntegration: false
    }
  });

  mainWindow.loadFile('index.html');
}

app.whenReady().then(() => {
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

// IPC handler for SSH connection
ipcMain.handle('connect-ssh', async (event, credentials) => {
  return new Promise((resolve, reject) => {
    sshClient = new Client();

    sshClient.on('ready', () => {
      console.log('SSH Client Ready');

      // Create local TCP server for tunneling
      localServer = net.createServer(socket => {
        // Forward local connection to remote localhost:8080
        sshClient.forwardOut(
          socket.remoteAddress,
          socket.remotePort,
          '127.0.0.1',
          8080,
          (err, stream) => {
            if (err) {
              console.error('Port forwarding error:', err);
              return socket.end();
            }
            socket.pipe(stream);
            stream.pipe(socket);
          }
        );
      });

      localServer.listen(8080, '127.0.0.1', () => {
        console.log('Local port forwarding established on 127.0.0.1:8080');
        event.sender.send('tunnel-ready');
        resolve({ success: true });
      });
      
      localServer.on('error', (err) => {
        console.error('Local server error:', err);
        // If port 8080 is already in use, we still want to resolve success if we are just connecting
        // For robustness, one might pick a dynamic port, but we'll stick to 8080 as requested.
        resolve({ success: false, error: err.message });
      });
    }).on('error', (err) => {
      console.error('SSH Client Error:', err);
      reject(err.message);
    }).connect({
      host: credentials.host,
      port: 22,
      username: credentials.username,
      password: credentials.password
    });
  });
});

// IPC handler for SFTP file upload
ipcMain.handle('upload-file', async (event, filePath) => {
  if (!sshClient) {
    throw new Error('SSH client not connected');
  }

  return new Promise((resolve, reject) => {
    sshClient.sftp((err, sftp) => {
      if (err) return reject(err.message);

      const fileName = path.basename(filePath);
      const remotePath = `/path/to/models/${fileName}`; // Adjust as needed
      
      console.log(`Starting upload to ${remotePath}`);

      fs.stat(filePath, (err, stats) => {
        if (err) return reject(err.message);
        
        const totalSize = stats.size;
        let uploadedSize = 0;

        const readStream = fs.createReadStream(filePath);
        const writeStream = sftp.createWriteStream(remotePath);

        readStream.on('data', (chunk) => {
          uploadedSize += chunk.length;
          const progress = Math.round((uploadedSize / totalSize) * 100);
          event.sender.send('upload-progress', progress);
        });

        writeStream.on('close', () => {
          console.log('Upload complete');
          resolve({ success: true, remotePath });
        });

        writeStream.on('error', (writeErr) => {
          console.error('Upload error:', writeErr);
          reject(writeErr.message);
        });

        readStream.pipe(writeStream);
      });
    });
  });
});
