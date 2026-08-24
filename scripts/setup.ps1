# Agent Harness — Windows setup script
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "Creating virtual environment..."
python -m venv .venv

Write-Host "Activating virtual environment..."
& "$Root\.venv\Scripts\Activate.ps1"

Write-Host "Installing dependencies..."
python -m pip install --upgrade pip setuptools wheel
pip install -e ".[dev]"

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host ""
    Write-Host "Created .env from .env.example — add your API keys before running."
}

Write-Host ""
Write-Host "Setup complete."
Write-Host "  Activate:  .\.venv\Scripts\Activate.ps1"
Write-Host "  Test:      pytest -q"
Write-Host "  Run API:   harness-serve"
Write-Host ""
Write-Host "See SETUP.md for API key configuration and usage examples."
