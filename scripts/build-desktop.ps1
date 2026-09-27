param(
    [string]$Python = "python",
    [string]$Iscc = "",
    [switch]$SkipTests
)
$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repoRoot
try {
    if (-not $SkipTests) {
        & $Python -m unittest discover -s tests -v
        if ($LASTEXITCODE -ne 0) { throw "Les tests Desktop ont échoué." }
    }
    & $Python scripts/make-icon.py
    if ($LASTEXITCODE -ne 0) { throw "La génération de l'icône a échoué." }
    & $Python -m PyInstaller --noconfirm packaging/windows/ChaosticTool.spec
    if ($LASTEXITCODE -ne 0) { throw "La compilation de l'application a échoué." }
    if (-not $Iscc) {
        $compiler = Get-Command ISCC.exe -ErrorAction SilentlyContinue
        if ($compiler) { $Iscc = $compiler.Source }
        else {
            $paths = @("${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe")
            $Iscc = $paths | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
        }
    }
    if (-not $Iscc) { throw "Application générée dans dist. Pour l'installateur, installez Inno Setup 6 et relancez avec -Iscc <chemin-vers-ISCC.exe>." }
    & $Iscc packaging/windows/installer.iss
    if ($LASTEXITCODE -ne 0) { throw "La compilation de l'installateur a échoué." }
    Get-ChildItem release/*.exe | Get-FileHash -Algorithm SHA256
}
finally { Pop-Location }
