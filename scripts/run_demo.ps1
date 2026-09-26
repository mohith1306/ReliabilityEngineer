# Start the BRE dashboard in demo mode (simulated Bob) on http://127.0.0.1:8000
#   .\scripts\run_demo.ps1            simulated Bob
#   .\scripts\run_demo.ps1 -Live      real IBM Bob (needs Bob Shell on PATH and BOB_API_KEY set)
param([switch]$Live, [int]$Port = 8000)
$env:BRE_DEMO = "1"
$env:BRE_DEMO_DIR = Join-Path $env:TEMP "bre-demo"
$env:BRE_OPERATOR_KEY = "demo-operator-key"
$env:BRE_OPERATOR_NAME = "Demo operator"
$env:BRE_DEMO_SHOW_KEY = "1"
$env:BRE_TAU = "0.30"
if ($Live) { Remove-Item Env:BRE_BOB_TRANSPORT -ErrorAction SilentlyContinue } else { $env:BRE_BOB_TRANSPORT = "replay" }
$py = if (Test-Path "venv\Scripts\python.exe") { "venv\Scripts\python.exe" } else { "python" }
Write-Host "BRE dashboard: http://127.0.0.1:$Port   (Bob: $(if ($Live) {'LIVE'} else {'SIMULATED'}))" -ForegroundColor Cyan
& $py -m uvicorn apps.api.main:app --host 127.0.0.1 --port $Port
