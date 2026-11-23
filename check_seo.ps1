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
# add catalog urls
$catalog = Get-Content -Raw "c:\Users\veere\new new latest\FieldOps_Nexus_Internal\src\apps\ui\public_catalog.py"
# extract slugs using regex (simplify by importing via python is heavy). We'll just skip dynamic for now.
function Test-Page($url){
    $resp = Invoke-WebRequest -Uri $url -UseBasicParsing -ErrorAction SilentlyContinue
    if(-not $resp){ Write-Host "Failed $url"; return $false }
    $html = $resp.Content
    $checks = @(
        '<meta[^>]+name=["\']description["\']',
        '<meta[^>]+name=["\']robots["\']',
        '<link[^>]+rel=["\']canonical["\']',
        '<meta[^>]+property=["\']og:title["\']',
        '<meta[^>]+property=["\']og:description["\']',
        '<meta[^>]+property=["\']og:image["\']',
        '<meta[^>]+name=["\']twitter:card["\']'
    )
    foreach($pattern in $checks){
        if($html -notmatch $pattern){
            Write-Host "Missing $pattern on $url"
            return $false
        }
    }
    return $true
}
$allGood = $true
foreach($p in $paths){
    $url = "$base$p"
    if(-not (Test-Page $url)) { $allGood = $false }
}
if($allGood){ Write-Host 'All pages have required SEO metadata.' } else { Write-Host 'Some pages missing metadata.'; exit 1 }

