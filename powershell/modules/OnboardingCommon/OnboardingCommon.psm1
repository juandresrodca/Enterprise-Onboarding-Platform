#Requires -Version 5.1
<#
.SYNOPSIS
    Shared plumbing for all onboarding scripts.

.DESCRIPTION
    Implements the JSON contract used by the FastAPI backend:
      * Parameters arrive as a single JSON document on STDIN (never on the
        command line, so passwords/secrets stay out of process listings and
        PowerShell operational event logs).
      * Exactly one JSON object is written to STDOUT:
          { success, data, error: {code, message}, logs: [...] }
      * Diagnostics go to a structured JSONL log file, never to STDOUT.

    Target runtime is PowerShell 7+; the module itself loads on 5.1 so Pester
    tests can run anywhere.
#>

Set-StrictMode -Version Latest

$script:LogBuffer = [System.Collections.Generic.List[object]]::new()
$script:OnboardingScriptName = 'module'

function Get-OnboardingLogDirectory {
    [CmdletBinding()]
    param()
    if ($env:EIO_PS_LOG_DIR) { return $env:EIO_PS_LOG_DIR }
    # powershell/modules/OnboardingCommon -> <project>/logs
    return (Join-Path $PSScriptRoot '..\..\..\logs' | Resolve-PathSafe)
}

function Resolve-PathSafe {
    [CmdletBinding()]
    param([Parameter(Mandatory, ValueFromPipeline)][string]$Path)
    process {
        $resolved = [System.IO.Path]::GetFullPath($Path)
        return $resolved
    }
}

function Write-OnboardingLog {
    <#
    .SYNOPSIS
        Structured log entry: buffered for the JSON result and appended to the
        JSONL log file for SIEM ingestion.
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][ValidateSet('DEBUG', 'INFO', 'WARN', 'ERROR')][string]$Level,
        [Parameter(Mandatory)][string]$Message,
        [hashtable]$Context
    )
    $entry = [ordered]@{
        ts      = (Get-Date).ToUniversalTime().ToString('o')
        level   = $Level
        script  = $script:OnboardingScriptName
        message = $Message
    }
    if ($Context) { $entry.context = $Context }
    $script:LogBuffer.Add($entry) | Out-Null

    try {
        $dir = Get-OnboardingLogDirectory
        if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
        $line = ($entry | ConvertTo-Json -Compress -Depth 6)
        $file = Join-Path $dir 'powershell.jsonl'
        $mutex = [System.Threading.Mutex]::new($false, 'Global\EIOPowerShellLog')
        [void]$mutex.WaitOne(2000)
        try { Add-Content -LiteralPath $file -Value $line -Encoding UTF8 }
        finally { $mutex.ReleaseMutex(); $mutex.Dispose() }
    }
    catch {
        # Logging must never break the operation itself.
        Write-Verbose "Log write failed: $($_.Exception.Message)"
    }
}

function Read-OnboardingParams {
    <#
    .SYNOPSIS
        Reads the JSON parameter document from STDIN.
    #>
    [CmdletBinding()]
    param()
    $raw = [Console]::In.ReadToEnd()
    if ([string]::IsNullOrWhiteSpace($raw)) { return [pscustomobject]@{} }
    try {
        return ($raw | ConvertFrom-Json)
    }
    catch {
        Stop-Onboarding -Code 'invalid_params' -Message "STDIN did not contain valid JSON: $($_.Exception.Message)"
    }
}

function Get-ParamValue {
    <#
    .SYNOPSIS
        Safe property access on the params object with a default.
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]$Params,
        [Parameter(Mandatory)][string]$Name,
        $Default = $null
    )
    if ($null -ne $Params -and $Params.PSObject.Properties[$Name] -and $null -ne $Params.$Name) {
        return $Params.$Name
    }
    return $Default
}

function Stop-Onboarding {
    <#
    .SYNOPSIS
        Throws a terminating error carrying a machine-readable error code.
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$Code,
        [Parameter(Mandatory)][string]$Message
    )
    $ex = [System.InvalidOperationException]::new($Message)
    $ex.Data['OnboardingCode'] = $Code
    throw $ex
}

function Assert-ModuleAvailable {
    <#
    .SYNOPSIS
        Imports a required module or fails with a precise error code.
    #>
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$Name)
    if (Get-Module -Name $Name) { return }
    try {
        Import-Module -Name $Name -ErrorAction Stop
        Write-OnboardingLog -Level INFO -Message "Imported module $Name"
    }
    catch {
        Stop-Onboarding -Code 'module_missing' -Message "Required module '$Name' is not available: $($_.Exception.Message)"
    }
}

function Out-OnboardingResult {
    <#
    .SYNOPSIS
        Emits the single JSON result object. -PassThru returns the string
        instead of writing it (used by Pester tests).
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][bool]$Success,
        $Data,
        [string]$ErrorCode,
        [string]$ErrorMessage,
        [switch]$PassThru
    )
    $result = [ordered]@{
        success = $Success
        data    = $Data
        error   = $null
        logs    = @($script:LogBuffer)
    }
    if (-not $Success) {
        $result.error = [ordered]@{ code = $ErrorCode; message = $ErrorMessage }
    }
    $json = $result | ConvertTo-Json -Compress -Depth 12
    if ($PassThru) { return $json }
    # Single line on stdout - the backend parses the last JSON line.
    [Console]::Out.WriteLine($json)
}

function Invoke-OnboardingScript {
    <#
    .SYNOPSIS
        Standard entry point wrapper: read params -> run main -> emit result.
        Guarantees exactly one JSON object on stdout and a correct exit code.
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][scriptblock]$Main,
        [string]$ScriptName = 'unknown.ps1'
    )
    $script:OnboardingScriptName = $ScriptName
    $script:LogBuffer.Clear()
    try {
        $params = Read-OnboardingParams
        $data = & $Main $params
        Out-OnboardingResult -Success $true -Data $data
        exit 0
    }
    catch {
        $code = 'script_error'
        if ($_.Exception.Data -and $_.Exception.Data.Contains('OnboardingCode')) {
            $code = [string]$_.Exception.Data['OnboardingCode']
        }
        Write-OnboardingLog -Level ERROR -Message $_.Exception.Message
        Out-OnboardingResult -Success $false -ErrorCode $code -ErrorMessage $_.Exception.Message
        exit 1
    }
}

function ConvertTo-OnboardingUser {
    <#
    .SYNOPSIS
        Maps an ADUser object (Get-ADUser with properties) to the normalized
        field names the backend expects.
    #>
    [CmdletBinding()]
    param([Parameter(Mandatory)]$ADUser, [switch]$Summary)

    function Get-Prop($obj, $name) {
        if ($obj.PSObject.Properties[$name]) { return $obj.$name }
        return $null
    }

    $managerSam = $null
    $managerDn = Get-Prop $ADUser 'Manager'
    if ($managerDn) {
        try { $managerSam = (Get-ADUser -Identity $managerDn -ErrorAction Stop).SamAccountName }
        catch { $managerSam = $managerDn }
    }

    $user = [ordered]@{
        sam_account_name    = $ADUser.SamAccountName
        user_principal_name = $ADUser.UserPrincipalName
        display_name        = Get-Prop $ADUser 'DisplayName'
        email               = Get-Prop $ADUser 'EmailAddress'
        first_name          = Get-Prop $ADUser 'GivenName'
        last_name           = Get-Prop $ADUser 'Surname'
        ou                  = ($ADUser.DistinguishedName -replace '^CN=[^,]+,', '')
        department          = Get-Prop $ADUser 'Department'
        company             = Get-Prop $ADUser 'Company'
        office              = Get-Prop $ADUser 'Office'
        job_title           = Get-Prop $ADUser 'Title'
        manager             = $managerSam
        enabled             = [bool](Get-Prop $ADUser 'Enabled')
        created_at          = if (Get-Prop $ADUser 'whenCreated') { $ADUser.whenCreated.ToUniversalTime().ToString('o') } else { $null }
        source              = 'directory'
        employee_type       = Get-Prop $ADUser 'employeeType'
    }
    if ($Summary) { return $user }

    $extension = [ordered]@{}
    foreach ($i in 1..15) {
        $name = "extensionAttribute$i"
        $value = Get-Prop $ADUser $name
        if ($value) { $extension[$name] = [string]$value }
    }
    $proxies = @(Get-Prop $ADUser 'proxyAddresses')

    $user += [ordered]@{
        employee_id          = Get-Prop $ADUser 'EmployeeID'
        cost_center          = Get-Prop $ADUser 'extensionAttribute10'
        description          = Get-Prop $ADUser 'Description'
        office_location      = Get-Prop $ADUser 'physicalDeliveryOfficeName'
        phone                = Get-Prop $ADUser 'OfficePhone'
        mobile               = Get-Prop $ADUser 'MobilePhone'
        country              = Get-Prop $ADUser 'Country'
        city                 = Get-Prop $ADUser 'City'
        state                = Get-Prop $ADUser 'State'
        address              = Get-Prop $ADUser 'StreetAddress'
        postal_code          = Get-Prop $ADUser 'PostalCode'
        proxy_addresses      = @($proxies | Where-Object { $_ })
        extension_attributes = $extension
        account_expiration   = if (Get-Prop $ADUser 'AccountExpirationDate') { $ADUser.AccountExpirationDate.ToString('yyyy-MM-dd') } else { $null }
        home_folder          = if (Get-Prop $ADUser 'HomeDirectory') {
                                   @{ path = $ADUser.HomeDirectory; drive = ((Get-Prop $ADUser 'HomeDrive') -replace ':', '') }
                               } else { $null }
        profile              = @{
                                   roaming_profile_path = Get-Prop $ADUser 'ProfilePath'
                                   logon_script         = Get-Prop $ADUser 'ScriptPath'
                               }
    }
    return $user
}

Export-ModuleMember -Function @(
    'Read-OnboardingParams', 'Get-ParamValue', 'Write-OnboardingLog',
    'Out-OnboardingResult', 'Invoke-OnboardingScript', 'Stop-Onboarding',
    'Assert-ModuleAvailable', 'ConvertTo-OnboardingUser', 'Get-OnboardingLogDirectory'
)
