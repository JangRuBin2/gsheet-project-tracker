# Windows 로그인 시 gtrack 작업 창이 자동으로 열리도록 시작프로그램에 바로가기를 등록한다.
#   등록: powershell -ExecutionPolicy Bypass -File scripts\install-startup.ps1
#   해제: powershell -ExecutionPolicy Bypass -File scripts\install-startup.ps1 -Uninstall
param([switch]$Uninstall)

$shortcut = Join-Path ([Environment]::GetFolderPath('Startup')) 'gtrack.lnk'

if ($Uninstall) {
    if (Test-Path $shortcut) { Remove-Item $shortcut; Write-Host "해제했습니다: $shortcut" }
    else { Write-Host '등록된 바로가기가 없습니다.' }
    return
}

$start = Join-Path $PSScriptRoot 'start-gtrack.ps1'
$repo = Split-Path -Parent $PSScriptRoot
$lnk = (New-Object -ComObject WScript.Shell).CreateShortcut($shortcut)
$lnk.TargetPath = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$lnk.Arguments = "-NoExit -NoLogo -ExecutionPolicy Bypass -Command `". '$start'`""
$lnk.WorkingDirectory = $repo
$lnk.Description = 'gtrack 프로젝트 관리 CLI'
$lnk.Save()
Write-Host "등록했습니다: $shortcut"
