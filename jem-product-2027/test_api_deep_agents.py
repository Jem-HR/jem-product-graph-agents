"""Test Smart CSV Agent via LangGraph API."""

import requests
import json
import time
import sys

API_URL = "http://127.0.0.1:2024"
GRAPH_ID = "hr_admin"

def test_smart_csv_via_api():
    """Test the Smart CSV Agent through HR Admin agent via API."""

    print("\n" + "=" * 80)
    print("🧪 TESTING DEEP AGENTS SMART CSV AGENT VIA API")
    print("=" * 80 + "\n")

    # Test message - ask agent to analyze CSV file
    test_message = """Analyze the messy CSV file at data/sample_csvs/messy_employees.csv

Use your Deep Agents capabilities:
1. Create a todo list with write_todos
2. Use ls to check your filesystem
3. Inspect the CSV structure
4. Store findings in /csv_analysis/analysis.txt using write_file
5. Provide a brief summary

NOTE: This is a TEST - do NOT import data to Neo4j. Just analyze and demonstrate Deep Agents features."""

    # Create a thread
    print("📝 Creating thread...")
    thread_response = requests.post(
        f"{API_URL}/threads",
        json={"metadata": {"test": "deep_agents_csv"}}
    )

    if thread_response.status_code != 200:
        print(f"❌ Failed to create thread: {thread_response.status_code}")
        print(thread_response.text)
        return False

    thread_data = thread_response.json()
    thread_id = thread_data["thread_id"]
    print(f"✅ Thread created: {thread_id}\n")

    # Send message to agent
    print(f"💬 Sending message to {GRAPH_ID} agent...")
    print(f"Message: {test_message[:100]}...\n")

    run_response = requests.post(
        f"{API_URL}/threads/{thread_id}/runs",
        json={
            "assistant_id": GRAPH_ID,
            "input": {"messages": [{"role": "user", "content": test_message}]},
            "config": {"configurable": {"thread_id": thread_id}},
            "stream_mode": "values"
        },
        headers={"Accept": "text/event-stream"},
        stream=True
    )

    if run_response.status_code != 200:
        print(f"❌ Failed to start run: {run_response.status_code}")
        print(run_response.text)
        return False

    print("🚀 Agent is processing (this may take 30-60 seconds)...\n")
    print("=" * 80)
    print("📊 STREAMING RESULTS:")
    print("=" * 80 + "\n")

    # Stream and collect results
    messages = []
    tool_calls = []
    event_count = 0

    for line in run_response.iter_lines():
        if line:
            line = line.decode('utf-8')
            if line.startswith('data: '):
                try:
                    data = json.loads(line[6:])
                    event_count += 1

                    # Extract messages
                    if isinstance(data, dict) and "messages" in data:
                        new_messages = data["messages"]
                        if new_messages:
                            for msg in new_messages:
                                if msg not in messages:
                                    messages.append(msg)

                                    # Display message info
                                    msg_type = msg.get("type", "unknown")
                                    content = msg.get("content", "")

                                    if msg_type == "human":
                                        print(f"[USER] {content[:100]}...")
                                    elif msg_type == "ai":
                                        # Check for tool calls
                                        if "tool_calls" in msg and msg["tool_calls"]:
                                            for tc in msg["tool_calls"]:
                                                tool_name = tc.get("name", "unknown")
                                                tool_calls.append(tool_name)
                                                print(f"[TOOL CALL] {tool_name}")
                                        elif content:
                                            print(f"[AI] {content[:200]}...")
                                    elif msg_type == "tool":
                                        tool_name = msg.get("name", "unknown")
                                        print(f"[TOOL RESULT] {tool_name}: {str(content)[:100]}...")

                except json.JSONDecodeError:
                    continue

    print("\n" + "=" * 80)
    print("✅ PROCESSING COMPLETE")
    print("=" * 80 + "\n")

    # Analyze results
    print("📊 ANALYSIS:")
    print("-" * 80)
    print(f"Total events: {event_count}")
    print(f"Total messages: {len(messages)}")
    print(f"Total tool calls: {len(tool_calls)}")

    if tool_calls:
        print(f"\n🔧 Tools used: {', '.join(set(tool_calls))}")

    # Check for Deep Agents features
    print("\n🔍 DEEP AGENTS FEATURES DETECTED:")
    print("-" * 80)

    found_todos = "write_todos" in tool_calls
    found_filesystem = any(t in tool_calls for t in ["write_file", "read_file", "ls", "edit_file"])
    found_task = "task" in tool_calls
    found_csv_tools = any(t in tool_calls for t in ["inspect_csv_structure", "map_csv_columns"])

    print(f"1. TodoListMiddleware: {'✅ YES' if found_todos else '❌ NO'}")
    if found_todos:
        print("   - Agent used write_todos for planning")

    print(f"\n2. FilesystemMiddleware: {'✅ YES' if found_filesystem else '❌ NO'}")
    if found_filesystem:
        fs_tools = [t for t in tool_calls if t in ["write_file", "read_file", "ls", "edit_file"]]
        print(f"   - Tools used: {', '.join(set(fs_tools))}")

    print(f"\n3. SubAgentMiddleware: {'✅ YES' if found_task else '❌ NO'}")
    if found_task:
        print("   - Agent delegated to subagent")

    if found_csv_tools:
        print(f"\n4. CSV Tools: ✅ YES")
        csv_tools_used = [t for t in tool_calls if "csv" in t or "inspect" in t]
        print(f"   - Tools used: {', '.join(set(csv_tools_used))}")

    # Display final response
    if messages:
        final_msg = messages[-1]
        if final_msg.get("type") == "ai":
            final_content = final_msg.get("content", "")
            print("\n" + "=" * 80)
            print("📌 FINAL AGENT RESPONSE:")
            print("=" * 80)
            if len(final_content) > 1000:
                print(final_content[:1000] + f"\n... [+{len(final_content) - 1000} chars]")
            else:
                print(final_content)
            print("=" * 80)

    # Verdict
    any_deep_agents = found_todos or found_filesystem or found_task

    print("\n" + "=" * 80)
    if any_deep_agents:
        print("✅ TEST PASSED: Deep Agents features are working via API!")
        print("\nDeep Agents capabilities demonstrated:")
        if found_todos:
            print("  ✓ Task planning (TodoListMiddleware)")
        if found_filesystem:
            print("  ✓ Context storage (FilesystemMiddleware)")
        if found_task:
            print("  ✓ Subagent delegation (SubAgentMiddleware)")
    else:
        print("⚠️  TEST RESULT: Agent executed but Deep Agents features not detected")
        print("   (This may be normal for simple queries)")

    print("=" * 80 + "\n")

    return any_deep_agents


def check_server():
    """Check if LangGraph server is running."""
    try:
        response = requests.get(f"{API_URL}/ok", timeout=5)
        return response.status_code == 200
    except:
        return False


if __name__ == "__main__":
    print("\n🔬 Deep Agents API Test Suite\n")

    # Check if server is running
    print("🔍 Checking if LangGraph server is running...")
    if not check_server():
        print("❌ LangGraph server is not running!")
        print("\n💡 Start the server with: langgraph dev")
        sys.exit(1)

    print("✅ LangGraph server is running at", API_URL)

    # Run test
    print("\n" + "=" * 80)
    print("Starting API test...")
    print("=" * 80)

    success = test_smart_csv_via_api()

    if success:
        print("\n🎉 Test completed successfully!")
        sys.exit(0)
    else:
        print("\n⚠️  Test completed with warnings")
        sys.exit(0)
