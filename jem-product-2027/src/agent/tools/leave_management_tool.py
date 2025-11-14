"""Neo4j leave management operations.

Provides tools for:
- Creating leave requests
- Approving/rejecting leave
- Querying leave balances and history
- Managing leave balances
"""

from __future__ import annotations

import os
from datetime import datetime, date
from typing import Any

from dotenv import load_dotenv
from langchain_core.tools import tool
from neo4j import AsyncGraphDatabase

load_dotenv()


def get_neo4j_driver():
    """Get Neo4j driver connection.

    Returns:
        Neo4j driver instance.
    """
    uri = os.getenv("NEO4J_URI")
    username = os.getenv("NEO4J_USERNAME")
    password = os.getenv("NEO4J_PASSWORD")

    if not all([uri, username, password]):
        msg = "Neo4j credentials not found in environment variables"
        raise ValueError(msg)

    return AsyncGraphDatabase.driver(uri, auth=(username, password))


def calculate_business_days(start_date: str, end_date: str) -> float:
    """Calculate business days between two dates.

    Simple implementation that counts weekdays.
    Does not account for public holidays.

    Args:
        start_date: Start date in YYYY-MM-DD format.
        end_date: End date in YYYY-MM-DD format.

    Returns:
        Number of business days (float).
    """
    from datetime import datetime, timedelta

    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    # Count weekdays
    business_days = 0
    current = start

    while current <= end:
        if current.weekday() < 5:  # Monday = 0, Friday = 4
            business_days += 1
        current += timedelta(days=1)

    return float(business_days)


@tool
async def create_leave_request(
    employee_id: int,
    leave_type: str,
    start_date: str,
    end_date: str,
    reason: str,
    employer_id: int | None = None,
) -> dict[str, Any]:
    """Create a new leave request for an employee.

    Leave types: annual, sick, unpaid, maternity, paternity, study, compassionate, family
    Scoped to employer for data isolation.

    Args:
        employee_id: Employee's ID.
        leave_type: Type of leave.
        start_date: Start date in YYYY-MM-DD format.
        end_date: End date in YYYY-MM-DD format.
        reason: Reason for leave request.
        employer_id: Employer ID for scoping (data isolation).

    Returns:
        Created leave request with ID and status.
    """
    driver = get_neo4j_driver()

    valid_leave_types = [
        "annual", "sick", "unpaid", "maternity", "paternity",
        "study", "compassionate", "family"
    ]

    try:
        async with driver.session() as session:
            # Validate leave type
            if leave_type not in valid_leave_types:
                return {
                    "success": False,
                    "error": f"Invalid leave type. Must be one of: {', '.join(valid_leave_types)}"
                }

            # Validate dates
            try:
                start = datetime.strptime(start_date, "%Y-%m-%d").date()
                end = datetime.strptime(end_date, "%Y-%m-%d").date()

                if end < start:
                    return {
                        "success": False,
                        "error": "End date must be after start date"
                    }

                if start < date.today():
                    return {
                        "success": False,
                        "error": "Cannot create leave request for past dates"
                    }

            except ValueError:
                return {
                    "success": False,
                    "error": "Invalid date format. Use YYYY-MM-DD"
                }

            # Check if employee exists (scoped to employer if provided)
            if employer_id:
                check_query = """
                MATCH (e:Employee {id: $employee_id, employer_id: $employer_id})
                RETURN e.first_name as first_name,
                       e.last_name as last_name,
                       e.status as status
                """
                result = await session.run(check_query, employee_id=employee_id, employer_id=employer_id)
            else:
                check_query = """
                MATCH (e:Employee {id: $employee_id})
                RETURN e.first_name as first_name,
                       e.last_name as last_name,
                       e.status as status
                """
                result = await session.run(check_query, employee_id=employee_id)
            employee = await result.single()

            if not employee:
                return {
                    "success": False,
                    "error": f"Employee with ID {employee_id} not found"
                }

            if employee["status"] != "active":
                return {
                    "success": False,
                    "error": f"Cannot create leave request for {employee['status']} employee"
                }

            # Calculate business days
            days_requested = calculate_business_days(start_date, end_date)

            # Check leave balance for leave types that require balance
            if leave_type in ["annual", "sick", "family"]:
                current_year = datetime.now().year
                balance_query = """
                MATCH (e:Employee {id: $employee_id})-[:HAS_BALANCE]->(lb:LeaveBalance)
                WHERE lb.year = $year AND lb.leave_type = $leave_type
                RETURN lb.remaining_days as remaining_days
                """
                result = await session.run(
                    balance_query,
                    employee_id=employee_id,
                    year=current_year,
                    leave_type=leave_type
                )
                balance = await result.single()

                if not balance:
                    return {
                        "success": False,
                        "error": f"No {leave_type} leave balance found for {current_year}"
                    }

                if balance["remaining_days"] < days_requested:
                    return {
                        "success": False,
                        "error": f"Insufficient leave balance. Requested: {days_requested} days, Available: {balance['remaining_days']} days"
                    }

            # Get next leave request ID
            id_query = """
            MATCH (lr:LeaveRequest)
            RETURN coalesce(max(lr.id), 0) + 1 as next_id
            """
            result = await session.run(id_query)
            record = await result.single()
            next_id = record["next_id"]

            # Create leave request
            create_query = """
            MATCH (e:Employee {id: $employee_id})
            CREATE (lr:LeaveRequest {
                id: $leave_request_id,
                employee_id: $employee_id,
                leave_type: $leave_type,
                start_date: date($start_date),
                end_date: date($end_date),
                days_requested: $days_requested,
                status: 'pending',
                reason: $reason,
                created_at: datetime(),
                updated_at: datetime()
            })
            CREATE (e)-[:SUBMITTED_LEAVE]->(lr)
            RETURN lr.id as id,
                   lr.employee_id as employee_id,
                   lr.leave_type as leave_type,
                   lr.start_date as start_date,
                   lr.end_date as end_date,
                   lr.days_requested as days_requested,
                   lr.status as status,
                   lr.reason as reason
            """

            result = await session.run(
                create_query,
                leave_request_id=next_id,
                employee_id=employee_id,
                leave_type=leave_type,
                start_date=start_date,
                end_date=end_date,
                days_requested=days_requested,
                reason=reason
            )
            record = await result.single()

            if record:
                # Update pending_days in leave balance
                if leave_type in ["annual", "sick", "family"]:
                    await session.run(
                        """
                        MATCH (e:Employee {id: $employee_id})-[:HAS_BALANCE]->(lb:LeaveBalance)
                        WHERE lb.year = $year AND lb.leave_type = $leave_type
                        SET lb.pending_days = lb.pending_days + $days_requested,
                            lb.remaining_days = lb.total_days - lb.used_days - lb.pending_days,
                            lb.updated_at = datetime()
                        """,
                        employee_id=employee_id,
                        year=datetime.now().year,
                        leave_type=leave_type,
                        days_requested=days_requested
                    )

                return {
                    "success": True,
                    "leave_request": dict(record),
                    "message": f"Leave request created successfully for {employee['first_name']} {employee['last_name']}"
                }

            return {
                "success": False,
                "error": "Failed to create leave request"
            }

    except Exception as e:
        return {
            "success": False,
            "error": f"Database error: {str(e)}"
        }
    finally:
        await driver.close()


@tool
async def approve_leave_request(
    leave_request_id: int,
    approved_by_id: int,
) -> dict[str, Any]:
    """Approve a pending leave request.

    Updates leave balance and marks request as approved.

    Args:
        leave_request_id: ID of leave request to approve.
        approved_by_id: Employee ID of manager approving the request.

    Returns:
        Updated leave request.
    """
    driver = get_neo4j_driver()

    try:
        async with driver.session() as session:
            # Get leave request details
            get_query = """
            MATCH (lr:LeaveRequest {id: $leave_request_id})
            OPTIONAL MATCH (e:Employee {id: lr.employee_id})
            RETURN lr.id as id,
                   lr.employee_id as employee_id,
                   lr.leave_type as leave_type,
                   lr.days_requested as days_requested,
                   lr.status as status,
                   e.first_name as employee_first_name,
                   e.last_name as employee_last_name
            """
            result = await session.run(get_query, leave_request_id=leave_request_id)
            leave_request = await result.single()

            if not leave_request:
                return {
                    "success": False,
                    "error": f"Leave request with ID {leave_request_id} not found"
                }

            if leave_request["status"] != "pending":
                return {
                    "success": False,
                    "error": f"Cannot approve leave request with status '{leave_request['status']}'"
                }

            # Check if approver is the employee's manager or HR admin
            manager_check_query = """
            MATCH (e:Employee {id: $employee_id})-[:REPORTS_TO]->(manager:Employee {id: $approved_by_id})
            RETURN count(manager) as is_manager
            """
            result = await session.run(
                manager_check_query,
                employee_id=leave_request["employee_id"],
                approved_by_id=approved_by_id
            )
            check = await result.single()

            # For now, allow approval (authorization will be added later)
            # if check["is_manager"] == 0:
            #     return {
            #         "success": False,
            #         "error": "Only the employee's direct manager can approve leave requests"
            #     }

            # Update leave request status
            approve_query = """
            MATCH (lr:LeaveRequest {id: $leave_request_id})
            MATCH (approver:Employee {id: $approved_by_id})
            SET lr.status = 'approved',
                lr.approved_by_id = $approved_by_id,
                lr.updated_at = datetime()
            CREATE (approver)-[:APPROVED_LEAVE]->(lr)
            RETURN lr.id as id,
                   lr.employee_id as employee_id,
                   lr.leave_type as leave_type,
                   lr.days_requested as days_requested,
                   lr.status as status,
                   approver.first_name as approved_by_first_name,
                   approver.last_name as approved_by_last_name
            """
            result = await session.run(
                approve_query,
                leave_request_id=leave_request_id,
                approved_by_id=approved_by_id
            )
            record = await result.single()

            if record:
                # Update leave balance (move from pending to used)
                if leave_request["leave_type"] in ["annual", "sick", "family"]:
                    await session.run(
                        """
                        MATCH (e:Employee {id: $employee_id})-[:HAS_BALANCE]->(lb:LeaveBalance)
                        WHERE lb.year = $year AND lb.leave_type = $leave_type
                        SET lb.used_days = lb.used_days + $days_requested,
                            lb.pending_days = lb.pending_days - $days_requested,
                            lb.remaining_days = lb.total_days - lb.used_days - lb.pending_days,
                            lb.updated_at = datetime()
                        """,
                        employee_id=leave_request["employee_id"],
                        year=datetime.now().year,
                        leave_type=leave_request["leave_type"],
                        days_requested=leave_request["days_requested"]
                    )

                return {
                    "success": True,
                    "leave_request": dict(record),
                    "message": f"Leave request approved by {record['approved_by_first_name']} {record['approved_by_last_name']}"
                }

            return {
                "success": False,
                "error": "Failed to approve leave request"
            }

    except Exception as e:
        return {
            "success": False,
            "error": f"Database error: {str(e)}"
        }
    finally:
        await driver.close()


@tool
async def reject_leave_request(
    leave_request_id: int,
    rejected_by_id: int,
    rejection_reason: str,
) -> dict[str, Any]:
    """Reject a pending leave request.

    Restores leave balance and marks request as rejected.

    Args:
        leave_request_id: ID of leave request to reject.
        rejected_by_id: Employee ID of manager rejecting the request.
        rejection_reason: Reason for rejection.

    Returns:
        Updated leave request.
    """
    driver = get_neo4j_driver()

    try:
        async with driver.session() as session:
            # Get leave request details
            get_query = """
            MATCH (lr:LeaveRequest {id: $leave_request_id})
            RETURN lr.id as id,
                   lr.employee_id as employee_id,
                   lr.leave_type as leave_type,
                   lr.days_requested as days_requested,
                   lr.status as status
            """
            result = await session.run(get_query, leave_request_id=leave_request_id)
            leave_request = await result.single()

            if not leave_request:
                return {
                    "success": False,
                    "error": f"Leave request with ID {leave_request_id} not found"
                }

            if leave_request["status"] != "pending":
                return {
                    "success": False,
                    "error": f"Cannot reject leave request with status '{leave_request['status']}'"
                }

            # Update leave request status
            reject_query = """
            MATCH (lr:LeaveRequest {id: $leave_request_id})
            SET lr.status = 'rejected',
                lr.rejected_by_id = $rejected_by_id,
                lr.rejection_reason = $rejection_reason,
                lr.updated_at = datetime()
            RETURN lr.id as id,
                   lr.status as status,
                   lr.rejection_reason as rejection_reason
            """
            result = await session.run(
                reject_query,
                leave_request_id=leave_request_id,
                rejected_by_id=rejected_by_id,
                rejection_reason=rejection_reason
            )
            record = await result.single()

            if record:
                # Restore leave balance (remove from pending)
                if leave_request["leave_type"] in ["annual", "sick", "family"]:
                    await session.run(
                        """
                        MATCH (e:Employee {id: $employee_id})-[:HAS_BALANCE]->(lb:LeaveBalance)
                        WHERE lb.year = $year AND lb.leave_type = $leave_type
                        SET lb.pending_days = lb.pending_days - $days_requested,
                            lb.remaining_days = lb.total_days - lb.used_days - lb.pending_days,
                            lb.updated_at = datetime()
                        """,
                        employee_id=leave_request["employee_id"],
                        year=datetime.now().year,
                        leave_type=leave_request["leave_type"],
                        days_requested=leave_request["days_requested"]
                    )

                return {
                    "success": True,
                    "leave_request": dict(record),
                    "message": f"Leave request rejected"
                }

            return {
                "success": False,
                "error": "Failed to reject leave request"
            }

    except Exception as e:
        return {
            "success": False,
            "error": f"Database error: {str(e)}"
        }
    finally:
        await driver.close()


@tool
async def get_leave_balance(
    employee_id: int,
    year: int | None = None,
) -> dict[str, Any]:
    """Get leave balance for an employee.

    Args:
        employee_id: Employee's ID.
        year: Year to query (default: current year).

    Returns:
        Leave balance information.
    """
    driver = get_neo4j_driver()

    if year is None:
        year = datetime.now().year

    try:
        async with driver.session() as session:
            query = """
            MATCH (e:Employee {id: $employee_id})-[:HAS_BALANCE]->(lb:LeaveBalance)
            WHERE lb.year = $year
            RETURN lb.leave_type as leave_type,
                   lb.total_days as total_days,
                   lb.used_days as used_days,
                   lb.pending_days as pending_days,
                   lb.remaining_days as remaining_days,
                   lb.year as year
            ORDER BY lb.leave_type
            """
            result = await session.run(query, employee_id=employee_id, year=year)
            records = await result.data()

            if records:
                return {
                    "success": True,
                    "employee_id": employee_id,
                    "year": year,
                    "balances": records
                }

            return {
                "success": False,
                "error": f"No leave balance found for employee {employee_id} in year {year}"
            }

    except Exception as e:
        return {
            "success": False,
            "error": f"Database error: {str(e)}"
        }
    finally:
        await driver.close()


@tool
async def get_leave_history(
    employee_id: int,
    year: int | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    """Get leave request history for an employee.

    Args:
        employee_id: Employee's ID.
        year: Filter by year (optional).
        status: Filter by status (pending/approved/rejected, optional).

    Returns:
        List of leave requests.
    """
    driver = get_neo4j_driver()

    try:
        async with driver.session() as session:
            query = """
            MATCH (e:Employee {id: $employee_id})-[:SUBMITTED_LEAVE]->(lr:LeaveRequest)
            """

            # Add filters
            filters = []
            params = {"employee_id": employee_id}

            if year:
                filters.append("date(lr.start_date).year = $year")
                params["year"] = year

            if status:
                filters.append("lr.status = $status")
                params["status"] = status

            if filters:
                query += "WHERE " + " AND ".join(filters) + "\n"

            query += """
            OPTIONAL MATCH (approver:Employee)-[:APPROVED_LEAVE]->(lr)
            RETURN lr.id as id,
                   lr.leave_type as leave_type,
                   lr.start_date as start_date,
                   lr.end_date as end_date,
                   lr.days_requested as days_requested,
                   lr.status as status,
                   lr.reason as reason,
                   lr.rejection_reason as rejection_reason,
                   approver.first_name as approved_by_first_name,
                   approver.last_name as approved_by_last_name,
                   lr.created_at as created_at
            ORDER BY lr.created_at DESC
            """

            result = await session.run(query, **params)
            records = await result.data()

            return {
                "success": True,
                "employee_id": employee_id,
                "leave_requests": records
            }

    except Exception as e:
        return {
            "success": False,
            "error": f"Database error: {str(e)}"
        }
    finally:
        await driver.close()


@tool
async def get_pending_leave_requests(
    manager_id: int,
    employer_id: int | None = None,
) -> dict[str, Any]:
    """Get pending leave requests for employees reporting to a manager.

    Scoped to employer for data isolation.

    Args:
        manager_id: Manager's employee ID.
        employer_id: Employer ID for scoping (data isolation).

    Returns:
        List of pending leave requests from direct reports.
    """
    driver = get_neo4j_driver()

    try:
        async with driver.session() as session:
            # Scope to employer if provided
            if employer_id:
                query = """
                MATCH (report:Employee)-[:REPORTS_TO]->(manager:Employee {id: $manager_id})
                WHERE report.employer_id = $employer_id AND manager.employer_id = $employer_id
                MATCH (report)-[:SUBMITTED_LEAVE]->(lr:LeaveRequest {status: 'pending'})
                RETURN lr.id as id,
                       report.id as employee_id,
                       report.first_name as employee_first_name,
                       report.last_name as employee_last_name,
                       lr.leave_type as leave_type,
                       lr.start_date as start_date,
                       lr.end_date as end_date,
                       lr.days_requested as days_requested,
                       lr.reason as reason,
                       lr.created_at as created_at
                ORDER BY lr.created_at ASC
                """
                result = await session.run(query, manager_id=manager_id, employer_id=employer_id)
            else:
                query = """
                MATCH (report:Employee)-[:REPORTS_TO]->(manager:Employee {id: $manager_id})
                MATCH (report)-[:SUBMITTED_LEAVE]->(lr:LeaveRequest {status: 'pending'})
                RETURN lr.id as id,
                       report.id as employee_id,
                       report.first_name as employee_first_name,
                       report.last_name as employee_last_name,
                       lr.leave_type as leave_type,
                       lr.start_date as start_date,
                       lr.end_date as end_date,
                       lr.days_requested as days_requested,
                       lr.reason as reason,
                       lr.created_at as created_at
                ORDER BY lr.created_at ASC
                """
                result = await session.run(query, manager_id=manager_id)
            records = await result.data()

            return {
                "success": True,
                "manager_id": manager_id,
                "pending_requests": records,
                "count": len(records)
            }

    except Exception as e:
        return {
            "success": False,
            "error": f"Database error: {str(e)}"
        }
    finally:
        await driver.close()
