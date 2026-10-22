$desktop = [Environment]::GetFolderPath('DesktopDirectory')
$shortcutPath = Join-Path $desktop "AI Avatar Studio NextGen.lnk"
$targetBat = Join-Path $PSScriptRoot "..\AI_Avatar_Studio.bat"
$iconPath = Join-Path $PSScriptRoot "..\assets\app_icon.ico"
$workingDir = Join-Path $PSScriptRoot ".."

$targetBat = [System.IO.Path]::GetFullPath($targetBat)
$iconPath = [System.IO.Path]::GetFullPath($iconPath)
$workingDir = [System.IO.Path]::GetFullPath($workingDir)

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $targetBat
$shortcut.WorkingDirectory = $workingDir
if (Test-Path $iconPath) {
    $shortcut.IconLocation = "$iconPath,0"
}
$shortcut.Description = "AI Avatar Studio NextGen (RTX 5090 Blackwell sm_120)"
$shortcut.Save()

Write-Host "[OK] Đã tạo biểu tượng 'AI Avatar Studio NextGen' ngoài màn hình Desktop: $shortcutPath"
