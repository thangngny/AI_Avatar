using System;
using System.Diagnostics;
using System.IO;
using System.Net;
using System.Threading;
using System.Windows.Forms;

namespace AIAvatarStudio
{
    static class Launcher
    {
        [STAThread]
        static void Main(string[] args)
        {
            string url = "http://127.0.0.1:8077";
            string baseDir = AppDomain.CurrentDomain.BaseDirectory;

            // Auto-create Desktop Shortcut on first run
            EnsureDesktopShortcut(baseDir);

            // Check if server is already running
            if (!IsServerRunning(url))
            {
                string pythonPath = FindPython(baseDir);
                if (string.IsNullOrEmpty(pythonPath))
                {
                    MessageBox.Show(
                        "Không tìm thấy môi trường Python AI (runtime\\venv).\n\n" +
                        "Vui lòng đảm bảo thư mục runtime\\venv đã được cài đặt đúng đường dẫn.",
                        "AI Avatar Studio - Thiếu Runtime",
                        MessageBoxButtons.OK,
                        MessageBoxIcon.Warning
                    );
                    return;
                }

                // Start Studio server in background
                ProcessStartInfo psi = new ProcessStartInfo();
                psi.FileName = pythonPath;
                psi.Arguments = "run_studio.py --no-browser --port 8077";
                psi.WorkingDirectory = baseDir;
                psi.UseShellExecute = false;
                psi.CreateNoWindow = true; // Silently runs in background
                try
                {
                    Process.Start(psi);
                }
                catch (Exception ex)
                {
                    MessageBox.Show("Lỗi khởi động Studio: " + ex.Message, "Lỗi", MessageBoxButtons.OK, MessageBoxIcon.Error);
                    return;
                }

                // Wait for server to be responsive
                bool ready = false;
                for (int i = 0; i < 30; i++)
                {
                    Thread.Sleep(500);
                    if (IsServerRunning(url))
                    {
                        ready = true;
                        break;
                    }
                }

                if (!ready)
                {
                    MessageBox.Show("Studio đang khởi động chậm. Hệ thống sẽ mở giao diện ngay bây giờ.", "Thông báo", MessageBoxButtons.OK, MessageBoxIcon.Information);
                }
            }

            // Launch browser in app mode
            OpenInAppMode(url);
        }

        static void EnsureDesktopShortcut(string baseDir)
        {
            try
            {
                string desktop = Environment.GetFolderPath(Environment.SpecialFolder.Desktop);
                string lnkPath = Path.Combine(desktop, "AI Avatar Studio.lnk");
                string exePath = Path.Combine(baseDir, "AI_Avatar_Studio.exe");
                if (!File.Exists(lnkPath) && File.Exists(exePath))
                {
                    Type shellType = Type.GetTypeFromProgID("WScript.Shell");
                    if (shellType != null)
                    {
                        dynamic shell = Activator.CreateInstance(shellType);
                        dynamic sc = shell.CreateShortcut(lnkPath);
                        sc.TargetPath = exePath;
                        sc.WorkingDirectory = baseDir;
                        sc.Description = "AI Avatar Studio - Tạo Video AI Avatar";
                        sc.Save();
                    }
                }
            }
            catch { }
        }

        static bool IsServerRunning(string url)
        {
            try
            {
                HttpWebRequest req = (HttpWebRequest)WebRequest.Create(url + "/api/system/status");
                req.Timeout = 800;
                req.Method = "GET";
                using (HttpWebResponse res = (HttpWebResponse)req.GetResponse())
                {
                    return res.StatusCode == HttpStatusCode.OK;
                }
            }
            catch
            {
                return false;
            }
        }

        static string FindPython(string baseDir)
        {
            string[] candidates = new string[]
            {
                Path.Combine(baseDir, @"..\runtime\venv\Scripts\python.exe"),
                @"C:\CongThang_AI_Avatar\runtime\venv\Scripts\python.exe",
                @"D:\CongThang_AI_Avatar\runtime\venv\Scripts\python.exe",
                Path.Combine(baseDir, @"runtime\venv\Scripts\python.exe")
            };

            foreach (string p in candidates)
            {
                try
                {
                    string full = Path.GetFullPath(p);
                    if (File.Exists(full)) return full;
                }
                catch { }
            }
            return null;
        }

        static void OpenInAppMode(string url)
        {
            string[] browsers = new string[]
            {
                @"C:\Program Files\Google\Chrome\Application\chrome.exe",
                @"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), @"Google\Chrome\Application\chrome.exe"),
                @"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                @"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
            };

            foreach (string b in browsers)
            {
                if (File.Exists(b))
                {
                    try
                    {
                        ProcessStartInfo psi = new ProcessStartInfo();
                        psi.FileName = b;
                        psi.Arguments = "--app=" + url + " --window-size=1440,900";
                        Process.Start(psi);
                        return;
                    }
                    catch { }
                }
            }

            // Fallback default browser
            try
            {
                Process.Start(new ProcessStartInfo(url) { UseShellExecute = true });
            }
            catch { }
        }
    }
}
