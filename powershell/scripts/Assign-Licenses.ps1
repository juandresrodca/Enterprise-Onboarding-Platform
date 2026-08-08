#Requires -Version 7.0
<#
.SYNOPSIS
    Lists tenant license SKUs or assigns licenses to a user via Microsoft Graph.
.DESCRIPTION
    Params:
      { "action": "list" }
      { "action": "assign", "sam": "jane.doe", "skus": ["SPE_E3"],
        "defaultUsageLocation": "US" }
      { "action": "revoke", "sam": "jane.doe" }
    A usage location is mandatory before license assignment; the user's AD
    country is used, falling back to defaultUsageLocation. "revoke" removes
    every license currently assigned to the user (offboarding).
    Requires an established Graph session (Connect-Entra.ps1).
#>
[CmdletBinding()] param()
Set-StrictMode -Version Latest
Import-Module (Join-Path $PSScriptRoot '..\modules\OnboardingCommon\OnboardingCommon.psd1') -Force

Invoke-OnboardingScript -ScriptName 'Assign-Licenses.ps1' -Main {
    param($Params)
    Assert-ModuleAvailable -Name Microsoft.Graph.Users
    Assert-ModuleAvailable -Name Microsoft.Graph.Identity.DirectoryManagement

    $action = Get-ParamValue $Params 'action' 'list'

    if ($action -eq 'list') {
        $skus = @(Get-MgSubscribedSku -ErrorAction Stop)
        return @{
            licenses = @($skus | ForEach-Object {
                [ordered]@{
                    sku_id          = $_.SkuId
                    sku_part_number = $_.SkuPartNumber
                    display_name    = $_.SkuPartNumber
                    total           = [int]$_.PrepaidUnits.Enabled
                    assigned        = [int]$_.ConsumedUnits
                }
            })
        }
    }

    if ($action -eq 'revoke') {
        $sam = Get-ParamValue $Params 'sam'
        if (-not $sam) { Stop-Onboarding -Code 'invalid_params' -Message 'sam is required for revoke' }
        Assert-ModuleAvailable -Name ActiveDirectory
        $adUser = Get-ADUser -Identity $sam -Properties UserPrincipalName -ErrorAction Stop
        $mgUser = Get-MgUser -Filter "userPrincipalName eq '$($adUser.UserPrincipalName)'" -Property Id -ErrorAction Stop
        if (-not $mgUser) {
            Write-OnboardingLog -Level WARN -Message "User '$sam' not found in Entra ID; nothing to revoke"
            return @{ revoked = @() }
        }
        $current = @(Get-MgUserLicenseDetail -UserId $mgUser.Id -ErrorAction Stop)
        if ($current.Count -eq 0) { return @{ revoked = @() } }
        $removeIds = @($current | ForEach-Object { $_.SkuId })
        Set-MgUserLicense -UserId $mgUser.Id -AddLicenses @() -RemoveLicenses $removeIds -ErrorAction Stop
        $skus = @($current | ForEach-Object { $_.SkuPartNumber })
        Write-OnboardingLog -Level INFO -Message "Revoked licenses from ${sam}: $($skus -join ', ')"
        return @{ revoked = @($skus) }
    }

    $sam  = Get-ParamValue $Params 'sam'
    $skus = @(Get-ParamValue $Params 'skus' @())
    if (-not $sam -or $skus.Count -eq 0) {
        Stop-Onboarding -Code 'invalid_params' -Message 'sam and skus are required for assign'
    }

    Assert-ModuleAvailable -Name ActiveDirectory
    $adUser = Get-ADUser -Identity $sam -Properties Country -ErrorAction Stop
    $mgUser = Get-MgUser -Filter "userPrincipalName eq '$($adUser.UserPrincipalName)'" `
        -Property Id, UsageLocation -ErrorAction Stop
    if (-not $mgUser) {
        Stop-Onboarding -Code 'not_synced' -Message "User '$sam' has not synchronized to Entra ID yet (check Azure AD Connect cycle)"
    }

    if (-not $mgUser.UsageLocation) {
        $location = $adUser.Country
        if (-not $location) { $location = Get-ParamValue $Params 'defaultUsageLocation' 'US' }
        Update-MgUser -UserId $mgUser.Id -UsageLocation $location -ErrorAction Stop
        Write-OnboardingLog -Level INFO -Message "Set usage location '$location' for $sam"
    }

    $tenantSkus = @(Get-MgSubscribedSku -ErrorAction Stop)
    $addLicenses = @()
    foreach ($sku in $skus) {
        $match = $tenantSkus | Where-Object SkuPartNumber -eq $sku | Select-Object -First 1
        if (-not $match) {
            Stop-Onboarding -Code 'unknown_sku' -Message "License SKU '$sku' not found in tenant"
        }
        if ($match.ConsumedUnits -ge $match.PrepaidUnits.Enabled) {
            Stop-Onboarding -Code 'license_exhausted' -Message "No '$sku' licenses available ($($match.ConsumedUnits)/$($match.PrepaidUnits.Enabled) assigned)"
        }
        $addLicenses += @{ SkuId = $match.SkuId }
    }

    Set-MgUserLicense -UserId $mgUser.Id -AddLicenses $addLicenses -RemoveLicenses @() -ErrorAction Stop
    Write-OnboardingLog -Level INFO -Message "Assigned licenses to ${sam}: $($skus -join ', ')"
    return @{ assigned = @($skus) }
}
