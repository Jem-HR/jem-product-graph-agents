"""Test Neo4j with employee who has a manager."""

import asyncio
from langchain_core.messages import HumanMessage
from agent.graph import graph


async def test_employee_with_manager():
    """Test with Gustavo Mendes who reports to Thamsanqa Moyo."""

    config = {"configurable": {"my_configurable_param": "test", "thread_id": "test-gustavo"}}

    print("=" * 70)
    print("TESTING: Employee with Manager (Gustavo Mendes)")
    print("=" * 70)

    # Step 1: Initial greeting
    print("\n[STEP 1] Starting conversation...")
    print("-" * 70)
    result = await graph.ainvoke({"messages": []}, config)

    if result.get("messages"):
        last_msg = result["messages"][-1]
        if hasattr(last_msg, "content"):
            print(f"🤖 Agent: {last_msg.content}")

    # Step 2: Provide mobile number (Gustavo Mendes: 27768047864)
    print("\n[STEP 2] User provides mobile number: 27768047864")
    print("-" * 70)

    previous_messages = result.get("messages", [])
    result = await graph.ainvoke(
        {
            "messages": previous_messages + [HumanMessage(content="My number is 27768047864")],
            "mobile_number": result.get("mobile_number"),
            "employee_context": result.get("employee_context"),
            "employee_found": result.get("employee_found", False),
            "conversation_stage": result.get("conversation_stage", ""),
        },
        config
    )

    # Print greeting
    if result.get("messages"):
        for msg in result["messages"][-3:]:
            if hasattr(msg, "content") and msg.__class__.__name__ == "AIMessage" and ("Hello" in str(msg.content) or "Welcome" in str(msg.content)):
                print(f"🤖 Agent: {msg.content}")
                break

    employee_context = result.get("employee_context", {})
    print(f"\n✅ Employee Found: {result.get('employee_found', False)}")
    print(f"✅ Name: {employee_context.get('first_name', 'N/A')} {employee_context.get('last_name', 'N/A')}")

    # Step 3: Ask about manager
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

    # Step 4: Ask about salary
    print("\n[STEP 4] User asks: What is my salary?")
    print("-" * 70)

    previous_messages = result.get("messages", [])
    result = await graph.ainvoke(
        {
            "messages": previous_messages + [HumanMessage(content="What is my salary?")],
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
    print("✅ TEST COMPLETE - Testing employee with manager!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_employee_with_manager())
