#Requires -Version 7.0
<#
.SYNOPSIS
    Server-side existence checks used by the backend validation service.
.DESCRIPTION
    Params (one "check" per call):
      { "check": "identity", "sam": "x", "upn": "x@corp.com", "email": "x@corp.com" }
      { "check": "manager", "manager": "sam-or-upn" }
      { "check": "ou", "ou": "OU=...,DC=..." }
      { "check": "groups", "groups": ["SG-A", "SG-B"] }
      { "check": "employeeId", "employeeId": "EMP-1234" }
#>
[CmdletBinding()] param()
Set-StrictMode -Version Latest
Import-Module (Join-Path $PSScriptRoot '..\modules\OnboardingCommon\OnboardingCommon.psd1') -Force

Invoke-OnboardingScript -ScriptName 'Validation.ps1' -Main {
    param($Params)
    Assert-ModuleAvailable -Name ActiveDirectory

    $check = Get-ParamValue $Params 'check'
    switch ($check) {
        'identity' {
            $clauses = @()
            foreach ($pair in @(
                @{ attr = 'sAMAccountName';    value = Get-ParamValue $Params 'sam' },
                @{ attr = 'userPrincipalName'; value = Get-ParamValue $Params 'upn' },
                @{ attr = 'mail';              value = Get-ParamValue $Params 'email' },
                @{ attr = 'proxyAddresses';    value = if (Get-ParamValue $Params 'email') { "smtp:$(Get-ParamValue $Params 'email')" } else { $null } }
            )) {
                if ($pair.value) { $clauses += "($($pair.attr)=$($pair.value))" }
            }
            if ($clauses.Count -eq 0) { return @{ exists = $false } }
            $ldap = "(|$($clauses -join ''))"
            $found = Get-ADUser -LDAPFilter $ldap -ResultSetSize 1
            return @{ exists = [bool]$found }
        }
        'manager' {
            $ref = Get-ParamValue $Params 'manager'
            if (-not $ref) { return @{ manager = $null } }
            $safe = $ref -replace '\\', '\5c' -replace '\*', '\2a' -replace '\(', '\28' -replace '\)', '\29'
            $found = Get-ADUser -LDAPFilter "(|(sAMAccountName=$safe)(userPrincipalName=$safe))" `
                -Properties DisplayName -ResultSetSize 1
            if (-not $found) { return @{ manager = $null } }
            return @{ manager = (ConvertTo-OnboardingUser -ADUser $found -Summary) }
        }
        'ou' {
            $dn = Get-ParamValue $Params 'ou'
            $exists = $false
            if ($dn) {
                try { $exists = [bool](Get-ADOrganizationalUnit -Identity $dn -ErrorAction Stop) }
                catch { $exists = $false }
            }
            return @{ exists = $exists }
        }
        'groups' {
            $names = @(Get-ParamValue $Params 'groups' @())
            $missing = [System.Collections.Generic.List[string]]::new()
            foreach ($name in $names) {
                $safe = $name -replace "'", "''"
                $found = Get-ADGroup -Filter "Name -eq '$safe'" -ErrorAction SilentlyContinue
                if (-not $found -and (Get-Command Get-MgGroup -ErrorAction SilentlyContinue)) {
                    try {
                        $found = Get-MgGroup -Filter "displayName eq '$safe'" -ErrorAction Stop | Select-Object -First 1
                    } catch { $found = $null }
                }
                if (-not $found) { $missing.Add($name) }
            }
            return @{ missing = @($missing) }
        }
        'employeeId' {
            $id = Get-ParamValue $Params 'employeeId'
            if (-not $id) { return @{ exists = $false } }
            $found = Get-ADUser -Filter "EmployeeID -eq '$($id -replace "'", "''")'" -ResultSetSize 1
            return @{ exists = [bool]$found }
        }
        default {
            Stop-Onboarding -Code 'invalid_params' -Message "Unknown check '$check'"
        }
    }
}
