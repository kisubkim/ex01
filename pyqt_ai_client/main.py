import sys
import os
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QProgressBar, QStatusBar,
    QFrame
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, pyqtSlot, QUrl
from PyQt6.QtWebEngineWidgets import QWebEngineView
import paramiko
from sshtunnel import SSHTunnelForwarder

class SSHTunnelWorker(QThread):
    connected = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, host, port, user, password, local_bind_port=8080, remote_bind_port=8080):
        super().__init__()
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.local_bind_port = local_bind_port
        self.remote_bind_port = remote_bind_port
        self.server = None

    def run(self):
        try:
            self.server = SSHTunnelForwarder(
                (self.host, self.port),
                ssh_username=self.user,
                ssh_password=self.password,
                remote_bind_address=('127.0.0.1', self.remote_bind_port),
                local_bind_address=('127.0.0.1', self.local_bind_port)
            )
            self.server.start()
            self.connected.emit()
        except Exception as e:
            self.error.emit(str(e))
            
    def stop(self):
        if self.server:
            self.server.stop()

class SFTPUploadWorker(QThread):
    progress = pyqtSignal(int, int) # bytes transferred, total bytes
    finished = pyqtSignal(str) # success message
    error = pyqtSignal(str) # error message

    def __init__(self, host, port, user, password, local_path, remote_path):
        super().__init__()
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.local_path = local_path
        self.remote_path = remote_path

    def run(self):
        try:
            transport = paramiko.Transport((self.host, self.port))
            transport.connect(username=self.user, password=self.password)
            sftp = paramiko.SFTPClient.from_transport(transport)
            
            def cb(transferred, total):
                self.progress.emit(transferred, total)
                
            sftp.put(self.local_path, self.remote_path, callback=cb)
            sftp.close()
            transport.close()
            self.finished.emit(f"Uploaded: {os.path.basename(self.local_path)}")
        except Exception as e:
            self.error.emit(str(e))

class DropZoneWidget(QFrame):
    files_dropped = pyqtSignal(list)

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Sunken)
        self.setMinimumSize(200, 150)
        
        layout = QVBoxLayout()
        self.label = QLabel("Drag & Drop Files Here\nfor SFTP Upload")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.label)
        self.setLayout(layout)
        
        self.setStyleSheet("""
            QFrame {
                border: 2px dashed #aaa;
                border-radius: 5px;
                background-color: #f9f9f9;
            }
        """)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
            self.setStyleSheet("""
                QFrame {
                    border: 2px dashed #0078d7;
                    border-radius: 5px;
                    background-color: #e5f1fb;
                }
            """)
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.setStyleSheet("""
            QFrame {
                border: 2px dashed #aaa;
                border-radius: 5px;
                background-color: #f9f9f9;
            }
        """)

    def dropEvent(self, event):
        self.setStyleSheet("""
            QFrame {
                border: 2px dashed #aaa;
                border-radius: 5px;
                background-color: #f9f9f9;
            }
        """)
        file_paths = []
        for url in event.mimeData().urls():
            if url.isLocalFile():
                file_paths.append(url.toLocalFile())
        if file_paths:
            self.files_dropped.emit(file_paths)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Client - SSH Tunnel & SFTP")
        self.resize(1024, 768)

        self.tunnel_worker = None
        self.upload_workers = []

        # -- UI Elements --
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        # Connection Config Layout
        config_layout = QHBoxLayout()
        self.host_input = QLineEdit()
        self.host_input.setPlaceholderText("SSH Host (e.g. 192.168.1.100)")
        self.user_input = QLineEdit()
        self.user_input.setPlaceholderText("SSH User")
        self.pass_input = QLineEdit()
        self.pass_input.setPlaceholderText("SSH Password")
        self.pass_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.connect_btn = QPushButton("Connect & Tunnel")
        self.connect_btn.clicked.connect(self.start_tunnel)

        config_layout.addWidget(QLabel("Host:"))
        config_layout.addWidget(self.host_input)
        config_layout.addWidget(QLabel("User:"))
        config_layout.addWidget(self.user_input)
        config_layout.addWidget(QLabel("Password:"))
        config_layout.addWidget(self.pass_input)
        config_layout.addWidget(self.connect_btn)

        main_layout.addLayout(config_layout)

        # Split Main Area (Browser + Dropzone)
        split_layout = QHBoxLayout()
        
        # Web Engine View
        self.browser = QWebEngineView()
        self.browser.setUrl(QUrl("about:blank"))
        split_layout.addWidget(self.browser, stretch=3)

        # Dropzone side panel
        side_panel = QVBoxLayout()
        self.dropzone = DropZoneWidget()
        self.dropzone.files_dropped.connect(self.handle_files_dropped)
        side_panel.addWidget(self.dropzone)
        
        # Remote path input
        self.remote_path_input = QLineEdit("/tmp/")
        self.remote_path_input.setPlaceholderText("Remote SFTP Upload Path")
        side_panel.addWidget(QLabel("Remote Path:"))
        side_panel.addWidget(self.remote_path_input)
        side_panel.addStretch(1)
        
        split_layout.addLayout(side_panel, stretch=1)
        main_layout.addLayout(split_layout)

        # Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(200)
        self.progress_bar.hide()
        self.status_bar.addPermanentWidget(self.progress_bar)

    def start_tunnel(self):
        host = self.host_input.text()
        user = self.user_input.text()
        password = self.pass_input.text()
        
        if not host or not user:
            self.status_bar.showMessage("Please provide host and user.")
            return

        self.connect_btn.setEnabled(False)
        self.status_bar.showMessage("Connecting SSH Tunnel...")

        self.tunnel_worker = SSHTunnelWorker(host, 22, user, password)
        self.tunnel_worker.connected.connect(self.on_tunnel_connected)
        self.tunnel_worker.error.connect(self.on_tunnel_error)
        self.tunnel_worker.start()

    @pyqtSlot()
    def on_tunnel_connected(self):
        self.status_bar.showMessage("Tunnel connected. Loading web view...", 5000)
        self.connect_btn.setText("Connected")
        self.browser.setUrl(QUrl("http://localhost:8080"))

    @pyqtSlot(str)
    def on_tunnel_error(self, err):
        self.status_bar.showMessage(f"Tunnel Error: {err}")
        self.connect_btn.setEnabled(True)

    @pyqtSlot(list)
    def handle_files_dropped(self, file_paths):
        host = self.host_input.text()
        user = self.user_input.text()
        password = self.pass_input.text()
        remote_dir = self.remote_path_input.text()

        if not host or not user:
            self.status_bar.showMessage("Please provide host and user first.")
            return

        if not remote_dir.endswith("/"):
            remote_dir += "/"

        for local_path in file_paths:
            filename = os.path.basename(local_path)
            remote_path = remote_dir + filename
            
            worker = SFTPUploadWorker(host, 22, user, password, local_path, remote_path)
            worker.progress.connect(self.on_upload_progress)
            worker.finished.connect(self.on_upload_finished)
            worker.error.connect(self.on_upload_error)
            
            self.upload_workers.append(worker)
            self.progress_bar.setValue(0)
            self.progress_bar.show()
            self.status_bar.showMessage(f"Uploading {filename}...")
            worker.start()

    @pyqtSlot(int, int)
    def on_upload_progress(self, transferred, total):
        if total > 0:
            percentage = int((transferred / total) * 100)
            self.progress_bar.setValue(percentage)

    @pyqtSlot(str)
    def on_upload_finished(self, msg):
        self.status_bar.showMessage(msg, 5000)
        self.progress_bar.hide()
        # Clean up worker
        worker = self.sender()
        if worker in self.upload_workers:
            self.upload_workers.remove(worker)

    @pyqtSlot(str)
    def on_upload_error(self, err):
        self.status_bar.showMessage(f"Upload Error: {err}", 5000)
        self.progress_bar.hide()
        worker = self.sender()
        if worker in self.upload_workers:
            self.upload_workers.remove(worker)

    def closeEvent(self, event):
        if self.tunnel_worker:
            self.tunnel_worker.stop()
            self.tunnel_worker.wait()
        for worker in self.upload_workers:
            worker.wait()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
