#Requires -Version 7.0
<#
.SYNOPSIS
    Verifies Active Directory connectivity and returns domain information.
.DESCRIPTION
    Params (stdin JSON): { "server": "dc01.corp.local" (optional) }
    Runs under the backend service account (gMSA recommended). Fails fast with
    a precise error code if the ActiveDirectory module or the domain is
    unreachable, so the platform can surface the problem at startup.
#>
[CmdletBinding()] param()
Set-StrictMode -Version Latest
Import-Module (Join-Path $PSScriptRoot '..\modules\OnboardingCommon\OnboardingCommon.psd1') -Force

Invoke-OnboardingScript -ScriptName 'Connect-AD.ps1' -Main {
    param($Params)
    Assert-ModuleAvailable -Name ActiveDirectory

    $server = Get-ParamValue $Params 'server'
    $splat = @{}
    if ($server) { $splat.Server = $server }

    try {
        $domain = Get-ADDomain @splat -ErrorAction Stop
        $dc = Get-ADDomainController -Discover -ErrorAction Stop
    }
    catch {
        Stop-Onboarding -Code 'ad_unreachable' -Message "Cannot reach Active Directory: $($_.Exception.Message)"
    }

    Write-OnboardingLog -Level INFO -Message "Connected to domain $($domain.DNSRoot) via $($dc.HostName)"
    return @{
        domain      = $domain.DNSRoot
        netbios     = $domain.NetBIOSName
        forest      = $domain.Forest
        dn          = $domain.DistinguishedName
        controller  = [string]$dc.HostName
        users_container = $domain.UsersContainer
    }
}
