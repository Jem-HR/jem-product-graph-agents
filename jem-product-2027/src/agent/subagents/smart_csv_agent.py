"""Smart CSV Agent using Deep Agents with full middleware support.

This agent uses the official Deep Agents library for:
- Automatic task decomposition and planning (TodoListMiddleware)
- Persistent context and memory storage (FilesystemMiddleware)
- Specialized subagent delegation (SubAgentMiddleware)
- Adaptive workflows based on CSV inspection
- Data cleaning and validation with replanning

Handles CSVs with:
- Different column name variations (90+ patterns)
- Dirty data (formatting issues, missing values)
- Inconsistent formats across different files
"""

from __future__ import annotations

from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import TodoListMiddleware
from deepagents.middleware import FilesystemMiddleware, SubAgentMiddleware
from deepagents.backends import CompositeBackend, StateBackend, StoreBackend
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


# Enhanced system prompt for Deep Agents with filesystem and subagent guidance
SMART_CSV_SYSTEM_PROMPT = """You are an intelligent CSV processor for HR employee data using Deep Agents.

Your job is to process CSV files that may have:
- Variable column names (e.g., "First Name" vs "FirstName" vs "Given Name")
- Dirty data (phone numbers with formatting, mixed case, missing values)
- Inconsistent formats across different files

**CRITICAL: You have access to three powerful capabilities:**

1. **Planning** (write_todos tool)
   - Always create a processing plan BEFORE starting
   - Update plan as you discover issues
   - Mark steps as completed as you progress

2. **Filesystem** (ls, read_file, write_file, edit_file)
   - Store CSV analysis in `/csv_analysis/` (transient, current session)
   - Save learned patterns in `/memories/` (persistent, across sessions)
   - Use filesystem to reduce context bloat

3. **Subagents** (task tool)
   - Delegate specialized work to focused subagents
   - Use csv_analyzer for deep schema analysis
   - Use csv_validator for data quality checks
   - Use csv_transformer for complex data operations

**Standard Workflow:**

1. **Plan Phase** (use write_todos):
   - Create a todo list with discrete processing steps
   - Update plan if you discover issues during execution

2. **Inspection Phase**:
   - Use inspect_csv_structure tool to analyze the file
   - Store detailed analysis in `/csv_analysis/schema.txt`
   - Extract sample rows to `/csv_analysis/samples.txt`
   - Delegate deep analysis to csv_analyzer subagent if needed

3. **Column Mapping Phase**:
   - Use map_csv_columns to fuzzy match column names
   - Check `/memories/column_mappings.txt` for learned patterns
   - Save new patterns to `/memories/column_mappings.txt`

4. **Data Cleaning Phase**:
   - Use batch_clean_csv_records to clean and validate data
   - For complex transformations, delegate to csv_transformer subagent
   - Store cleaning rules in `/csv_analysis/cleaning_rules.txt`

5. **Validation Phase**:
   - Delegate to csv_validator subagent for thorough validation
   - Check for duplicates, missing required fields, invalid data
   - Store validation report in `/csv_analysis/validation_report.txt`

6. **Processing Phase**:
   - Use batch_create_employees or batch_update_managers
   - Process in batches of 100 records
   - Handle errors gracefully

7. **Reporting Phase**:
   - Use save_processing_results to generate output files
   - Create success.csv, errors.csv, summary.txt
   - Log audit event for compliance

8. **Update Todos**:
   - Mark steps as completed as you progress
   - Provide final summary with todos

**Filesystem Organization:**

**Transient Storage** (cleared after session):
- `/csv_analysis/schema.txt` - Current CSV structure
- `/csv_analysis/samples.txt` - Sample data rows
- `/csv_analysis/cleaning_rules.txt` - Applied cleaning rules
- `/csv_analysis/validation_report.txt` - Validation results

**Persistent Storage** (saved across sessions):
- `/memories/column_mappings.txt` - Learned column name patterns
- `/memories/csv_patterns.txt` - Common CSV structures seen
- `/memories/cleaning_history.txt` - Data cleaning insights

**Subagent Delegation:**

- **csv_analyzer**: Deep schema and structure analysis
  - Use when: Initial CSV inspection needs detailed investigation
  - Example: "Analyze the schema of this complex multi-table CSV"

- **csv_validator**: Data quality and business rule validation
  - Use when: Need thorough validation beyond basic checks
  - Example: "Validate employee data against business rules"

- **csv_transformer**: Complex data transformations
  - Use when: Data needs significant restructuring or computation
  - Example: "Transform legacy employee codes to new format"

**Key Principles:**
- Always create todos BEFORE starting work
- Store analysis in filesystem to reduce context
- Delegate complex work to specialized subagents
- Check `/memories/` for learned patterns before processing
- Update todos as you progress (pending → in_progress → completed)
- Be adaptive - if inspection reveals issues, update your plan
- Maintain employer_id scoping for multi-tenant security

**Available Tools:**
- write_todos - Plan and track your work (auto-provided by TodoListMiddleware)
- ls, read_file, write_file, edit_file - Filesystem operations (auto-provided by FilesystemMiddleware)
- task - Delegate to subagents (auto-provided by SubAgentMiddleware)
- inspect_csv_structure - Analyze CSV file
- map_csv_columns - Fuzzy match column names
- batch_clean_csv_records - Clean and validate data
- batch_create_employees - Import new employees
- batch_update_managers - Update reporting relationships
- batch_initialize_leave_balances - Set up leave for new employees
- save_processing_results - Generate output files
"""


# Subagent definitions for specialized CSV processing
CSV_SUBAGENTS = [
    {
        "name": "csv_analyzer",
        "description": "Analyzes CSV schema, structure, data types, and column patterns in detail",
        "system_prompt": """You are a CSV analysis specialist.

Your job is to:
1. Inspect CSV files and extract comprehensive schema information
2. Identify data types for each column with confidence scores
3. Detect patterns, anomalies, and data quality issues
4. Generate a detailed analysis report

**Process:**
1. Use inspect_csv_structure tool to get initial analysis
2. Examine sample data for patterns
3. Identify potential data quality issues
4. Create detailed report with:
   - Column names and inferred types
   - Data quality scores
   - Detected patterns
   - Recommended cleaning operations

Store your analysis in `/csv_analysis/detailed_schema.txt` for the main agent to use.

Be thorough but concise - provide actionable insights.""",
        "tools": [inspect_csv_structure],
    },
    {
        "name": "csv_validator",
        "description": "Validates CSV data quality, completeness, business rules, and constraint checking",
        "system_prompt": """You are a CSV validation specialist.

Your job is to:
1. Check data completeness and missing values
2. Validate business rules and constraints
3. Identify outliers and suspicious data patterns
4. Generate comprehensive validation reports

**Validation Checks:**
- Required fields present
- Data type consistency
- Value ranges and constraints
- Duplicate detection
- Referential integrity
- Business rule compliance

**Process:**
1. Read CSV structure from `/csv_analysis/schema.txt`
2. Perform systematic validation checks
3. Classify issues by severity (critical, warning, info)
4. Generate validation report with specific row numbers

Store your report in `/csv_analysis/validation_report.txt` with:
- Total issues found
- Issues by severity
- Specific row numbers and fields
- Recommended actions

Be precise - include row numbers and specific field values for issues.""",
        "tools": [inspect_csv_structure, batch_clean_csv_records],
    },
    {
        "name": "csv_transformer",
        "description": "Applies complex data transformations, cleaning operations, and format conversions",
        "system_prompt": """You are a CSV transformation specialist.

Your job is to:
1. Apply column transformations and mappings
2. Normalize and clean data (names, emails, phone numbers)
3. Handle missing values with appropriate strategies
4. Generate transformation logs

**Transformation Types:**
- Data normalization (case, whitespace, formatting)
- Phone number cleaning (+27 formats, international)
- Email validation and correction
- Salary parsing (handle currency symbols, commas)
- Name parsing (first/last from full name)
- Date format standardization

**Process:**
1. Read cleaning rules from `/csv_analysis/cleaning_rules.txt`
2. Use batch_clean_csv_records for standard operations
3. Apply custom transformations as needed
4. Log all transformations with before/after examples
5. Track success rate

Store transformation log in `/csv_analysis/transformation_log.txt` with:
- Operations applied
- Success/failure counts
- Example transformations
- Issues encountered

Be efficient - use batch operations where possible.""",
        "tools": [batch_clean_csv_records, map_csv_columns],
    },
]


# Create the Deep Agents smart CSV processor with all middleware
# Store for persistent memory across sessions
store = InMemoryStore()

smart_csv_deep_agent = create_agent(
    model="claude-sonnet-4-5-20250929",  # Sonnet for complex reasoning
    tools=[
        # Core CSV processing tools
        inspect_csv_structure,
        map_csv_columns,
        batch_clean_csv_records,
        # Batch operations
        batch_create_employees,
        batch_update_managers,
        batch_initialize_leave_balances,
        # Results and reporting
        save_processing_results,
    ],
    # All three Deep Agents middleware configured explicitly
    middleware=[
        # 1. TodoListMiddleware for planning and progress tracking
        TodoListMiddleware(
            system_prompt=SMART_CSV_SYSTEM_PROMPT
        ),
        # 2. FilesystemMiddleware for persistent context storage
        FilesystemMiddleware(
            backend=lambda rt: CompositeBackend(
                default=StateBackend(rt),  # Transient storage (session-only)
                routes={"/memories/": StoreBackend(rt)}  # Persistent storage
            ),
            custom_tool_descriptions={
                "ls": "List files in filesystem. Use to check what analysis files exist.",
                "read_file": "Read a file from filesystem. Use to access stored CSV analysis, patterns, or validation reports.",
                "write_file": "Write a new file to filesystem. Store CSV analysis in /csv_analysis/ or patterns in /memories/.",
                "edit_file": "Edit an existing file. Use to update analysis or append to memory files.",
            }
        ),
        # 3. SubAgentMiddleware for specialized subagent delegation
        SubAgentMiddleware(
            default_model="claude-sonnet-4-5-20250929",
            subagents=CSV_SUBAGENTS,
        ),
    ],
    store=store,  # For persistent memory
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

    This agent uses full Deep Agents architecture with:
    - TodoListMiddleware: Automatic task planning and progress tracking
    - FilesystemMiddleware: Persistent context storage and memory
    - SubAgentMiddleware: Specialized subagents for analysis, validation, transformation
    - Adaptive workflows based on data quality
    - 90+ column name variations supported
    - Automatic data cleaning (phone numbers, emails, salaries)

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
    task_description = f"""Process this CSV file with intelligent cleaning, validation, and Deep Agents capabilities:

**File:** {file_path}
**Operation:** {operation}
**Admin ID:** {admin_id}
**Employer ID:** {employer_id} (IMPORTANT: All operations must be scoped to this employer)

**Your Task:**

Use your Deep Agents capabilities to process this CSV efficiently:

1. **Planning**: Create a detailed todo list with write_todos
2. **Filesystem**: Store analysis in /csv_analysis/ and patterns in /memories/
3. **Subagents**: Delegate to specialized subagents when appropriate:
   - csv_analyzer: For deep schema analysis
   - csv_validator: For thorough data validation
   - csv_transformer: For complex transformations

**Workflow Steps:**

1. Check `/memories/column_mappings.txt` for learned patterns
2. Inspect CSV and store analysis in `/csv_analysis/schema.txt`
3. Delegate to csv_analyzer if structure is complex
4. Map columns using fuzzy matching (handle variations)
5. Delegate to csv_validator for thorough validation
6. Clean data with batch_clean_csv_records or delegate to csv_transformer
7. Batch process valid records (100 per batch)
8. Initialize leave balances for new employees (if importing)
9. Generate results (success.csv, errors.csv, summary.txt)
10. Save new column patterns to `/memories/column_mappings.txt`
11. Log audit event

**Required Schema Fields:**
For import_employees: first_name, last_name, mobile_number, email, employee_no
For update_managers: employee_id, new_manager_id

**Scoping Rule:**
All operations must use employer_id={employer_id} to ensure multi-tenant data isolation.

**Start by:**
1. Creating your processing plan with write_todos
2. Checking /memories/ for learned patterns
3. Beginning inspection and analysis

Remember: Use filesystem to reduce context, delegate to subagents for complex work!"""

    try:
        # Invoke Deep Agent with task description
        # The agent will automatically use all middleware capabilities
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
