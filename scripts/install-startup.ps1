# Windows 로그인 시 이 프로젝트 폴더에서 작업 창이 자동으로 열리도록 시작프로그램에 바로가기를 등록한다.
#   Claude Code 로 열기 (기본): powershell -ExecutionPolicy Bypass -File scripts\install-startup.ps1
#   gtrack 대시보드로 열기:     powershell -ExecutionPolicy Bypass -File scripts\install-startup.ps1 -Mode gtrack
#   해제:                       powershell -ExecutionPolicy Bypass -File scripts\install-startup.ps1 -Uninstall
param(
    [ValidateSet('claude', 'gtrack')][string]$Mode = 'claude',
    [switch]$Uninstall
)

$shortcut = Join-Path ([Environment]::GetFolderPath('Startup')) 'gtrack.lnk'

if ($Uninstall) {
    if (Test-Path $shortcut) { Remove-Item $shortcut; Write-Host "해제했습니다: $shortcut" }
    else { Write-Host '등록된 바로가기가 없습니다.' }
    return
}

$start = Join-Path $PSScriptRoot 'start-gtrack.ps1'
$repo = Split-Path -Parent $PSScriptRoot
$flag = if ($Mode -eq 'claude') { ' -Claude' } else { '' }
$lnk = (New-Object -ComObject WScript.Shell).CreateShortcut($shortcut)
$lnk.TargetPath = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$lnk.Arguments = "-NoExit -NoLogo -ExecutionPolicy Bypass -Command `". '$start'$flag`""
$lnk.WorkingDirectory = $repo
$lnk.Description = "gtrack 프로젝트 관리 ($Mode)"
$lnk.Save()
Write-Host "등록했습니다 ($Mode): $shortcut"
