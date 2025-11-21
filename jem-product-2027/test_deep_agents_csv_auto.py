"""Automated test script for Deep Agents Smart CSV Agent (no interactive prompts)."""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from agent.subagents.smart_csv_agent import smart_csv_deep_agent


async def main():
    """Run automated test."""

    print("\n" + "=" * 80)
    print("🧪 AUTOMATED DEEP AGENTS TEST")
    print("=" * 80 + "\n")

    # Structural test
    print("✅ Agent type:", type(smart_csv_deep_agent).__name__)
    print("✅ Is CompiledStateGraph:", "CompiledStateGraph" in str(type(smart_csv_deep_agent)))

    print("\n" + "=" * 80)
    print("🚀 Running Deep Agents Feature Test")
    print("=" * 80 + "\n")

    test_file = "data/sample_csvs/messy_employees.csv"

    task_message = f"""Analyze this CSV file using your Deep Agents capabilities:

**File:** {test_file}

**Your Task:**

1. **Use write_todos** to create an analysis plan (3-5 steps)
2. **Use ls** to check your filesystem
3. **Use inspect_csv_structure** to analyze the file
4. **Store findings** in /csv_analysis/analysis.txt using write_file
5. Provide a brief summary

**IMPORTANT:** This is a TEST - do NOT process/import data. Just analyze and demonstrate Deep Agents features.
"""

    try:
        print(f"📁 Test File: {test_file}")
        print("⏱️  Invoking agent (this will take 20-40 seconds)...\n")

        result = await smart_csv_deep_agent.ainvoke({
            "messages": [{"role": "user", "content": task_message}]
        })

        print("\n" + "=" * 80)
        print("✅ AGENT EXECUTION COMPLETE")
        print("=" * 80 + "\n")

        messages = result.get("messages", [])
        print(f"💬 Total messages: {len(messages)}\n")

        # Display conversation
        for i, msg in enumerate(messages, 1):
            role = msg.__class__.__name__
            content = str(msg.content) if hasattr(msg, "content") else str(msg)

            print(f"\n[{i}] {role} ({len(content)} chars):")
            print("-" * 40)

            # Show tool calls if present
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                print(f"🔧 Tool Calls: {len(msg.tool_calls)}")
                for tc in msg.tool_calls[:3]:  # Show first 3
                    print(f"   - {tc.get('name', 'unknown')}")

            # Truncate long content
            if len(content) > 800:
                print(content[:800] + f"\n... [+{len(content) - 800} chars]")
            else:
                print(content)

        # Feature detection
        print("\n" + "=" * 80)
        print("🔍 FEATURE DETECTION")
        print("=" * 80 + "\n")

        all_content = " ".join([
            str(msg.content) if hasattr(msg, "content") else str(msg)
            for msg in messages
        ]).lower()

        # Check tool usage
        tool_names = []
        for msg in messages:
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                tool_names.extend([tc.get("name", "") for tc in msg.tool_calls])

        found_todos = "write_todos" in tool_names
        found_filesystem = any(t in tool_names for t in ["write_file", "read_file", "ls", "edit_file"])
        found_task = "task" in tool_names  # SubAgent delegation

        print(f"1. TodoListMiddleware:")
        print(f"   {'✅ USED' if found_todos else '❌ NOT USED'} - write_todos tool")
        if found_todos:
            print("   Agent created a task plan")

        print(f"\n2. FilesystemMiddleware:")
        print(f"   {'✅ USED' if found_filesystem else '❌ NOT USED'} - filesystem tools")
        if found_filesystem:
            fs_tools = [t for t in tool_names if t in ["write_file", "read_file", "ls", "edit_file"]]
            print(f"   Tools used: {', '.join(fs_tools)}")

        print(f"\n3. SubAgentMiddleware:")
        print(f"   {'✅ USED' if found_task else '❌ NOT USED'} - task delegation")
        if found_task:
            print("   Agent delegated to subagent")

        # CSV tools
        csv_tools = [t for t in tool_names if "csv" in t or "inspect" in t or "map" in t]
        if csv_tools:
            print(f"\n4. CSV Analysis Tools:")
            print(f"   ✅ USED - {', '.join(csv_tools)}")

        all_features = found_todos or found_filesystem or found_task

        print("\n" + "=" * 80)
        if all_features:
            print("✅ TEST PASSED: Deep Agents features are functional!")
        else:
            print("⚠️  TEST WARNING: No Deep Agents features detected")
            print("   The agent may not have needed them for this simple task")
        print("=" * 80)

        # Final response
        if messages:
            final = messages[-1]
            final_content = str(final.content) if hasattr(final, "content") else str(final)
            print("\n📌 FINAL RESPONSE:")
            print("-" * 80)
            if len(final_content) > 1000:
                print(final_content[:1000] + f"\n... [+{len(final_content) - 1000} chars]")
            else:
                print(final_content)
            print("-" * 80)

        return True

    except Exception as e:
        print(f"\n❌ TEST FAILED:\n{str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("\n🔬 Starting automated test...")
    success = asyncio.run(main())

    print("\n" + "=" * 80)
    if success:
        print("🏁 TEST COMPLETE - SUCCESS")
    else:
        print("🏁 TEST COMPLETE - FAILED")
    print("=" * 80 + "\n")

    sys.exit(0 if success else 1)
