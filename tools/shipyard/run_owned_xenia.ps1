param(
    [UInt64]$CpuAffinityMask = 4294901760,
    [int]$StartupWaitSeconds = 12
)

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
$runtime = Join-Path $projectRoot 'scratch\runtime'
$emulator = Join-Path $runtime 'xenia\xenia_canary.exe'
$executable = Join-Path $runtime '3Shipsty\3Shipsty.xex'
if (-not (Test-Path -LiteralPath $emulator -PathType Leaf)) { throw "Owned Xenia missing: $emulator" }
if (-not (Test-Path -LiteralPath $executable -PathType Leaf)) { throw "Staged XEX missing: $executable" }

$process = Start-Process -FilePath $emulator -ArgumentList $executable `
    -WorkingDirectory (Join-Path $runtime 'xenia') -WindowStyle Normal -PassThru
$process.ProcessorAffinity = [IntPtr]::new([Int64]$CpuAffinityMask)
$process.Refresh()
if ($process.ProcessorAffinity.ToInt64() -ne [Int64]$CpuAffinityMask) {
    throw 'Owned Xenia affinity was not applied'
}

Start-Sleep -Seconds $StartupWaitSeconds
$process.Refresh()
if (-not $process.HasExited -and $process.ProcessorAffinity.ToInt64() -ne [Int64]$CpuAffinityMask) {
    $process.ProcessorAffinity = [IntPtr]::new([Int64]$CpuAffinityMask)
    $process.Refresh()
    if ($process.ProcessorAffinity.ToInt64() -ne [Int64]$CpuAffinityMask) {
        throw 'Owned Xenia affinity did not persist after startup'
    }
}

if ($process.HasExited) { throw "Owned Xenia exited during startup: PID $($process.Id)" }
'Owned Xenia PID {0}; affinity 0x{1:X8}' -f $process.Id, $process.ProcessorAffinity.ToInt64()
