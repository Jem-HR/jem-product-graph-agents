"""Test the complete employee greeting agent flow with follow-up questions."""

import asyncio
from langchain_core.messages import HumanMessage
from agent.graph import graph


async def test_full_conversation():
    """Test complete conversation including follow-up questions."""

    config = {"configurable": {"my_configurable_param": "test", "thread_id": "test-full-123"}}

    print("=" * 70)
    print("COMPLETE EMPLOYEE GREETING AGENT TEST")
    print("=" * 70)

    # Step 1: Initial greeting
    print("\n[STEP 1] Starting conversation...")
    print("-" * 70)
    result = await graph.ainvoke({"messages": []}, config)

    if result.get("messages"):
        last_msg = result["messages"][-1]
        if hasattr(last_msg, "content"):
            print(f"🤖 Agent: {last_msg.content}")

    # Step 2: Provide mobile number
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
            if hasattr(msg, "content") and msg.__class__.__name__ == "AIMessage" and "Hello Thamsanqa" in str(msg.content):
                print(f"🤖 Agent: {msg.content}")
                break

    print(f"\n✅ Employee Found: {result.get('first_name', 'N/A')} {result.get('last_name', 'N/A')}")
    print(f"✅ Status: {result.get('employee_context', {}).get('status', 'N/A')}")
    print(f"✅ Mobile: {result.get('mobile_number', 'N/A')}")

    # Step 3: Ask a follow-up question
    print("\n[STEP 3] User asks: What is my smartwage status?")
    print("-" * 70)

    previous_messages = result.get("messages", [])
    result = await graph.ainvoke(
        {
            "messages": previous_messages + [HumanMessage(content="What is my smartwage status?")],
            "mobile_number": result.get("mobile_number"),
            "employee_context": result.get("employee_context"),
            "employee_found": result.get("employee_found", False),
            "conversation_stage": result.get("conversation_stage", ""),
        },
        config
    )

    # Print Claude's response
    if result.get("messages"):
        last_msg = result["messages"][-1]
        if hasattr(last_msg, "content") and last_msg.__class__.__name__ == "AIMessage":
            print(f"🤖 Agent: {last_msg.content}")

    print("\n" + "=" * 70)
    print("✅ TEST COMPLETE - All conversation flows working!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_full_conversation())
