import json
import urllib.request
import urllib.error
import sys

command = sys.stdin.read().strip()
if not command:
    print("No command provided")
    sys.exit(1)

data = json.dumps({"command": command}).encode()
req = urllib.request.Request(
    "http://127.0.0.1:8000/execute",
    data=data,
    headers={"Content-Type": "application/json"},
    method="POST",
)
try:
    with urllib.request.urlopen(req, timeout=60) as resp:
        print(resp.read().decode())
except urllib.error.HTTPError as e:
    print(f"HTTP {e.code}: {e.read().decode()}")
except Exception as e:
    print(f"Error: {e}")
