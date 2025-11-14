"""Leave management subagent.

Specialized agent for handling leave requests, approvals, and balance queries.
Uses LangChain with tool calling for leave management operations.
"""

from __future__ import annotations

from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.tools import tool

from agent.tools.leave_management_tool import (
    create_leave_request,
    approve_leave_request,
    reject_leave_request,
    get_leave_balance,
    get_leave_history,
    get_pending_leave_requests,
)
from agent.tools.authorization import check_permission, Permission, log_audit_event


@tool
async def leave_management_agent(
    operation: str,
    admin_id: int,
    leave_data: dict[str, Any],
    employer_id: int | None = None,
) -> str:
    """Handle leave management operations with validation and authorization.

    This specialized agent handles leave requests, approvals, rejections, and queries.
    All operations are scoped to the admin's employer for data isolation.

    Args:
        operation: Operation to perform ('create', 'approve', 'reject', 'balance', 'history', 'pending').
        admin_id: ID of admin/employee performing the operation.
        leave_data: Leave data including required fields for the operation.
        employer_id: Employer ID for scoping queries (data isolation).

    Returns:
        Result message describing the outcome.
    """
    model = ChatAnthropic(model="claude-haiku-4-5-20251001")

    # Map operations to permissions
    permission_map = {
        "create": Permission.CREATE_LEAVE_REQUEST,
        "approve": Permission.APPROVE_LEAVE,
        "reject": Permission.REJECT_LEAVE,
        "balance": Permission.VIEW_LEAVE,
        "history": Permission.VIEW_LEAVE,
        "pending": Permission.VIEW_TEAM_LEAVE,
    }

    required_permission = permission_map.get(operation)

    if not required_permission:
        return f"Invalid operation: {operation}. Must be 'create', 'approve', 'reject', 'balance', 'history', or 'pending'"

    # For view operations on self, allow employee role
    target_employee_id = leave_data.get("employee_id") if operation in ["balance", "history"] else None

    # Check authorization
    auth_result = await check_permission(admin_id, required_permission, target_employee_id, employer_id)

    if not auth_result["authorized"]:
        return f"❌ Permission denied: {auth_result['reason']}"

    # Get employer_id from auth result if not provided
    if not employer_id:
        employer_id = auth_result.get("employer_id")

    # Perform the operation
    try:
        if operation == "create":
            # Validate required fields
            required_fields = ["employee_id", "leave_type", "start_date", "end_date", "reason"]
            missing_fields = [f for f in required_fields if f not in leave_data]

            if missing_fields:
                return f"❌ Missing required fields: {', '.join(missing_fields)}"

            result = await create_leave_request.ainvoke(leave_data)

            # Log audit event
            if result.get("success"):
                leave_request = result["leave_request"]
                await log_audit_event(
                    admin_id=admin_id,
                    operation="create_leave_request",
                    target_entity="LeaveRequest",
                    target_id=leave_request["id"],
                    changes=leave_data,
                    success=True
                )

                return (
                    f"✅ Leave request created successfully!\n\n"
                    f"**Leave Request Details:**\n"
                    f"- Request ID: {leave_request['id']}\n"
                    f"- Leave Type: {leave_request['leave_type']}\n"
                    f"- Dates: {leave_request['start_date']} to {leave_request['end_date']}\n"
                    f"- Days: {leave_request['days_requested']}\n"
                    f"- Status: {leave_request['status']}\n"
                    f"- Reason: {leave_request['reason']}"
                )
            else:
                await log_audit_event(
                    admin_id=admin_id,
                    operation="create_leave_request",
                    target_entity="LeaveRequest",
                    target_id=0,
                    changes=leave_data,
                    success=False,
                    error_message=result.get("error")
                )
                return f"❌ Failed to create leave request: {result.get('error')}"

        elif operation == "approve":
            leave_request_id = leave_data.get("leave_request_id")
            if not leave_request_id:
                return "❌ Missing leave_request_id for approve operation"

            result = await approve_leave_request.ainvoke({
                "leave_request_id": leave_request_id,
                "approved_by_id": admin_id
            })

            # Log audit event
            if result.get("success"):
                leave_request = result["leave_request"]
                await log_audit_event(
                    admin_id=admin_id,
                    operation="approve_leave",
                    target_entity="LeaveRequest",
                    target_id=leave_request_id,
                    changes={"approved_by_id": admin_id},
                    success=True
                )

                return (
                    f"✅ Leave request approved!\n\n"
                    f"**Approved Leave:**\n"
                    f"- Request ID: {leave_request['id']}\n"
                    f"- Employee ID: {leave_request['employee_id']}\n"
                    f"- Leave Type: {leave_request['leave_type']}\n"
                    f"- Days: {leave_request['days_requested']}\n"
                    f"- Approved By: {leave_request.get('approved_by_first_name', '')} {leave_request.get('approved_by_last_name', '')}"
                )
            else:
                await log_audit_event(
                    admin_id=admin_id,
                    operation="approve_leave",
                    target_entity="LeaveRequest",
                    target_id=leave_request_id,
                    changes={"approved_by_id": admin_id},
                    success=False,
                    error_message=result.get("error")
                )
                return f"❌ Failed to approve leave: {result.get('error')}"

        elif operation == "reject":
            leave_request_id = leave_data.get("leave_request_id")
            rejection_reason = leave_data.get("rejection_reason")

            if not leave_request_id:
                return "❌ Missing leave_request_id for reject operation"
            if not rejection_reason:
                return "❌ Missing rejection_reason for reject operation"

            result = await reject_leave_request.ainvoke({
                "leave_request_id": leave_request_id,
                "rejected_by_id": admin_id,
                "rejection_reason": rejection_reason
            })

            # Log audit event
            if result.get("success"):
                leave_request = result["leave_request"]
                await log_audit_event(
                    admin_id=admin_id,
                    operation="reject_leave",
                    target_entity="LeaveRequest",
                    target_id=leave_request_id,
                    changes={"rejected_by_id": admin_id, "rejection_reason": rejection_reason},
                    success=True
                )

                return (
                    f"✅ Leave request rejected\n\n"
                    f"**Rejected Leave:**\n"
                    f"- Request ID: {leave_request['id']}\n"
                    f"- Status: {leave_request['status']}\n"
                    f"- Rejection Reason: {leave_request['rejection_reason']}"
                )
            else:
                await log_audit_event(
                    admin_id=admin_id,
                    operation="reject_leave",
                    target_entity="LeaveRequest",
                    target_id=leave_request_id,
                    changes={"rejected_by_id": admin_id, "rejection_reason": rejection_reason},
                    success=False,
                    error_message=result.get("error")
                )
                return f"❌ Failed to reject leave: {result.get('error')}"

        elif operation == "balance":
            employee_id = leave_data.get("employee_id")
            year = leave_data.get("year")

            if not employee_id:
                return "❌ Missing employee_id for balance query"

            result = await get_leave_balance.ainvoke({
                "employee_id": employee_id,
                "year": year
            })

            if result.get("success"):
                balances = result["balances"]
                if not balances:
                    return f"No leave balance found for employee {employee_id}"

                response = f"**Leave Balance for Employee {employee_id} (Year {result['year']}):**\n\n"

                for balance in balances:
                    response += (
                        f"**{balance['leave_type'].title()} Leave:**\n"
                        f"- Total: {balance['total_days']} days\n"
                        f"- Used: {balance['used_days']} days\n"
                        f"- Pending: {balance['pending_days']} days\n"
                        f"- Remaining: {balance['remaining_days']} days\n\n"
                    )

                return response
            else:
                return f"❌ Failed to get leave balance: {result.get('error')}"

        elif operation == "history":
            employee_id = leave_data.get("employee_id")
            year = leave_data.get("year")
            status = leave_data.get("status")

            if not employee_id:
                return "❌ Missing employee_id for history query"

            result = await get_leave_history.ainvoke({
                "employee_id": employee_id,
                "year": year,
                "status": status
            })

            if result.get("success"):
                leave_requests = result["leave_requests"]

                if not leave_requests:
                    return f"No leave history found for employee {employee_id}"

                response = f"**Leave History for Employee {employee_id}:**\n\n"

                for lr in leave_requests:
                    response += (
                        f"**Request #{lr['id']}** - {lr['status'].upper()}\n"
                        f"- Type: {lr['leave_type']}\n"
                        f"- Dates: {lr['start_date']} to {lr['end_date']}\n"
                        f"- Days: {lr['days_requested']}\n"
                        f"- Reason: {lr['reason']}\n"
                    )

                    if lr.get('approved_by_first_name'):
                        response += f"- Approved By: {lr['approved_by_first_name']} {lr['approved_by_last_name']}\n"

                    if lr.get('rejection_reason'):
                        response += f"- Rejection Reason: {lr['rejection_reason']}\n"

                    response += "\n"

                return response
            else:
                return f"❌ Failed to get leave history: {result.get('error')}"

        elif operation == "pending":
            manager_id = leave_data.get("manager_id") or admin_id  # Default to admin if not specified

            result = await get_pending_leave_requests.ainvoke({
                "manager_id": manager_id,
                "employer_id": employer_id
            })

            if result.get("success"):
                pending_requests = result["pending_requests"]
                count = result["count"]

                if count == 0:
                    return f"No pending leave requests for approval"

                response = f"**Pending Leave Requests ({count}):**\n\n"

                for req in pending_requests:
                    response += (
                        f"**Request #{req['id']}**\n"
                        f"- Employee: {req['employee_first_name']} {req['employee_last_name']} (ID: {req['employee_id']})\n"
                        f"- Type: {req['leave_type']}\n"
                        f"- Dates: {req['start_date']} to {req['end_date']}\n"
                        f"- Days: {req['days_requested']}\n"
                        f"- Reason: {req['reason']}\n"
                        f"- Submitted: {req['created_at']}\n\n"
                    )

                return response
            else:
                return f"❌ Failed to get pending requests: {result.get('error')}"

    except Exception as e:
        return f"❌ Error performing {operation}: {str(e)}"
