using System;
using System.Diagnostics;
using System.IO;
using System.Net.Sockets;
using System.Threading;

namespace AIAvatarStudio
{
    class Program
    {
        static void Main(string[] args)
        {
            Console.Title = "AI Avatar Studio NextGen V2 (RTX 5090 Blackwell)";
            Console.OutputEncoding = System.Text.Encoding.UTF8;

            string appDir = AppDomain.CurrentDomain.BaseDirectory.TrimEnd('\\', '/');
            string[] pythonCandidates = new string[]
            {
                @"C:\Users\phuongpn\runtime_avatar_v2\Scripts\python.exe",
                Path.GetFullPath(Path.Combine(appDir, @"..\runtime_avatar_v2\Scripts\python.exe")),
                @"C:\Users\phuongpn\runtime_nextgen\venv\Scripts\python.exe",
                Path.GetFullPath(Path.Combine(appDir, @"runtime\venv\Scripts\python.exe"))
            };

            string pythonExe = null;
            foreach (var cand in pythonCandidates)
            {
                if (File.Exists(cand))
                {
                    pythonExe = cand;
                    break;
                }
            }

            if (string.IsNullOrEmpty(pythonExe))
            {
                Console.ForegroundColor = ConsoleColor.Red;
                Console.WriteLine("=====================================================================");
                Console.WriteLine(" [LỖI] Không tìm thấy môi trường Python AI Avatar Studio!");
                Console.WriteLine(" Đã kiểm tra các đường dẫn:");
                foreach (var c in pythonCandidates) Console.WriteLine("   - " + c);
                Console.WriteLine(" Vui lòng kiểm tra lại thư mục runtime_avatar_v2.");
                Console.WriteLine("=====================================================================");
                Console.ResetColor();
                Console.WriteLine("\nNhấn phím bất kỳ để thoát...");
                Console.ReadKey();
                return;
            }

            string host = "127.0.0.1";
            int port = 8178;
            string url = "http://" + host + ":" + port + "/";

            Console.ForegroundColor = ConsoleColor.Cyan;
            Console.WriteLine("=====================================================================");
            Console.WriteLine("  AI AVATAR STUDIO NEXTGEN V2 (RTX 5090 BLACKWELL EDITION)");
            Console.WriteLine("  Phiên bản: SOTA Multi-Band Laplacian Pyramid & Dental Enamel");
            Console.WriteLine("  Địa chỉ:   " + url);
            Console.WriteLine("  Runtime:   " + pythonExe);
            Console.WriteLine("=====================================================================");
            Console.ResetColor();

            // Check if server is already running on port 8178
            bool alreadyRunning = IsPortOpen(host, port);
            if (alreadyRunning)
            {
                Console.ForegroundColor = ConsoleColor.Green;
                Console.WriteLine("\n[THÔNG BÁO] Máy chủ Studio V2 đang chạy ngầm trên cổng " + port + "!");
                Console.WriteLine("Đang mở giao diện trên trình duyệt web...");
                Console.ResetColor();
                OpenBrowser(url);
                Console.WriteLine("\nBạn có thể đóng cửa sổ này hoặc nhấn phím bất kỳ để kết thúc.");
                Thread.Sleep(2000);
                return;
            }

            // Launch browser after slight delay
            new Thread(() =>
            {
                Thread.Sleep(1500);
                OpenBrowser(url);
            }).Start();

            // Start run_studio.py
            ProcessStartInfo psi = new ProcessStartInfo
            {
                FileName = pythonExe,
                Arguments = "run_studio.py --host " + host + " --port " + port,
                WorkingDirectory = appDir,
                UseShellExecute = false,
                RedirectStandardOutput = false,
                RedirectStandardError = false,
                CreateNoWindow = false
            };

            try
            {
                using (Process proc = Process.Start(psi))
                {
                    proc.WaitForExit();
                }
            }
            catch (Exception ex)
            {
                Console.ForegroundColor = ConsoleColor.Red;
                Console.WriteLine("[LỖI KHỞI CHẠY] " + ex.Message);
                Console.ResetColor();
                Console.WriteLine("\nNhấn phím bất kỳ để thoát...");
                Console.ReadKey();
            }
        }

        static bool IsPortOpen(string host, int port)
        {
            try
            {
                using (TcpClient client = new TcpClient())
                {
                    IAsyncResult result = client.BeginConnect(host, port, null, null);
                    bool success = result.AsyncWaitHandle.WaitOne(1000);
                    if (!success) return false;
                    client.EndConnect(result);
                    return true;
                }
            }
            catch
            {
                return false;
            }
        }

        static void OpenBrowser(string url)
        {
            try
            {
                Process.Start(new ProcessStartInfo
                {
                    FileName = url,
                    UseShellExecute = true
                });
            }
            catch { }
        }
    }
}
