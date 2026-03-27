import json
import re
from datetime import datetime

log_file = "d:/AutoSocial/backend/webhook_debug.log"

with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
    lines = f.readlines()

latest_events = []
current_event = {}

for line in lines:
    if "--- " in line and " ---" in line:
        if current_event:
            latest_events.append(current_event)
        current_event = {"time": line.strip("- \n")}
    elif "DEBUG [Webhook]: Received object:" in line:
        current_event["obj"] = line.strip()
    elif "DEBUG [Upsert]:" in line:
        current_event["upsert"] = line.strip()

if current_event:
    latest_events.append(current_event)

print("--- Latest 5 Webhook Events ---")
for event in latest_events[-5:]:
    print(event)
