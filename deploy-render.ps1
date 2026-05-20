param(
    [Parameter(Mandatory = $true)]
    [string]$RenderApiKey,
    [string]$OwnerId = "",
    [string]$ServiceName = "jodala-microfinance",
    [string]$RepoUrl = "https://github.com/livingstoneouma117/jodala-microfinance",
    [string]$Branch = "main",
    [string]$Domain = "jodalamicrofinance.co.ke",
    [string]$Region = "frankfurt",
    [string]$Plan = "starter",
    [int]$DeployWaitMinutes = 25,
    [switch]$NoDisk
)

$ErrorActionPreference = "Stop"

$apiBase = "https://api.render.com/v1"
$headers = @{
    Authorization = "Bearer $RenderApiKey"
    Accept        = "application/json"
    "User-Agent"  = "codex-render-deployer"
}

function New-QueryString {
    param([hashtable]$Query)
    if (-not $Query -or $Query.Count -eq 0) { return "" }
    $pairs = foreach ($k in $Query.Keys) {
        $v = [string]$Query[$k]
        "{0}={1}" -f [uri]::EscapeDataString($k), [uri]::EscapeDataString($v)
    }
    return "?" + ($pairs -join "&")
}

function Invoke-RenderApi {
    param(
        [string]$Method,
        [string]$Path,
        [object]$Body = $null,
        [hashtable]$Query = $null
    )
    $uri = "$apiBase$Path$(New-QueryString -Query $Query)"
    try {
        if ($null -eq $Body) {
            return Invoke-RestMethod -Method $Method -Uri $uri -Headers $headers
        }
        $json = $Body | ConvertTo-Json -Depth 30 -Compress
        return Invoke-RestMethod -Method $Method -Uri $uri -Headers $headers -Body $json -ContentType "application/json"
    } catch {
        $status = ""
        $responseBody = ""
        if ($_.Exception.Response -and $_.Exception.Response.StatusCode) {
            $status = [int]$_.Exception.Response.StatusCode
        }
        if ($_.ErrorDetails -and $_.ErrorDetails.Message) {
            $responseBody = $_.ErrorDetails.Message
        }
        throw "Render API call failed ($Method $uri). Status: $status. Details: $responseBody"
    }
}

function Expand-Collection {
    param(
        [object]$Response,
        [string]$ItemProperty
    )
    if ($null -eq $Response) { return @() }
    $items = @()
    if ($Response -is [System.Array]) {
        $items = $Response
    } elseif ($Response.data) {
        $items = $Response.data
    } else {
        $items = @($Response)
    }

    $out = @()
    foreach ($i in $items) {
        if ($i -and $i.PSObject.Properties.Match($ItemProperty).Count -gt 0) {
            $out += $i.$ItemProperty
        } else {
            $out += $i
        }
    }
    return $out
}

Write-Host "Checking Render workspace access..."
$ownersRaw = Invoke-RenderApi -Method "GET" -Path "/owners"
$owners = Expand-Collection -Response $ownersRaw -ItemProperty "owner" | Where-Object { $_.id }
if (-not $owners -or $owners.Count -eq 0) {
    throw "No Render workspaces returned for this API key."
}

if (-not $OwnerId) {
    $OwnerId = $owners[0].id
}

$selectedOwner = $owners | Where-Object { $_.id -eq $OwnerId } | Select-Object -First 1
if (-not $selectedOwner) {
    throw "OwnerId '$OwnerId' was not found for this API key."
}
Write-Host ("Using workspace: {0} ({1})" -f $selectedOwner.name, $OwnerId)

Write-Host "Looking for existing Render service..."
$servicesRaw = Invoke-RenderApi -Method "GET" -Path "/services"
$services = Expand-Collection -Response $servicesRaw -ItemProperty "service" | Where-Object { $_.id }
$service = $services | Where-Object { $_.name -eq $ServiceName -and $_.ownerId -eq $OwnerId } | Select-Object -First 1

if (-not $service) {
    Write-Host "Creating Render web service..."
    $dbPath = if ($NoDisk) { "/opt/render/project/src/sacco.db" } else { "/var/data/sacco.db" }
    $diskConfig = if ($NoDisk) { $null } else { @{ name = "data"; mountPath = "/var/data"; sizeGB = 1 } }
    $createBody = @{
        type       = "web_service"
        name       = $ServiceName
        ownerId    = $OwnerId
        repo       = $RepoUrl
        branch     = $Branch
        autoDeploy = "yes"
        envVars    = @(
            @{ key = "DEBUG"; value = "false" },
            @{ key = "DB_PATH"; value = $dbPath },
            @{ key = "JWT_ALGORITHM"; value = "HS256" },
            @{ key = "JWT_EXP_HOURS"; value = "24" },
            @{ key = "SECRET_KEY"; generateValue = $true }
        )
        serviceDetails = @{
            runtime = "python"
            plan = $Plan
            region = $Region
            healthCheckPath = "/api/health"
            envSpecificDetails = @{
                buildCommand = "pip install -r requirements.txt"
                startCommand = "python app.py"
            }
        }
    }
    if ($diskConfig) {
        $createBody.serviceDetails.disk = $diskConfig
    }
    $service = Invoke-RenderApi -Method "POST" -Path "/services" -Body $createBody
    Write-Host ("Created service: {0} ({1})" -f $service.name, $service.id)
} else {
    Write-Host ("Service already exists: {0} ({1})" -f $service.name, $service.id)
}

$serviceId = $service.id

Write-Host "Ensuring domain is attached..."
$domainsRaw = Invoke-RenderApi -Method "GET" -Path "/services/$serviceId/custom-domains"
$domains = Expand-Collection -Response $domainsRaw -ItemProperty "customDomain"

if (-not ($domains | Where-Object { $_.name -eq $Domain })) {
    [void](Invoke-RenderApi -Method "POST" -Path "/services/$serviceId/custom-domains" -Body @{ name = $Domain })
    Write-Host "Attached domain: $Domain"
} else {
    Write-Host "Domain already attached: $Domain"
}

$wwwDomain = "www.$Domain"
if (-not ($domains | Where-Object { $_.name -eq $wwwDomain })) {
    try {
        [void](Invoke-RenderApi -Method "POST" -Path "/services/$serviceId/custom-domains" -Body @{ name = $wwwDomain })
        Write-Host "Attached domain: $wwwDomain"
    } catch {
        Write-Host "Skipped attaching $wwwDomain (it may already be auto-added by Render)."
    }
}

Write-Host "Getting deploy status..."
$deadline = (Get-Date).AddMinutes($DeployWaitMinutes)
$deployReady = $false
$currentStatus = ""

while ((Get-Date) -lt $deadline) {
    $deploysRaw = Invoke-RenderApi -Method "GET" -Path "/services/$serviceId/deploys"
    $deploys = Expand-Collection -Response $deploysRaw -ItemProperty "deploy" | Where-Object { $_.id }
    $latest = $deploys | Sort-Object createdAt -Descending | Select-Object -First 1
    if ($latest) {
        $currentStatus = $latest.status
        Write-Host ("Latest deploy {0}: {1}" -f $latest.id, $currentStatus)
        if ($currentStatus -eq "live") {
            $deployReady = $true
            break
        }
        if ($currentStatus -in @("build_failed", "update_failed", "pre_deploy_failed", "canceled", "deactivated")) {
            throw "Deploy failed with status '$currentStatus'. Check Render logs in dashboard."
        }
    } else {
        Write-Host "No deploy found yet..."
    }
    Start-Sleep -Seconds 15
}

if (-not $deployReady) {
    throw "Timed out waiting for a live deploy after $DeployWaitMinutes minutes."
}

$serviceLatest = Invoke-RenderApi -Method "GET" -Path "/services/$serviceId"
$renderHost = $serviceLatest.serviceDetails.url -replace '^https?://', ''
$renderHost = $renderHost.TrimEnd('/')

Write-Host ""
Write-Host "Render service is live."
Write-Host ("Service ID: {0}" -f $serviceId)
Write-Host ("Render URL: {0}" -f $serviceLatest.serviceDetails.url)
Write-Host ""
Write-Host "Set DNS records exactly as follows:"
Write-Host ("A record: @ -> 216.24.57.1")
Write-Host ("CNAME record: www -> {0}" -f $renderHost)
Write-Host ""
Write-Host "After DNS propagation, run:"
Write-Host ("  Invoke-RestMethod -Method POST -Uri ""https://api.render.com/v1/services/{0}/custom-domains/{1}/verify"" -Headers @{{ Authorization = ""Bearer <RENDER_API_KEY>""; Accept = ""application/json"" }}" -f $serviceId, $Domain)
