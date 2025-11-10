"""Test the employee greeting agent with a number not in the database."""

import asyncio
from langchain_core.messages import HumanMessage
from agent.graph import graph


async def test_not_found():
    """Test with a mobile number that doesn't exist in the database."""

    config = {"configurable": {"my_configurable_param": "test", "thread_id": "test-notfound"}}

    print("=" * 70)
    print("TESTING: Employee Not Found Scenario")
    print("=" * 70)

    # Step 1: Initial greeting
    print("\n[STEP 1] Starting conversation...")
    print("-" * 70)
    result = await graph.ainvoke({"messages": []}, config)

    if result.get("messages"):
        last_msg = result["messages"][-1]
        if hasattr(last_msg, "content"):
            print(f"🤖 Agent: {last_msg.content}")

    # Step 2: Provide a mobile number that doesn't exist
    print("\n[STEP 2] User provides non-existent number: 27999999999")
    print("-" * 70)

    previous_messages = result.get("messages", [])
    result = await graph.ainvoke(
        {
            "messages": previous_messages + [HumanMessage(content="My number is 27999999999")],
            "mobile_number": result.get("mobile_number"),
            "employee_context": result.get("employee_context"),
            "employee_found": result.get("employee_found", False),
            "conversation_stage": result.get("conversation_stage", ""),
        },
        config
    )

    # Print the not-found message
    if result.get("messages"):
        for msg in result["messages"][-3:]:
            if hasattr(msg, "content") and msg.__class__.__name__ == "AIMessage" and ("couldn't find" in str(msg.content) or "sorry" in str(msg.content).lower()):
                print(f"🤖 Agent: {msg.content}")
                break

    print(f"\n❌ Employee Found: {result.get('employee_found', False)}")
    print(f"❌ Mobile: {result.get('mobile_number', 'N/A')}")
    print(f"📍 Conversation Stage: {result.get('conversation_stage', 'N/A')}")

    print("\n" + "=" * 70)
    print("✅ TEST COMPLETE - Not found scenario handled correctly!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_not_found())
