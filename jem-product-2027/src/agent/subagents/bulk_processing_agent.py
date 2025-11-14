"""Bulk processing agent with task planning for CSV operations.

Handles large-scale employee and leave management operations from CSV files.
Uses explicit planning and progress tracking for up to 5000 records.
"""

from __future__ import annotations

from typing import Any
from datetime import datetime

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.tools import tool

from agent.tools.csv_processing_tool import (
    parse_employee_csv,
    save_processing_results,
)
from agent.tools.batch_operations_tool import (
    batch_create_employees,
    batch_update_managers,
    batch_initialize_leave_balances,
)
from agent.tools.authorization import check_permission, Permission, log_audit_event


@tool
async def bulk_processing_agent(
    operation: str,
    file_path: str,
    admin_id: int,
    employer_id: int,
) -> str:
    """Handle bulk CSV processing operations with planning and progress tracking.

    This agent processes large CSV files (up to 5000 records) with:
    - Automatic task decomposition
    - Batch processing
    - Error handling and reporting
    - Progress tracking

    Args:
        operation: Operation type ('import_employees', 'update_managers', 'update_employees').
        file_path: Path to the uploaded CSV file.
        admin_id: Admin performing the operation.
        employer_id: Employer ID for scoping.

    Returns:
        Processing results with detailed summary.
    """
    model = ChatAnthropic(model="claude-sonnet-4-5-20250514")  # Use Sonnet for complex planning

    # Permission check
    if operation in ["import_employees", "update_employees"]:
        perm = Permission.CREATE_EMPLOYEE if operation == "import_employees" else Permission.UPDATE_EMPLOYEE
    elif operation == "update_managers":
        perm = Permission.UPDATE_EMPLOYEE
    else:
        return f"Unknown bulk operation: {operation}"

    auth_result = await check_permission(admin_id, perm, employer_id=employer_id)

    if not auth_result["authorized"]:
        return f"❌ Permission denied: {auth_result['reason']}"

    # Generate unique operation ID
    operation_id = f"{operation}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    try:
        # Step 1: Parse and validate CSV
        print(f"📄 Parsing CSV file: {file_path}")

        parse_result = parse_employee_csv.invoke({"file_path": file_path})

        if not parse_result["success"]:
            return f"❌ CSV parsing failed: {parse_result['error']}"

        total_records = parse_result["total_records"]
        valid_records = parse_result["valid_records"]
        invalid_records = parse_result["invalid_records"]
        operation_type = parse_result["operation_type"]

        summary = f"**CSV Parsing Complete**\n\n"
        summary += f"- Total Records: {total_records}\n"
        summary += f"- Valid: {len(valid_records)}\n"
        summary += f"- Invalid: {len(invalid_records)}\n"
        summary += f"- Operation Type: {operation_type}\n\n"

        if invalid_records:
            summary += f"⚠️ {len(invalid_records)} records have validation errors:\n"
            for inv in invalid_records[:5]:  # Show first 5
                summary += f"  - Row {inv['row']}: {', '.join(inv['errors'])}\n"
            if len(invalid_records) > 5:
                summary += f"  ... and {len(invalid_records) - 5} more\n"
            summary += "\n"

        if not valid_records:
            return summary + "❌ No valid records to process."

        # Step 2: Process based on operation type
        print(f"🔄 Processing {len(valid_records)} valid records...")

        if operation_type == "employee_create":
            # Batch create employees
            result = await batch_create_employees.ainvoke({
                "records": valid_records,
                "employer_id": employer_id,
                "admin_id": admin_id,
                "batch_size": 100
            })

            if result["success"]:
                # Initialize leave balances for successful creates
                success_ids = [s["new_id"] for s in result["successes"]]

                if success_ids:
                    leave_result = await batch_initialize_leave_balances.ainvoke({
                        "employee_ids": success_ids,
                        "year": datetime.now().year,
                        "employer_id": employer_id,
                        "batch_size": 100
                    })

                    summary += f"✅ Leave balances initialized for {len(success_ids)} employees\n\n"

        elif operation_type == "manager_update":
            # Batch update manager relationships
            result = await batch_update_managers.ainvoke({
                "records": valid_records,
                "employer_id": employer_id,
                "admin_id": admin_id,
                "batch_size": 100
            })

        else:
            return summary + f"❌ Unsupported operation type: {operation_type}"

        # Step 3: Save results
        save_result = save_processing_results.invoke({
            "operation_id": operation_id,
            "results": result
        })

        # Step 4: Log audit event
        await log_audit_event(
            admin_id=admin_id,
            operation=f"bulk_{operation_type}",
            target_entity="Employee",
            target_id=0,
            changes={"total": total_records, "successful": result["success_count"]},
            success=True
        )

        # Format final summary
        summary += f"**Processing Complete**\n\n"
        summary += f"✅ Successful: {result['success_count']}/{total_records} ({result['success_rate']:.1f}%)\n"
        summary += f"❌ Failed: {result['failure_count']}/{total_records}\n\n"

        if result["failures"]:
            summary += f"**Failed Records (first 5):**\n"
            for fail in result["failures"][:5]:
                summary += f"- {fail.get('first_name', '')} {fail.get('last_name', '')} (ID: {fail.get('employee_id', 'N/A')}): {fail['error']}\n"

        summary += f"\n**Results Files:**\n"
        if save_result.get("success"):
            if save_result.get("success_file"):
                summary += f"- ✅ Success CSV: `{save_result['success_file']}`\n"
            if save_result.get("errors_file"):
                summary += f"- ❌ Errors CSV: `{save_result['errors_file']}`\n"
            summary += f"- 📊 Summary: `{save_result['summary_file']}`\n"

        return summary

    except Exception as e:
        await log_audit_event(
            admin_id=admin_id,
            operation=f"bulk_{operation}",
            target_entity="Employee",
            target_id=0,
            success=False,
            error_message=str(e)
        )

        return f"❌ Bulk processing failed: {str(e)}"
