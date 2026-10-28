import urllib.request
import ssl
import re

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

url = 'https://docs.google.com/spreadsheets/d/12KV3WHzfYKPEu4uOYD3a5FvNXWRGwUue/edit?pli=1'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
    html = resp.read().decode('utf-8', errors='replace')

# Find pattern: \"([0-9]+)\",\[\{\"1\":\[\[0,0,\"([^\"]+)\"
matches = re.findall(r'\\\"(\d+)\\\",\[\{\\\"1\\\":\[\[0,0,\\\"([^\\\"]+)\\\"', html)
print(f"Found {len(matches)} sheets:")
for gid, name in matches:
    print(f"- {name}: gid={gid}")
