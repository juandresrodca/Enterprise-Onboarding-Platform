#Requires -Version 7.0
<#
.SYNOPSIS
    Dashboard counters from Active Directory.
.DESCRIPTION
    Params: {} (none)
    Note: user counts use an indexed LDAP query; on very large directories
    consider caching this result in the backend (it changes slowly).
#>
[CmdletBinding()] param()
Set-StrictMode -Version Latest
Import-Module (Join-Path $PSScriptRoot '..\modules\OnboardingCommon\OnboardingCommon.psd1') -Force

Invoke-OnboardingScript -ScriptName 'Get-Stats.ps1' -Main {
    param($Params)
    Assert-ModuleAvailable -Name ActiveDirectory

    $all = @(Get-ADUser -Filter * -Properties whenCreated, employeeType, Enabled)
    $cutoff = (Get-Date).AddDays(-7)
    $recent = @($all | Where-Object { $_.whenCreated -ge $cutoff } |
        Sort-Object whenCreated -Descending)

    $licenses = @()
    if (Get-Command Get-MgSubscribedSku -ErrorAction SilentlyContinue) {
        try {
            $licenses = @(Get-MgSubscribedSku -ErrorAction Stop | ForEach-Object {
                [ordered]@{
                    sku_part_number = $_.SkuPartNumber
                    display_name    = $_.SkuPartNumber
                    total           = [int]$_.PrepaidUnits.Enabled
                    assigned        = [int]$_.ConsumedUnits
                }
            })
        }
        catch {
            Write-OnboardingLog -Level WARN -Message "License stats skipped: $($_.Exception.Message)"
        }
    }

    return @{
        total_users         = $all.Count
        enabled_users       = @($all | Where-Object Enabled).Count
        created_last_7_days = $recent.Count
        contractors         = @($all | Where-Object { $_.employeeType -eq 'Contractor' }).Count
        groups              = @(Get-ADGroup -Filter * -ResultSetSize 5000).Count
        licenses            = $licenses
        recent_users        = @($recent | Select-Object -First 8 | ForEach-Object {
                                  ConvertTo-OnboardingUser -ADUser $_ -Summary
                              })
    }
}
