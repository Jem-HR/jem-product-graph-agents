#!/usr/bin/env python
"""Direct CSV processing test via API."""
import requests
import json

API_URL = "http://127.0.0.1:2024"

# Create thread
print("Creating thread...")
thread_resp = requests.post(f"{API_URL}/threads", json={})
thread_id = thread_resp.json()["thread_id"]
print(f"✅ Thread: {thread_id}\n")

# Send CSV processing request
print("Sending CSV processing request...")
run_resp = requests.post(
    f"{API_URL}/threads/{thread_id}/runs/wait",
    json={
        "assistant_id": "hr_admin",
        "input": {
            "messages": [{
                "role": "user",
                "content": "Process the messy CSV file at data/sample_csvs/messy_employees.csv using smart CSV processing with data cleaning"
            }]
        }
    },
    timeout=120
)

print(f"Status: {run_resp.status_code}\n")

if run_resp.status_code == 200:
    data = run_resp.json()
    messages = data.get("values", {}).get("messages", [])

    print(f"📊 Received {len(messages)} messages\n")
    print("=" * 80)

    for i, msg in enumerate(messages, 1):
        msg_type = msg.get("type", "unknown")
        content = msg.get("content", "")

        print(f"\n[{i}] {msg_type.upper()}:")
        print("-" * 40)

        if msg_type == "ai" and "tool_calls" in msg and msg["tool_calls"]:
            print(f"🔧 Tool Calls: {len(msg['tool_calls'])}")
            for tc in msg["tool_calls"]:
                tool_name = tc.get("name", "unknown")
                print(f"   - {tool_name}")

        if isinstance(content, str) and content:
            if len(content) > 1000:
                print(content[:1000] + f"\n... [+{len(content)-1000} more chars]")
            else:
                print(content)

    print("\n" + "=" * 80)

    # Check for Deep Agents features
    all_tool_calls = []
    for msg in messages:
        if "tool_calls" in msg and msg["tool_calls"]:
            all_tool_calls.extend([tc.get("name") for tc in msg["tool_calls"]])

    if all_tool_calls:
        print(f"\n🔧 Tools Used: {', '.join(set(all_tool_calls))}")

        has_todos = "write_todos" in all_tool_calls
        has_fs = any(t in all_tool_calls for t in ["write_file", "read_file", "ls", "edit_file"])
        has_task = "task" in all_tool_calls

        print(f"\n🎯 Deep Agents Features:")
        print(f"   TodoListMiddleware: {'✅' if has_todos else '❌'}")
        print(f"   FilesystemMiddleware: {'✅' if has_fs else '❌'}")
        print(f"   SubAgentMiddleware: {'✅' if has_task else '❌'}")
else:
    print(f"Error: {run_resp.text}")
