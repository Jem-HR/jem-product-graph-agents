"""Smart CSV Agent using Deep Agents TodoListMiddleware for adaptive planning.

This agent uses the official Deep Agents library for:
- Automatic task decomposition and planning
- Progress tracking with write_todos tool
- Adaptive workflows based on CSV inspection
- Data cleaning and validation with replanning

Handles CSVs with:
- Different column name variations (90+ patterns)
- Dirty data (formatting issues, missing values)
- Inconsistent formats across files
"""

from __future__ import annotations

from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import TodoListMiddleware
from langchain_core.tools import tool
from langgraph.store.memory import InMemoryStore

from agent.tools.csv_intelligence_tool import inspect_csv_structure, map_csv_columns
from agent.tools.data_cleaning_tool import batch_clean_csv_records
from agent.tools.batch_operations_tool import (
    batch_create_employees,
    batch_update_managers,
    batch_initialize_leave_balances,
)
from agent.tools.csv_processing_tool import save_processing_results
from agent.tools.authorization import check_permission, Permission, log_audit_event


# Deep Agents system prompt for CSV processing
SMART_CSV_SYSTEM_PROMPT = """You are an intelligent CSV processor for HR employee data.

Your job is to process CSV files that may have:
- Variable column names (e.g., "First Name" vs "FirstName" vs "Given Name")
- Dirty data (phone numbers with formatting, mixed case, missing values)
- Inconsistent formats across different files

**CRITICAL: Always use the write_todos tool to plan your approach before processing.**

**Standard Workflow:**

1. **Plan Phase** (use write_todos):
   - Inspect CSV structure to understand columns and data quality
   - Create a processing plan with discrete steps
   - Update plan if you discover issues

2. **Inspection Phase**:
   - Use inspect_csv_structure tool to analyze the file
   - Check columns, data types, quality issues, missing values
   - Identify what cleaning is needed

3. **Column Mapping Phase**:
   - Use map_csv_columns to fuzzy match column names
   - Handle variations like "First Name" → first_name
   - Verify all required fields can be mapped

4. **Data Cleaning Phase**:
   - Use batch_clean_csv_records to clean and validate data
   - Handles: mobile numbers (+27 82...), emails, salaries (R 55,000)
   - Track valid vs invalid records

5. **Processing Phase**:
   - Use batch_create_employees or batch_update_managers
   - Process in batches of 100 records
   - Handle errors gracefully

6. **Reporting Phase**:
   - Use save_processing_results to generate output files
   - Create success.csv, errors.csv, summary.txt
   - Log audit event for compliance

7. **Update Todos**:
   - Mark steps as completed as you progress
   - Adapt plan if errors occur
   - Provide final summary

**Key Principles:**
- Always create todos BEFORE starting work
- Update todos as you progress (pending → in_progress → completed)
- Be adaptive - if inspection reveals issues, update your plan
- Provide detailed error information for failed records
- Maintain employer_id scoping for multi-tenant security

**Available Tools:**
- write_todos - Plan and track your work
- inspect_csv_structure - Analyze CSV file
- map_csv_columns - Fuzzy match column names
- batch_clean_csv_records - Clean and validate data
- batch_create_employees - Import new employees
- batch_update_managers - Update reporting relationships
- batch_initialize_leave_balances - Set up leave for new employees
- save_processing_results - Generate output files
"""


# Create the Deep Agents smart CSV processor
# This uses TodoListMiddleware to automatically enable planning
smart_csv_deep_agent = create_agent(
    model="claude-sonnet-4-5-20250929",  # Sonnet for complex reasoning
    tools=[
        inspect_csv_structure,
        map_csv_columns,
        batch_clean_csv_records,
        batch_create_employees,
        batch_update_managers,
        batch_initialize_leave_balances,
        save_processing_results,
    ],
    middleware=[
        TodoListMiddleware(
            system_prompt=SMART_CSV_SYSTEM_PROMPT
        ),
    ],
    store=InMemoryStore(),  # For context management
)


# Wrapper tool for integration with HR Admin supervisor
@tool
async def smart_csv_agent(
    file_path: str,
    operation: str,
    admin_id: int,
    employer_id: int,
) -> str:
    """Process variable-format CSV files with intelligent data cleaning using Deep Agents.

    This agent uses Deep Agents TodoListMiddleware to:
    - Automatically create a processing plan
    - Track progress with todos
    - Adapt to data quality issues
    - Clean dirty data (phone numbers, emails, salaries)
    - Handle 90+ column name variations

    Args:
        file_path: Path to CSV file.
        operation: Operation type ('import_employees', 'update_managers').
        admin_id: Admin performing operation.
        employer_id: Employer ID for scoping.

    Returns:
        Processing results with plan execution summary.
    """
    # Check permissions
    perm = Permission.CREATE_EMPLOYEE if operation == "import_employees" else Permission.UPDATE_EMPLOYEE
    auth_result = await check_permission(admin_id, perm, employer_id=employer_id)

    if not auth_result["authorized"]:
        return f"❌ Permission denied: {auth_result['reason']}"

    # Build task description for Deep Agent
    task_description = f"""Process this CSV file with intelligent cleaning and validation:

**File:** {file_path}
**Operation:** {operation}
**Admin ID:** {admin_id}
**Employer ID:** {employer_id} (IMPORTANT: All operations must be scoped to this employer)

**Your Task:**
1. Inspect the CSV file to understand its structure
2. Create a detailed processing plan using write_todos
3. Map columns to the required schema (handle variations)
4. Clean any dirty data (mobiles, emails, salaries)
5. Validate all records
6. Batch process valid records (100 per batch)
7. Initialize leave balances for new employees (if importing)
8. Generate detailed results (success.csv, errors.csv, summary.txt)
9. Log audit event

**Required Schema Fields:**
For import_employees: first_name, last_name, mobile_number, email, employee_no
For update_managers: employee_id, new_manager_id

**Scoping Rule:**
All operations must use employer_id={employer_id} to ensure multi-tenant data isolation.

Begin by creating your processing plan with write_todos!"""

    try:
        # Invoke Deep Agent with task description
        # The agent will automatically use write_todos to plan its approach
        result = await smart_csv_deep_agent.ainvoke({
            "messages": [{"role": "user", "content": task_description}]
        })

        # Extract the final response
        messages = result.get("messages", [])
        if messages:
            final_response = messages[-1]
            return final_response.content if hasattr(final_response, "content") else str(final_response)

        return "Processing completed"

    except Exception as e:
        # Log failure
        await log_audit_event(
            admin_id=admin_id,
            operation=f"smart_csv_{operation}",
            target_entity="Employee",
            target_id=0,
            success=False,
            error_message=str(e)
        )

        return f"❌ Smart CSV processing failed: {str(e)}"
