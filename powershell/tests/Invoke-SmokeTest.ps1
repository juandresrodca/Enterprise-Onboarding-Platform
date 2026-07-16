<#
.SYNOPSIS
    Version-independent smoke test for the OnboardingCommon module.
    Works on Windows PowerShell 5.1 and PowerShell 7+ without Pester.
.DESCRIPTION
    Exercises the JSON contract, error codes, logging and AD serialization.
    Exit code 0 = all checks passed.
#>
[CmdletBinding()] param()
$ErrorActionPreference = 'Stop'
$failures = 0

function Check {
    param([string]$Name, [bool]$Condition)
    if ($Condition) { Write-Host "  PASS  $Name" }
    else { Write-Host "  FAIL  $Name"; $script:failures++ }
}

$env:EIO_PS_LOG_DIR = Join-Path ([System.IO.Path]::GetTempPath()) "eio-smoke-$([guid]::NewGuid())"
Import-Module (Join-Path $PSScriptRoot '..\modules\OnboardingCommon\OnboardingCommon.psd1') -Force

Write-Host "OnboardingCommon smoke test (PS $($PSVersionTable.PSVersion))"

# JSON success contract
$json = Out-OnboardingResult -Success $true -Data @{ answer = 42 } -PassThru
$obj = $json | ConvertFrom-Json
Check 'success contract: success flag' ($obj.success -eq $true)
Check 'success contract: data payload' ($obj.data.answer -eq 42)
Check 'success contract: single line' (-not $json.Contains("`n"))

# JSON failure contract
$json = Out-OnboardingResult -Success $false -ErrorCode 'dup' -ErrorMessage 'exists' -PassThru
$obj = $json | ConvertFrom-Json
Check 'failure contract: error code' ($obj.error.code -eq 'dup')
Check 'failure contract: error message' ($obj.error.message -eq 'exists')

# Stop-Onboarding error code round-trip
$caughtCode = $null
try { Stop-Onboarding -Code 'invalid_ou' -Message 'missing' }
catch { $caughtCode = $_.Exception.Data['OnboardingCode'] }
Check 'Stop-Onboarding carries machine code' ($caughtCode -eq 'invalid_ou')

# Structured logging
Write-OnboardingLog -Level INFO -Message 'smoke entry' -Context @{ a = 1 }
$logFile = Join-Path $env:EIO_PS_LOG_DIR 'powershell.jsonl'
Check 'log file created' (Test-Path $logFile)
$line = (Get-Content $logFile | Select-Object -Last 1) | ConvertFrom-Json
Check 'log entry structured' ($line.message -eq 'smoke entry' -and $line.level -eq 'INFO')

# Get-ParamValue defaults
$params = [pscustomobject]@{ limit = $null; q = 'x' }
Check 'Get-ParamValue present' ((Get-ParamValue $params 'q' 'd') -eq 'x')
Check 'Get-ParamValue null -> default' ((Get-ParamValue $params 'limit' 50) -eq 50)
Check 'Get-ParamValue missing -> default' ((Get-ParamValue $params 'nope' 'd') -eq 'd')

# AD serialization
$fake = [pscustomobject]@{
    SamAccountName = 'jane.doe'; UserPrincipalName = 'jane.doe@northwind.com'
    DisplayName = 'Jane Doe'; EmailAddress = 'jane.doe@northwind.com'
    GivenName = 'Jane'; Surname = 'Doe'
    DistinguishedName = 'CN=Jane Doe,OU=Finance,OU=Company,DC=northwind,DC=local'
    Department = 'Finance'; Company = 'Northwind'; Office = 'HQ'; Title = 'Analyst'
    Manager = $null; Enabled = $true; whenCreated = Get-Date; employeeType = 'Employee'
}
$user = ConvertTo-OnboardingUser -ADUser $fake -Summary
Check 'ConvertTo-OnboardingUser sam' ($user.sam_account_name -eq 'jane.doe')
Check 'ConvertTo-OnboardingUser ou strips CN' ($user.ou -eq 'OU=Finance,OU=Company,DC=northwind,DC=local')

Remove-Item $env:EIO_PS_LOG_DIR -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item Env:EIO_PS_LOG_DIR -ErrorAction SilentlyContinue

if ($failures -gt 0) { Write-Host "`n$failures check(s) FAILED"; exit 1 }
Write-Host "`nAll checks passed."
exit 0
