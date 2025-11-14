"""Employee CRUD subagent.

Specialized agent for handling employee create, update, and delete operations.
Uses LangChain with tool calling for structured CRUD operations.
"""

from __future__ import annotations

from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.tools import tool

from agent.tools.neo4j_crud_tool import (
    create_employee,
    update_employee,
    delete_employee,
    update_employee_relationships,
)
from agent.tools.authorization import check_permission, Permission, log_audit_event


@tool
async def employee_crud_agent(
    operation: str,
    admin_id: int,
    employee_data: dict[str, Any],
    employer_id: int | None = None,
) -> str:
    """Handle employee CRUD operations with validation and authorization.

    This is a specialized agent that can create, update, or delete employees.
    All operations are scoped to the admin's employer for data isolation.

    Args:
        operation: Operation to perform ('create', 'update', 'delete').
        admin_id: ID of admin performing the operation.
        employee_data: Employee data including fields to create/update.
        employer_id: Employer ID for scoping queries (for data isolation).

    Returns:
        Result message describing the outcome.
    """
    model = ChatAnthropic(model="claude-haiku-4-5-20251001")

    # Map operations to permissions
    permission_map = {
        "create": Permission.CREATE_EMPLOYEE,
        "update": Permission.UPDATE_EMPLOYEE,
        "delete": Permission.DELETE_EMPLOYEE,
    }

    # Check if salary is being updated (requires special permission)
    if operation == "update" and "salary" in employee_data:
        required_permission = Permission.UPDATE_EMPLOYEE_SALARY
    else:
        required_permission = permission_map.get(operation)

    if not required_permission:
        return f"Invalid operation: {operation}. Must be 'create', 'update', or 'delete'"

    # Check authorization
    auth_result = await check_permission(admin_id, required_permission, employer_id=employer_id)

    if not auth_result["authorized"]:
        return f"❌ Permission denied: {auth_result['reason']}"

    # Get employer_id from auth result if not provided
    if not employer_id:
        employer_id = auth_result.get("employer_id")

    # Perform the operation
    try:
        if operation == "create":
            # Validate required fields
            required_fields = ["first_name", "last_name", "mobile_number", "email", "employer_id", "employee_no"]
            missing_fields = [f for f in required_fields if f not in employee_data]

            if missing_fields:
                return f"❌ Missing required fields: {', '.join(missing_fields)}"

            # Ensure employee is created in the same employer
            employee_data["employer_id"] = employer_id

            result = await create_employee.ainvoke(employee_data)

            # Log audit event
            if result.get("success"):
                await log_audit_event(
                    admin_id=admin_id,
                    operation="create_employee",
                    target_entity="Employee",
                    target_id=result["employee"]["id"],
                    changes=employee_data,
                    success=True
                )

                employee = result["employee"]
                return (
                    f"✅ Employee created successfully!\n\n"
                    f"**Employee Details:**\n"
                    f"- ID: {employee['id']}\n"
                    f"- Name: {employee['first_name']} {employee['last_name']}\n"
                    f"- Mobile: {employee['mobile_number']}\n"
                    f"- Email: {employee['email']}\n"
                    f"- Status: {employee['status']}"
                )
            else:
                await log_audit_event(
                    admin_id=admin_id,
                    operation="create_employee",
                    target_entity="Employee",
                    target_id=0,
                    changes=employee_data,
                    success=False,
                    error_message=result.get("error")
                )
                return f"❌ Failed to create employee: {result.get('error')}"

        elif operation == "update":
            employee_id = employee_data.get("employee_id")
            if not employee_id:
                return "❌ Missing employee_id for update operation"

            # Remove employee_id from update data
            update_data = {k: v for k, v in employee_data.items() if k != "employee_id"}
            update_data["employee_id"] = employee_id
            update_data["employer_id"] = employer_id  # For scoping check

            result = await update_employee.ainvoke(update_data)

            # Log audit event
            if result.get("success"):
                await log_audit_event(
                    admin_id=admin_id,
                    operation="update_employee",
                    target_entity="Employee",
                    target_id=employee_id,
                    changes=update_data,
                    success=True
                )

                employee = result["employee"]
                return (
                    f"✅ Employee updated successfully!\n\n"
                    f"**Updated Employee Details:**\n"
                    f"- ID: {employee['id']}\n"
                    f"- Name: {employee['first_name']} {employee['last_name']}\n"
                    f"- Email: {employee['email']}\n"
                    f"- Status: {employee['status']}\n"
                    f"- Updated: {employee.get('updated_at', 'N/A')}"
                )
            else:
                await log_audit_event(
                    admin_id=admin_id,
                    operation="update_employee",
                    target_entity="Employee",
                    target_id=employee_id,
                    changes=update_data,
                    success=False,
                    error_message=result.get("error")
                )
                return f"❌ Failed to update employee: {result.get('error')}"

        elif operation == "delete":
            employee_id = employee_data.get("employee_id")
            if not employee_id:
                return "❌ Missing employee_id for delete operation"

            soft_delete = employee_data.get("soft_delete", True)

            result = await delete_employee.ainvoke({
                "employee_id": employee_id,
                "soft_delete": soft_delete,
                "employer_id": employer_id  # For scoping check
            })

            # Log audit event
            if result.get("success"):
                await log_audit_event(
                    admin_id=admin_id,
                    operation="delete_employee",
                    target_entity="Employee",
                    target_id=employee_id,
                    changes={"soft_delete": soft_delete},
                    success=True
                )

                return f"✅ {result['message']}"
            else:
                await log_audit_event(
                    admin_id=admin_id,
                    operation="delete_employee",
                    target_entity="Employee",
                    target_id=employee_id,
                    changes={"soft_delete": soft_delete},
                    success=False,
                    error_message=result.get("error")
                )
                return f"❌ Failed to delete employee: {result.get('error')}"

    except Exception as e:
        return f"❌ Error performing {operation}: {str(e)}"
