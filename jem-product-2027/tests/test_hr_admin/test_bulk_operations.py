"""Tests for bulk CSV processing operations."""

import pytest
from pathlib import Path

from agent.tools.csv_processing_tool import parse_employee_csv
from agent.tools.batch_operations_tool import (
    batch_create_employees,
    batch_update_managers,
    batch_initialize_leave_balances,
)
from agent.subagents.bulk_processing_agent import bulk_processing_agent


class TestBulkOperations:
    """Test bulk CSV processing."""

    @pytest.mark.asyncio
    async def test_parse_employee_csv_valid(self):
        """Test parsing valid employee CSV."""
        csv_path = "data/sample_csvs/sample_employees.csv"

        result = parse_employee_csv.invoke({"file_path": csv_path})

        assert result["success"] is True
        assert result["operation_type"] == "employee_create"
        assert result["valid_count"] == 5
        assert result["invalid_count"] == 0

    @pytest.mark.asyncio
    async def test_parse_manager_updates_csv(self):
        """Test parsing manager updates CSV."""
        csv_path = "data/sample_csvs/sample_manager_updates.csv"

        result = parse_employee_csv.invoke({"file_path": csv_path})

        assert result["success"] is True
        assert result["operation_type"] == "manager_update"
        assert result["valid_count"] == 2

    @pytest.mark.asyncio
    async def test_batch_update_managers(self):
        """Test bulk manager relationship updates."""
        # This test requires existing employees in the database
        records = [
            {"employee_id": 22483, "new_manager_id": 22489},
        ]

        result = await batch_update_managers.ainvoke({
            "records": records,
            "employer_id": 189,  # Your employer
            "admin_id": 101487,
            "batch_size": 100
        })

        assert result["success"] is True
        # May have failures if employees don't exist
        assert "success_count" in result
        assert "failure_count" in result

    @pytest.mark.asyncio
    async def test_batch_initialize_leave_balances(self):
        """Test batch leave balance initialization."""
        # Use existing employee IDs
        employee_ids = [101487]  # Your employee ID

        result = await batch_initialize_leave_balances.ainvoke({
            "employee_ids": employee_ids,
            "year": 2025,
            "employer_id": 189,
            "batch_size": 100
        })

        assert result["success"] is True
        assert result["created_counts"]["annual"] > 0

    @pytest.mark.asyncio
    async def test_bulk_processing_agent_manager_updates(self):
        """Test full bulk processing workflow for manager updates."""
        # This is an integration test
        result = await bulk_processing_agent.ainvoke({
            "operation": "update_managers",
            "file_path": "data/sample_csvs/sample_manager_updates.csv",
            "admin_id": 101487,
            "employer_id": 189
        })

        # Check that result contains summary
        assert "Processing Complete" in result or "CSV Parsing Complete" in result
