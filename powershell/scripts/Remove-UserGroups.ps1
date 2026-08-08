#Requires -Version 7.0
<#
.SYNOPSIS
    Removes a user from all group memberships as part of offboarding.
.DESCRIPTION
    Params: { "sam": "jane.doe", "keepDistributionLists": true }
    Removes AD security-group and (via Graph) M365 unified-group membership.
    When keepDistributionLists is true, distribution-list membership is left
    in place - departed employees commonly stay on announcement/newsletter
    lists briefly during handover; only security and M365 groups are removed.
    The primary group (usually Domain Users) is never touched - AD requires
    every account to keep exactly one, and Remove-ADGroupMember cannot
    remove it anyway.
#>
[CmdletBinding()] param()
Set-StrictMode -Version Latest
Import-Module (Join-Path $PSScriptRoot '..\modules\OnboardingCommon\OnboardingCommon.psd1') -Force

Invoke-OnboardingScript -ScriptName 'Remove-UserGroups.ps1' -Main {
    param($Params)
    Assert-ModuleAvailable -Name ActiveDirectory

    $sam = Get-ParamValue $Params 'sam'
    if (-not $sam) { Stop-Onboarding -Code 'invalid_params' -Message 'sam is required' }
    $keepDistributionLists = [bool](Get-ParamValue $Params 'keepDistributionLists' $true)

    $adUser = Get-ADUser -Identity $sam -Properties primaryGroupID -ErrorAction Stop
    $removed = [System.Collections.Generic.List[string]]::new()

    foreach ($membership in @(Get-ADPrincipalGroupMembership -Identity $sam)) {
        $adGroup = Get-ADGroup -Identity $membership.DistinguishedName -Properties GroupCategory, primaryGroupToken
        # The primary group cannot be removed via Remove-ADGroupMember (AD requires exactly one).
        if ($adGroup.primaryGroupToken -eq $adUser.primaryGroupID) { continue }
        if ($keepDistributionLists -and $adGroup.GroupCategory -eq 'Distribution') { continue }
        try {
            Remove-ADGroupMember -Identity $adGroup -Members $adUser -Confirm:$false -ErrorAction Stop
            $removed.Add($adGroup.Name)
            Write-OnboardingLog -Level INFO -Message "Removed $sam from AD group $($adGroup.Name)"
        }
        catch {
            Write-OnboardingLog -Level WARN -Message "Failed removing $sam from '$($adGroup.Name)': $($_.Exception.Message)"
        }
    }

    # M365 unified groups aren't visible to Get-ADPrincipalGroupMembership - Graph, best-effort.
    if (Get-Command Get-MgUserMemberOfAsGroup -ErrorAction SilentlyContinue) {
        try {
            $mgUser = Get-MgUser -Filter "userPrincipalName eq '$($adUser.UserPrincipalName)'" -ErrorAction Stop
            if ($mgUser) {
                foreach ($mg in @(Get-MgUserMemberOfAsGroup -UserId $mgUser.Id -ErrorAction Stop)) {
                    if ($mg.GroupTypes -contains 'Unified') {
                        Remove-MgGroupMemberByRef -GroupId $mg.Id -DirectoryObjectId $mgUser.Id -ErrorAction Stop
                        $removed.Add($mg.DisplayName)
                        Write-OnboardingLog -Level INFO -Message "Removed $sam from M365 group $($mg.DisplayName)"
                    }
                }
            }
        }
        catch {
            Write-OnboardingLog -Level WARN -Message "M365 group removal skipped: $($_.Exception.Message)"
        }
    }

    return @{ removed = @($removed) }
}
