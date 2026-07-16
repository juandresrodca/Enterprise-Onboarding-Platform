#Requires -Version 7.0
<#
.SYNOPSIS
    Searches AD security/distribution groups and (when Graph is connected)
    Microsoft 365 unified groups.
.DESCRIPTION
    Params: { "search": "finance", "category": "security"|"distribution"|"m365"|null, "limit": 100 }
#>
[CmdletBinding()] param()
Set-StrictMode -Version Latest
Import-Module (Join-Path $PSScriptRoot '..\modules\OnboardingCommon\OnboardingCommon.psd1') -Force

Invoke-OnboardingScript -ScriptName 'Get-Groups.ps1' -Main {
    param($Params)
    Assert-ModuleAvailable -Name ActiveDirectory

    $search   = [string](Get-ParamValue $Params 'search' '')
    $category = Get-ParamValue $Params 'category'
    $limit    = [int](Get-ParamValue $Params 'limit' 100)
    $results  = [System.Collections.Generic.List[object]]::new()

    if ($category -ne 'm365') {
        $filter = if ($search) {
            $safe = $search -replace "'", "''"
            "Name -like '*$safe*' -or Description -like '*$safe*'"
        } else { '*' }
        foreach ($g in @(Get-ADGroup -Filter $filter -Properties Description, mail -ResultSetSize $limit)) {
            $cat = if ($g.GroupCategory -eq 'Distribution') { 'distribution' } else { 'security' }
            if ($category -and $cat -ne $category) { continue }
            $results.Add([ordered]@{
                name         = $g.Name
                category     = $cat
                scope        = [string]$g.GroupScope
                description  = [string]$g.Description
                dn           = $g.DistinguishedName
                member_count = $null   # counting members is expensive at scale
            })
        }
    }

    if (($category -eq 'm365' -or -not $category) -and (Get-Command Get-MgGroup -ErrorAction SilentlyContinue)) {
        try {
            $mgFilter = "groupTypes/any(c:c eq 'Unified')"
            $mgGroups = @(Get-MgGroup -Filter $mgFilter -Top $limit -ErrorAction Stop)
            foreach ($mg in $mgGroups) {
                if ($search -and $mg.DisplayName -notlike "*$search*") { continue }
                $results.Add([ordered]@{
                    name         = $mg.DisplayName
                    category     = 'm365'
                    scope        = 'Universal'
                    description  = [string]$mg.Description
                    dn           = $mg.Id
                    member_count = $null
                })
            }
        }
        catch {
            Write-OnboardingLog -Level WARN -Message "M365 group lookup skipped: $($_.Exception.Message)"
        }
    }

    return @{ groups = @($results | Select-Object -First $limit) }
}
