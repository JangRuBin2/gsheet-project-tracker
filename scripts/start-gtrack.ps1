# gtrack 작업 창: 저장소 폴더로 이동하고, 대시보드를 보여주고, `gtrack` 단축 명령을 등록한다.
# 이 파일을 dot-source 해야 gtrack 함수가 창에 남는다:
#   powershell -NoExit -ExecutionPolicy Bypass -Command ". '<경로>\scripts\start-gtrack.ps1'"
# -Claude: 대시보드 대신 이 폴더에서 Claude Code 를 실행한다 (종료 후에도 창과 gtrack 명령은 남음).
# Windows 시작 시 자동 실행 등록/해제: scripts\install-startup.ps1 [-Mode claude|gtrack] [-Uninstall]
param([switch]$Claude)

$Host.UI.RawUI.WindowTitle = 'gtrack - 프로젝트 관리'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$env:PYTHONIOENCODING = 'utf-8'
Set-Location (Split-Path -Parent $PSScriptRoot)

# Store 별칭(WindowsApps\python.exe)이 아닌 실제 Python 을 찾는다.
$script:GtrackPython = @(
    Get-ChildItem "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe" -ErrorAction SilentlyContinue |
        Sort-Object FullName -Descending | Select-Object -ExpandProperty FullName
    (Get-Command py -ErrorAction SilentlyContinue).Source
    (Get-Command python -ErrorAction SilentlyContinue | Where-Object { $_.Source -notlike '*WindowsApps*' }).Source
) | Where-Object { $_ } | Select-Object -First 1

if (-not $script:GtrackPython) {
    Write-Host 'Python 을 찾을 수 없습니다. skill/gtrack/references/SETUP.md 의 0단계를 참고해 설치하세요.' -ForegroundColor Red
    return
}

function global:gtrack { & $script:GtrackPython -m gtrack @args }

if ($Claude) {
    $claudeCmd = Get-Command claude.cmd, claude -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($claudeCmd) {
        $Host.UI.RawUI.WindowTitle = 'Claude Code - gtrack'
        & $claudeCmd.Source
        Write-Host ''
        Write-Host "  Claude Code 를 종료했습니다. 이 창에서 'gtrack' 명령을 쓰거나 'claude' 로 다시 시작하세요." -ForegroundColor DarkGray
        return
    }
    Write-Host '  Claude Code(claude) 를 찾을 수 없습니다. gtrack 대시보드를 대신 표시합니다.' -ForegroundColor Yellow
}

Write-Host ''
Write-Host '  gtrack 프로젝트 관리' -ForegroundColor Cyan
Write-Host "  $(Get-Location)" -ForegroundColor DarkGray
Write-Host ''

if (-not (Test-Path credentials.json)) {
    Write-Host '  credentials.json 이 없습니다. skill/gtrack/references/SETUP.md 를 참고해 인증을 설정하세요.' -ForegroundColor Yellow
} elseif (-not (Test-Path .gtrack.json)) {
    Write-Host "  연결된 스프레드시트가 없습니다. 'gtrack init' 을 실행하세요." -ForegroundColor Yellow
} else {
    gtrack project list
    Write-Host ''
    gtrack raid list --open
}

Write-Host ''
Write-Host '  자주 쓰는 명령' -ForegroundColor Cyan
Write-Host '    gtrack project list                          대시보드'
Write-Host '    gtrack task list "<프로젝트>" --open          미완료 작업'
Write-Host '    gtrack task update "<프로젝트>" T-001 --progress 60'
Write-Host '    gtrack raid list --open                      열린 리스크·이슈'
Write-Host '    gtrack open                                  시트 주소'
Write-Host '    gtrack --help                                전체 도움말'
Write-Host ''
