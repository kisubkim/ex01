document.addEventListener('DOMContentLoaded', () => {
  const loginForm = document.getElementById('login-form');
  const loginContainer = document.getElementById('login-container');
  const dashboardContainer = document.getElementById('dashboard-container');
  const webview = document.getElementById('remote-ui');
  const connectBtn = document.getElementById('connect-btn');
  const errorMsg = document.getElementById('error-message');
  
  const dropzone = document.getElementById('dropzone');
  const progressContainer = document.getElementById('progress-container');
  const progressBarFill = document.getElementById('progress-bar-fill');
  const progressText = document.getElementById('progress-text');
  const uploadStatus = document.getElementById('upload-status');

  // Handle Login Submission
  loginForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const host = document.getElementById('host').value;
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;

    connectBtn.disabled = true;
    connectBtn.textContent = 'Connecting...';
    errorMsg.textContent = '';

    try {
      const result = await window.api.connectSSH({ host, username, password });
      if (!result.success) {
        throw new Error(result.error);
      }
      // Wait for tunnel-ready event to switch view
    } catch (err) {
      errorMsg.textContent = `Connection failed: ${err.message || err}`;
      connectBtn.disabled = false;
      connectBtn.textContent = 'Connect';
    }
  });

  // Handle Tunnel Ready
  window.api.onTunnelReady(() => {
    loginContainer.classList.add('hidden');
    dashboardContainer.classList.remove('hidden');
    
    // Load the local forwarded port in webview
    webview.src = 'http://127.0.0.1:8080';
  });

  // Handle Drag and Drop for SFTP
  dropzone.addEventListener('dragover', (e) => {
    e.preventDefault();
    e.stopPropagation();
    dropzone.classList.add('drag-active');
  });

  dropzone.addEventListener('dragleave', (e) => {
    e.preventDefault();
    e.stopPropagation();
    dropzone.classList.remove('drag-active');
  });

  dropzone.addEventListener('drop', async (e) => {
    e.preventDefault();
    e.stopPropagation();
    dropzone.classList.remove('drag-active');

    const files = e.dataTransfer.files;
    if (files.length > 0) {
      const file = files[0];
      // File.path is available in Electron environments
      if (!file.path) {
        uploadStatus.textContent = 'Error: Cannot get file path.';
        return;
      }

      uploadStatus.textContent = 'Uploading...';
      uploadStatus.className = 'status-message';
      progressContainer.classList.remove('hidden');
      progressBarFill.style.width = '0%';
      progressText.textContent = '0%';

      try {
        const result = await window.api.uploadFile(file.path);
        if (result.success) {
          uploadStatus.textContent = `Upload successful: ${result.remotePath}`;
          uploadStatus.classList.add('success');
        }
      } catch (err) {
        uploadStatus.textContent = `Upload failed: ${err.message || err}`;
        uploadStatus.classList.add('error');
      } finally {
        setTimeout(() => {
          progressContainer.classList.add('hidden');
        }, 3000);
      }
    }
  });

  // Handle Upload Progress
  window.api.onUploadProgress((progress) => {
    progressBarFill.style.width = `${progress}%`;
    progressText.textContent = `${progress}%`;
  });
});
