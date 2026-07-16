#Requires -Version 7.0
<#
.SYNOPSIS
    Returns one user with full detail: attributes, group memberships,
    licenses (Graph) and shared mailbox permissions (EXO) when available.
.DESCRIPTION
    Params: { "sam": "john.smith", "expand": true }
    Cloud lookups are best-effort: if Graph/EXO sessions are not established
    the corresponding arrays are empty and a WARN log entry explains why.
#>
[CmdletBinding()] param()
Set-StrictMode -Version Latest
Import-Module (Join-Path $PSScriptRoot '..\modules\OnboardingCommon\OnboardingCommon.psd1') -Force

Invoke-OnboardingScript -ScriptName 'Get-User.ps1' -Main {
    param($Params)
    Assert-ModuleAvailable -Name ActiveDirectory

    $sam = Get-ParamValue $Params 'sam'
    if (-not $sam) { Stop-Onboarding -Code 'invalid_params' -Message 'sam is required' }
    $expand = [bool](Get-ParamValue $Params 'expand' $true)

    try {
        $adUser = Get-ADUser -Identity $sam -Properties * -ErrorAction Stop
    }
    catch [Microsoft.ActiveDirectory.Management.ADIdentityNotFoundException] {
        return @{ user = $null }
    }

    $user = ConvertTo-OnboardingUser -ADUser $adUser
    if (-not $expand) { return @{ user = $user } }

    # --- Group memberships (AD) ------------------------------------------------
    $groups = @()
    $groupDetail = @()
    try {
        foreach ($g in @(Get-ADPrincipalGroupMembership -Identity $sam)) {
            $adGroup = Get-ADGroup -Identity $g.DistinguishedName -Properties mail, GroupCategory
            $category = if ($adGroup.GroupCategory -eq 'Distribution') { 'distribution' } else { 'security' }
            $groups += $adGroup.Name
            $groupDetail += @{ name = $adGroup.Name; category = $category }
        }
    }
    catch {
        Write-OnboardingLog -Level WARN -Message "Group lookup failed: $($_.Exception.Message)"
    }

    # --- Licenses + M365 groups (Graph, best-effort) ------------------------------
    $licenses = @()
    $licenseDetail = @()
    if (Get-Command Get-MgUserLicenseDetail -ErrorAction SilentlyContinue) {
        try {
            $mgUser = Get-MgUser -Filter "userPrincipalName eq '$($adUser.UserPrincipalName)'" -ErrorAction Stop
            if ($mgUser) {
                foreach ($lic in @(Get-MgUserLicenseDetail -UserId $mgUser.Id)) {
                    $licenses += $lic.SkuPartNumber
                    $licenseDetail += @{ sku_part_number = $lic.SkuPartNumber; display_name = $lic.SkuPartNumber }
                }
                foreach ($mg in @(Get-MgUserMemberOfAsGroup -UserId $mgUser.Id -ErrorAction Stop)) {
                    if ($mg.GroupTypes -contains 'Unified' -and $groups -notcontains $mg.DisplayName) {
                        $groups += $mg.DisplayName
                        $groupDetail += @{ name = $mg.DisplayName; category = 'm365' }
                    }
                }
            }
        }
        catch {
            Write-OnboardingLog -Level WARN -Message "Graph license/group lookup skipped: $($_.Exception.Message)"
        }
    }

    # --- Shared mailbox permissions (Exchange Online, best-effort) -----------------
    $sharedMailboxes = @()
    if (Get-Command Get-EXOMailboxPermission -ErrorAction SilentlyContinue) {
        try {
            $shared = @(Get-EXOMailbox -RecipientTypeDetails SharedMailbox -ResultSize 200)
            foreach ($mb in $shared) {
                $perm = Get-EXOMailboxPermission -Identity $mb.Identity -User $adUser.UserPrincipalName -ErrorAction SilentlyContinue
                if ($perm) { $sharedMailboxes += $mb.PrimarySmtpAddress }
            }
        }
        catch {
            Write-OnboardingLog -Level WARN -Message "Shared mailbox lookup skipped: $($_.Exception.Message)"
        }
    }

    $user.groups = $groups
    $user.group_detail = $groupDetail
    $user.licenses = $licenses
    $user.license_detail = $licenseDetail
    $user.shared_mailboxes = $sharedMailboxes
    $user.mailbox = [bool]$user.email

    return @{ user = $user }
}
