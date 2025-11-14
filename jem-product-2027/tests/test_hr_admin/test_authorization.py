"""Tests for authorization and RBAC."""

import pytest
from agent.tools.authorization import (
    AdminRole,
    Permission,
    has_permission,
    check_permission,
    log_audit_event,
    get_audit_log,
)


class TestAuthorization:
    """Test authorization and role-based access control."""

    def test_hr_admin_has_all_permissions(self):
        """Test that HR Admin role has all permissions."""
        role = AdminRole.HR_ADMIN

        # Check key permissions
        assert has_permission(role, Permission.CREATE_EMPLOYEE)
        assert has_permission(role, Permission.UPDATE_EMPLOYEE)
        assert has_permission(role, Permission.UPDATE_EMPLOYEE_SALARY)
        assert has_permission(role, Permission.DELETE_EMPLOYEE)
        assert has_permission(role, Permission.APPROVE_LEAVE)
        assert has_permission(role, Permission.VIEW_AUDIT_LOG)

    def test_hr_manager_limited_permissions(self):
        """Test that HR Manager has limited permissions."""
        role = AdminRole.HR_MANAGER

        # Should have these permissions
        assert has_permission(role, Permission.VIEW_EMPLOYEE)
        assert has_permission(role, Permission.UPDATE_EMPLOYEE)
        assert has_permission(role, Permission.APPROVE_LEAVE)

        # Should NOT have these permissions
        assert not has_permission(role, Permission.UPDATE_EMPLOYEE_SALARY)
        assert not has_permission(role, Permission.DELETE_EMPLOYEE)
        assert not has_permission(role, Permission.MANAGE_ROLES)

    def test_hr_viewer_read_only(self):
        """Test that HR Viewer has read-only access."""
        role = AdminRole.HR_VIEWER

        # Should have read permissions
        assert has_permission(role, Permission.VIEW_EMPLOYEE)
        assert has_permission(role, Permission.VIEW_LEAVE)

        # Should NOT have write permissions
        assert not has_permission(role, Permission.CREATE_EMPLOYEE)
        assert not has_permission(role, Permission.UPDATE_EMPLOYEE)
        assert not has_permission(role, Permission.APPROVE_LEAVE)

    def test_employee_self_service_only(self):
        """Test that Employee role has minimal permissions."""
        role = AdminRole.EMPLOYEE

        # Should have self-service permissions
        assert has_permission(role, Permission.CREATE_LEAVE_REQUEST)
        assert has_permission(role, Permission.VIEW_LEAVE)

        # Should NOT have admin permissions
        assert not has_permission(role, Permission.VIEW_EMPLOYEE)
        assert not has_permission(role, Permission.APPROVE_LEAVE)
        assert not has_permission(role, Permission.CREATE_EMPLOYEE)

    @pytest.mark.asyncio
    async def test_check_permission_hr_admin(self):
        """Test permission check for HR Admin (employee ID 1)."""
        result = await check_permission(1, Permission.CREATE_EMPLOYEE)

        assert result["authorized"] is True
        assert result["role"] == "hr_admin"
        assert "admin_name" in result

    @pytest.mark.asyncio
    async def test_check_permission_nonexistent_user(self):
        """Test permission check for non-existent user."""
        result = await check_permission(999999, Permission.VIEW_EMPLOYEE)

        assert result["authorized"] is False
        assert "not found" in result["reason"].lower()

    @pytest.mark.asyncio
    async def test_audit_logging(self):
        """Test audit log creation."""
        # Log a test event
        await log_audit_event(
            admin_id=1,
            operation="test_operation",
            target_entity="TestEntity",
            target_id=123,
            changes={"field": "value"},
            success=True
        )

        # Retrieve audit log
        result = await get_audit_log(
            admin_id=1,
            operation="test_operation",
            limit=1
        )

        assert result["success"] is True
        assert result["count"] > 0
        assert result["audit_logs"][0]["operation"] == "test_operation"

    @pytest.mark.asyncio
    async def test_audit_log_filtering(self):
        """Test audit log filtering by operation."""
        # Log multiple events
        await log_audit_event(
            admin_id=1,
            operation="create_employee",
            target_entity="Employee",
            target_id=1,
            success=True
        )

        await log_audit_event(
            admin_id=1,
            operation="update_employee",
            target_entity="Employee",
            target_id=1,
            success=True
        )

        # Filter by operation
        result = await get_audit_log(
            operation="create_employee",
            limit=10
        )

        assert result["success"] is True
        for log_entry in result["audit_logs"]:
            assert log_entry["operation"] == "create_employee"

    @pytest.mark.asyncio
    async def test_audit_log_error_tracking(self):
        """Test audit logging of failed operations."""
        await log_audit_event(
            admin_id=1,
            operation="delete_employee",
            target_entity="Employee",
            target_id=999,
            changes={"soft_delete": True},
            success=False,
            error_message="Employee not found"
        )

        result = await get_audit_log(
            admin_id=1,
            operation="delete_employee",
            limit=1
        )

        assert result["success"] is True
        if result["count"] > 0:
            log_entry = result["audit_logs"][0]
            assert log_entry["success"] is False
            assert log_entry["error_message"] is not None
