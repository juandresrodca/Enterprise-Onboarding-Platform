#Requires -Version 5.1
<#
.SYNOPSIS
    Pester 5 tests for the OnboardingCommon module (no AD required).
.NOTES
    Run: Invoke-Pester -Path powershell/tests
#>

BeforeAll {
    $env:EIO_PS_LOG_DIR = Join-Path ([System.IO.Path]::GetTempPath()) "eio-tests-$([guid]::NewGuid())"
    Import-Module (Join-Path $PSScriptRoot '..\modules\OnboardingCommon\OnboardingCommon.psd1') -Force
}

AfterAll {
    if (Test-Path $env:EIO_PS_LOG_DIR) { Remove-Item $env:EIO_PS_LOG_DIR -Recurse -Force }
    Remove-Item Env:EIO_PS_LOG_DIR -ErrorAction SilentlyContinue
}

Describe 'Out-OnboardingResult' {
    It 'produces the success JSON contract' {
        $json = Out-OnboardingResult -Success $true -Data @{ answer = 42 } -PassThru
        $obj = $json | ConvertFrom-Json
        $obj.success | Should -BeTrue
        $obj.data.answer | Should -Be 42
        $obj.error | Should -BeNullOrEmpty
        # Compressed single-line output (backend parses the last stdout line).
        $json | Should -Not -Match "`n"
    }

    It 'produces the failure JSON contract with an error code' {
        $json = Out-OnboardingResult -Success $false -ErrorCode 'duplicate_sam' `
            -ErrorMessage 'exists' -PassThru
        $obj = $json | ConvertFrom-Json
        $obj.success | Should -BeFalse
        $obj.error.code | Should -Be 'duplicate_sam'
        $obj.error.message | Should -Be 'exists'
    }
}

Describe 'Stop-Onboarding' {
    It 'throws with a retrievable machine-readable code' {
        try {
            Stop-Onboarding -Code 'invalid_ou' -Message 'OU missing'
            throw 'should not reach here'
        }
        catch {
            $_.Exception.Message | Should -Be 'OU missing'
            $_.Exception.Data['OnboardingCode'] | Should -Be 'invalid_ou'
        }
    }
}

Describe 'Write-OnboardingLog' {
    It 'buffers entries into the JSON result and writes JSONL to disk' {
        Write-OnboardingLog -Level INFO -Message 'test entry' -Context @{ a = 1 }
        $json = Out-OnboardingResult -Success $true -Data @{} -PassThru
        $obj = $json | ConvertFrom-Json
        @($obj.logs | Where-Object message -eq 'test entry').Count | Should -BeGreaterOrEqual 1

        $file = Join-Path $env:EIO_PS_LOG_DIR 'powershell.jsonl'
        Test-Path $file | Should -BeTrue
        $line = (Get-Content $file | Select-Object -Last 1) | ConvertFrom-Json
        $line.level | Should -Be 'INFO'
        $line.message | Should -Be 'test entry'
        $line.context.a | Should -Be 1
    }
}

Describe 'Get-ParamValue' {
    It 'returns the value when present' {
        $params = [pscustomobject]@{ limit = 25 }
        Get-ParamValue $params 'limit' 50 | Should -Be 25
    }
    It 'returns the default when absent or null' {
        $params = [pscustomobject]@{ limit = $null }
        Get-ParamValue $params 'limit' 50 | Should -Be 50
        Get-ParamValue $params 'missing' 'x' | Should -Be 'x'
    }
}

Describe 'ConvertTo-OnboardingUser' {
    It 'maps an AD-shaped object to the normalized backend contract' {
        $fake = [pscustomobject]@{
            SamAccountName    = 'jane.doe'
            UserPrincipalName = 'jane.doe@northwind.com'
            DisplayName       = 'Jane Doe'
            EmailAddress      = 'jane.doe@northwind.com'
            GivenName         = 'Jane'
            Surname           = 'Doe'
            DistinguishedName = 'CN=Jane Doe,OU=Finance,OU=Company,DC=northwind,DC=local'
            Department        = 'Finance'
            Company           = 'Northwind Dynamics'
            Office            = 'Seattle HQ'
            Title             = 'Analyst'
            Manager           = $null
            Enabled           = $true
            whenCreated       = Get-Date '2026-01-15'
            employeeType      = 'Employee'
        }
        $user = ConvertTo-OnboardingUser -ADUser $fake -Summary
        $user.sam_account_name | Should -Be 'jane.doe'
        $user.ou | Should -Be 'OU=Finance,OU=Company,DC=northwind,DC=local'
        $user.display_name | Should -Be 'Jane Doe'
        $user.enabled | Should -BeTrue
        $user.job_title | Should -Be 'Analyst'
    }
}
