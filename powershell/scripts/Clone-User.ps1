#Requires -Version 7.0
<#
.SYNOPSIS
    Gathers the complete, copyable attribute bundle of a template user.
.DESCRIPTION
    Params: { "sourceSam": "john.smith" }
    Returns the source user fully expanded (attributes, groups, licenses,
    shared mailboxes, proxy addresses, extension attributes). The backend
    merges this bundle into the new user specs according to the clone options
    chosen by the administrator; protected identity attributes (SID, GUID,
    password, username, email, employeeID, displayName, personal data) are
    excluded by the backend merge logic and are never applied to new users.
#>
[CmdletBinding()] param()
Set-StrictMode -Version Latest
Import-Module (Join-Path $PSScriptRoot '..\modules\OnboardingCommon\OnboardingCommon.psd1') -Force

Invoke-OnboardingScript -ScriptName 'Clone-User.ps1' -Main {
    param($Params)
    $sourceSam = Get-ParamValue $Params 'sourceSam'
    if (-not $sourceSam) { Stop-Onboarding -Code 'invalid_params' -Message 'sourceSam is required' }

    # Reuse Get-User.ps1's expansion logic by invoking it in-process.
    $getUser = Join-Path $PSScriptRoot 'Get-User.ps1'
    $json = @{ sam = $sourceSam; expand = $true } | ConvertTo-Json -Compress
    $result = $json | pwsh -NoProfile -NonInteractive -File $getUser | Select-Object -Last 1 | ConvertFrom-Json
    if (-not $result.success) {
        Stop-Onboarding -Code $result.error.code -Message $result.error.message
    }
    if (-not $result.data.user) {
        Stop-Onboarding -Code 'not_found' -Message "Source user '$sourceSam' not found"
    }

    Write-OnboardingLog -Level INFO -Message "Clone bundle gathered for $sourceSam"
    return @{ source = $result.data.user }
}
