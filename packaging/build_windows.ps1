# Builds dist\ScreenCapture\ScreenCapture.exe (PyInstaller) and, if Inno Setup is installed,
# dist\ScreenCapture-Setup-<version>.exe.   Run from the repository root in PowerShell:
#   powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1
$ErrorActionPreference = "Stop"
$version = (Select-String -Path pyproject.toml -Pattern '^version = "(.+)"').Matches[0].Groups[1].Value

python -m pip install --upgrade pip pyinstaller .
python -m PyInstaller --noconfirm --clean --windowed --name ScreenCapture `
    --icon packaging\screencapture.ico `
    --exclude-module PySide6.QtQml --exclude-module PySide6.QtQuick --exclude-module PySide6.QtPdf `
    --exclude-module PySide6.QtSvg --exclude-module PySide6.QtNetworkAuth `
    --collect-submodules screencapture `
    screencapture\__main__.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

$iscc = Get-Command iscc -ErrorAction SilentlyContinue
if (-not $iscc) {
    $candidate = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
    if (Test-Path $candidate) { $iscc = $candidate }
}
if ($iscc) {
    & $iscc "/DAppVersion=$version" packaging\windows.iss
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed" }
    Write-Host "Installer: dist\ScreenCapture-Setup-$version.exe"
} else {
    Write-Warning "Inno Setup not found (winget install JRSoftware.InnoSetup); only the portable folder dist\ScreenCapture was built."
}
