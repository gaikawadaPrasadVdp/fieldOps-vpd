import urllib.request
import ssl
import csv
import io

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

url = 'https://docs.google.com/spreadsheets/d/12KV3WHzfYKPEu4uOYD3a5FvNXWRGwUue/export?format=csv&gid=1680696391'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
    data = resp.read().decode('utf-8', errors='replace')

reader = csv.DictReader(io.StringIO(data))
defects = list(reader)
print(f"Total Defects in Defect_Log: {len(defects)}")
for d in defects:
    did = d.get('ID', '').strip()
    sev = d.get('Severity', '').strip()
    mod = d.get('Module', '').strip()
    scen = d.get('Scenario', '').strip()[:80]
    dev_status = d.get('Dev Status', '').strip()
    print(f"{did} | {sev} | {mod} | {dev_status} | {scen}")
