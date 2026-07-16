@{
    RootModule        = 'OnboardingCommon.psm1'
    ModuleVersion     = '1.0.0'
    GUID              = '7f6c2a1e-9d4b-4c8a-b1f3-2e5d8a9c0e41'
    Author            = 'Enterprise Identity Onboarding'
    CompanyName       = 'Northwind Dynamics'
    Description       = 'Shared JSON contract, logging and AD serialization helpers for onboarding scripts.'
    PowerShellVersion = '5.1'
    FunctionsToExport = @(
        'Read-OnboardingParams', 'Get-ParamValue', 'Write-OnboardingLog',
        'Out-OnboardingResult', 'Invoke-OnboardingScript', 'Stop-Onboarding',
        'Assert-ModuleAvailable', 'ConvertTo-OnboardingUser', 'Get-OnboardingLogDirectory'
    )
    PrivateData       = @{ PSData = @{ Tags = @('ActiveDirectory', 'Onboarding', 'Automation') } }
}
