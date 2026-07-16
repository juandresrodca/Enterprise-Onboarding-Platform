#Requires -Version 7.0
<#
.SYNOPSIS
    Mailbox provisioning: remote (hybrid) mailbox creation, shared mailbox
    access grants, and shared mailbox listing.
.DESCRIPTION
    Params:
      { "action": "create", "sam": "jane.doe",
        "remoteRoutingDomain": "contoso.mail.onmicrosoft.com" }
      { "action": "grant-shared", "sam": "jane.doe",
        "mailboxes": ["finance-invoices@contoso.com"] }
      { "action": "list-shared" }
    Notes:
      * In hybrid environments, Enable-RemoteMailbox (Exchange Management
        Tools) creates the on-prem stub; the cloud mailbox materializes once
        a license lands after AAD Connect sync.
      * In cloud-only tenants, Exchange Online provisions the mailbox
        automatically when an Exchange-bearing license is assigned; "create"
        then simply verifies/records that state.
      * grant-shared/list-shared require an ExchangeOnlineManagement session.
#>
[CmdletBinding()] param()
Set-StrictMode -Version Latest
Import-Module (Join-Path $PSScriptRoot '..\modules\OnboardingCommon\OnboardingCommon.psd1') -Force

Invoke-OnboardingScript -ScriptName 'Create-Mailbox.ps1' -Main {
    param($Params)
    $action = Get-ParamValue $Params 'action' 'create'

    if ($action -eq 'list-shared') {
        Assert-ModuleAvailable -Name ExchangeOnlineManagement
        $shared = @(Get-EXOMailbox -RecipientTypeDetails SharedMailbox -ResultSize 500 -ErrorAction Stop)
        return @{
            mailboxes = @($shared | ForEach-Object {
                @{ name = $_.DisplayName; email = [string]$_.PrimarySmtpAddress }
            })
        }
    }

    $sam = Get-ParamValue $Params 'sam'
    if (-not $sam) { Stop-Onboarding -Code 'invalid_params' -Message 'sam is required' }
    Assert-ModuleAvailable -Name ActiveDirectory
    $adUser = Get-ADUser -Identity $sam -Properties EmailAddress -ErrorAction Stop

    if ($action -eq 'create') {
        if (Get-Command Enable-RemoteMailbox -ErrorAction SilentlyContinue) {
            $routingDomain = Get-ParamValue $Params 'remoteRoutingDomain'
            if (-not $routingDomain) {
                Stop-Onboarding -Code 'invalid_params' -Message 'remoteRoutingDomain is required for hybrid mailbox creation'
            }
            $routing = "$sam@$routingDomain"
            Enable-RemoteMailbox -Identity $sam -RemoteRoutingAddress $routing -ErrorAction Stop | Out-Null
            Write-OnboardingLog -Level INFO -Message "Remote mailbox enabled for $sam ($routing)"
            return @{ mailbox = @{ email = $adUser.UserPrincipalName; type = 'RemoteUserMailbox'; routing_address = $routing } }
        }
        # Cloud-only: license-driven provisioning; verify via EXO when possible.
        if (Get-Command Get-EXOMailbox -ErrorAction SilentlyContinue) {
            $mailbox = Get-EXOMailbox -Identity $adUser.UserPrincipalName -ErrorAction SilentlyContinue
            if ($mailbox) {
                return @{ mailbox = @{ email = [string]$mailbox.PrimarySmtpAddress; type = [string]$mailbox.RecipientTypeDetails } }
            }
            Write-OnboardingLog -Level INFO -Message "Mailbox for $sam will provision automatically with its Exchange license"
            return @{ mailbox = @{ email = $adUser.UserPrincipalName; type = 'PendingLicenseProvisioning' } }
        }
        Stop-Onboarding -Code 'module_missing' -Message 'Neither Exchange Management Tools nor ExchangeOnlineManagement is available'
    }

    if ($action -eq 'grant-shared') {
        Assert-ModuleAvailable -Name ExchangeOnlineManagement
        $mailboxes = @(Get-ParamValue $Params 'mailboxes' @())
        if ($mailboxes.Count -eq 0) {
            Stop-Onboarding -Code 'invalid_params' -Message 'mailboxes is required for grant-shared'
        }
        $granted = [System.Collections.Generic.List[string]]::new()
        foreach ($mb in $mailboxes) {
            Add-MailboxPermission -Identity $mb -User $adUser.UserPrincipalName `
                -AccessRights FullAccess -AutoMapping $true -ErrorAction Stop | Out-Null
            Add-RecipientPermission -Identity $mb -Trustee $adUser.UserPrincipalName `
                -AccessRights SendAs -Confirm:$false -ErrorAction Stop | Out-Null
            $granted.Add($mb)
            Write-OnboardingLog -Level INFO -Message "Granted $sam FullAccess+SendAs on $mb"
        }
        return @{ granted = @($granted) }
    }

    Stop-Onboarding -Code 'invalid_params' -Message "Unknown action '$action'"
}
