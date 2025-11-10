"""Employee greeting agent with database integration.

Agent asks for mobile number, queries database, and greets user by name.
"""

from __future__ import annotations

from typing import Any, Annotated

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, add_messages, END
from langgraph.runtime import Runtime
from typing_extensions import TypedDict

from agent.tools.database import get_employee_by_mobile  # PostgreSQL - kept for reference
from agent.tools.neo4j_tool import get_employee_by_mobile_neo4j, query_neo4j_with_natural_language


class Context(TypedDict):
    """Context parameters for the agent.

    Set these when creating assistants OR when invoking the graph.
    """

    my_configurable_param: str


class State(TypedDict):
    """Agent state tracking conversation and employee context.

    Attributes:
        messages: Conversation history with add_messages reducer.
        mobile_number: User-provided mobile number.
        employee_context: Employee data from database if found.
        employee_found: Whether employee lookup was successful.
        conversation_stage: Current stage of the conversation flow.
    """

    messages: Annotated[list[BaseMessage], add_messages]
    mobile_number: str | None
    employee_context: dict[str, Any] | None
    employee_found: bool
    conversation_stage: str


def convert_messages(messages: list) -> list[BaseMessage]:
    """Convert dict messages to BaseMessage objects.

    Args:
        messages: List of messages (dicts or BaseMessage objects).

    Returns:
        List of BaseMessage objects.
    """
    converted = []
    for msg in messages:
        if isinstance(msg, dict):
            msg_type = msg.get("type", "").lower()
            content = msg.get("content", "")
            if msg_type == "human":
                converted.append(HumanMessage(content=content))
            elif msg_type == "ai":
                converted.append(AIMessage(content=content))
            elif msg_type == "system":
                converted.append(SystemMessage(content=content))
            else:
                converted.append(msg)
        else:
            converted.append(msg)
    return converted


async def ask_mobile_number(state: State, runtime: Runtime[Context]) -> dict[str, Any]:
    """Initial node: Ask user for their mobile number or continue conversation.

    Args:
        state: Current conversation state.
        runtime: Runtime context.

    Returns:
        Updated state with AI message asking for mobile number or routing to continue.
    """
    # If employee is already identified, continue the conversation
    if state.get("employee_found") and state.get("employee_context"):
        return {"conversation_stage": "continue_conversation"}

    # Check if this is the first interaction (no messages or only initial user message)
    if not state.get("messages") or len(state["messages"]) <= 1:
        greeting_message = AIMessage(
            content="Hello! Welcome to our employee system. To get started, please provide your mobile number."
        )

        return {
            "messages": [greeting_message],
            "conversation_stage": "awaiting_mobile",
        }

    # If we're here, user has responded - move to extraction
    return {"conversation_stage": "extract_mobile"}


async def extract_mobile_number(
    state: State, runtime: Runtime[Context]
) -> dict[str, Any]:
    """Extract mobile number from user's message using LLM.

    Args:
        state: Current conversation state.
        runtime: Runtime context.

    Returns:
        Updated state with extracted mobile number.
    """
    # Get the last user message
    messages = state.get("messages", [])
    if not messages:
        return {"conversation_stage": "ask_mobile"}

    last_message = messages[-1]
    user_input = ""

    if isinstance(last_message, dict):
        content = last_message.get("content", "")
        # Handle multimodal content (list of content blocks)
        if isinstance(content, list):
            # Extract text from content blocks
            user_input = " ".join(
                block.get("text", "") if isinstance(block, dict) else str(block)
                for block in content
            )
        else:
            user_input = str(content)
    elif hasattr(last_message, "content"):
        content = last_message.content
        # Handle multimodal content (list of content blocks)
        if isinstance(content, list):
            # Extract text from content blocks
            user_input = " ".join(
                block.get("text", "") if isinstance(block, dict) else str(block)
                for block in content
            )
        else:
            user_input = str(content)

    # Use Claude to extract the mobile number
    model = ChatAnthropic(model="claude-haiku-4-5-20251001")

    extraction_prompt = f"""Extract the South African mobile number from the following text and return ONLY the number in the format 27XXXXXXXXX (11 digits starting with 27).

Rules:
- Convert 0XXXXXXXXX to 27XXXXXXXXX (replace leading 0 with 27)
- Convert +27XXXXXXXXX to 27XXXXXXXXX (remove the +)
- Remove all spaces, dashes, and formatting
- Return ONLY the 11-digit number, nothing else
- If no valid mobile number is found, return the word "NONE"

Text: {user_input}

Mobile number in 27XXXXXXXXX format:"""

    try:
        response = await model.ainvoke([HumanMessage(content=extraction_prompt)])
        extracted = response.content.strip()

        # Validate the extracted number
        if extracted == "NONE" or not extracted.startswith("27") or len(extracted) != 11 or not extracted.isdigit():
            error_message = AIMessage(
                content="I couldn't find a valid mobile number in your message. Please provide your mobile number in a format like 0821234567 or +27821234567."
            )
            return {
                "messages": [error_message],
                "conversation_stage": "awaiting_mobile",
            }

        return {
            "mobile_number": extracted,
            "conversation_stage": "lookup_employee",
        }

    except Exception as e:
        error_message = AIMessage(
            content=f"I encountered an error processing your message. Please try again with your mobile number."
        )
        return {
            "messages": [error_message],
            "conversation_stage": "awaiting_mobile",
        }


async def lookup_employee(state: State, runtime: Runtime[Context]) -> dict[str, Any]:
    """Query Neo4j database for employee by mobile number.

    Args:
        state: Current conversation state with mobile_number set.
        runtime: Runtime context.

    Returns:
        Updated state with employee_context and employee_found flag.
    """
    mobile_number = state.get("mobile_number")

    if not mobile_number:
        return {
            "employee_found": False,
            "conversation_stage": "ask_mobile",
        }

    try:
        # Query Neo4j database (async)
        employee = await get_employee_by_mobile_neo4j(mobile_number)

        if employee:
            return {
                "employee_context": employee,
                "employee_found": True,
                "conversation_stage": "greet_employee",
            }
        else:
            return {
                "employee_found": False,
                "conversation_stage": "handle_not_found",
            }

    except Exception as e:
        # Handle database errors gracefully
        error_message = AIMessage(
            content=f"I encountered an issue while looking up your information. Please try again later. (Error: {str(e)})"
        )
        return {
            "messages": [error_message],
            "employee_found": False,
            "conversation_stage": "end",
        }


async def greet_employee(state: State, runtime: Runtime[Context]) -> dict[str, Any]:
    """Greet employee by name with personalized message.

    Args:
        state: Current conversation state with employee_context.
        runtime: Runtime context.

    Returns:
        Updated state with personalized greeting.
    """
    employee = state.get("employee_context", {})

    if not employee:
        return {"conversation_stage": "handle_not_found"}

    first_name = employee.get("first_name", "")
    last_name = employee.get("last_name", "")
    status = employee.get("status", "")
    smartwage_status = employee.get("smartwage_status", "")

    greeting = AIMessage(
        content=f"Hello {first_name} {last_name}! Welcome back. "
        f"I've found your employee record. Your status is {status}. "
        f"How can I assist you today?"
    )

    return {
        "messages": [greeting],
        "conversation_stage": "continue_conversation",
    }


async def handle_not_found(state: State, runtime: Runtime[Context]) -> dict[str, Any]:
    """Handle case where mobile number is not in database.

    Args:
        state: Current conversation state.
        runtime: Runtime context.

    Returns:
        Updated state with not-found message.
    """
    mobile_number = state.get("mobile_number", "")

    not_found_message = AIMessage(
        content=f"I'm sorry, but I couldn't find an employee record for mobile number {mobile_number}. "
        "Please verify your number is correct. If you believe this is an error, "
        "please contact your HR department for assistance."
    )

    return {
        "messages": [not_found_message],
        "conversation_stage": "end",
    }


async def continue_conversation(
    state: State, runtime: Runtime[Context]
) -> dict[str, Any]:
    """Handle ongoing conversation with Claude after employee is identified.

    Uses Neo4j for questions about org structure, relationships, and employee data.

    Args:
        state: Current conversation state with employee_context.
        runtime: Runtime context.

    Returns:
        Updated state with Claude's response.
    """
    model = ChatAnthropic(model="claude-haiku-4-5-20251001")

    # Build context-aware system message
    employee = state.get("employee_context", {})
    system_context = f"""You are a helpful employee assistance agent. You are currently speaking with:
Employee: {employee.get('first_name', '')} {employee.get('last_name', '')}
Mobile: {employee.get('mobile_number', '')}
Status: {employee.get('status', '')}
SmartWage Status: {employee.get('smartwage_status', '')}

Provide helpful, professional assistance related to their employment."""

    # Get the last user message
    messages = state.get("messages", [])
    if messages:
        last_message = messages[-1]
        user_question = ""

        if isinstance(last_message, dict):
            content = last_message.get("content", "")
            if isinstance(content, list):
                user_question = " ".join(
                    block.get("text", "") if isinstance(block, dict) else str(block)
                    for block in content
                )
            else:
                user_question = str(content)
        elif hasattr(last_message, "content"):
            content = last_message.content
            if isinstance(content, list):
                user_question = " ".join(
                    block.get("text", "") if isinstance(block, dict) else str(block)
                    for block in content
                )
            else:
                user_question = str(content)

        # Determine if question requires Neo4j query
        # Questions about org structure, relationships, colleagues, managers, teams, etc.
        neo4j_keywords = [
            "manager", "report", "team", "colleague", "work with", "works with",
            "org", "organization", "structure", "hierarchy", "supervisor",
            "direct report", "who is", "who are", "salary", "pay", "compensation",
            "benefit", "employment history", "job", "role", "position", "department"
        ]

        should_use_neo4j = any(keyword in user_question.lower() for keyword in neo4j_keywords)

        if should_use_neo4j and employee:
            try:
                # Use Neo4j to answer the question
                answer = await query_neo4j_with_natural_language(user_question, employee)
                response_message = AIMessage(content=answer)

                return {
                    "messages": [response_message],
                    "conversation_stage": "continue_conversation",
                }
            except Exception as e:
                # Fall back to regular conversation if Neo4j query fails
                error_context = f"\n\n(Note: I couldn't query the organizational database, so I'm providing a general response. Error: {str(e)})"
                system_context += error_context

    # Convert messages and add system context
    converted_messages = convert_messages(state["messages"])
    full_messages = [SystemMessage(content=system_context)] + converted_messages

    # Get response from Claude
    response = await model.ainvoke(full_messages)

    return {
        "messages": [response],
        "conversation_stage": "continue_conversation",
    }


def route_after_ask_mobile(state: State) -> str:
    """Route after asking for mobile number.

    Args:
        state: Current state.

    Returns:
        Next node name based on conversation stage.
    """
    stage = state.get("conversation_stage", "")

    if stage == "extract_mobile":
        return "extract_mobile_number"
    elif stage == "continue_conversation":
        # Employee already identified, continue conversation
        return "continue_conversation"
    elif stage == "awaiting_mobile":
        # After greeting, wait for user input (end the flow)
        return END

    return END


def route_after_extraction(state: State) -> str:
    """Route after mobile number extraction attempt.

    Args:
        state: Current state.

    Returns:
        Next node name based on whether mobile was extracted.
    """
    stage = state.get("conversation_stage", "")

    if stage == "lookup_employee":
        return "lookup_employee"
    elif stage == "awaiting_mobile":
        return "ask_mobile_number"

    return "ask_mobile_number"


def route_after_lookup(state: State) -> str:
    """Route after database lookup.

    Args:
        state: Current state.

    Returns:
        Next node based on whether employee was found.
    """
    stage = state.get("conversation_stage", "")

    if stage == "greet_employee":
        return "greet_employee"
    elif stage == "handle_not_found":
        return "handle_not_found"
    elif stage == "end":
        return END

    return "handle_not_found"


def route_after_greeting(state: State) -> str:
    """Route after greeting employee.

    Args:
        state: Current state.

    Returns:
        Next node for continued conversation.
    """
    return "continue_conversation"


def route_continuation(state: State) -> str:
    """Route during ongoing conversation.

    Args:
        state: Current state.

    Returns:
        Continue conversation or end.
    """
    stage = state.get("conversation_stage", "")

    if stage == "end":
        return END

    # In interactive mode (LangGraph Studio), after responding, END the turn
    # and wait for the next user message to continue
    return END


# Build the graph
workflow = StateGraph(State, context_schema=Context)

# Add nodes
workflow.add_node("ask_mobile_number", ask_mobile_number)
workflow.add_node("extract_mobile_number", extract_mobile_number)
workflow.add_node("lookup_employee", lookup_employee)
workflow.add_node("greet_employee", greet_employee)
workflow.add_node("handle_not_found", handle_not_found)
workflow.add_node("continue_conversation", continue_conversation)

# Add edges
workflow.set_entry_point("ask_mobile_number")

workflow.add_conditional_edges(
    "ask_mobile_number",
    route_after_ask_mobile,
    {
        "extract_mobile_number": "extract_mobile_number",
        "continue_conversation": "continue_conversation",
        END: END,
    },
)

workflow.add_conditional_edges(
    "extract_mobile_number",
    route_after_extraction,
    {
        "lookup_employee": "lookup_employee",
        "ask_mobile_number": "ask_mobile_number",
    },
)

workflow.add_conditional_edges(
    "lookup_employee",
    route_after_lookup,
    {
        "greet_employee": "greet_employee",
        "handle_not_found": "handle_not_found",
        END: END,
    },
)

workflow.add_conditional_edges(
    "greet_employee",
    route_after_greeting,
    {
        "continue_conversation": "continue_conversation",
    },
)

workflow.add_conditional_edges(
    "continue_conversation",
    route_continuation,
    {
        "continue_conversation": "continue_conversation",
        END: END,
    },
)

workflow.add_edge("handle_not_found", END)

# Compile the graph
graph = workflow.compile(name="Employee Greeting Agent")
