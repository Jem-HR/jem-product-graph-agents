"""Test the employee greeting agent with proper conversation flow."""

import asyncio
from langchain_core.messages import HumanMessage
from agent.graph import graph


async def test_conversation():
    """Test conversation with proper state management."""

    config = {"configurable": {"my_configurable_param": "test", "thread_id": "test-123"}}

    print("=" * 60)
    print("TESTING EMPLOYEE GREETING AGENT - CONVERSATION FLOW")
    print("=" * 60)

    # Step 1: Start conversation (initial greeting)
    print("\n[STEP 1] Starting conversation...")
    result = await graph.ainvoke(
        {"messages": []},
        config
    )

    print("\n--- Agent Response ---")
    if result.get("messages"):
        last_msg = result["messages"][-1]
        if hasattr(last_msg, "content"):
            print(f"AI: {last_msg.content}")

    print(f"\nState after step 1:")
    print(f"  Conversation Stage: {result.get('conversation_stage', 'N/A')}")

    # Step 2: Provide mobile number in new conversation turn
    print("\n" + "=" * 60)
    print("[STEP 2] User provides mobile number: 27782440774")
    print("=" * 60)

    # Continue from previous state by including all previous messages
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

    print("\n--- Agent Response ---")
    if result.get("messages"):
        # Print last 2 AI messages
        for msg in result["messages"][-2:]:
            if hasattr(msg, "content") and msg.__class__.__name__ == "AIMessage":
                print(f"AI: {msg.content}")

    print(f"\n" + "=" * 60)
    print(f"Final State:")
    print(f"  Mobile Number: {result.get('mobile_number', 'N/A')}")
    print(f"  Employee Found: {result.get('employee_found', 'N/A')}")
    print(f"  Employee Name: {result.get('employee_context', {}).get('first_name', 'N/A')} {result.get('employee_context', {}).get('last_name', '')}")
    print(f"  Conversation Stage: {result.get('conversation_stage', 'N/A')}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_conversation())
