#Requires -Version 7.0
<#
.SYNOPSIS
    Creates the user's home folder with correct NTFS permissions and maps the
    home drive on the AD account.
.DESCRIPTION
    Params: { "sam": "jane.doe", "path": "\\\\FS01\\Home\\jane.doe", "drive": "H" }
    NTFS grant: user gets Modify (OI)(CI); inheritance from the share root is
    preserved so admin/backup ACEs continue to apply.
#>
[CmdletBinding()] param()
Set-StrictMode -Version Latest
Import-Module (Join-Path $PSScriptRoot '..\modules\OnboardingCommon\OnboardingCommon.psd1') -Force

Invoke-OnboardingScript -ScriptName 'Create-HomeFolder.ps1' -Main {
    param($Params)
    Assert-ModuleAvailable -Name ActiveDirectory

    $sam   = Get-ParamValue $Params 'sam'
    $path  = Get-ParamValue $Params 'path'
    $drive = [string](Get-ParamValue $Params 'drive' 'H')
    if (-not $sam -or -not $path) {
        Stop-Onboarding -Code 'invalid_params' -Message 'sam and path are required'
    }
    if ($path -notmatch '^\\\\[^\\]+\\') {
        Stop-Onboarding -Code 'invalid_params' -Message "Home folder path must be a UNC path, got '$path'"
    }

    $adUser = Get-ADUser -Identity $sam -ErrorAction Stop
    $domain = (Get-ADDomain).NetBIOSName

    if (-not (Test-Path -LiteralPath $path)) {
        New-Item -ItemType Directory -Path $path -Force -ErrorAction Stop | Out-Null
        Write-OnboardingLog -Level INFO -Message "Created folder $path"
    }
    else {
        Write-OnboardingLog -Level WARN -Message "Folder already existed: $path"
    }

    $account = "$domain\$sam"
    $icacls = icacls $path /grant "${account}:(OI)(CI)M" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Stop-Onboarding -Code 'acl_failed' -Message "icacls failed for ${path}: $icacls"
    }
    Write-OnboardingLog -Level INFO -Message "Granted $account Modify on $path"

    Set-ADUser -Identity $adUser -HomeDirectory $path -HomeDrive "${drive}:" -ErrorAction Stop
    return @{ homeFolder = @{ path = $path; drive = $drive } }
}
