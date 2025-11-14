"""Tests for employee CRUD operations."""

import pytest
from agent.tools.neo4j_crud_tool import (
    create_employee,
    update_employee,
    delete_employee,
    update_employee_relationships,
)


class TestEmployeeCRUD:
    """Test employee CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_employee_success(self):
        """Test successful employee creation."""
        employee_data = {
            "first_name": "Test",
            "last_name": "Employee",
            "mobile_number": "27821234567",
            "email": "test.employee@example.com",
            "employer_id": 1,
            "employee_no": "EMP001",
            "status": "active",
            "salary": 50000.0,
        }

        result = await create_employee.ainvoke(employee_data)

        assert result["success"] is True
        assert "employee" in result
        assert result["employee"]["first_name"] == "Test"
        assert result["employee"]["last_name"] == "Employee"
        assert result["employee"]["mobile_number"] == "27821234567"

        # Clean up
        if result["success"]:
            await delete_employee.ainvoke({
                "employee_id": result["employee"]["id"],
                "soft_delete": False
            })

    @pytest.mark.asyncio
    async def test_create_employee_invalid_mobile(self):
        """Test employee creation with invalid mobile number."""
        employee_data = {
            "first_name": "Test",
            "last_name": "Employee",
            "mobile_number": "0821234567",  # Invalid format
            "email": "test@example.com",
            "employer_id": 1,
            "employee_no": "EMP002",
        }

        result = await create_employee.ainvoke(employee_data)

        assert result["success"] is False
        assert "Mobile number must be in format 27XXXXXXXXX" in result["error"]

    @pytest.mark.asyncio
    async def test_create_employee_duplicate_mobile(self):
        """Test employee creation with duplicate mobile number."""
        # First, create an employee
        employee_data = {
            "first_name": "First",
            "last_name": "Employee",
            "mobile_number": "27821234999",
            "email": "first@example.com",
            "employer_id": 1,
            "employee_no": "EMP003",
        }

        result1 = await create_employee.ainvoke(employee_data)
        assert result1["success"] is True

        # Try to create another with same mobile
        employee_data["first_name"] = "Second"
        employee_data["employee_no"] = "EMP004"

        result2 = await create_employee.ainvoke(employee_data)

        assert result2["success"] is False
        assert "already exists" in result2["error"]

        # Clean up
        if result1["success"]:
            await delete_employee.ainvoke({
                "employee_id": result1["employee"]["id"],
                "soft_delete": False
            })

    @pytest.mark.asyncio
    async def test_update_employee_success(self):
        """Test successful employee update."""
        # Create employee first
        create_data = {
            "first_name": "Update",
            "last_name": "Test",
            "mobile_number": "27821234111",
            "email": "update.test@example.com",
            "employer_id": 1,
            "employee_no": "EMP005",
        }

        create_result = await create_employee.ainvoke(create_data)
        assert create_result["success"] is True
        employee_id = create_result["employee"]["id"]

        # Update employee
        update_data = {
            "employee_id": employee_id,
            "email": "updated.email@example.com",
            "status": "on_leave",
        }

        update_result = await update_employee.ainvoke(update_data)

        assert update_result["success"] is True
        assert update_result["employee"]["email"] == "updated.email@example.com"
        assert update_result["employee"]["status"] == "on_leave"

        # Clean up
        await delete_employee.ainvoke({
            "employee_id": employee_id,
            "soft_delete": False
        })

    @pytest.mark.asyncio
    async def test_update_employee_not_found(self):
        """Test updating non-existent employee."""
        update_data = {
            "employee_id": 999999,
            "email": "nonexistent@example.com",
        }

        result = await update_employee.ainvoke(update_data)

        assert result["success"] is False
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_delete_employee_soft(self):
        """Test soft delete (deactivation)."""
        # Create employee
        create_data = {
            "first_name": "Delete",
            "last_name": "Test",
            "mobile_number": "27821234222",
            "email": "delete.test@example.com",
            "employer_id": 1,
            "employee_no": "EMP006",
        }

        create_result = await create_employee.ainvoke(create_data)
        assert create_result["success"] is True
        employee_id = create_result["employee"]["id"]

        # Soft delete
        delete_result = await delete_employee.ainvoke({
            "employee_id": employee_id,
            "soft_delete": True
        })

        assert delete_result["success"] is True
        assert delete_result["employee"]["status"] == "terminated"

        # Clean up (hard delete)
        await delete_employee.ainvoke({
            "employee_id": employee_id,
            "soft_delete": False
        })

    @pytest.mark.asyncio
    async def test_delete_employee_hard(self):
        """Test hard delete (permanent removal)."""
        # Create employee
        create_data = {
            "first_name": "HardDelete",
            "last_name": "Test",
            "mobile_number": "27821234333",
            "email": "harddelete@example.com",
            "employer_id": 1,
            "employee_no": "EMP007",
        }

        create_result = await create_employee.ainvoke(create_data)
        assert create_result["success"] is True
        employee_id = create_result["employee"]["id"]

        # Hard delete
        delete_result = await delete_employee.ainvoke({
            "employee_id": employee_id,
            "soft_delete": False
        })

        assert delete_result["success"] is True
        assert "permanently deleted" in delete_result["message"]

    @pytest.mark.asyncio
    async def test_update_employee_relationships(self):
        """Test updating employee organizational relationships."""
        # This test assumes there are existing Employer, Division, Branch nodes
        # and manager employees in the database

        # Create employee
        create_data = {
            "first_name": "Relationship",
            "last_name": "Test",
            "mobile_number": "27821234444",
            "email": "relationship@example.com",
            "employer_id": 1,
            "employee_no": "EMP008",
        }

        create_result = await create_employee.ainvoke(create_data)
        assert create_result["success"] is True
        employee_id = create_result["employee"]["id"]

        # Update relationships (this will only work if manager with ID 1 exists)
        # For now, just test the function runs without error
        relationship_result = await update_employee_relationships.ainvoke({
            "employee_id": employee_id,
            "reports_to_id": 1,  # Assuming employee 1 exists
        })

        assert relationship_result["success"] is True

        # Clean up
        await delete_employee.ainvoke({
            "employee_id": employee_id,
            "soft_delete": False
        })
