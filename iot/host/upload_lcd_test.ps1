param([string]$Port, [switch]$CompileOnly, [switch]$Fixed)
$ErrorActionPreference = 'Stop'
if (!$CompileOnly -and [string]::IsNullOrWhiteSpace($Port)) { throw 'Indica el puerto de la placa dedicada al LCD. No usar la placa del criadero.' }
$cli = Join-Path $env:LOCALAPPDATA 'Programs\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe'
$name = if ($Fixed) { 'lcd_fixed_test' } else { 'lcd_test' }
$source = Join-Path $PSScriptRoot "..\firmware\$name"
$sketch = Join-Path $env:TEMP "camera-lcd-only\$name"
New-Item -ItemType Directory -Force -Path $sketch | Out-Null
Copy-Item -LiteralPath (Join-Path $source "$name.ino") -Destination $sketch -Force
& $cli compile --fqbn arduino:avr:uno $sketch
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
if (!$CompileOnly) {
  & $cli upload --fqbn arduino:avr:uno --verify --port $Port $sketch
  exit $LASTEXITCODE
}
