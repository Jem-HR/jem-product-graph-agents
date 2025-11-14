"""Tests for leave management operations."""

import pytest
from datetime import datetime, timedelta
from agent.tools.leave_management_tool import (
    create_leave_request,
    approve_leave_request,
    reject_leave_request,
    get_leave_balance,
    get_leave_history,
    get_pending_leave_requests,
)
from agent.tools.neo4j_crud_tool import create_employee, delete_employee


class TestLeaveManagement:
    """Test leave management operations."""

    @pytest.fixture
    async def test_employee(self):
        """Create a test employee for leave operations."""
        employee_data = {
            "first_name": "Leave",
            "last_name": "Tester",
            "mobile_number": "27821111111",
            "email": "leave.tester@example.com",
            "employer_id": 1,
            "employee_no": "LEAVE001",
            "status": "active",
        }

        result = await create_employee.ainvoke(employee_data)
        assert result["success"] is True

        employee_id = result["employee"]["id"]

        # Initialize leave balance
        from agent.tools.neo4j_tool import get_neo4j_driver
        driver = get_neo4j_driver()
        try:
            async with driver.session() as session:
                await session.run(
                    """
                    MATCH (e:Employee {id: $employee_id})
                    MERGE (e)-[:HAS_BALANCE]->(lb:LeaveBalance {
                        employee_id: $employee_id,
                        year: $year,
                        leave_type: 'annual'
                    })
                    SET lb.total_days = 21.0,
                        lb.used_days = 0.0,
                        lb.pending_days = 0.0,
                        lb.remaining_days = 21.0,
                        lb.updated_at = datetime()
                    """,
                    employee_id=employee_id,
                    year=datetime.now().year
                )
        finally:
            await driver.close()

        yield employee_id

        # Clean up
        await delete_employee.ainvoke({
            "employee_id": employee_id,
            "soft_delete": False
        })

    @pytest.mark.asyncio
    async def test_create_leave_request_success(self, test_employee):
        """Test successful leave request creation."""
        employee_id = await test_employee

        # Create leave request for next week
        start_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        end_date = (datetime.now() + timedelta(days=11)).strftime("%Y-%m-%d")

        leave_data = {
            "employee_id": employee_id,
            "leave_type": "annual",
            "start_date": start_date,
            "end_date": end_date,
            "reason": "Vacation",
        }

        result = await create_leave_request.ainvoke(leave_data)

        assert result["success"] is True
        assert "leave_request" in result
        assert result["leave_request"]["status"] == "pending"
        assert result["leave_request"]["leave_type"] == "annual"

    @pytest.mark.asyncio
    async def test_create_leave_request_insufficient_balance(self, test_employee):
        """Test leave request with insufficient balance."""
        employee_id = await test_employee

        # Request more days than available
        start_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        end_date = (datetime.now() + timedelta(days=35)).strftime("%Y-%m-%d")  # ~20 business days

        leave_data = {
            "employee_id": employee_id,
            "leave_type": "annual",
            "start_date": start_date,
            "end_date": end_date,
            "reason": "Long vacation",
        }

        result = await create_leave_request.ainvoke(leave_data)

        assert result["success"] is False
        assert "Insufficient leave balance" in result["error"]

    @pytest.mark.asyncio
    async def test_create_leave_request_past_date(self, test_employee):
        """Test leave request with past dates."""
        employee_id = await test_employee

        # Use past dates
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        end_date = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")

        leave_data = {
            "employee_id": employee_id,
            "leave_type": "annual",
            "start_date": start_date,
            "end_date": end_date,
            "reason": "Past leave",
        }

        result = await create_leave_request.ainvoke(leave_data)

        assert result["success"] is False
        assert "past dates" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_approve_leave_request(self, test_employee):
        """Test leave request approval."""
        employee_id = await test_employee

        # Create leave request
        start_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        end_date = (datetime.now() + timedelta(days=9)).strftime("%Y-%m-%d")

        leave_data = {
            "employee_id": employee_id,
            "leave_type": "annual",
            "start_date": start_date,
            "end_date": end_date,
            "reason": "Short break",
        }

        create_result = await create_leave_request.ainvoke(leave_data)
        assert create_result["success"] is True
        leave_request_id = create_result["leave_request"]["id"]

        # Approve the request
        approve_result = await approve_leave_request.ainvoke({
            "leave_request_id": leave_request_id,
            "approved_by_id": 1  # Assuming employee 1 is the manager
        })

        assert approve_result["success"] is True
        assert approve_result["leave_request"]["status"] == "approved"

    @pytest.mark.asyncio
    async def test_reject_leave_request(self, test_employee):
        """Test leave request rejection."""
        employee_id = await test_employee

        # Create leave request
        start_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        end_date = (datetime.now() + timedelta(days=9)).strftime("%Y-%m-%d")

        leave_data = {
            "employee_id": employee_id,
            "leave_type": "annual",
            "start_date": start_date,
            "end_date": end_date,
            "reason": "Personal matters",
        }

        create_result = await create_leave_request.ainvoke(leave_data)
        assert create_result["success"] is True
        leave_request_id = create_result["leave_request"]["id"]

        # Reject the request
        reject_result = await reject_leave_request.ainvoke({
            "leave_request_id": leave_request_id,
            "rejected_by_id": 1,
            "rejection_reason": "Insufficient staffing during this period"
        })

        assert reject_result["success"] is True
        assert reject_result["leave_request"]["status"] == "rejected"

    @pytest.mark.asyncio
    async def test_get_leave_balance(self, test_employee):
        """Test retrieving leave balance."""
        employee_id = await test_employee

        result = await get_leave_balance.ainvoke({
            "employee_id": employee_id,
            "year": datetime.now().year
        })

        assert result["success"] is True
        assert "balances" in result
        assert len(result["balances"]) > 0
        assert result["balances"][0]["leave_type"] == "annual"
        assert result["balances"][0]["total_days"] == 21.0

    @pytest.mark.asyncio
    async def test_get_leave_history(self, test_employee):
        """Test retrieving leave history."""
        employee_id = await test_employee

        # Create a leave request first
        start_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        end_date = (datetime.now() + timedelta(days=9)).strftime("%Y-%m-%d")

        leave_data = {
            "employee_id": employee_id,
            "leave_type": "annual",
            "start_date": start_date,
            "end_date": end_date,
            "reason": "Test history",
        }

        await create_leave_request.ainvoke(leave_data)

        # Get history
        result = await get_leave_history.ainvoke({
            "employee_id": employee_id
        })

        assert result["success"] is True
        assert "leave_requests" in result
        assert len(result["leave_requests"]) > 0

    @pytest.mark.asyncio
    async def test_get_pending_leave_requests(self):
        """Test retrieving pending leave requests for a manager."""
        # Assuming employee 1 is a manager with direct reports
        result = await get_pending_leave_requests.ainvoke({
            "manager_id": 1
        })

        assert result["success"] is True
        assert "pending_requests" in result
        assert "count" in result

    @pytest.mark.asyncio
    async def test_leave_balance_updates_on_approval(self, test_employee):
        """Test that leave balance updates correctly when request is approved."""
        employee_id = await test_employee

        # Get initial balance
        balance_before = await get_leave_balance.ainvoke({
            "employee_id": employee_id,
            "year": datetime.now().year
        })
        initial_remaining = balance_before["balances"][0]["remaining_days"]

        # Create and approve leave request
        start_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        end_date = (datetime.now() + timedelta(days=9)).strftime("%Y-%m-%d")

        leave_data = {
            "employee_id": employee_id,
            "leave_type": "annual",
            "start_date": start_date,
            "end_date": end_date,
            "reason": "Balance test",
        }

        create_result = await create_leave_request.ainvoke(leave_data)
        days_requested = create_result["leave_request"]["days_requested"]

        await approve_leave_request.ainvoke({
            "leave_request_id": create_result["leave_request"]["id"],
            "approved_by_id": 1
        })

        # Check balance after approval
        balance_after = await get_leave_balance.ainvoke({
            "employee_id": employee_id,
            "year": datetime.now().year
        })
        final_remaining = balance_after["balances"][0]["remaining_days"]

        assert final_remaining == initial_remaining - days_requested
