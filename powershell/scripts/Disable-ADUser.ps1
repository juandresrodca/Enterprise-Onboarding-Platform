#Requires -Version 7.0
<#
.SYNOPSIS
    Disables an Active Directory user account for offboarding.
.DESCRIPTION
    Params: { "sam": "jane.doe", "moveToOu": "OU=Disabled Users,DC=...", "resetPassword": true }
    Disables sign-in (Disable-ADAccount), optionally relocates the account to
    a disabled-users OU (Move-ADObject) and randomizes the password so no
    stale credential remains usable if the account is ever re-enabled by
    mistake. The random password is generated, applied, and discarded in the
    same scope - it is never returned, logged, or persisted anywhere.
#>
[CmdletBinding()] param()
Set-StrictMode -Version Latest
Import-Module (Join-Path $PSScriptRoot '..\modules\OnboardingCommon\OnboardingCommon.psd1') -Force

Invoke-OnboardingScript -ScriptName 'Disable-ADUser.ps1' -Main {
    param($Params)
    Assert-ModuleAvailable -Name ActiveDirectory

    $sam = Get-ParamValue $Params 'sam'
    if (-not $sam) { Stop-Onboarding -Code 'invalid_params' -Message 'sam is required' }
    $moveToOu = Get-ParamValue $Params 'moveToOu'
    $resetPassword = [bool](Get-ParamValue $Params 'resetPassword' $true)

    $adUser = Get-ADUser -Identity $sam -Properties Enabled -ErrorAction Stop
    if (-not $adUser.Enabled) {
        Stop-Onboarding -Code 'already_disabled' -Message "User '$sam' is already disabled"
    }

    Disable-ADAccount -Identity $adUser -ErrorAction Stop
    Write-OnboardingLog -Level INFO -Message "Disabled account $sam"

    if ($resetPassword) {
        $bytes = [byte[]]::new(24)
        [System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
        $randomPassword = [Convert]::ToBase64String($bytes)
        $secure = ConvertTo-SecureString -String $randomPassword -AsPlainText -Force
        try {
            Set-ADAccountPassword -Identity $adUser -Reset -NewPassword $secure -ErrorAction Stop
            Write-OnboardingLog -Level INFO -Message "Password randomized for $sam"
        }
        finally {
            $secure.Dispose()
            $randomPassword = $null
        }
    }

    if ($moveToOu) {
        try {
            Move-ADObject -Identity $adUser.DistinguishedName -TargetPath $moveToOu -ErrorAction Stop
            Write-OnboardingLog -Level INFO -Message "Moved $sam to $moveToOu"
        }
        catch {
            Stop-Onboarding -Code 'move_failed' -Message "Failed to move '$sam' to '$moveToOu': $($_.Exception.Message)"
        }
    }

    $updated = Get-ADUser -Identity $sam -Properties DisplayName, EmailAddress, Department, Title, Office, whenCreated, employeeType, Enabled
    return @{ user = (ConvertTo-OnboardingUser -ADUser $updated -Summary) }
}
