$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$composeFile = Join-Path $PSScriptRoot 'compose.yaml'
$projectName = 'supportpilot-db000-test'
$environmentNames = @(
    'POSTGRES_USER',
    'POSTGRES_DB',
    'POSTGRES_PASSWORD',
    'POSTGRES_BOOTSTRAP_DATABASE_URL',
    'POSTGRES_HOST',
    'POSTGRES_PORT',
    'SUPPORT_OWNER_PASSWORD',
    'COMMERCE_OWNER_PASSWORD',
    'SUPPORT_APP_PASSWORD',
    'COMMERCE_APP_PASSWORD'
)
$originalEnvironment = @{}

foreach ($name in $environmentNames) {
    $originalEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}

function Set-DefaultEnvironmentValue {
    param(
        [Parameter(Mandatory)] [string] $Name,
        [Parameter(Mandatory)] [string] $Value
    )
    if ([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($Name, 'Process'))) {
        [Environment]::SetEnvironmentVariable($Name, $Value, 'Process')
    }
}

function Invoke-Compose {
    param([Parameter(Mandatory)] [string[]] $ComposeArguments)
    & docker compose --project-name $projectName --file $composeFile @ComposeArguments
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose command failed with exit code $LASTEXITCODE"
    }
}

try {
    Set-DefaultEnvironmentValue -Name 'POSTGRES_USER' -Value 'postgres'
    Set-DefaultEnvironmentValue -Name 'POSTGRES_DB' -Value 'supportpilot'
    Set-DefaultEnvironmentValue -Name 'POSTGRES_PASSWORD' -Value ([guid]::NewGuid().ToString('N'))
    Set-DefaultEnvironmentValue -Name 'SUPPORT_OWNER_PASSWORD' -Value ([guid]::NewGuid().ToString('N'))
    Set-DefaultEnvironmentValue -Name 'COMMERCE_OWNER_PASSWORD' -Value ([guid]::NewGuid().ToString('N'))
    Set-DefaultEnvironmentValue -Name 'SUPPORT_APP_PASSWORD' -Value ([guid]::NewGuid().ToString('N'))
    Set-DefaultEnvironmentValue -Name 'COMMERCE_APP_PASSWORD' -Value ([guid]::NewGuid().ToString('N'))
    Set-DefaultEnvironmentValue -Name 'POSTGRES_HOST' -Value 'postgres'
    Set-DefaultEnvironmentValue -Name 'POSTGRES_PORT' -Value '5432'

    $encodedPassword = [uri]::EscapeDataString($env:POSTGRES_PASSWORD)
    $bootstrapUrl = "postgresql://$($env:POSTGRES_USER):$encodedPassword@postgres:5432/$($env:POSTGRES_DB)"
    [Environment]::SetEnvironmentVariable(
        'POSTGRES_BOOTSTRAP_DATABASE_URL',
        $bootstrapUrl,
        'Process'
    )

    Invoke-Compose -ComposeArguments @('config', '--quiet')
    $configJson = & docker compose --project-name $projectName --file $composeFile config --format json
    if ($LASTEXITCODE -ne 0) {
        throw 'docker compose JSON config validation failed'
    }
    $config = ($configJson -join [Environment]::NewLine) | ConvertFrom-Json
    foreach ($serviceProperty in $config.services.PSObject.Properties) {
        if ($serviceProperty.Name -ne 'db-bootstrap') {
            $environment = $serviceProperty.Value.environment
            if ($null -ne $environment -and
                $environment.PSObject.Properties.Name -contains 'POSTGRES_BOOTSTRAP_DATABASE_URL') {
                throw "Bootstrap admin DSN leaked to service: $($serviceProperty.Name)"
            }
        }
    }

    Invoke-Compose -ComposeArguments @('down', '--volumes', '--remove-orphans')
    Invoke-Compose -ComposeArguments @('up', '--build', '--detach', '--wait', 'postgres')
    Invoke-Compose -ComposeArguments @('run', '--rm', '--no-deps', 'db-bootstrap')
    Invoke-Compose -ComposeArguments @('run', '--rm', '--no-deps', 'db-bootstrap')
    Invoke-Compose -ComposeArguments @('run', '--rm', '--no-deps', 'grant-tests')

    Write-Output 'DB-000 clean Compose, rerun, catalog and grant checks passed.'
}
finally {
    $cleanupErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = 'SilentlyContinue'
    & docker compose --project-name $projectName --file $composeFile down --volumes --remove-orphans 2>&1 | Out-Null
    $cleanupExitCode = $LASTEXITCODE
    $ErrorActionPreference = $cleanupErrorActionPreference
    foreach ($name in $environmentNames) {
        [Environment]::SetEnvironmentVariable($name, $originalEnvironment[$name], 'Process')
    }
    if ($cleanupExitCode -ne 0) {
        Write-Warning "DB-000 test cleanup exited with code $cleanupExitCode"
    }
}
