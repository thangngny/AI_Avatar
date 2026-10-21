$desktop = [Environment]::GetFolderPath('DesktopDirectory')
$shortcutPath = Join-Path $desktop "AI Avatar Studio.lnk"
$targetExe = Join-Path $PSScriptRoot "..\AI_Avatar_Studio.exe"
$workingDir = Join-Path $PSScriptRoot ".."

$targetExe = [System.IO.Path]::GetFullPath($targetExe)
$workingDir = [System.IO.Path]::GetFullPath($workingDir)

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $targetExe
$shortcut.WorkingDirectory = $workingDir
$shortcut.Description = "AI Avatar Studio - Tạo Video AI Avatar"
$shortcut.Save()

Write-Host "[OK] Đã tạo biểu tượng 'AI Avatar Studio' ngoài màn hình Desktop: $shortcutPath"
