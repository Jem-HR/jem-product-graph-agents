"""Neo4j database operations for employee data and organizational queries.

Provides async operations for:
- Employee authentication by mobile number
- Direct Cypher query execution
- Tool-based querying with LLM
"""

from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv
from langchain_core.tools import tool

# Load environment variables
load_dotenv()


def get_neo4j_driver():
    """Get Neo4j driver connection.

    Returns:
        Neo4j driver instance.
    """
    from neo4j import AsyncGraphDatabase

    uri = os.getenv("NEO4J_URI")
    username = os.getenv("NEO4J_USERNAME")
    password = os.getenv("NEO4J_PASSWORD")

    if not all([uri, username, password]):
        msg = "Neo4j credentials not found in environment variables"
        raise ValueError(msg)

    return AsyncGraphDatabase.driver(uri, auth=(username, password))


async def get_employee_by_mobile_neo4j(mobile_number: str) -> dict[str, Any] | None:
    """Query employee by mobile number from Neo4j.

    Args:
        mobile_number: Mobile number in 27XXXXXXXXX format.

    Returns:
        Employee data dict if found, None otherwise.

    Raises:
        RuntimeError: If database query fails.
    """
    driver = get_neo4j_driver()

    try:
        async with driver.session() as session:
            query = """
            MATCH (e:Employee {mobile_number: $mobile_number})
            RETURN e.id as id,
                   e.uuid as uuid,
                   e.first_name as first_name,
                   e.last_name as last_name,
                   e.mobile_number as mobile_number,
                   e.email as email,
                   e.status as status,
                   e.employer_id as employer_id,
                   e.employee_no as employee_no,
                   e.smartwage_status as smartwage_status
            LIMIT 1
            """

            result = await session.run(query, mobile_number=mobile_number)
            record = await result.single()

            if record:
                return dict(record)

            return None

    except Exception as e:
        msg = f"Unexpected error querying Neo4j for employee: {e}"
        raise RuntimeError(msg) from e
    finally:
        await driver.close()


@tool
async def query_neo4j_cypher(cypher_query: str) -> list[dict[str, Any]]:
    """Execute a Cypher query against the Neo4j database.

    Use this tool to query employee relationships, organizational structure, and profile data.

    Important relationships:
    - (:Employee)-[:REPORTS_TO]->(:Employee) - Find manager
    - (:Employee)-[:WORKS_FOR]->(:Employer) - Find employer
    - (:Employee)-[:IN_DIVISION]->(:Division) - Find division/team
    - (:Employee)-[:ASSIGNED_TO_BRANCH]->(:Branch) - Find branch

    Args:
        cypher_query: Valid Cypher query to execute.

    Returns:
        List of result dictionaries.
    """
    driver = get_neo4j_driver()

    try:
        async with driver.session() as session:
            result = await session.run(cypher_query)
            records = await result.data()
            return records
    except Exception as e:
        return [{"error": f"Query failed: {str(e)}"}]
    finally:
        await driver.close()


async def query_neo4j_with_natural_language(
    question: str, employee_context: dict[str, Any]
) -> str:
    """Answer questions using Neo4j graph with LLM and tool calling.

    Uses Claude with the query_neo4j_cypher tool to answer questions.

    Args:
        question: Natural language question about org structure, relationships, etc.
        employee_context: Current employee's context for personalized queries.

    Returns:
        Answer string from the graph query.

    Raises:
        RuntimeError: If query fails.
    """
    from langchain_anthropic import ChatAnthropic
    from langchain_core.messages import SystemMessage, HumanMessage

    try:
        model = ChatAnthropic(model="claude-haiku-4-5-20251001")
        model_with_tools = model.bind_tools([query_neo4j_cypher])

        employee_id = employee_context.get("id")
        first_name = employee_context.get("first_name", "")
        last_name = employee_context.get("last_name", "")

        system_prompt = f"""You are a helpful assistant with access to a Neo4j graph database containing employee information.

Current employee: {first_name} {last_name} (ID: {employee_id})

Neo4j Schema:
- Employee nodes: id, first_name, last_name, mobile_number, email, status, salary, employer_id, etc.
- Employer nodes: id, company_name, status
- Division nodes: id, name
- Branch nodes: id, name

Key Relationships:
- (Employee)-[:REPORTS_TO]->(Employee) - Employee reports to their manager
- (Employee)-[:WORKS_FOR]->(Employer) - Employee works for employer
- (Employee)-[:IN_DIVISION]->(Division) - Employee is in division/team
- (Employee)-[:ASSIGNED_TO_BRANCH]->(Branch) - Employee assigned to branch

When answering questions:
1. Write a Cypher query using the query_neo4j_cypher tool
2. Analyze the results
3. Provide a clear, natural language answer

Example queries:
- To find manager: MATCH (e:Employee {{id: {employee_id}}})-[:REPORTS_TO]->(manager:Employee) RETURN manager
- To find direct reports: MATCH (report:Employee)-[:REPORTS_TO]->(e:Employee {{id: {employee_id}}}) RETURN report
- To find division: MATCH (e:Employee {{id: {employee_id}}})-[:IN_DIVISION]->(d:Division) RETURN d
"""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=question)
        ]

        # First LLM call with tools
        response = await model_with_tools.ainvoke(messages)

        # Check if LLM wants to use tools
        if response.tool_calls:
            # Execute the tool
            for tool_call in response.tool_calls:
                if tool_call["name"] == "query_neo4j_cypher":
                    cypher_query = tool_call["args"]["cypher_query"]
                    results = await query_neo4j_cypher.ainvoke({"cypher_query": cypher_query})

                    # Add tool result to messages
                    messages.append(response)
                    from langchain_core.messages import ToolMessage
                    messages.append(ToolMessage(
                        content=str(results),
                        tool_call_id=tool_call["id"]
                    ))

            # Second LLM call to format the answer
            final_response = await model.ainvoke(messages)
            return final_response.content

        # If no tool call, return direct response
        return response.content

    except Exception as e:
        msg = f"Error querying Neo4j with natural language: {e}"
        raise RuntimeError(msg) from e
