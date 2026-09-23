param([string]$Port = "COM3", [switch]$CompileOnly)
$ErrorActionPreference = "Stop"
$cli = Join-Path $env:LOCALAPPDATA 'Programs\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe'
if (!(Test-Path $cli)) { throw 'No se encontró arduino-cli.exe instalado.' }
$stage = Join-Path $env:TEMP 'camera-servo-python'
$sketch = Join-Path $stage 'servo_usb'
New-Item -ItemType Directory -Force -Path $sketch | Out-Null
$firmware = Join-Path $PSScriptRoot '..\firmware\servo_usb'
foreach ($name in 'servo_usb.ino', 'pins.h', 'servo_control.h', 'relay_light.h', 'sound_sensor.h', 'dht11_sensor.h') {
    Copy-Item -LiteralPath (Join-Path $firmware $name) -Destination $sketch -Force
}
$libraries = Join-Path $env:LOCALAPPDATA 'Arduino15\libraries'
if ($CompileOnly) {
    & $cli compile --fqbn arduino:avr:uno --libraries $libraries $sketch
} else {
    & $cli compile --fqbn arduino:avr:uno --libraries $libraries --upload --verify --port $Port $sketch
}
exit $LASTEXITCODE
