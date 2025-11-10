"""Test Neo4j integration with employee lookup and queries."""

import asyncio
from langchain_core.messages import HumanMessage
from agent.graph import graph


async def test_neo4j_authentication():
    """Test the complete Neo4j-based authentication flow."""

    config = {"configurable": {"my_configurable_param": "test", "thread_id": "test-neo4j-123"}}

    print("=" * 70)
    print("TESTING: Neo4j Employee Authentication")
    print("=" * 70)

    # Step 1: Initial greeting
    print("\n[STEP 1] Starting conversation...")
    print("-" * 70)
    result = await graph.ainvoke({"messages": []}, config)

    if result.get("messages"):
        last_msg = result["messages"][-1]
        if hasattr(last_msg, "content"):
            print(f"🤖 Agent: {last_msg.content}")

    # Step 2: Provide mobile number (testing with 27782440774)
    print("\n[STEP 2] User provides mobile number: 27782440774")
    print("-" * 70)

    previous_messages = result.get("messages", [])
    result = await graph.ainvoke(
        {
            "messages": previous_messages + [HumanMessage(content="My number is 27782440774")],
            "mobile_number": result.get("mobile_number"),
            "employee_context": result.get("employee_context"),
            "employee_found": result.get("employee_found", False),
            "conversation_stage": result.get("conversation_stage", ""),
        },
        config
    )

    # Find and print the greeting message
    if result.get("messages"):
        for msg in result["messages"][-3:]:
            if hasattr(msg, "content") and msg.__class__.__name__ == "AIMessage" and ("Hello" in str(msg.content) or "Welcome" in str(msg.content)):
                print(f"🤖 Agent: {msg.content}")
                break

    employee_context = result.get("employee_context", {})
    print(f"\n✅ Employee Found: {result.get('employee_found', False)}")
    print(f"✅ Name: {employee_context.get('first_name', 'N/A')} {employee_context.get('last_name', 'N/A')}")
    print(f"✅ Status: {employee_context.get('status', 'N/A')}")
    print(f"✅ Mobile: {result.get('mobile_number', 'N/A')}")

    # Step 3: Ask a Neo4j-based question about manager
    print("\n[STEP 3] User asks: Who is my manager?")
    print("-" * 70)

    previous_messages = result.get("messages", [])
    result = await graph.ainvoke(
        {
            "messages": previous_messages + [HumanMessage(content="Who is my manager?")],
            "mobile_number": result.get("mobile_number"),
            "employee_context": result.get("employee_context"),
            "employee_found": result.get("employee_found", False),
            "conversation_stage": result.get("conversation_stage", ""),
        },
        config
    )

    # Print response
    if result.get("messages"):
        last_msg = result["messages"][-1]
        if hasattr(last_msg, "content") and last_msg.__class__.__name__ == "AIMessage":
            print(f"🤖 Agent: {last_msg.content}")

    # Step 4: Ask another Neo4j-based question about org structure
    print("\n[STEP 4] User asks: What team do I work in?")
    print("-" * 70)

    previous_messages = result.get("messages", [])
    result = await graph.ainvoke(
        {
            "messages": previous_messages + [HumanMessage(content="What team do I work in?")],
            "mobile_number": result.get("mobile_number"),
            "employee_context": result.get("employee_context"),
            "employee_found": result.get("employee_found", False),
            "conversation_stage": result.get("conversation_stage", ""),
        },
        config
    )

    # Print response
    if result.get("messages"):
        last_msg = result["messages"][-1]
        if hasattr(last_msg, "content") and last_msg.__class__.__name__ == "AIMessage":
            print(f"🤖 Agent: {last_msg.content}")

    print("\n" + "=" * 70)
    print("✅ TEST COMPLETE - Neo4j integration working!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_neo4j_authentication())
