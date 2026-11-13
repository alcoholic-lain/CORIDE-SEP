param(
    [ValidateRange(1, 65535)]
    [int]$Port = 8000
)

$ErrorActionPreference = 'Stop'

function Test-PrivateIPv4 {
    param([string]$Address)

    return $Address -match '^(10\.|172\.(1[6-9]|2\d|3[01])\.|192\.168\.)'
}

$adapters = @(Get-NetAdapter -ErrorAction Stop | Where-Object { $_.Status -eq 'Up' })
$physicalIndices = @(
    Get-NetAdapter -Physical -ErrorAction SilentlyContinue |
        Where-Object { $_.Status -eq 'Up' } |
        ForEach-Object { $_.ifIndex }
)
$defaultRoutes = @(
    Get-NetRoute -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue |
        Sort-Object RouteMetric
)

$candidates = foreach ($adapter in $adapters) {
    $addresses = @(
        Get-NetIPAddress -InterfaceIndex $adapter.ifIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue |
            Where-Object {
                $_.AddressState -eq 'Preferred' -and
                -not $_.SkipAsSource -and
                (Test-PrivateIPv4 $_.IPAddress)
            }
    )
    if ($addresses.Count -eq 0) {
        continue
    }

    $route = $defaultRoutes |
        Where-Object { $_.InterfaceIndex -eq $adapter.ifIndex } |
        Select-Object -First 1
    $interface = Get-NetIPInterface -InterfaceIndex $adapter.ifIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Select-Object -First 1
    $routeMetric = if ($route) { $route.RouteMetric } else { [int]::MaxValue }
    $interfaceMetric = if ($interface) { $interface.InterfaceMetric } else { [int]::MaxValue }

    foreach ($address in $addresses) {
        [PSCustomObject]@{
            Address         = $address.IPAddress
            Interface       = $adapter.Name
            InterfaceIndex  = $adapter.ifIndex
            IsPhysical      = $physicalIndices -contains $adapter.ifIndex
            HasDefaultRoute = [bool]$route
            RouteMetric     = $routeMetric
            InterfaceMetric = $interfaceMetric
        }
    }
}

$candidates = @($candidates)
$preferredCandidates = @(
    $candidates | Where-Object { $_.IsPhysical -and $_.HasDefaultRoute }
)
if ($preferredCandidates.Count -eq 0) {
    $preferredCandidates = @(
        $candidates | Where-Object { $_.HasDefaultRoute }
    )
}
if ($preferredCandidates.Count -eq 0) {
    $preferredCandidates = @(
        $candidates | Where-Object { $_.IsPhysical }
    )
}
if ($preferredCandidates.Count -eq 0) {
    $preferredCandidates = $candidates
}
if ($preferredCandidates.Count -eq 0) {
    throw 'No private IPv4 address found on an active network adapter. Connect to Wi-Fi or Ethernet and try again.'
}

$selected = $preferredCandidates |
    Sort-Object RouteMetric, InterfaceMetric, InterfaceIndex |
    Select-Object -First 1
$env:DJANGO_ALLOWED_HOSTS = "localhost,127.0.0.1,$($selected.Address)"

$uv = Get-Command uv -CommandType Application -ErrorAction SilentlyContinue |
    Select-Object -First 1
if (-not $uv) {
    throw 'uv was not found on PATH. Install uv, then run this script again.'
}

Write-Host "Using $($selected.Address) on $($selected.Interface)." -ForegroundColor Cyan
Write-Host "Starting CoRide on port $Port with automatic Android discovery." -ForegroundColor Cyan

Push-Location $PSScriptRoot
try {
    & $uv.Source run manage.py corideserver --port $Port
    if ($LASTEXITCODE -ne 0) {
        throw "CoRide server exited with code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}
