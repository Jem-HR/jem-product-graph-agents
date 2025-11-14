"""Authorization and role-based access control (RBAC) for HR operations.

Defines roles, permissions, and audit logging for HR admin operations.
"""

from __future__ import annotations

import os
from datetime import datetime
from enum import Enum
from typing import Any

from dotenv import load_dotenv
from neo4j import AsyncGraphDatabase

load_dotenv()


class AdminRole(str, Enum):
    """Admin roles with different permission levels."""

    HR_ADMIN = "hr_admin"  # Full CRUD access
    HR_MANAGER = "hr_manager"  # Read + Leave approvals + Limited updates
    HR_VIEWER = "hr_viewer"  # Read-only access
    EMPLOYEE = "employee"  # Self-service only


class Permission(str, Enum):
    """Granular permissions for operations."""

    # Employee CRUD permissions
    CREATE_EMPLOYEE = "create_employee"
    UPDATE_EMPLOYEE = "update_employee"
    UPDATE_EMPLOYEE_SALARY = "update_employee_salary"
    DELETE_EMPLOYEE = "delete_employee"
    VIEW_EMPLOYEE = "view_employee"

    # Leave management permissions
    CREATE_LEAVE_REQUEST = "create_leave_request"
    APPROVE_LEAVE = "approve_leave"
    REJECT_LEAVE = "reject_leave"
    VIEW_LEAVE = "view_leave"
    VIEW_TEAM_LEAVE = "view_team_leave"

    # Administrative permissions
    VIEW_AUDIT_LOG = "view_audit_log"
    MANAGE_ROLES = "manage_roles"


# Role to permissions mapping
ROLE_PERMISSIONS: dict[AdminRole, set[Permission]] = {
    AdminRole.HR_ADMIN: {
        # Full access to all operations
        Permission.CREATE_EMPLOYEE,
        Permission.UPDATE_EMPLOYEE,
        Permission.UPDATE_EMPLOYEE_SALARY,
        Permission.DELETE_EMPLOYEE,
        Permission.VIEW_EMPLOYEE,
        Permission.CREATE_LEAVE_REQUEST,
        Permission.APPROVE_LEAVE,
        Permission.REJECT_LEAVE,
        Permission.VIEW_LEAVE,
        Permission.VIEW_TEAM_LEAVE,
        Permission.VIEW_AUDIT_LOG,
        Permission.MANAGE_ROLES,
    },
    AdminRole.HR_MANAGER: {
        # Can view and update employees, approve leave
        Permission.VIEW_EMPLOYEE,
        Permission.UPDATE_EMPLOYEE,  # Limited updates, no salary
        Permission.CREATE_LEAVE_REQUEST,
        Permission.APPROVE_LEAVE,
        Permission.REJECT_LEAVE,
        Permission.VIEW_LEAVE,
        Permission.VIEW_TEAM_LEAVE,
    },
    AdminRole.HR_VIEWER: {
        # Read-only access
        Permission.VIEW_EMPLOYEE,
        Permission.VIEW_LEAVE,
        Permission.VIEW_TEAM_LEAVE,
    },
    AdminRole.EMPLOYEE: {
        # Self-service only
        Permission.CREATE_LEAVE_REQUEST,
        Permission.VIEW_LEAVE,  # Own leave only
    },
}


class AuthorizationError(Exception):
    """Raised when user lacks required permissions."""

    pass


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


def has_permission(role: AdminRole, permission: Permission) -> bool:
    """Check if a role has a specific permission.

    Args:
        role: Admin role to check.
        permission: Required permission.

    Returns:
        True if role has permission, False otherwise.
    """
    return permission in ROLE_PERMISSIONS.get(role, set())


async def check_permission(
    admin_id: int,
    permission: Permission,
    target_employee_id: int | None = None,
    employer_id: int | None = None,
) -> dict[str, Any]:
    """Check if admin has permission for an operation.

    For employee self-service operations, also checks if admin is the target employee.
    Returns employer_id for scoping queries.

    Args:
        admin_id: Admin's employee ID.
        permission: Required permission.
        target_employee_id: Target employee ID for self-service operations.
        employer_id: Employer ID for additional validation (optional).

    Returns:
        Dict with 'authorized' boolean, 'employer_id', and 'reason' if not authorized.
    """
    driver = get_neo4j_driver()

    try:
        async with driver.session() as session:
            # Get admin's role
            # For now, we'll check if employee is a manager by checking REPORTS_TO relationships
            # In production, you'd have a role property on Employee node
            query = """
            MATCH (admin:Employee {id: $admin_id})
            OPTIONAL MATCH (report:Employee)-[:REPORTS_TO]->(admin)
            WHERE report.employer_id = admin.employer_id
            WITH admin, count(report) as report_count
            RETURN admin.id as id,
                   admin.first_name as first_name,
                   admin.last_name as last_name,
                   admin.status as status,
                   admin.employer_id as employer_id,
                   CASE
                       WHEN admin.id = 101487 THEN 'hr_admin'  // Employee ID 101487 is HR admin
                       WHEN report_count > 0 THEN 'hr_manager'
                       ELSE 'employee'
                   END as role
            """
            result = await session.run(query, admin_id=admin_id)
            admin = await result.single()

            if not admin:
                return {
                    "authorized": False,
                    "reason": f"Admin with ID {admin_id} not found"
                }

            if admin["status"] != "active":
                return {
                    "authorized": False,
                    "reason": f"Admin account is {admin['status']}"
                }

            # Get admin role
            role = AdminRole(admin["role"])

            # Check if role has permission
            if not has_permission(role, permission):
                return {
                    "authorized": False,
                    "reason": f"Role '{role.value}' does not have permission '{permission.value}'"
                }

            # For self-service operations, verify admin is the target employee
            if target_employee_id and permission in [Permission.CREATE_LEAVE_REQUEST, Permission.VIEW_LEAVE]:
                if role == AdminRole.EMPLOYEE and admin_id != target_employee_id:
                    return {
                        "authorized": False,
                        "reason": "Employees can only perform this operation on their own records"
                    }

            return {
                "authorized": True,
                "admin_id": admin_id,
                "admin_name": f"{admin['first_name']} {admin['last_name']}",
                "role": role.value,
                "employer_id": admin.get("employer_id")  # Return for scoping queries
            }

    except Exception as e:
        return {
            "authorized": False,
            "reason": f"Authorization check failed: {str(e)}"
        }
    finally:
        await driver.close()


async def log_audit_event(
    admin_id: int,
    operation: str,
    target_entity: str,
    target_id: int,
    changes: dict[str, Any] | None = None,
    success: bool = True,
    error_message: str | None = None,
) -> None:
    """Log an audit event for administrative operations.

    Creates an AuditLog node in Neo4j tracking all CRUD operations.

    Args:
        admin_id: ID of admin performing the operation.
        operation: Operation type (e.g., 'create_employee', 'approve_leave').
        target_entity: Entity type (e.g., 'Employee', 'LeaveRequest').
        target_id: ID of the entity being modified.
        changes: Dict of changes made (optional).
        success: Whether operation succeeded.
        error_message: Error message if operation failed.
    """
    driver = get_neo4j_driver()

    try:
        async with driver.session() as session:
            # Get next audit log ID
            id_query = """
            MATCH (al:AuditLog)
            RETURN coalesce(max(al.id), 0) + 1 as next_id
            """
            result = await session.run(id_query)
            record = await result.single()
            next_id = record["next_id"]

            # Create audit log entry
            import json

            create_query = """
            MATCH (admin:Employee {id: $admin_id})
            CREATE (al:AuditLog {
                id: $log_id,
                admin_id: $admin_id,
                operation: $operation,
                target_entity: $target_entity,
                target_id: $target_id,
                changes: $changes,
                success: $success,
                error_message: $error_message,
                timestamp: datetime()
            })
            CREATE (admin)-[:PERFORMED]->(al)
            """

            await session.run(
                create_query,
                log_id=next_id,
                admin_id=admin_id,
                operation=operation,
                target_entity=target_entity,
                target_id=target_id,
                changes=json.dumps(changes) if changes else None,
                success=success,
                error_message=error_message
            )

    except Exception as e:
        # Log to stdout if database logging fails
        print(f"Failed to log audit event: {e}")
    finally:
        await driver.close()


async def get_audit_log(
    admin_id: int | None = None,
    operation: str | None = None,
    target_entity: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """Retrieve audit log entries.

    Args:
        admin_id: Filter by admin ID (optional).
        operation: Filter by operation type (optional).
        target_entity: Filter by entity type (optional).
        limit: Maximum number of entries to return.

    Returns:
        List of audit log entries.
    """
    driver = get_neo4j_driver()

    try:
        async with driver.session() as session:
            query = """
            MATCH (admin:Employee)-[:PERFORMED]->(al:AuditLog)
            """

            # Add filters
            filters = []
            params = {"limit": limit}

            if admin_id:
                filters.append("admin.id = $admin_id")
                params["admin_id"] = admin_id

            if operation:
                filters.append("al.operation = $operation")
                params["operation"] = operation

            if target_entity:
                filters.append("al.target_entity = $target_entity")
                params["target_entity"] = target_entity

            if filters:
                query += "WHERE " + " AND ".join(filters) + "\n"

            query += """
            RETURN al.id as id,
                   admin.id as admin_id,
                   admin.first_name as admin_first_name,
                   admin.last_name as admin_last_name,
                   al.operation as operation,
                   al.target_entity as target_entity,
                   al.target_id as target_id,
                   al.changes as changes,
                   al.success as success,
                   al.error_message as error_message,
                   al.timestamp as timestamp
            ORDER BY al.timestamp DESC
            LIMIT $limit
            """

            result = await session.run(query, **params)
            records = await result.data()

            return {
                "success": True,
                "audit_logs": records,
                "count": len(records)
            }

    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to retrieve audit log: {str(e)}"
        }
    finally:
        await driver.close()


# Decorator for permission checking (for use in agents)
def require_permission(permission: Permission):
    """Decorator to check permissions before executing a function.

    Usage:
        @require_permission(Permission.CREATE_EMPLOYEE)
        async def create_employee_handler(state, runtime):
            ...
    """
    def decorator(func):
        async def wrapper(state, runtime):
            admin_context = state.get("admin_context", {})
            admin_id = admin_context.get("id")

            if not admin_id:
                return {
                    "error": "No admin context found. Please authenticate first."
                }

            # Check permission
            auth_result = await check_permission(admin_id, permission)

            if not auth_result["authorized"]:
                return {
                    "error": f"Permission denied: {auth_result['reason']}"
                }

            # Execute original function
            return await func(state, runtime)

        return wrapper
    return decorator
