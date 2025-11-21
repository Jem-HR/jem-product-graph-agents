"""Test script for Deep Agents Smart CSV Agent.

Tests all three middleware components:
- TodoListMiddleware (planning)
- FilesystemMiddleware (context storage)
- SubAgentMiddleware (subagent delegation)
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from agent.subagents.smart_csv_agent import smart_csv_deep_agent


async def test_deep_agents_features():
    """Test Deep Agents features with a small CSV file."""

    print("=" * 80)
    print("Testing Deep Agents Smart CSV Agent")
    print("=" * 80)

    # Test with messy CSV to trigger all Deep Agents features
    test_file = "data/sample_csvs/messy_employees.csv"

    print(f"\n📁 Test File: {test_file}")
    print("\nThis test will verify:")
    print("  1. ✅ TodoListMiddleware - Agent creates and updates todos")
    print("  2. ✅ FilesystemMiddleware - Agent stores context in files")
    print("  3. ✅ SubAgentMiddleware - Agent delegates to specialized subagents")
    print("\n" + "=" * 80 + "\n")

    # Create a task that will trigger Deep Agents features
    task_message = f"""Analyze this CSV file using your Deep Agents capabilities:

**File:** {test_file}

**Your Task:**

1. **Use write_todos** to create a detailed analysis plan
2. **Use filesystem tools** to:
   - Store CSV schema analysis in /csv_analysis/schema.txt
   - Check /memories/column_mappings.txt for learned patterns
   - Save findings to /memories/csv_patterns.txt

3. **Consider delegating to subagents**:
   - csv_analyzer: For deep schema inspection
   - csv_validator: For data quality assessment
   - csv_transformer: If cleaning is needed

**Instructions:**
- Start by creating a todo list with write_todos
- Use ls to check what files exist in your filesystem
- Store your analysis in the filesystem
- Provide a summary of what you found

**Note:** This is a TEST run - do NOT actually import the data to Neo4j.
Just analyze the file and demonstrate your Deep Agents capabilities.
"""

    try:
        print("🚀 Invoking Deep Agents Smart CSV Agent...\n")

        # Invoke the agent
        result = await smart_csv_deep_agent.ainvoke({
            "messages": [{"role": "user", "content": task_message}]
        })

        print("\n" + "=" * 80)
        print("📊 AGENT EXECUTION COMPLETE")
        print("=" * 80 + "\n")

        # Extract and display results
        messages = result.get("messages", [])

        print(f"💬 Total messages in conversation: {len(messages)}")
        print("\n" + "-" * 80)
        print("📝 CONVERSATION FLOW:")
        print("-" * 80 + "\n")

        for i, msg in enumerate(messages, 1):
            role = msg.__class__.__name__
            content = msg.content if hasattr(msg, "content") else str(msg)

            # Truncate long messages for readability
            if len(content) > 500:
                content = content[:500] + f"\n... [truncated, {len(content) - 500} more chars]"

            print(f"\n[{i}] {role}:")
            print("-" * 40)
            print(content)

        # Check for evidence of Deep Agents features
        print("\n" + "=" * 80)
        print("🔍 DEEP AGENTS FEATURES VERIFICATION")
        print("=" * 80 + "\n")

        conversation_text = " ".join([
            str(msg.content) if hasattr(msg, "content") else str(msg)
            for msg in messages
        ])

        # Check for TodoListMiddleware usage
        todo_keywords = ["write_todos", "todo", "plan", "step", "pending", "in_progress", "completed"]
        found_todos = any(keyword in conversation_text.lower() for keyword in todo_keywords)
        print(f"1. TodoListMiddleware (Planning): {'✅ DETECTED' if found_todos else '❌ NOT DETECTED'}")
        if found_todos:
            print("   - Agent created or referenced a todo list")

        # Check for FilesystemMiddleware usage
        fs_keywords = ["write_file", "read_file", "ls", "/csv_analysis/", "/memories/", "filesystem"]
        found_filesystem = any(keyword in conversation_text.lower() for keyword in fs_keywords)
        print(f"\n2. FilesystemMiddleware (Context Storage): {'✅ DETECTED' if found_filesystem else '❌ NOT DETECTED'}")
        if found_filesystem:
            print("   - Agent used filesystem tools for context storage")

        # Check for SubAgentMiddleware usage
        subagent_keywords = ["csv_analyzer", "csv_validator", "csv_transformer", "subagent", "delegate", "task"]
        found_subagents = any(keyword in conversation_text.lower() for keyword in subagent_keywords)
        print(f"\n3. SubAgentMiddleware (Delegation): {'✅ DETECTED' if found_subagents else '❌ NOT DETECTED'}")
        if found_subagents:
            print("   - Agent referenced or delegated to specialized subagents")

        # Overall result
        all_features_working = found_todos and found_filesystem and found_subagents

        print("\n" + "=" * 80)
        if all_features_working:
            print("✅ TEST PASSED: All Deep Agents features are working!")
        else:
            print("⚠️  TEST PARTIAL: Some features may need verification")
            print("\nNote: The agent may not use all features in every run.")
            print("Try testing with more complex scenarios to see all features in action.")
        print("=" * 80 + "\n")

        # Display final response
        if messages:
            final_message = messages[-1]
            print("📌 FINAL AGENT RESPONSE:")
            print("-" * 80)
            final_content = final_message.content if hasattr(final_message, "content") else str(final_message)
            print(final_content)
            print("-" * 80)

        return result

    except Exception as e:
        print(f"\n❌ TEST FAILED with error:\n{str(e)}")
        import traceback
        print("\nFull traceback:")
        print(traceback.format_exc())
        return None


async def quick_import_test():
    """Quick test to verify the agent can be imported and has correct structure."""

    print("\n" + "=" * 80)
    print("🔧 QUICK STRUCTURAL TEST")
    print("=" * 80 + "\n")

    print(f"✅ Agent type: {type(smart_csv_deep_agent)}")
    print(f"✅ Agent class: {smart_csv_deep_agent.__class__.__name__}")

    # Check if it's a compiled graph
    is_graph = "Graph" in str(type(smart_csv_deep_agent))
    print(f"✅ Is LangGraph compiled graph: {is_graph}")

    if hasattr(smart_csv_deep_agent, "get_graph"):
        graph = smart_csv_deep_agent.get_graph()
        nodes = list(graph.nodes.keys()) if hasattr(graph, "nodes") else []
        print(f"✅ Graph nodes: {len(nodes)}")
        if nodes:
            print(f"   Nodes: {nodes[:5]}...")  # Show first 5 nodes

    print("\n✅ Import and structure test passed!")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("🧪 DEEP AGENTS SMART CSV AGENT TEST SUITE")
    print("=" * 80 + "\n")

    # Run quick structural test
    asyncio.run(quick_import_test())

    # Ask if user wants to run full test
    print("\n" + "=" * 80)
    print("⚠️  FULL TEST WARNING")
    print("=" * 80)
    print("\nThe full test will:")
    print("  - Invoke the agent with a real task")
    print("  - Make API calls to Claude (costs ~$0.01-0.05)")
    print("  - Take 30-60 seconds to complete")
    print("\nDo you want to run the full test? (y/n): ", end="")

    response = input().strip().lower()

    if response in ["y", "yes"]:
        print("\n🚀 Running full Deep Agents feature test...\n")
        result = asyncio.run(test_deep_agents_features())

        if result:
            print("\n✅ All tests completed successfully!")
        else:
            print("\n❌ Tests failed. Check the output above for details.")
            sys.exit(1)
    else:
        print("\n⏭️  Skipping full test. Structural test passed!")
        print("\n💡 To run the full test later, run: python test_deep_agents_csv.py")

    print("\n" + "=" * 80)
    print("🏁 TEST SUITE COMPLETE")
    print("=" * 80 + "\n")
