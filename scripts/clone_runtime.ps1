$src = 'C:\Users\phuongpn\runtime_nextgen\venv\Lib\site-packages'
$dst = 'C:\Users\phuongpn\runtime_avatar_v2\Lib\site-packages'

Write-Host "Copying site-packages..."
Copy-Item -Path "$src\*" -Destination $dst -Recurse -Force

Write-Host "Verifying torch in runtime_avatar_v2..."
& 'C:\Users\phuongpn\runtime_avatar_v2\Scripts\python.exe' -c "import torch; print('V2 Torch:', torch.__version__, 'CUDA:', torch.cuda.is_available(), 'Archs:', torch.cuda.get_arch_list())"
