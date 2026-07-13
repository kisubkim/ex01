using System;
using System.IO;
using System.Threading.Tasks;
using System.Windows;
using Renci.SshNet;
using Microsoft.Web.WebView2.Core;

namespace AIDashboard
{
    public partial class MainWindow : Window
    {
        private SshClient? sshClient;
        private ForwardedPortLocal? portForwarded;

        public MainWindow()
        {
            InitializeComponent();
            InitializeWebViewAsync();
        }

        private async void InitializeWebViewAsync()
        {
            await webView.EnsureCoreWebView2Async(null);
        }

        private async void btnConnect_Click(object sender, RoutedEventArgs e)
        {
            string host = txtHost.Text;
            string user = txtUser.Text;
            string password = txtPassword.Password;

            txtStatus.Text = "Connecting...";

            try
            {
                await Task.Run(() =>
                {
                    sshClient = new SshClient(host, user, password);
                    sshClient.Connect();

                    if (sshClient.IsConnected)
                    {
                        portForwarded = new ForwardedPortLocal("127.0.0.1", 8080, "127.0.0.1", 8080);
                        sshClient.AddForwardedPort(portForwarded);
                        portForwarded.Start();
                    }
                });

                if (sshClient != null && sshClient.IsConnected)
                {
                    txtStatus.Text = "Connected & Tunnel Established.";
                    txtStatus.Foreground = System.Windows.Media.Brushes.Green;
                    
                    // Navigate to the tunneled port
                    if (webView.CoreWebView2 != null)
                    {
                        webView.CoreWebView2.Navigate("http://localhost:8080");
                    }
                }
            }
            catch (Exception ex)
            {
                txtStatus.Text = $"Error: {ex.Message}";
                txtStatus.Foreground = System.Windows.Media.Brushes.Red;
            }
        }

        private async void Dropzone_Drop(object sender, DragEventArgs e)
        {
            if (e.Data.GetDataPresent(DataFormats.FileDrop))
            {
                string[] files = (string[])e.Data.GetData(DataFormats.FileDrop);
                
                if (sshClient == null || !sshClient.IsConnected)
                {
                    MessageBox.Show("Please connect to SSH first.", "Error", MessageBoxButton.OK, MessageBoxImage.Error);
                    return;
                }

                // Prepare progress reporting
                var progress = new Progress<int>(percent =>
                {
                    uploadProgress.Value = percent;
                });

                try
                {
                    txtUploadStatus.Text = $"Uploading {files.Length} file(s)...";
                    
                    await Task.Run(() =>
                    {
                        using (var sftp = new SftpClient(sshClient.ConnectionInfo))
                        {
                            sftp.Connect();

                            string remoteDir = "/path/to/models/";
                            // Create directory if not exists - simplistically handled
                            try { sftp.ChangeDirectory(remoteDir); }
                            catch { sftp.CreateDirectory(remoteDir); sftp.ChangeDirectory(remoteDir); }

                            foreach (var file in files)
                            {
                                FileInfo fileInfo = new FileInfo(file);
                                string remotePath = remoteDir + fileInfo.Name;

                                using (var fileStream = new FileStream(file, FileMode.Open))
                                {
                                    sftp.UploadFile(fileStream, remotePath, (uploadedBytes) =>
                                    {
                                        int percent = (int)(((long)uploadedBytes * 100) / fileStream.Length);
                                        ((IProgress<int>)progress).Report(percent);
                                    });
                                }
                            }
                            sftp.Disconnect();
                        }
                    });

                    txtUploadStatus.Text = "Upload Complete!";
                    uploadProgress.Value = 100;
                }
                catch (Exception ex)
                {
                    txtUploadStatus.Text = $"Upload Failed: {ex.Message}";
                    MessageBox.Show(ex.Message, "Upload Error", MessageBoxButton.OK, MessageBoxImage.Error);
                }
            }
        }

        protected override void OnClosed(EventArgs e)
        {
            if (portForwarded != null && portForwarded.IsStarted)
            {
                portForwarded.Stop();
                portForwarded.Dispose();
            }

            if (sshClient != null && sshClient.IsConnected)
            {
                sshClient.Disconnect();
                sshClient.Dispose();
            }

            base.OnClosed(e);
        }
    }
}