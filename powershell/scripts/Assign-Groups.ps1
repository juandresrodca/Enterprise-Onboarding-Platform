#Requires -Version 7.0
<#
.SYNOPSIS
    Adds a user to AD groups and (via Graph) Microsoft 365 unified groups.
.DESCRIPTION
    Params: { "sam": "jane.doe", "groups": ["SG-Finance-Users", "M365-Project-Phoenix"] }
    Groups are resolved in AD first; names not found in AD are attempted as
    M365 unified groups through Graph. Partial failures are reported per group.
#>
[CmdletBinding()] param()
Set-StrictMode -Version Latest
Import-Module (Join-Path $PSScriptRoot '..\modules\OnboardingCommon\OnboardingCommon.psd1') -Force

Invoke-OnboardingScript -ScriptName 'Assign-Groups.ps1' -Main {
    param($Params)
    Assert-ModuleAvailable -Name ActiveDirectory

    $sam    = Get-ParamValue $Params 'sam'
    $groups = @(Get-ParamValue $Params 'groups' @())
    if (-not $sam -or $groups.Count -eq 0) {
        Stop-Onboarding -Code 'invalid_params' -Message 'sam and groups are required'
    }

    $adUser = Get-ADUser -Identity $sam -ErrorAction Stop
    $added  = [System.Collections.Generic.List[string]]::new()
    $failed = [System.Collections.Generic.List[object]]::new()

    foreach ($name in $groups) {
        try {
            $adGroup = Get-ADGroup -Filter "Name -eq '$($name -replace "'", "''")'" -ErrorAction Stop
            if ($adGroup) {
                Add-ADGroupMember -Identity $adGroup -Members $adUser -ErrorAction Stop
                $added.Add($name)
                Write-OnboardingLog -Level INFO -Message "Added $sam to AD group $name"
                continue
            }
            # Not in AD: try as an M365 unified group via Graph.
            if (Get-Command Get-MgGroup -ErrorAction SilentlyContinue) {
                $safe = $name -replace "'", "''"
                $mgGroup = Get-MgGroup -Filter "displayName eq '$safe'" -ErrorAction Stop | Select-Object -First 1
                if ($mgGroup) {
                    $mgUser = Get-MgUser -Filter "userPrincipalName eq '$($adUser.UserPrincipalName)'" -ErrorAction Stop
                    New-MgGroupMember -GroupId $mgGroup.Id -DirectoryObjectId $mgUser.Id -ErrorAction Stop
                    $added.Add($name)
                    Write-OnboardingLog -Level INFO -Message "Added $sam to M365 group $name"
                    continue
                }
            }
            $failed.Add(@{ group = $name; error = 'group not found' })
        }
        catch {
            $failed.Add(@{ group = $name; error = $_.Exception.Message })
            Write-OnboardingLog -Level WARN -Message "Failed adding $sam to '$name': $($_.Exception.Message)"
        }
    }

    if ($added.Count -eq 0 -and $failed.Count -gt 0) {
        Stop-Onboarding -Code 'groups_failed' -Message "No groups could be assigned: $(($failed | ForEach-Object { $_.group }) -join ', ')"
    }
    return @{ added = @($added); failed = @($failed) }
}
