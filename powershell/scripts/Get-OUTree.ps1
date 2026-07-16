#Requires -Version 7.0
<#
.SYNOPSIS
    Returns the full organizational unit tree.
.DESCRIPTION
    Params: {} (none)
    Output: { "tree": [ { name, dn, children: [...] } ] }
#>
[CmdletBinding()] param()
Set-StrictMode -Version Latest
Import-Module (Join-Path $PSScriptRoot '..\modules\OnboardingCommon\OnboardingCommon.psd1') -Force

Invoke-OnboardingScript -ScriptName 'Get-OUTree.ps1' -Main {
    param($Params)
    Assert-ModuleAvailable -Name ActiveDirectory

    $ous = @(Get-ADOrganizationalUnit -Filter * -Properties Name | Sort-Object DistinguishedName)
    $nodes = @{}
    $roots = [System.Collections.Generic.List[object]]::new()

    foreach ($ou in $ous) {
        $nodes[$ou.DistinguishedName] = [ordered]@{
            name     = $ou.Name
            dn       = $ou.DistinguishedName
            children = [System.Collections.Generic.List[object]]::new()
        }
    }
    foreach ($ou in $ous) {
        $parentDn = ($ou.DistinguishedName -replace '^OU=[^,]+,', '')
        if ($nodes.ContainsKey($parentDn)) {
            $nodes[$parentDn].children.Add($nodes[$ou.DistinguishedName])
        }
        else {
            $roots.Add($nodes[$ou.DistinguishedName])
        }
    }

    Write-OnboardingLog -Level INFO -Message "OU tree built: $($ous.Count) OUs"
    return @{ tree = @($roots) }
}
