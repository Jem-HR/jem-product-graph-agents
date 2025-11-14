"""Integration tests for HR Admin agent."""

import pytest
from agent.subagents.employee_crud_agent import employee_crud_agent
from agent.subagents.leave_agent import leave_management_agent
from agent.subagents.query_agent import query_employee_info
from datetime import datetime, timedelta


class TestHRAdminIntegration:
    """Integration tests for HR Admin workflows."""

    @pytest.mark.asyncio
    async def test_full_employee_lifecycle(self):
        """Test complete employee lifecycle: create, update, query, delete."""
        admin_id = 1  # HR Admin

        # 1. Create employee
        create_result = await employee_crud_agent.ainvoke({
            "operation": "create",
            "admin_id": admin_id,
            "employee_data": {
                "first_name": "Integration",
                "last_name": "Test",
                "mobile_number": "27829999999",
                "email": "integration.test@example.com",
                "employer_id": 1,
                "employee_no": "INT001",
                "salary": 60000.0,
            }
        })

        assert "created successfully" in create_result or "Employee created" in create_result

        # Extract employee ID from response
        # This is a simple parse - in real tests you'd use regex or structured data
        import re
        id_match = re.search(r"ID: (\d+)", create_result)
        if id_match:
            employee_id = int(id_match.group(1))

            # 2. Update employee
            update_result = await employee_crud_agent.ainvoke({
                "operation": "update",
                "admin_id": admin_id,
                "employee_data": {
                    "employee_id": employee_id,
                    "email": "updated.integration@example.com",
                }
            })

            assert "updated successfully" in update_result or "Employee updated" in update_result

            # 3. Query employee
            query_result = await query_employee_info.ainvoke({
                "question": f"What is the email of employee {employee_id}?",
                "admin_id": admin_id,
            })

            assert "updated.integration@example.com" in query_result

            # 4. Delete employee
            delete_result = await employee_crud_agent.ainvoke({
                "operation": "delete",
                "admin_id": admin_id,
                "employee_data": {
                    "employee_id": employee_id,
                    "soft_delete": False,
                }
            })

            assert "deleted" in delete_result or "deactivated" in delete_result

    @pytest.mark.asyncio
    async def test_leave_approval_workflow(self):
        """Test complete leave approval workflow."""
        # This test assumes employee with ID 1 exists and has direct reports
        admin_id = 1
        employee_id = 1

        # 1. Check leave balance
        balance_result = await leave_management_agent.ainvoke({
            "operation": "balance",
            "admin_id": employee_id,
            "leave_data": {
                "employee_id": employee_id,
            }
        })

        assert "Leave Balance" in balance_result

        # 2. Create leave request
        start_date = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")
        end_date = (datetime.now() + timedelta(days=16)).strftime("%Y-%m-%d")

        create_result = await leave_management_agent.ainvoke({
            "operation": "create",
            "admin_id": employee_id,
            "leave_data": {
                "employee_id": employee_id,
                "leave_type": "annual",
                "start_date": start_date,
                "end_date": end_date,
                "reason": "Integration test leave",
            }
        })

        if "created successfully" in create_result:
            # Extract leave request ID
            import re
            id_match = re.search(r"Request ID: (\d+)", create_result)

            if id_match:
                leave_request_id = int(id_match.group(1))

                # 3. Approve leave request
                approve_result = await leave_management_agent.ainvoke({
                    "operation": "approve",
                    "admin_id": admin_id,
                    "leave_data": {
                        "leave_request_id": leave_request_id,
                    }
                })

                assert "approved" in approve_result.lower()

                # 4. Check leave history
                history_result = await leave_management_agent.ainvoke({
                    "operation": "history",
                    "admin_id": employee_id,
                    "leave_data": {
                        "employee_id": employee_id,
                        "status": "approved",
                    }
                })

                assert "Leave History" in history_result

    @pytest.mark.asyncio
    async def test_permission_enforcement(self):
        """Test that permissions are properly enforced."""
        # Try to create employee as a regular employee (should fail)
        employee_id = 2  # Assuming this is not HR admin

        result = await employee_crud_agent.ainvoke({
            "operation": "create",
            "admin_id": employee_id,
            "employee_data": {
                "first_name": "Should",
                "last_name": "Fail",
                "mobile_number": "27821111222",
                "email": "should.fail@example.com",
                "employer_id": 1,
                "employee_no": "FAIL001",
            }
        })

        # Should be denied due to lack of permissions
        assert "Permission denied" in result or "not have permission" in result

    @pytest.mark.asyncio
    async def test_manager_approve_own_leave_forbidden(self):
        """Test that managers cannot approve their own leave requests."""
        # This test would require specific setup with manager/employee relationships
        # For now, document the expected behavior
        pass

    @pytest.mark.asyncio
    async def test_query_organizational_structure(self):
        """Test querying organizational structure."""
        admin_id = 1

        # Query about org structure
        result = await query_employee_info.ainvoke({
            "question": "Who are the managers in the organization?",
            "admin_id": admin_id,
        })

        # Should return information about managers
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_error_handling_invalid_data(self):
        """Test error handling with invalid data."""
        admin_id = 1

        # Try to create employee with missing required fields
        result = await employee_crud_agent.ainvoke({
            "operation": "create",
            "admin_id": admin_id,
            "employee_data": {
                "first_name": "Missing",
                # Missing last_name, mobile_number, etc.
            }
        })

        assert "Missing required fields" in result or "error" in result.lower()
