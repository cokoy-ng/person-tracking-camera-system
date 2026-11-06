param([string]$Port, [switch]$CompileOnly)
$ErrorActionPreference = 'Stop'
if (!$CompileOnly -and [string]::IsNullOrWhiteSpace($Port)) {
    throw 'Indica el puerto actual con -Port COMx o usa -CompileOnly.'
}
$cli = Join-Path $env:LOCALAPPDATA 'Programs\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe'
if (!(Test-Path $cli)) { throw 'No se encontró arduino-cli.exe instalado.' }
$sketch = Join-Path $env:TEMP 'camera-sg90-test\sg90_test'
New-Item -ItemType Directory -Force -Path $sketch | Out-Null
Copy-Item -LiteralPath (Join-Path $PSScriptRoot '..\firmware\sg90_test\sg90_test.ino') -Destination $sketch -Force
$libraries = Join-Path $env:LOCALAPPDATA 'Arduino15\libraries'
& $cli compile --fqbn arduino:avr:uno --libraries $libraries $sketch
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
if (!$CompileOnly) {
    & $cli upload --fqbn arduino:avr:uno --verify --port $Port $sketch
    exit $LASTEXITCODE
}
exit 0
