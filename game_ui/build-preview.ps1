param([string]$OutputDirectory = '')
$ErrorActionPreference='Stop'
$projectRoot=$PSScriptRoot
if(-not $OutputDirectory){$OutputDirectory=Join-Path $projectRoot 'build'}
$outputRoot=[IO.Path]::GetFullPath($OutputDirectory)
$engineRoot=Join-Path $outputRoot 'engine'
$portableRoot=Join-Path $outputRoot 'ChaosticTool-Game-Preview'
New-Item -ItemType Directory -Force -Path $engineRoot,$portableRoot,(Join-Path $portableRoot 'runtime'),(Join-Path $portableRoot 'game') | Out-Null
$archive=Join-Path $engineRoot 'godot.zip'
$expected='731980f9608d61333e5baf54a2ef17210acc7a538446c0cb9969f002aca1e953'
if(-not (Test-Path -LiteralPath $archive)){
    Invoke-WebRequest 'https://github.com/godotengine/godot-builds/releases/download/4.7.2-stable/Godot_v4.7.2-stable_win64.exe.zip' -OutFile $archive
}
if((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash -ne $expected){throw 'Godot checksum mismatch'}
Expand-Archive -LiteralPath $archive -DestinationPath $engineRoot -Force
New-Item -ItemType File -Force -Path (Join-Path $engineRoot '_sc_') | Out-Null
& (Join-Path $engineRoot 'Godot_v4.7.2-stable_win64_console.exe') --headless --path $projectRoot --editor --import --quit
if($LASTEXITCODE){throw 'Godot resource import failed'}
$sourceFiles=@(Get-ChildItem -LiteralPath $projectRoot -File -Recurse | Where-Object { -not $_.FullName.StartsWith($outputRoot+'\',[StringComparison]::OrdinalIgnoreCase) })
$sourceFiles | ForEach-Object {
    $relative=$_.FullName.Substring($projectRoot.Length+1)
    $normalized=$relative.Replace('\','/')
    if($normalized -match '^(build|qa|[.]git)/' -or $normalized -match '^[.]godot/(?!imported/)' -or $_.Extension -in @('.cs','.ps1')){return}
    $target=Join-Path (Join-Path $portableRoot 'game') $relative
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
    Copy-Item -LiteralPath $_.FullName -Destination $target -Force
}
Copy-Item -LiteralPath (Join-Path $engineRoot 'Godot_v4.7.2-stable_win64.exe') -Destination (Join-Path $portableRoot 'runtime/Godot.exe') -Force
$compiler=Join-Path $env:WINDIR 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
& $compiler /nologo /target:winexe /reference:System.Windows.Forms.dll ("/out:"+(Join-Path $portableRoot 'ChaosticTool Game Preview.exe')) (Join-Path $projectRoot 'Launcher.cs')
if($LASTEXITCODE){throw 'Launcher compilation failed'}
Copy-Item -LiteralPath (Join-Path $projectRoot 'README.md') -Destination (Join-Path $portableRoot 'LIRE-MOI.md') -Force
Write-Output ('Portable ready: '+$portableRoot)
