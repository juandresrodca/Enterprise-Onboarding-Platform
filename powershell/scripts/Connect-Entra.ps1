#Requires -Version 7.0
<#
.SYNOPSIS
    Establishes an app-only Microsoft Graph session for Entra ID operations.
.DESCRIPTION
    Params (stdin JSON):
      { "tenantId": "...", "clientId": "...", "certThumbprint": "..." }
    Authentication order:
      1. Certificate (certThumbprint) - recommended for production.
      2. Client secret from the EIO_GRAPH_CLIENT_SECRET environment variable
         (never passed as a parameter; injected by the service host / vault).
    Required Graph application permissions:
      User.ReadWrite.All, Group.ReadWrite.All, Organization.Read.All,
      Directory.ReadWrite.All (licenses).
#>
[CmdletBinding()] param()
Set-StrictMode -Version Latest
Import-Module (Join-Path $PSScriptRoot '..\modules\OnboardingCommon\OnboardingCommon.psd1') -Force

Invoke-OnboardingScript -ScriptName 'Connect-Entra.ps1' -Main {
    param($Params)
    Assert-ModuleAvailable -Name Microsoft.Graph.Authentication

    $tenantId = Get-ParamValue $Params 'tenantId'
    $clientId = Get-ParamValue $Params 'clientId'
    $thumb    = Get-ParamValue $Params 'certThumbprint'
    if (-not $tenantId -or -not $clientId) {
        Stop-Onboarding -Code 'invalid_params' -Message 'tenantId and clientId are required'
    }

    try {
        if ($thumb) {
            Connect-MgGraph -TenantId $tenantId -ClientId $clientId `
                -CertificateThumbprint $thumb -NoWelcome -ErrorAction Stop
        }
        elseif ($env:EIO_GRAPH_CLIENT_SECRET) {
            $secure = ConvertTo-SecureString $env:EIO_GRAPH_CLIENT_SECRET -AsPlainText -Force
            $credential = [pscredential]::new($clientId, $secure)
            Connect-MgGraph -TenantId $tenantId -ClientSecretCredential $credential `
                -NoWelcome -ErrorAction Stop
        }
        else {
            Stop-Onboarding -Code 'missing_credential' -Message 'Provide certThumbprint or set EIO_GRAPH_CLIENT_SECRET'
        }
    }
    catch [System.InvalidOperationException] { throw }
    catch {
        Stop-Onboarding -Code 'graph_auth_failed' -Message "Graph sign-in failed: $($_.Exception.Message)"
    }

    $ctx = Get-MgContext
    Write-OnboardingLog -Level INFO -Message "Graph connected to tenant $($ctx.TenantId)"
    return @{
        tenant_id = $ctx.TenantId
        client_id = $ctx.ClientId
        scopes    = @($ctx.Scopes)
        auth_type = [string]$ctx.AuthType
    }
}
