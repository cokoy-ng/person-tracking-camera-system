param([string]$Port = "COM3")
$ErrorActionPreference = "Stop"
$cli = Join-Path $env:LOCALAPPDATA 'Programs\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe'
if (!(Test-Path $cli)) { throw 'No se encontró arduino-cli.exe instalado.' }
$stage = Join-Path $env:TEMP 'camera-servo-python'
$sketch = Join-Path $stage 'servo_usb'
New-Item -ItemType Directory -Force -Path $sketch | Out-Null
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'firmware\servo_usb\servo_usb.ino') -Destination $sketch -Force
$libraries = Join-Path $env:LOCALAPPDATA 'Arduino15\libraries'
& $cli compile --fqbn arduino:avr:uno --libraries $libraries --upload --verify --port $Port $sketch
exit $LASTEXITCODE
