import urllib.request
import ssl
import csv
import io

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

base_url = "https://docs.google.com/spreadsheets/d/12KV3WHzfYKPEu4uOYD3a5FvNXWRGwUue/export?format=csv&gid="

sheets_to_check = [
    ("Executive_Summary", "1710860819"),
    ("Summary_Breakdown", "581283452"),
    ("Defect_Log", "1680696391"),
    ("Members_Users", "162869640"),
    ("Blocked_Skipped", "1567828806"),
]

for name, gid in sheets_to_check:
    url = base_url + gid
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
            data = resp.read().decode('utf-8', errors='replace')
        print(f"\n=================== {name} (gid={gid}) ===================")
        lines = [line.strip() for line in data.splitlines() if line.strip()]
        for line in lines[:25]:
            print(line)
        if len(lines) > 25:
            print(f"... and {len(lines) - 25} more lines.")
    except Exception as e:
        print(f"Error fetching {name}: {e}")
