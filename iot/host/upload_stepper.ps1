param([string]$Port, [switch]$CompileOnly)
$ErrorActionPreference = "Stop"
if (!$CompileOnly -and [string]::IsNullOrWhiteSpace($Port)) {
    throw 'Indica el puerto actual con -Port COMx o usa -CompileOnly.'
}
$cli = Join-Path $env:LOCALAPPDATA 'Programs\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe'
if (!(Test-Path $cli)) { throw 'No se encontró arduino-cli.exe instalado.' }
$sketch = Join-Path $env:TEMP 'camera-stepper-test\stepper_test'
New-Item -ItemType Directory -Force -Path $sketch | Out-Null
$source = Join-Path $PSScriptRoot '..\firmware\stepper_test\stepper_test.ino'
Copy-Item -LiteralPath $source -Destination $sketch -Force
& $cli compile --fqbn arduino:avr:uno $sketch
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
if (!$CompileOnly) {
    & $cli upload --fqbn arduino:avr:uno --verify --port $Port $sketch
    exit $LASTEXITCODE
}
exit 0
