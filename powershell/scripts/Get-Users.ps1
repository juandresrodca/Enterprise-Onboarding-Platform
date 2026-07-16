#Requires -Version 7.0
<#
.SYNOPSIS
    Searches Active Directory users.
.DESCRIPTION
    Params: { "query": "smith", "limit": 50, "recentFirst": false }
    Returns summaries in the normalized backend shape.
#>
[CmdletBinding()] param()
Set-StrictMode -Version Latest
Import-Module (Join-Path $PSScriptRoot '..\modules\OnboardingCommon\OnboardingCommon.psd1') -Force

Invoke-OnboardingScript -ScriptName 'Get-Users.ps1' -Main {
    param($Params)
    Assert-ModuleAvailable -Name ActiveDirectory

    $query = [string](Get-ParamValue $Params 'query' '')
    $limit = [int](Get-ParamValue $Params 'limit' 50)
    $recentFirst = [bool](Get-ParamValue $Params 'recentFirst' $false)

    $props = @('DisplayName', 'EmailAddress', 'Department', 'Title', 'Office',
               'Manager', 'whenCreated', 'employeeType', 'GivenName', 'Surname')

    if ($query) {
        # Escape LDAP filter metacharacters (RFC 4515).
        $safe = $query -replace '\\', '\5c' -replace '\*', '\2a' `
                        -replace '\(', '\28' -replace '\)', '\29' -replace "`0", '\00'
        $ldap = "(&(objectCategory=person)(objectClass=user)(|(displayName=*$safe*)(sAMAccountName=*$safe*)(mail=*$safe*)(department=*$safe*)))"
        $users = @(Get-ADUser -LDAPFilter $ldap -Properties $props -ResultSetSize $limit)
    }
    else {
        $users = @(Get-ADUser -Filter 'enabled -eq $true' -Properties $props -ResultSetSize $limit)
    }

    if ($recentFirst) {
        $users = @($users | Sort-Object whenCreated -Descending)
    }

    Write-OnboardingLog -Level INFO -Message "Get-Users returned $($users.Count) users (query='$query')"
    return @{
        users = @($users | ForEach-Object { ConvertTo-OnboardingUser -ADUser $_ -Summary })
    }
}
