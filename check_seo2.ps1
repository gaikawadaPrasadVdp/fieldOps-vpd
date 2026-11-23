$base = 'http://localhost:8080'
$paths = @(
    '/',
    '/features/',
    '/product/',
    '/solutions/',
    '/platform/',
    '/resources/',
    '/about/',
    '/contact-sales/',
    '/legal/privacy-policy/',
    '/legal/terms-of-service/',
    '/legal/disclaimer/',
    '/legal/cookie-policy/',
    '/sitemap/',
    '/robots.txt'
)
# Add a selection of product slugs
$productSlugs = @(
    'asset-management','service-management','work-order-management','inventory-management','maintenance-management','audit-traceability','analytics-reporting','core-capabilities','enterprise-architecture','integrations','platform-overview'
)
foreach($s in $productSlugs){ $paths += "/product/$s/" }
# Add a selection of solution slugs
$solutionSlugs = @(
    'service-maintenance','facilities','multi-site-management','manufacturing','connected-data','infrastructure','sla-management','enterprise-operations'
)
foreach($s in $solutionSlugs){ $paths += "/solutions/$s/" }
# Add a selection of module slugs
$moduleSlugs = @(
    'asset-management','work-order-management','service-management','inventory-management','maintenance-management','workforce-management','analytics-reporting','audit-traceability','inspection-checklist','contracts-warranty','sla-management','qr-identification','client-portal','technician-workspace','asset-hierarchy'
)
foreach($s in $moduleSlugs){ $paths += "/platform/$s/" }

$missing = @()
foreach($p in $paths){
    $url = "$base$p"
    try {
        $resp = Invoke-WebRequest -Uri $url -UseBasicParsing -ErrorAction Stop
        $html = $resp.Content
    } catch {
        $missing += "${p} : Request failed"
        continue
    }
    $checks = @(
        '<meta[^>]+name=["\']description["\']',
        '<meta[^>]+name=["\']robots["\']',
        '<link[^>]+rel=["\']canonical["\']',
        '<meta[^>]+property=["\']og:title["\']',
        '<meta[^>]+property=["\']og:description["\']',
        '<meta[^>]+property=["\']og:image["\']',
        '<meta[^>]+name=["\']twitter:card["\']'
    )
    foreach($pat in $checks){
        if(-not ($html -match $pat)){
            $missing += "${p} : Missing pattern $pat"
            break
        }
    }
}
if($missing.Count -eq 0){
    Write-Output 'All pages have required SEO metadata.'
    exit 0
} else {
    Write-Output 'SEO issues found:'
    $missing | ForEach-Object { Write-Output $_ }
    exit 1
}

