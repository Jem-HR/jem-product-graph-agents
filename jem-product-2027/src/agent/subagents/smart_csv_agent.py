"""Smart CSV Agent with planning capabilities for variable-format, dirty data.

Implements Deep Agents pattern using LangGraph:
- TodoList-style planning and progress tracking
- Adaptive workflows based on CSV inspection
- Data cleaning and validation
- Error recovery and replanning

This agent handles CSVs with:
- Different column name variations (90+ patterns)
- Dirty data (formatting issues, missing values)
- Inconsistent formats across files
"""

from __future__ import annotations

from typing import Any, Annotated
from datetime import datetime

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, add_messages, END
from langgraph.runtime import Runtime
from typing_extensions import TypedDict

from agent.tools.csv_intelligence_tool import inspect_csv_structure, map_csv_columns
from agent.tools.data_cleaning_tool import batch_clean_csv_records
from agent.tools.batch_operations_tool import batch_create_employees, batch_update_managers
from agent.tools.authorization import check_permission, Permission


class SmartCSVState(TypedDict):
    """State for Smart CSV processing with planning."""

    messages: Annotated[list[BaseMessage], add_messages]
    todos: list[dict[str, str]]  # Task list with status tracking
    file_path: str | None
    operation: str | None
    csv_analysis: dict[str, Any] | None
    column_mappings: dict[str, Any] | None
    cleaned_data: dict[str, Any] | None
    processing_results: dict[str, Any] | None
    admin_id: int
    employer_id: int
    current_step: str


async def create_processing_plan(state: SmartCSVState, runtime: Runtime) -> dict[str, Any]:
    """Inspect CSV and create adaptive processing plan.

    This implements TodoList-style planning based on CSV inspection.
    """
    file_path = state.get("file_path")
    operation = state.get("operation")

    # Inspect CSV structure
    analysis_result = inspect_csv_structure.invoke({"file_path": file_path})

    if not analysis_result["success"]:
        return {
            "messages": [AIMessage(content=f"❌ CSV inspection failed: {analysis_result['error']}")],
            "current_step": "failed"
        }

    csv_analysis = analysis_result

    # Create adaptive plan based on inspection
    todos = [
        {"task": f"Inspect CSV structure ({csv_analysis['total_rows']} rows, {csv_analysis['total_columns']} columns)", "status": "completed"},
        {"task": "Map columns to schema", "status": "pending"},
    ]

    # Add data cleaning tasks if needed
    if csv_analysis.get("cleaning_needed"):
        for cleaning_task in csv_analysis["cleaning_needed"]:
            todos.append({
                "task": f"Clean {cleaning_task['column']}: {cleaning_task['issue']}",
                "status": "pending"
            })

    # Add validation task
    todos.append({"task": "Validate and clean all records", "status": "pending"})

    # Add processing task
    if operation == "import_employees":
        todos.append({"task": f"Batch create {csv_analysis['total_rows']} employees", "status": "pending"})
        todos.append({"task": "Initialize leave balances", "status": "pending"})
    elif operation == "update_managers":
        todos.append({"task": f"Batch update {csv_analysis['total_rows']} manager relationships", "status": "pending"})

    # Add reporting task
    todos.append({"task": "Generate processing report and result files", "status": "pending"})

    # Create summary message
    summary = AIMessage(content=f"""📊 **CSV Analysis Complete**

**File:** {file_path}
**Rows:** {csv_analysis['total_rows']}
**Columns:** {csv_analysis['total_columns']}

**Columns Found:**
{', '.join(csv_analysis['columns'])}

**Data Quality:**
- Missing values: {csv_analysis['data_quality']['total_missing_values']}
- Rows with missing data: {csv_analysis['data_quality']['rows_with_missing']}
- Duplicate rows: {csv_analysis['data_quality']['duplicate_rows']}

**Cleaning Required:**
{chr(10).join(f"- {item['column']}: {item['issue']}" for item in csv_analysis.get('cleaning_needed', []))}

**Processing Plan Created:**
{chr(10).join(f"{i+1}. {todo['task']}" for i, todo in enumerate(todos))}

Proceeding with processing...""")

    return {
        "messages": [summary],
        "todos": todos,
        "csv_analysis": csv_analysis,
        "current_step": "map_columns"
    }


async def map_columns_step(state: SmartCSVState, runtime: Runtime) -> dict[str, Any]:
    """Map CSV columns to expected schema using fuzzy matching."""
    csv_analysis = state.get("csv_analysis", {})
    todos = state.get("todos", [])

    # Map columns
    mapping_result = map_csv_columns.invoke({
        "csv_columns": csv_analysis.get("columns", [])
    })

    # Update todos
    for todo in todos:
        if "Map columns" in todo["task"]:
            todo["status"] = "completed"
            break

    # Check if we have good mappings
    mappings = mapping_result.get("mappings", {})
    required_fields = ["first_name", "last_name", "mobile_number", "email"]

    if state.get("operation") == "update_managers":
        required_fields = ["employee_id", "new_manager_id"]

    missing_required = [f for f in required_fields if f not in mappings]

    if missing_required:
        return {
            "messages": [AIMessage(content=f"❌ Cannot map required fields: {', '.join(missing_required)}")],
            "todos": todos,
            "current_step": "failed"
        }

    return {
        "todos": todos,
        "column_mappings": mappings,
        "current_step": "clean_data"
    }


async def clean_data_step(state: SmartCSVState, runtime: Runtime) -> dict[str, Any]:
    """Clean and validate CSV data."""
    file_path = state.get("file_path")
    column_mappings = state.get("column_mappings", {})
    todos = state.get("todos", [])

    # Read CSV and apply mappings
    import pandas as pd
    df = pd.read_csv(file_path)

    # Create renamed dataframe
    rename_map = {m["csv_column"]: field for field, m in column_mappings.items()}
    records = df.to_dict('records')

    # Extract simple column mappings for cleaning tool
    simple_mappings = {field: m["csv_column"] for field, m in column_mappings.items()}

    # Clean records
    cleaning_result = batch_clean_csv_records.invoke({
        "records": records,
        "column_mappings": column_mappings  # Pass full mappings - tool will extract csv_column
    })

    # Update todos - mark cleaning tasks complete
    for todo in todos:
        if "Clean" in todo["task"] or "Validate" in todo["task"]:
            todo["status"] = "completed"

    summary_msg = AIMessage(content=f"""✅ **Data Cleaning Complete**

**Results:**
- Total records: {len(records)}
- Successfully cleaned: {cleaning_result['clean_count']}
- Failed validation: {cleaning_result['failed_count']}
- Success rate: {cleaning_result['success_rate']:.1f}%

Proceeding to batch processing...""")

    return {
        "messages": [summary_msg],
        "todos": todos,
        "cleaned_data": cleaning_result,
        "current_step": "process_batch"
    }


async def process_batch_step(state: SmartCSVState, runtime: Runtime) -> dict[str, Any]:
    """Process cleaned records in batches."""
    operation = state.get("operation")
    cleaned_data = state.get("cleaned_data", {})
    admin_id = state.get("admin_id")
    employer_id = state.get("employer_id")
    todos = state.get("todos", [])

    cleaned_records = cleaned_data.get("cleaned_records", [])

    if not cleaned_records:
        return {
            "messages": [AIMessage(content="❌ No valid records to process")],
            "current_step": "failed"
        }

    # Process based on operation type
    if operation == "import_employees":
        result = await batch_create_employees.ainvoke({
            "records": cleaned_records,
            "employer_id": employer_id,
            "admin_id": admin_id,
            "batch_size": 100
        })

    elif operation == "update_managers":
        result = await batch_update_managers.ainvoke({
            "records": cleaned_records,
            "employer_id": employer_id,
            "admin_id": admin_id,
            "batch_size": 100
        })
    else:
        return {
            "messages": [AIMessage(content=f"❌ Unknown operation: {operation}")],
            "current_step": "failed"
        }

    # Update todos
    for todo in todos:
        if "Batch" in todo["task"]:
            todo["status"] = "completed"

    return {
        "todos": todos,
        "processing_results": result,
        "current_step": "generate_report"
    }


async def generate_report_step(state: SmartCSVState, runtime: Runtime) -> dict[str, Any]:
    """Generate final processing report."""
    processing_results = state.get("processing_results", {})
    cleaned_data = state.get("cleaned_data", {})
    todos = state.get("todos", [])

    # Mark reporting todo complete
    for todo in todos:
        if "report" in todo["task"].lower():
            todo["status"] = "completed"

    # Generate summary
    total_csv_records = cleaned_data.get("clean_count", 0) + cleaned_data.get("failed_count", 0)
    db_successes = processing_results.get("success_count", 0)
    db_failures = processing_results.get("failure_count", 0)

    summary = f"""🎉 **Processing Complete!**

**CSV Processing:**
- Total rows in CSV: {total_csv_records}
- Passed data cleaning: {cleaned_data.get('clean_count', 0)}
- Failed data cleaning: {cleaned_data.get('failed_count', 0)}

**Database Operations:**
- Successfully processed: {db_successes}
- Failed: {db_failures}
- Overall success rate: {processing_results.get('success_rate', 0):.1f}%

**Task Completion:**
{chr(10).join(f"{'✅' if t['status'] == 'completed' else '⏸'} {t['task']}" for t in todos)}
"""

    return {
        "messages": [AIMessage(content=summary)],
        "todos": todos,
        "current_step": "completed"
    }


def route_step(state: SmartCSVState) -> str:
    """Route to next step based on current_step."""
    current = state.get("current_step", "")

    routes = {
        "map_columns": "map_columns_step",
        "clean_data": "clean_data_step",
        "process_batch": "process_batch_step",
        "generate_report": "generate_report_step",
        "completed": END,
        "failed": END,
    }

    return routes.get(current, END)


# Build the Smart CSV Agent graph with planning
workflow = StateGraph(SmartCSVState)

# Add nodes (planning workflow)
workflow.add_node("create_processing_plan", create_processing_plan)
workflow.add_node("map_columns_step", map_columns_step)
workflow.add_node("clean_data_step", clean_data_step)
workflow.add_node("process_batch_step", process_batch_step)
workflow.add_node("generate_report_step", generate_report_step)

# Set entry point
workflow.set_entry_point("create_processing_plan")

# Add conditional routing
workflow.add_conditional_edges("create_processing_plan", route_step)
workflow.add_conditional_edges("map_columns_step", route_step)
workflow.add_conditional_edges("clean_data_step", route_step)
workflow.add_conditional_edges("process_batch_step", route_step)
workflow.add_edge("generate_report_step", END)

# Compile graph
smart_csv_graph = workflow.compile(name="Smart CSV Processor")


# Wrapper tool for use in supervisor
@tool
async def smart_csv_agent(
    file_path: str,
    operation: str,
    admin_id: int,
    employer_id: int,
) -> str:
    """Process variable-format CSV files with intelligent data cleaning.

    Uses adaptive planning to handle:
    - Different column name variations
    - Dirty/inconsistent data
    - Missing values
    - Format variations

    Creates a processing plan, cleans data, and batch processes with progress tracking.

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

    # Initialize state and run planning workflow
    initial_state = {
        "messages": [],
        "todos": [],
        "file_path": file_path,
        "operation": operation,
        "admin_id": admin_id,
        "employer_id": employer_id,
        "current_step": "inspect"
    }

    # Run the smart CSV processing graph
    result = await smart_csv_graph.ainvoke(initial_state)

    # Return formatted summary
    messages = result.get("messages", [])
    if messages:
        return "\n\n".join(msg.content for msg in messages if isinstance(msg, AIMessage))

    return "Processing completed"
