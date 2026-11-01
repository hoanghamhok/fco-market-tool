param([switch]$Plan, [switch]$VerifyOnly)
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$downloads = [IO.Path]::GetFullPath((Join-Path $env:USERPROFILE 'Downloads'))
$version = [regex]::Match((Get-Content -LiteralPath (Join-Path $root 'fco/__init__.py') -Raw), '\d+(?:\.\d+)+').Value
if (!$version) { throw 'Cannot read application version.' }
$name = "FCO-Market-$version.exe"
$stage = Join-Path $root '.build-staging'
$release = Join-Path $root 'release'
$python = Join-Path $root '.venv/Scripts/python.exe'

function Assert-Child([string]$base, [string]$target) {
    $base = [IO.Path]::GetFullPath($base).TrimEnd('\')
    $target = [IO.Path]::GetFullPath($target)
    if (!$target.StartsWith($base + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing operation outside $base : $target"
    }
    $cursor = $target
    while ($cursor -and $cursor.Length -ge $base.Length) {
        if ((Test-Path -LiteralPath $cursor) -and ((Get-Item -LiteralPath $cursor).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw "Refusing operation through a filesystem link: $cursor"
        }
        $cursor = Split-Path -Parent $cursor
    }
}

function Old-Executables([string]$folder) {
    if (Test-Path -LiteralPath $folder) {
        Get-ChildItem -LiteralPath $folder -File | Where-Object {
            $_.Name -match '^FCO-Market(?:-\d+(?:\.\d+)*)?\.exe$' -and $_.Name -ne $name
        }
    }
}

if ($Plan) {
    Write-Output "Source: $root"
    Write-Output "Build and verify: $name"
    if ($VerifyOnly) { Write-Output 'Verify only: no publication or removal of previous EXEs.' }
    else { Write-Output "Publish: $release ; $downloads" }
    foreach ($folder in @($release,$downloads)) {
        if (!$VerifyOnly) { Old-Executables $folder | ForEach-Object { Write-Output "Remove after success: $($_.FullName)" } }
    }
    Write-Output 'Remove generated staging/cache/build directories after success. Keep source and user data.'
    exit 0
}

if (!(Test-Path -LiteralPath $python)) { throw 'Run setup.bat first to prepare the build environment.' }
Assert-Child $root $stage
Assert-Child $root $release
New-Item -ItemType Directory -Path $stage,$release,(Join-Path $stage 'temp') -Force | Out-Null
$oldTemp = $env:TEMP; $oldTmp = $env:TMP; $oldCache = $env:PYINSTALLER_CONFIG_DIR
try {
    $env:TEMP = Join-Path $stage 'temp'; $env:TMP = $env:TEMP
    $env:PYINSTALLER_CONFIG_DIR = Join-Path $stage 'cache'
    Push-Location $root
    try {
        & $python -m PyInstaller --clean --noconfirm --onefile --windowed --noupx --icon (Join-Path $root 'assets/fco.ico') --name "FCO-Market-$version" --collect-all tesserocr --collect-all webview --hidden-import pythonnet --add-data ((Join-Path $root 'vendor/tessdata') + ';vendor/tessdata') --add-data ((Join-Path $root 'vendor/licenses') + ';vendor/licenses') --add-data ((Join-Path $root 'vendor/ocr-sources.json') + ';vendor') --add-data ((Join-Path $root 'assets') + ';assets') --add-data ((Join-Path $root 'ui') + ';ui') --add-data ((Join-Path $root 'README.md') + ';.') --distpath (Join-Path $stage 'dist') --workpath (Join-Path $stage 'work') --specpath (Join-Path $stage 'spec') (Join-Path $root 'app.py')
        if ($LASTEXITCODE -ne 0) { throw 'Build failed; previous executables are kept.' }
    } finally { Pop-Location }
    $artifact = Join-Path $stage "dist/$name"
    $reportPath = Join-Path $stage ('verify-' + [guid]::NewGuid().ToString('N') + '.json')
    $check = Start-Process -FilePath $artifact -ArgumentList @('--self-test',('"' + $reportPath + '"')) -WindowStyle Hidden -Wait -PassThru
    if ($check.ExitCode -ne 0) { throw 'EXE verification failed; previous executables are kept.' }
    $report = Get-Content -LiteralPath $reportPath -Raw | ConvertFrom-Json
    if ($report.ok -ne $true -or $report.frozen -ne $true -or $report.version -ne $version) {
        throw 'Invalid verification report; previous executables are kept.'
    }
    if ($VerifyOnly) {
        $reports = Join-Path $root 'reports'
        Assert-Child $root $reports
        New-Item -ItemType Directory -Path $reports -Force | Out-Null
        Copy-Item -LiteralPath $reportPath -Destination (Join-Path $reports 'build-self-test.json') -Force
        Remove-Item -LiteralPath $stage -Recurse -Force
        Write-Output "Verified $name. Existing releases are unchanged."
        return
    }
    $hash = (Get-FileHash -LiteralPath $artifact -Algorithm SHA256).Hash
    foreach ($folder in @($release,$downloads)) {
        $target = Join-Path $folder $name
        Assert-Child $folder $target
        $temporary = $target + '.new'
        Assert-Child $folder $temporary
        Copy-Item -LiteralPath $artifact -Destination $temporary -Force
        Move-Item -LiteralPath $temporary -Destination $target -Force
        if ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash -ne $hash) { throw "Publication failed: $target" }
    }
    Copy-Item -LiteralPath $reportPath -Destination (Join-Path $release 'self-test.json') -Force
    # Remove old executables only after both published copies match the verified EXE.
    foreach ($folder in @($release,$downloads)) {
        foreach ($file in @(Old-Executables $folder)) {
            Assert-Child $folder $file.FullName
            Remove-Item -LiteralPath $file.FullName -Force
        }
    }
    foreach ($folder in @($stage,(Join-Path $root 'build'),(Join-Path $root '.pyinstaller-cache'))) {
        Assert-Child $root $folder
        if (Test-Path -LiteralPath $folder) { Remove-Item -LiteralPath $folder -Recurse -Force }
    }
    Write-Output "Verified and published $name. Older FCO builds removed."
} finally {
    $env:TEMP = $oldTemp; $env:TMP = $oldTmp; $env:PYINSTALLER_CONFIG_DIR = $oldCache
}
