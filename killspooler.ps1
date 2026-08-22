# ============================================================
# KillSpooler.ps1
# Purpose:
#   Force-clear Windows print spooler and stuck jobs
# ============================================================

Write-Host "Stopping Print Spooler..."
Stop-Service Spooler -Force -ErrorAction SilentlyContinue

# Give Windows a moment to release handles
Start-Sleep -Seconds 2

Write-Host "Killing any lingering spooler process..."
Get-Process spoolsv -ErrorAction SilentlyContinue | Stop-Process -Force

# Another short pause to ensure process is gone
Start-Sleep -Seconds 1

Write-Host "Clearing spool directory..."
$spoolPath = "$env:SystemRoot\System32\spool\PRINTERS\*"
Remove-Item $spoolPath -Force -Recurse -ErrorAction SilentlyContinue

Write-Host "Starting Print Spooler..."
Start-Service Spooler

Write-Host "Spooler reset complete."