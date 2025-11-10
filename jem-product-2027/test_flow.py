"""Test the employee greeting agent flow."""

import asyncio
from langchain_core.messages import HumanMessage
from agent.graph import graph


async def test_employee_flow():
    """Test the complete employee greeting flow."""

    # Initialize the state
    config = {"configurable": {"my_configurable_param": "test"}}

    print("=" * 60)
    print("TESTING EMPLOYEE GREETING AGENT")
    print("=" * 60)

    # Test 1: Initial greeting (no input)
    print("\n[TEST 1] Starting conversation...")
    result = await graph.ainvoke(
        {"messages": []},
        config
    )

    print("\n--- Agent Response ---")
    for msg in result["messages"]:
        if hasattr(msg, "content"):
            print(f"{msg.__class__.__name__}: {msg.content}")

    # Test 2: Provide mobile number
    print("\n" + "=" * 60)
    print("[TEST 2] Providing mobile number: 27782440774")
    print("=" * 60)

    result = await graph.ainvoke(
        {
            "messages": [
                HumanMessage(content="My number is 27782440774")
            ]
        },
        config
    )

    print("\n--- Agent Response ---")
    for msg in result["messages"]:
        if hasattr(msg, "content"):
            print(f"{msg.__class__.__name__}: {msg.content}")

    print("\n" + "=" * 60)
    print(f"Final State:")
    print(f"  Mobile Number: {result.get('mobile_number', 'N/A')}")
    print(f"  Employee Found: {result.get('employee_found', 'N/A')}")
    print(f"  Conversation Stage: {result.get('conversation_stage', 'N/A')}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_employee_flow())
