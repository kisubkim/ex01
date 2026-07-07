const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('api', {
  connectSSH: (credentials) => ipcRenderer.invoke('connect-ssh', credentials),
  uploadFile: (filePath) => ipcRenderer.invoke('upload-file', filePath),
  onTunnelReady: (callback) => ipcRenderer.on('tunnel-ready', callback),
  onUploadProgress: (callback) => ipcRenderer.on('upload-progress', (_event, value) => callback(value))
});
