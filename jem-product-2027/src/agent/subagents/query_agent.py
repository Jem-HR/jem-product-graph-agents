"""Query subagent wrapper.

Wraps the existing employee query functionality for use as a subagent.
Handles read-only queries about employees, org structure, and relationships.
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from agent.tools.neo4j_tool import query_neo4j_with_natural_language
from agent.tools.authorization import check_permission, Permission


@tool
async def query_employee_info(
    question: str,
    admin_id: int,
    employee_context: dict[str, Any] | None = None,
    employer_id: int | None = None,
) -> str:
    """Query employee information and organizational relationships.

    Uses the existing Neo4j natural language query system to answer questions
    about employees, managers, teams, org structure, etc.
    All queries are scoped to the admin's employer for data isolation.

    Args:
        question: Natural language question about employees or org structure.
        admin_id: ID of admin performing the query.
        employee_context: Optional employee context for personalized queries.
        employer_id: Employer ID for scoping queries (data isolation).

    Returns:
        Answer to the question.
    """
    # Check authorization
    auth_result = await check_permission(admin_id, Permission.VIEW_EMPLOYEE, employer_id=employer_id)

    if not auth_result["authorized"]:
        return f"❌ Permission denied: {auth_result['reason']}"

    # Get employer_id from auth result if not provided
    if not employer_id:
        employer_id = auth_result.get("employer_id")

    # If no employee_context provided, use admin's context
    if not employee_context:
        # Get admin's employee record
        from agent.tools.neo4j_tool import get_neo4j_driver

        driver = get_neo4j_driver()
        try:
            async with driver.session() as session:
                query = """
                MATCH (e:Employee {id: $admin_id})
                RETURN e.id as id,
                       e.first_name as first_name,
                       e.last_name as last_name,
                       e.mobile_number as mobile_number,
                       e.email as email,
                       e.status as status,
                       e.employer_id as employer_id
                """
                result = await session.run(query, admin_id=admin_id)
                record = await result.single()

                if record:
                    employee_context = dict(record)
                else:
                    return f"❌ Admin with ID {admin_id} not found in employee records"
        finally:
            await driver.close()

    # Use the existing natural language query system with employer scoping
    # Add employer context to the question
    if employer_id:
        scoped_question = f"{question} (Only show results for employer ID {employer_id})"
    else:
        scoped_question = question

    try:
        answer = await query_neo4j_with_natural_language(scoped_question, employee_context, employer_id)
        return answer
    except Exception as e:
        return f"❌ Error querying employee information: {str(e)}"
