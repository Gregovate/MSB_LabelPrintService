# powershell -ExecutionPolicy Bypass -File .\watch_brother_queue.ps1

$PrinterName = "Brother PT-P950NW"
$TimeoutSeconds = 30
$SleepMs = 1000

Write-Host "=================================================="
Write-Host "Brother Queue Watch Test"
Write-Host "Printer: $PrinterName"
Write-Host "Timeout: $TimeoutSeconds seconds"
Write-Host "=================================================="

$start = Get-Date
$seenJob = $false

for ($i = 0; $i -lt $TimeoutSeconds; $i++) {
    $elapsed = [int]((Get-Date) - $start).TotalSeconds

    try {
        $jobs = Get-PrintJob -PrinterName $PrinterName -ErrorAction Stop
    } catch {
        Write-Host "$elapsed s | ERROR reading print jobs: $($_.Exception.Message)"
        Start-Sleep -Milliseconds $SleepMs
        continue
    }

    if ($jobs) {
        $seenJob = $true
        Write-Host "$elapsed s | JOB COUNT: $($jobs.Count)"

        foreach ($job in $jobs) {
            Write-Host ("    JobId={0} Document='{1}' Submitted='{2}'" -f `
                $job.ID, $job.DocumentName, $job.SubmittedTime)
        }
    } else {
        if ($seenJob) {
            Write-Host "$elapsed s | Queue is now EMPTY after previously seeing a job."
            Write-Host "RESULT: Job appeared, then cleared."
            exit 0
        } else {
            Write-Host "$elapsed s | Queue empty."
        }
    }

    Start-Sleep -Milliseconds $SleepMs
}

if (-not $seenJob) {
    Write-Host "RESULT: No job ever appeared in the queue."
    exit 2
} else {
    Write-Host "RESULT: Job appeared but did NOT clear before timeout."
    exit 1
}