#Requires -Version 7.0
<#
.SYNOPSIS
    Appends an audit entry to the DC-side JSONL audit trail.
.DESCRIPTION
    Params: { "entry": { actor, action, target, status, details } }
    This complements the platform's SQLite audit store with an on-host record
    (useful when scripts run on a jump host near the DC and the security team
    ships local files to the SIEM).
#>
[CmdletBinding()] param()
Set-StrictMode -Version Latest
Import-Module (Join-Path $PSScriptRoot '..\modules\OnboardingCommon\OnboardingCommon.psd1') -Force

Invoke-OnboardingScript -ScriptName 'Audit.ps1' -Main {
    param($Params)
    $entry = Get-ParamValue $Params 'entry'
    if (-not $entry) { Stop-Onboarding -Code 'invalid_params' -Message 'entry is required' }

    $record = [ordered]@{
        ts       = (Get-Date).ToUniversalTime().ToString('o')
        computer = $env:COMPUTERNAME
        actor    = [string](Get-ParamValue $entry 'actor' 'unknown')
        action   = [string](Get-ParamValue $entry 'action' 'unknown')
        target   = [string](Get-ParamValue $entry 'target' '')
        status   = [string](Get-ParamValue $entry 'status' 'success')
        details  = Get-ParamValue $entry 'details'
    }

    $dir = Get-OnboardingLogDirectory
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    $file = Join-Path $dir 'audit-ps.jsonl'
    $mutex = [System.Threading.Mutex]::new($false, 'Global\EIOAuditLog')
    [void]$mutex.WaitOne(2000)
    try { Add-Content -LiteralPath $file -Value ($record | ConvertTo-Json -Compress -Depth 8) -Encoding UTF8 }
    finally { $mutex.ReleaseMutex(); $mutex.Dispose() }

    return @{ written = $true; file = $file }
}
