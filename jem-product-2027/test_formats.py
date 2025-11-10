"""Test different mobile number formats."""

import asyncio
from langchain_core.messages import HumanMessage
from agent.graph import graph


async def test_format(number_input: str, expected: str):
    """Test a specific mobile number format."""

    config = {"configurable": {"my_configurable_param": "test"}}

    # Step 1: Initial greeting
    result = await graph.ainvoke({"messages": []}, config)

    # Step 2: Provide mobile number
    previous_messages = result.get("messages", [])
    result = await graph.ainvoke(
        {
            "messages": previous_messages + [HumanMessage(content=f"My number is {number_input}")],
            "mobile_number": result.get("mobile_number"),
            "employee_context": result.get("employee_context"),
            "employee_found": result.get("employee_found", False),
            "conversation_stage": result.get("conversation_stage", ""),
        },
        config
    )

    extracted = result.get("mobile_number", "FAILED")
    found = result.get("employee_found", False)

    status = "✅" if extracted == expected and found else "❌"
    print(f"{status} Input: {number_input:20s} → Extracted: {extracted:15s} → Found: {found}")

    return extracted == expected


async def test_all_formats():
    """Test various mobile number formats."""

    print("=" * 70)
    print("TESTING: Mobile Number Format Extraction")
    print("=" * 70)
    print()

    tests = [
        ("27782440774", "27782440774"),          # Direct 27 format
        ("0782440774", "27782440774"),            # Local 0 format
        ("+27782440774", "27782440774"),          # International +27 format
        ("+27 782 440 774", "27782440774"),       # With spaces
        ("078-244-0774", "27782440774"),          # With dashes
        ("+27 78 244 0774", "27782440774"),       # Mixed spacing
    ]

    results = []
    for input_num, expected in tests:
        result = await test_format(input_num, expected)
        results.append(result)

    print()
    print("=" * 70)
    passed = sum(results)
    total = len(results)
    print(f"✅ Tests Passed: {passed}/{total}")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_all_formats())
