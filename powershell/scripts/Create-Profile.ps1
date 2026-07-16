#Requires -Version 7.0
<#
.SYNOPSIS
    Configures roaming profile path and logon script on the AD account.
.DESCRIPTION
    Params: { "sam": "jane.doe",
              "roaming_profile_path": "\\\\FS01\\Profiles\\jane.doe",
              "logon_script": "logon.bat" }
    Either field may be omitted; only provided fields are set.
#>
[CmdletBinding()] param()
Set-StrictMode -Version Latest
Import-Module (Join-Path $PSScriptRoot '..\modules\OnboardingCommon\OnboardingCommon.psd1') -Force

Invoke-OnboardingScript -ScriptName 'Create-Profile.ps1' -Main {
    param($Params)
    Assert-ModuleAvailable -Name ActiveDirectory

    $sam = Get-ParamValue $Params 'sam'
    if (-not $sam) { Stop-Onboarding -Code 'invalid_params' -Message 'sam is required' }
    $profilePath = Get-ParamValue $Params 'roaming_profile_path'
    $logonScript = Get-ParamValue $Params 'logon_script'
    if (-not $profilePath -and -not $logonScript) {
        Stop-Onboarding -Code 'invalid_params' -Message 'Provide roaming_profile_path and/or logon_script'
    }

    $splat = @{ Identity = $sam; ErrorAction = 'Stop' }
    if ($profilePath) { $splat.ProfilePath = $profilePath }
    if ($logonScript) { $splat.ScriptPath = $logonScript }
    Set-ADUser @splat

    Write-OnboardingLog -Level INFO -Message "Profile configured for $sam" `
        -Context @{ profile_path = $profilePath; logon_script = $logonScript }
    return @{
        profile = @{
            roaming_profile_path = $profilePath
            logon_script         = $logonScript
        }
    }
}
