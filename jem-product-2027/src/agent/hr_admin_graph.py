"""HR Admin Supervisor Agent.

Main supervisor agent that coordinates specialized subagents for:
- Employee CRUD operations
- Leave management
- Employee queries

Implements human-in-the-loop approval for sensitive operations.
"""

from __future__ import annotations

from typing import Any, Annotated

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, add_messages, END
# from langgraph.checkpoint.memory import MemorySaver  # Not needed - LangGraph Studio handles persistence
from langgraph.runtime import Runtime
from langgraph.types import interrupt
from typing_extensions import TypedDict

from agent.subagents.employee_crud_agent import employee_crud_agent
from agent.subagents.leave_agent import leave_management_agent
from agent.subagents.query_agent import query_employee_info
from agent.subagents.bulk_processing_agent import bulk_processing_agent
from agent.subagents.smart_csv_agent import smart_csv_agent
from agent.schemas.classification_schema import ClassificationResult
from agent.utils.context_extraction import (
    extract_text_from_message,
    extract_conversation_context,
    resolve_references,
    build_conversation_summary,
)


class Context(TypedDict):
    """Context parameters for the HR admin agent."""

    configurable_param: str


class HRAdminState(TypedDict):
    """HR admin agent state.

    Attributes:
        messages: Conversation history.
        admin_context: Admin user information and role.
        operation_type: Type of operation (query, crud, leave, bulk).
        pending_action: Action awaiting human approval.
        requires_approval: Whether current action needs approval.
        approved: Whether pending action was approved.
        classification_metadata: Classification confidence, reasoning, entities.
        conversation_context: Entities and context from conversation history.
    """

    messages: Annotated[list[BaseMessage], add_messages]
    admin_context: dict[str, Any] | None
    operation_type: str | None
    pending_action: dict[str, Any] | None
    requires_approval: bool
    approved: bool | None
    classification_metadata: dict[str, Any] | None
    conversation_context: dict[str, Any] | None


async def authenticate_admin(state: HRAdminState, runtime: Runtime[Context]) -> dict[str, Any]:
    """Authenticate and load admin context.

    In production, this would verify credentials and load admin profile.
    For now, we'll use a simple ID-based approach.

    Args:
        state: Current state.
        runtime: Runtime context.

    Returns:
        Updated state with admin_context.
    """
    admin_context = state.get("admin_context")

    # If admin is already authenticated, continue
    if admin_context and admin_context.get("id"):
        return {"operation_type": "classify"}

    # Extract admin ID from first message
    # In production, this would come from authentication system
    messages = state.get("messages", [])

    if not messages:
        return {
            "messages": [AIMessage(content="Hello! I'm the HR Admin Assistant. Please provide your employee ID to get started.")],
            "operation_type": "awaiting_auth"
        }

    # For now, assume admin ID is provided in a special format or we use a default
    # In a real system, this would be from the authenticated session
    admin_id = 101487  # Your employee ID (HR Admin)

    # Load admin profile from Neo4j
    from agent.tools.neo4j_tool import get_neo4j_driver

    driver = get_neo4j_driver()
    try:
        async with driver.session() as session:
            query = """
            MATCH (admin:Employee {id: $admin_id})
            OPTIONAL MATCH (report:Employee)-[:REPORTS_TO]->(admin)
            WHERE report.employer_id = admin.employer_id
            WITH admin, count(report) as report_count
            RETURN admin.id as id,
                   admin.first_name as first_name,
                   admin.last_name as last_name,
                   admin.email as email,
                   admin.status as status,
                   admin.employer_id as employer_id,
                   CASE
                       WHEN admin.id = 101487 THEN 'hr_admin'
                       WHEN report_count > 0 THEN 'hr_manager'
                       ELSE 'employee'
                   END as role
            """
            result = await session.run(query, admin_id=admin_id)
            record = await result.single()

            if record:
                admin_context = dict(record)
                greeting = AIMessage(
                    content=f"Welcome, {admin_context['first_name']} {admin_context['last_name']}! "
                    f"I'm your HR Admin Assistant (Role: {admin_context['role']}). "
                    f"I can help you with employee management, leave requests, and organizational queries. "
                    f"How can I assist you today?"
                )

                return {
                    "admin_context": admin_context,
                    "messages": [greeting],
                    "operation_type": "classify"
                }
            else:
                return {
                    "messages": [AIMessage(content=f"Admin with ID {admin_id} not found. Please contact system administrator.")],
                    "operation_type": "end"
                }
    finally:
        await driver.close()


async def classify_request(state: HRAdminState, runtime: Runtime[Context]) -> dict[str, Any]:
    """Enhanced classification with confidence scoring, chain-of-thought, and context awareness.

    Uses Claude Sonnet with structured output for robust classification.

    Args:
        state: Current state.
        runtime: Runtime context.

    Returns:
        Updated state with operation_type and metadata.
    """
    # Use Haiku for speed while keeping enhanced features
    model = ChatAnthropic(model="claude-haiku-4-5-20251001")
    structured_model = model.with_structured_output(ClassificationResult)

    messages = state.get("messages", [])
    admin_context = state.get("admin_context", {})

    if not messages:
        return {"operation_type": "end"}

    last_message = messages[-1]

    if isinstance(last_message, AIMessage):
        return {"operation_type": "end"}

    # Extract text from message
    user_message = extract_text_from_message(last_message)

    # Extract conversation context
    conv_context = extract_conversation_context(messages)

    # Resolve references if needed
    resolved_message = resolve_references(user_message, conv_context)

    # Build conversation summary
    conversation_summary = build_conversation_summary(messages, max_exchanges=3)

    # Enhanced classification prompt with chain-of-thought
    classification_prompt = f"""You are an intent classifier for an HR admin system. Analyze the user's request using step-by-step reasoning.

**Admin Context:**
- Admin Name: {admin_context.get('first_name', 'Unknown')} {admin_context.get('last_name', '')}
- Role: {admin_context.get('role', 'unknown')}
- Employer ID: {admin_context.get('employer_id', 'N/A')}

**Recent Conversation History:**
{conversation_summary}

**Entities from Previous Conversation:**
{conv_context.mentioned_employees if conv_context.mentioned_employees else 'None'}

**Current User Request:**
Original: "{user_message}"
{f'Resolved: "{resolved_message}"' if resolved_message != user_message else ''}

**Classification Categories:**

1. **query** - Read-only questions about employees, org structure, relationships, salaries
   Indicators: "who", "what", "show", "list", "find", "display", "view"
   Examples: "Who is John's manager?", "Show all employees", "List leave approvers"

2. **crud** - Create, update, or delete a SINGLE employee record
   Indicators: "create", "update", "change", "delete", "modify" + single employee
   Examples: "Create employee John Doe", "Update email for ID 123"

3. **leave** - Leave/PTO operations (create, approve, check balance, view pending)
   Indicators: "leave", "PTO", "vacation", "approve leave", "leave balance", "pending leave"
   Examples: "Check my leave balance", "Approve leave 123", "Show pending approvals"

4. **bulk** - Bulk operations from CSV files (multiple employees)
   Indicators: "CSV", "file", "import", "bulk", "upload", numbers >1, "batch"
   Examples: "Import from CSV", "Bulk update 100 employees", "Process file"

**Step-by-Step Analysis:**

**Step 1: Extract Key Entities**
Identify: employee names/IDs, dates, numbers, file references, action verbs

**Step 2: Identify Action Type**
Is this: asking for information OR modifying data OR managing leave OR processing files?

**Step 3: Check for Scope**
ONE employee (crud) vs MANY employees (bulk) vs information request (query) vs leave-related (leave)

**Step 4: Resolve Ambiguities**
- Multiple intents? Identify primary vs secondary
- Missing context? Check conversation history
- Vague request? Flag for clarification

**Step 5: Assess Confidence**
- High (0.9-1.0): Clear, unambiguous
- Medium (0.6-0.89): Likely correct but some ambiguity
- Low (<0.6): Requires clarification

**Step 6: Handle Edge Cases**
- Multi-intent: "Show salary AND create leave" → Both detected
- Implicit: "I need Friday off" → Interpret as leave request
- Typos: Fuzzy match keywords
- Context-dependent: Use conversation entities

**Provide structured classification with all required fields.**
"""

    try:
        # Get structured classification
        result = await structured_model.ainvoke([HumanMessage(content=classification_prompt)])

        # Store conversation context for next turn
        conv_context_dict = {
            "mentioned_employees": conv_context.mentioned_employees,
            "mentioned_dates": conv_context.mentioned_dates,
            "previous_operations": conv_context.previous_operations,
            "unresolved_references": conv_context.unresolved_references,
        }

        # Handle low confidence - request clarification
        if result.confidence < 0.6 or result.requires_clarification:
            clarification = result.clarification_question or (
                f"I'm not entirely sure what you'd like to do (confidence: {result.confidence:.0%}). "
                f"Could you provide more details?\n\n"
                f"**My understanding:** {result.reasoning[:200]}...\n\n"
                f"I can help you with:\n"
                f"- **Queries**: Employee information, org structure\n"
                f"- **CRUD**: Create/update single employee\n"
                f"- **Leave**: Manage leave requests and approvals\n"
                f"- **Bulk**: Process CSV files with multiple employees"
            )

            return {
                "messages": [AIMessage(content=clarification)],
                "operation_type": "awaiting_clarification",
                "classification_metadata": {
                    "confidence": result.confidence,
                    "reasoning": result.reasoning,
                    "primary_intent": result.primary_intent,
                    "requires_clarification": True
                },
                "conversation_context": conv_context_dict
            }

        # Handle multi-intent requests
        if result.secondary_intent:
            multi_intent_msg = AIMessage(
                content=f"I noticed your request has multiple parts:\n\n"
                        f"1. **{result.primary_intent.upper()}** operation (primary)\n"
                        f"2. **{result.secondary_intent.upper()}** operation (secondary)\n\n"
                        f"I'll handle the {result.primary_intent} operation first. Should I proceed?"
            )

            return {
                "messages": [multi_intent_msg],
                "operation_type": "confirm_multi_intent",
                "classification_metadata": {
                    "primary_intent": result.primary_intent,
                    "secondary_intent": result.secondary_intent,
                    "confidence": result.confidence,
                    "reasoning": result.reasoning,
                    "extracted_entities": result.extracted_entities
                },
                "conversation_context": conv_context_dict
            }

        # High confidence - proceed normally
        return {
            "operation_type": result.primary_intent,
            "classification_metadata": {
                "confidence": result.confidence,
                "reasoning": result.reasoning,
                "extracted_entities": result.extracted_entities
            },
            "conversation_context": conv_context_dict
        }

    except Exception as e:
        # Fallback to simple classification if structured fails
        print(f"⚠️ Enhanced classification failed, using fallback: {e}")

        # Fallback to original simple classification
        simple_model = ChatAnthropic(model="claude-haiku-4-5-20251001")
        simple_prompt = f"""Classify this request: "{user_message}"

Categories: query, crud, leave, or bulk

Respond with ONE word only."""

        response = await simple_model.ainvoke([HumanMessage(content=simple_prompt)])
        operation_type = response.content.strip().lower()

        if operation_type not in ["query", "crud", "leave", "bulk"]:
            operation_type = "query"

        return {
            "operation_type": operation_type,
            "classification_metadata": {
                "confidence": 0.5,  # Medium confidence for fallback
                "reasoning": "Used fallback classification due to error",
                "fallback": True,
                "error": str(e)
            }
        }


async def route_to_specialist(state: HRAdminState, runtime: Runtime[Context]) -> dict[str, Any]:
    """Route request to appropriate specialist subagent.

    Args:
        state: Current state.
        runtime: Runtime context.

    Returns:
        Updated state with subagent response.
    """
    operation_type = state.get("operation_type")
    admin_context = state.get("admin_context", {})
    admin_id = admin_context.get("id", 1)

    messages = state.get("messages", [])
    last_message = messages[-1] if messages else None

    if not last_message or isinstance(last_message, AIMessage):
        return {"operation_type": "end"}

    # Extract text from message (handle multimodal content)
    if hasattr(last_message, "content"):
        content = last_message.content
        if isinstance(content, list):
            # Multimodal message - extract text blocks
            user_message = " ".join(
                block.get("text", "") if isinstance(block, dict) else str(block)
                for block in content
            )
        else:
            user_message = str(content)
    else:
        user_message = str(last_message)

    model = ChatAnthropic(model="claude-haiku-4-5-20251001")

    try:
        if operation_type == "query":
            # Route to query agent
            employer_id = admin_context.get("employer_id")
            response = await query_employee_info.ainvoke({
                "question": user_message,
                "admin_id": admin_id,
                "employee_context": admin_context,
                "employer_id": employer_id
            })

            return {
                "messages": [AIMessage(content=response)],
                "operation_type": "end"
            }

        elif operation_type == "crud":
            # Parse CRUD operation and data using Claude
            extraction_prompt = f"""Extract the employee CRUD operation details from this request:

Request: "{user_message}"

Provide a JSON response with:
- operation: "create", "update", or "delete"
- employee_data: relevant fields

Example for create: {{"operation": "create", "employee_data": {{"first_name": "John", "last_name": "Doe", ...}}}}
Example for update: {{"operation": "update", "employee_data": {{"employee_id": 5, "email": "new@email.com"}}}}
Example for delete: {{"operation": "delete", "employee_data": {{"employee_id": 5}}}}

Respond with ONLY valid JSON, no other text."""

            response = await model.ainvoke([HumanMessage(content=extraction_prompt)])

            import json
            try:
                parsed = json.loads(response.content)
                operation = parsed.get("operation")
                employee_data = parsed.get("employee_data", {})

                # Check if this requires approval
                requires_approval = operation in ["create", "delete"] or "salary" in employee_data

                if requires_approval:
                    return {
                        "pending_action": {
                            "subagent": "employee_crud",
                            "operation": operation,
                            "data": employee_data
                        },
                        "requires_approval": True,
                        "operation_type": "confirm"
                    }
                else:
                    # Execute directly without approval
                    result = await employee_crud_agent.ainvoke({
                        "operation": operation,
                        "admin_id": admin_id,
                        "employee_data": employee_data
                    })

                    return {
                        "messages": [AIMessage(content=result)],
                        "operation_type": "end"
                    }

            except json.JSONDecodeError:
                return {
                    "messages": [AIMessage(content="I couldn't understand the employee operation. Please provide more details.")],
                    "operation_type": "end"
                }

        elif operation_type == "bulk":
            # Determine if smart CSV processing is needed
            complexity_indicators = [
                "clean", "messy", "dirty", "different format", "various format",
                "non-standard", "variable", "inconsistent", "external system",
                "need cleaning", "bad data", "quality issues"
            ]

            use_smart_processing = any(indicator in user_message.lower() for indicator in complexity_indicators)

            # For now, prompt user to provide CSV file path
            # In production, this would integrate with file upload system
            if use_smart_processing:
                bulk_message = AIMessage(
                    content="""🧠 **Smart CSV Processing Mode Activated**

I'll use intelligent processing for variable-format or dirty data:
- ✅ Fuzzy column matching (90+ name variations)
- ✅ Automatic data cleaning (mobile, email, salary)
- ✅ Adaptive planning based on data quality
- ✅ Progress tracking with todos
- ✅ Detailed error reporting

Please provide:
1. **File path** to your CSV
2. **Operation**: import_employees or update_managers

**Note:** This handles messy data automatically - no need for exact column names!

Example: "Process data/messy_hr_export.csv to import employees"
"""
                )
            else:
                bulk_message = AIMessage(
                    content="""📦 **Standard Bulk Processing Mode**

For clean, well-formatted CSV files with standard columns.

**Example CSV formats:**

**For importing employees:**
```csv
first_name,last_name,mobile_number,email,employee_no,salary
John,Doe,27821234567,john@company.com,EMP001,50000
```

**For updating managers:**
```csv
employee_id,new_manager_id
22483,22489
```

Provide file path to process.

💡 **Tip:** If your CSV has messy data or different column names, mention "clean" or "messy" to use smart processing!
"""
                )

            return {
                "messages": [bulk_message],
                "operation_type": "end"
            }

        elif operation_type == "leave":
            # Parse leave operation and data
            extraction_prompt = f"""Extract the leave management operation details from this request:

Request: "{user_message}"

Provide a JSON response with:
- operation: "create", "approve", "reject", "balance", "history", or "pending"
- leave_data: relevant fields

Operations:
- "create": Submit a new leave request
- "approve": Approve a specific leave request by ID
- "reject": Reject a specific leave request by ID
- "balance": Check leave balance for an employee
- "history": View leave request history for an employee
- "pending": View pending leave requests awaiting approval (also called "approval lines", "pending approvals", "requests to review")

Examples:
- Create: {{"operation": "create", "leave_data": {{"employee_id": 1, "leave_type": "annual", "start_date": "2025-01-15", "end_date": "2025-01-20", "reason": "vacation"}}}}
- Approve: {{"operation": "approve", "leave_data": {{"leave_request_id": 5}}}}
- Balance: {{"operation": "balance", "leave_data": {{"employee_id": 1}}}}
- Pending: {{"operation": "pending", "leave_data": {{"manager_id": 1}}}}

Common phrases for "pending":
- "show pending leave", "leave approval lines", "pending approvals", "requests awaiting approval", "what needs my approval", "show pending leave approval lines"

Common phrases for "balance":
- "show my leave balance", "check my leave balance", "how much leave do I have", "my leave balance"

If the user says "show my leave balance" or "check my leave balance":
{{"operation": "balance", "leave_data": {{"employee_id": {admin_id}}}}}

If the user says "show pending leave" or "pending approvals" or "leave approval lines":
{{"operation": "pending", "leave_data": {{"manager_id": {admin_id}}}}}

Respond with ONLY valid JSON, no other text."""

            response = await model.ainvoke([HumanMessage(content=extraction_prompt)])

            import json
            try:
                # Try to parse JSON
                content = response.content.strip()
                # Remove markdown code blocks if present
                if content.startswith("```"):
                    content = content.split("```")[1]
                    if content.startswith("json"):
                        content = content[4:]

                parsed = json.loads(content)
                operation = parsed.get("operation")
                leave_data = parsed.get("leave_data", {})

                # Auto-populate employee_id for self-service operations
                if operation in ["balance", "history"] and "employee_id" not in leave_data:
                    leave_data["employee_id"] = admin_id

                # Auto-populate manager_id for pending requests
                if operation == "pending" and "manager_id" not in leave_data:
                    leave_data["manager_id"] = admin_id

                # Check if this requires approval (create, approve, reject)
                requires_approval = operation in ["create", "approve", "reject"]

                if requires_approval:
                    return {
                        "pending_action": {
                            "subagent": "leave_management",
                            "operation": operation,
                            "data": leave_data
                        },
                        "requires_approval": True,
                        "operation_type": "confirm"
                    }
                else:
                    # Execute directly (balance, history, pending)
                    employer_id = admin_context.get("employer_id")
                    result = await leave_management_agent.ainvoke({
                        "operation": operation,
                        "admin_id": admin_id,
                        "leave_data": leave_data,
                        "employer_id": employer_id
                    })

                    return {
                        "messages": [AIMessage(content=result)],
                        "operation_type": "end"
                    }

            except json.JSONDecodeError as e:
                # Log the parsing error for debugging
                error_msg = f"I had trouble understanding your request. Could you rephrase it?\n\n"
                error_msg += "Examples:\n"
                error_msg += "- 'Show my leave balance'\n"
                error_msg += "- 'Show pending leave requests'\n"
                error_msg += "- 'Create a leave request from 2025-12-20 to 2025-12-24'"

                return {
                    "messages": [AIMessage(content=error_msg)],
                    "operation_type": "end"
                }

    except Exception as e:
        return {
            "messages": [AIMessage(content=f"Error routing request: {str(e)}")],
            "operation_type": "end"
        }

    return {"operation_type": "end"}


async def confirm_with_human(state: HRAdminState, runtime: Runtime[Context]) -> dict[str, Any]:
    """Request human approval for sensitive operations.

    Uses LangGraph's interrupt feature for human-in-the-loop.

    Args:
        state: Current state.
        runtime: Runtime context.

    Returns:
        Updated state after human decision.
    """
    pending_action = state.get("pending_action", {})

    if not pending_action:
        return {"operation_type": "end"}

    # Format action for human review
    subagent = pending_action.get("subagent")
    operation = pending_action.get("operation")
    data = pending_action.get("data", {})

    import json
    action_summary = f"""
**Action Requires Approval:**

Subagent: {subagent}
Operation: {operation}
Data: {json.dumps(data, indent=2)}

Please review and approve/reject this action.
"""

    # Send approval request to user
    approval_message = AIMessage(content=action_summary + "\n\nType 'approve' to proceed or 'reject' to cancel.")

    # Interrupt execution and wait for human input
    # In LangGraph Studio, this will pause execution
    decision = interrupt({"message": action_summary, "options": ["approve", "reject"]})

    if decision == "approve":
        return {
            "messages": [approval_message],
            "approved": True,
            "operation_type": "execute"
        }
    else:
        return {
            "messages": [
                approval_message,
                AIMessage(content="❌ Action rejected by admin. Operation cancelled.")
            ],
            "approved": False,
            "operation_type": "end"
        }


async def execute_action(state: HRAdminState, runtime: Runtime[Context]) -> dict[str, Any]:
    """Execute the approved action.

    Args:
        state: Current state.
        runtime: Runtime context.

    Returns:
        Updated state with execution result.
    """
    approved = state.get("approved")

    if not approved:
        return {
            "messages": [AIMessage(content="Action was not approved.")],
            "operation_type": "end"
        }

    pending_action = state.get("pending_action", {})
    admin_context = state.get("admin_context", {})
    admin_id = admin_context.get("id", 1)

    subagent = pending_action.get("subagent")
    operation = pending_action.get("operation")
    data = pending_action.get("data", {})

    try:
        employer_id = admin_context.get("employer_id")

        if subagent == "employee_crud":
            result = await employee_crud_agent.ainvoke({
                "operation": operation,
                "admin_id": admin_id,
                "employee_data": data,
                "employer_id": employer_id
            })
        elif subagent == "leave_management":
            result = await leave_management_agent.ainvoke({
                "operation": operation,
                "admin_id": admin_id,
                "leave_data": data,
                "employer_id": employer_id
            })
        else:
            result = f"Unknown subagent: {subagent}"

        return {
            "messages": [AIMessage(content=result)],
            "pending_action": None,
            "requires_approval": False,
            "approved": None,
            "operation_type": "end"
        }

    except Exception as e:
        return {
            "messages": [AIMessage(content=f"Error executing action: {str(e)}")],
            "operation_type": "end"
        }


def route_after_auth(state: HRAdminState) -> str:
    """Route after authentication."""
    op_type = state.get("operation_type", "")

    if op_type == "classify":
        return "classify_request"
    elif op_type == "awaiting_auth":
        return END
    elif op_type == "end":
        return END

    return END


def route_after_classify(state: HRAdminState) -> str:
    """Route after classification with enhanced confidence handling."""
    op_type = state.get("operation_type", "")

    # Handle new operation types from enhanced classification
    if op_type == "awaiting_clarification":
        # Low confidence - already sent clarification message, wait for response
        return END
    elif op_type == "confirm_multi_intent":
        # Multi-intent detected - already sent confirmation message, wait for response
        return END
    elif op_type in ["query", "crud", "leave", "bulk"]:
        # Normal classification - route to specialist
        return "route_to_specialist"
    elif op_type == "end":
        return END

    return END


def route_after_routing(state: HRAdminState) -> str:
    """Route after specialist routing."""
    op_type = state.get("operation_type", "")

    if op_type == "confirm":
        return "confirm_with_human"
    elif op_type == "end":
        return END

    return END


def route_after_confirm(state: HRAdminState) -> str:
    """Route after human confirmation."""
    op_type = state.get("operation_type", "")

    if op_type == "execute":
        return "execute_action"
    elif op_type == "end":
        return END

    return END


# Build the graph
workflow = StateGraph(HRAdminState, context_schema=Context)

# Add nodes
workflow.add_node("authenticate_admin", authenticate_admin)
workflow.add_node("classify_request", classify_request)
workflow.add_node("route_to_specialist", route_to_specialist)
workflow.add_node("confirm_with_human", confirm_with_human)
workflow.add_node("execute_action", execute_action)

# Set entry point
workflow.set_entry_point("authenticate_admin")

# Add conditional edges
workflow.add_conditional_edges(
    "authenticate_admin",
    route_after_auth,
    {
        "classify_request": "classify_request",
        END: END,
    },
)

workflow.add_conditional_edges(
    "classify_request",
    route_after_classify,
    {
        "route_to_specialist": "route_to_specialist",
        END: END,
    },
)

workflow.add_conditional_edges(
    "route_to_specialist",
    route_after_routing,
    {
        "confirm_with_human": "confirm_with_human",
        END: END,
    },
)

workflow.add_conditional_edges(
    "confirm_with_human",
    route_after_confirm,
    {
        "execute_action": "execute_action",
        END: END,
    },
)

workflow.add_edge("execute_action", END)

# Compile - LangGraph Studio automatically provides persistence
# checkpointer = MemorySaver()  # Not needed in Studio
graph = workflow.compile(name="HR Admin Agent")
