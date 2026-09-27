param([string]$Python = "python", [string]$Iscc = "", [switch]$SkipTests)
$ErrorActionPreference = "Stop"
$arguments = @((Join-Path $PSScriptRoot 'build-desktop.py'))
if ($Iscc) { $arguments += @('--iscc', $Iscc) }
if ($SkipTests) { $arguments += '--skip-tests' }
& $Python @arguments
if ($LASTEXITCODE -ne 0) { throw 'Build Desktop failed.' }
