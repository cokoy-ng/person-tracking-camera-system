param([string]$Port, [switch]$CompileOnly)
$ErrorActionPreference = "Stop"
if (!$CompileOnly -and [string]::IsNullOrWhiteSpace($Port)) {
    throw 'Indica el puerto actual con -Port COMx o usa -CompileOnly.'
}
$cli = Join-Path $env:LOCALAPPDATA 'Programs\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe'
if (!(Test-Path $cli)) { throw 'No se encontró arduino-cli.exe instalado.' }
$sketch = Join-Path $env:TEMP 'camera-brooder\brooder'
New-Item -ItemType Directory -Force -Path $sketch | Out-Null
 $source = Join-Path $PSScriptRoot '..\firmware\brooder'
foreach ($name in 'brooder.ino', 'config.h', 'control.h', 'door.h', 'protocol.h', 'dht11_sensor.h') {
    Copy-Item -LiteralPath (Join-Path $source $name) -Destination $sketch -Force
}
& $cli compile --fqbn arduino:avr:uno $sketch
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
if (!$CompileOnly) {
    & $cli upload --fqbn arduino:avr:uno --verify --port $Port $sketch
    exit $LASTEXITCODE
}
exit 0
