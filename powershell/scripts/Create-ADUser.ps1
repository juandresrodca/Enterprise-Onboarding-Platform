#Requires -Version 7.0
<#
.SYNOPSIS
    Creates an Active Directory user with the full attribute set.
.DESCRIPTION
    Params (stdin JSON):
      {
        "user": { first_name, last_name, display_name, sam_account_name,
                  user_principal_name, email, ou, department, company, office,
                  office_location, job_title, employee_id, employee_type,
                  cost_center, description, manager, phone, mobile, country,
                  city, state, address, postal_code, account_expiration,
                  proxy_addresses: [], extension_attributes: {},
                  force_change_at_logon, password_never_expires },
        "password": "<initial password - arrives via stdin only>"
      }
    Conventions:
      * cost_center is stored in extensionAttribute10 (documented convention).
      * proxyAddresses / extensionAttribute1-15 go through OtherAttributes.
#>
[CmdletBinding()] param()
Set-StrictMode -Version Latest
Import-Module (Join-Path $PSScriptRoot '..\modules\OnboardingCommon\OnboardingCommon.psd1') -Force

Invoke-OnboardingScript -ScriptName 'Create-ADUser.ps1' -Main {
    param($Params)
    Assert-ModuleAvailable -Name ActiveDirectory

    $u = Get-ParamValue $Params 'user'
    $password = Get-ParamValue $Params 'password'
    if (-not $u -or -not $password) {
        Stop-Onboarding -Code 'invalid_params' -Message 'user and password are required'
    }
    foreach ($required in 'sam_account_name', 'user_principal_name', 'ou', 'first_name', 'last_name') {
        if (-not (Get-ParamValue $u $required)) {
            Stop-Onboarding -Code 'invalid_params' -Message "user.$required is required"
        }
    }

    # Duplicate guard (validation runs earlier, but never trust a single check).
    if (Get-ADUser -Filter "sAMAccountName -eq '$($u.sam_account_name)'" -ErrorAction SilentlyContinue) {
        Stop-Onboarding -Code 'duplicate_sam' -Message "sAMAccountName '$($u.sam_account_name)' already exists"
    }

    $securePassword = ConvertTo-SecureString -String $password -AsPlainText -Force
    $splat = @{
        Name                  = Get-ParamValue $u 'display_name' "$($u.first_name) $($u.last_name)"
        GivenName             = $u.first_name
        Surname               = $u.last_name
        DisplayName           = Get-ParamValue $u 'display_name' "$($u.first_name) $($u.last_name)"
        SamAccountName        = $u.sam_account_name
        UserPrincipalName     = $u.user_principal_name
        Path                  = $u.ou
        AccountPassword       = $securePassword
        Enabled               = $true
        ChangePasswordAtLogon = [bool](Get-ParamValue $u 'force_change_at_logon' $true)
        PasswordNeverExpires  = [bool](Get-ParamValue $u 'password_never_expires' $false)
        ErrorAction           = 'Stop'
    }

    $optional = @{
        EmailAddress = 'email';        Department = 'department';  Company = 'company'
        Office       = 'office';       Title      = 'job_title';   EmployeeID = 'employee_id'
        Description  = 'description';  OfficePhone = 'phone';      MobilePhone = 'mobile'
        Country      = 'country';      City       = 'city';        State = 'state'
        StreetAddress = 'address';     PostalCode = 'postal_code'
    }
    foreach ($param in $optional.Keys) {
        $value = Get-ParamValue $u $optional[$param]
        if ($value) { $splat[$param] = $value }
    }

    $manager = Get-ParamValue $u 'manager'
    if ($manager) {
        try { $splat.Manager = (Get-ADUser -Identity $manager -ErrorAction Stop).DistinguishedName }
        catch { Stop-Onboarding -Code 'invalid_manager' -Message "Manager '$manager' not found" }
    }
    $expiration = Get-ParamValue $u 'account_expiration'
    if ($expiration) {
        # AccountExpirationDate is the first moment the account is INVALID;
        # add one day so the account works through the stated end date.
        $splat.AccountExpirationDate = ([datetime]$expiration).AddDays(1)
    }

    $other = @{}
    $ext = Get-ParamValue $u 'extension_attributes'
    if ($ext) {
        foreach ($prop in $ext.PSObject.Properties) {
            if ($prop.Name -match '^extensionAttribute([1-9]|1[0-5])$' -and $prop.Value) {
                $other[$prop.Name] = [string]$prop.Value
            }
        }
    }
    $costCenter = Get-ParamValue $u 'cost_center'
    if ($costCenter -and -not $other.ContainsKey('extensionAttribute10')) {
        $other['extensionAttribute10'] = [string]$costCenter
    }
    $employeeType = Get-ParamValue $u 'employee_type'
    if ($employeeType) { $other['employeeType'] = [string]$employeeType }
    $officeLocation = Get-ParamValue $u 'office_location'
    if ($officeLocation) { $other['physicalDeliveryOfficeName'] = [string]$officeLocation }
    $proxies = @(Get-ParamValue $u 'proxy_addresses' @())
    if ($proxies.Count -gt 0) { $other['proxyAddresses'] = [string[]]$proxies }
    if ($other.Count -gt 0) { $splat.OtherAttributes = $other }

    try {
        New-ADUser @splat
    }
    catch {
        Stop-Onboarding -Code 'create_failed' -Message "New-ADUser failed: $($_.Exception.Message)"
    }
    finally {
        $securePassword.Dispose()
    }

    Write-OnboardingLog -Level INFO -Message "Created user $($u.sam_account_name) in $($u.ou)" `
        -Context @{ upn = $u.user_principal_name }

    $created = Get-ADUser -Identity $u.sam_account_name -Properties DisplayName, EmailAddress,
        Department, Title, Office, whenCreated, employeeType
    return @{ user = (ConvertTo-OnboardingUser -ADUser $created -Summary) }
}
