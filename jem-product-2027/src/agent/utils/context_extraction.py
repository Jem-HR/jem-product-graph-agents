"""Conversation context extraction utilities.

Extracts entities, resolves references, and builds context from conversation history.
"""

from __future__ import annotations

import re
from typing import Any

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

from agent.schemas.classification_schema import ConversationContext


def extract_text_from_message(message: BaseMessage) -> str:
    """Extract plain text from message (handles multimodal content).

    Args:
        message: LangChain message object.

    Returns:
        Plain text string.
    """
    if hasattr(message, "content"):
        content = message.content
        if isinstance(content, list):
            # Multimodal message - extract text blocks
            return " ".join(
                block.get("text", "") if isinstance(block, dict) else str(block)
                for block in content
            )
        else:
            return str(content)
    else:
        return str(message)


def extract_conversation_context(messages: list[BaseMessage]) -> ConversationContext:
    """Extract context and entities from conversation history.

    Args:
        messages: List of conversation messages.

    Returns:
        Structured conversation context.
    """
    context = ConversationContext()

    # Analyze all messages except the current one
    for i, msg in enumerate(messages[:-1]):
        text = extract_text_from_message(msg)

        # Extract employee IDs mentioned
        emp_id_pattern = r'\b(?:employee|ID|emp)\s*(?:ID|#)?\s*(\d+)\b'
        emp_ids = re.findall(emp_id_pattern, text, re.IGNORECASE)

        for emp_id in emp_ids:
            if emp_id not in context.mentioned_employees:
                context.mentioned_employees[emp_id] = {
                    "mentioned_at": i,
                    "context": text[:100]
                }

        # Extract names mentioned (simple pattern: capitalized words)
        name_pattern = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b'
        names = re.findall(name_pattern, text)

        for name in names:
            # Store as potential employee reference
            if name not in context.mentioned_employees:
                context.mentioned_employees[f"name:{name}"] = {
                    "mentioned_at": i,
                    "name": name,
                    "context": text[:100]
                }

        # Extract dates mentioned (basic patterns)
        date_patterns = [
            r'\d{4}-\d{2}-\d{2}',  # YYYY-MM-DD
            r'\d{1,2}/\d{1,2}/\d{4}',  # MM/DD/YYYY or DD/MM/YYYY
            r'(?:next|last)\s+(?:week|month|monday|friday)',  # Relative dates
            r'(?:January|February|March|April|May|June|July|August|September|October|November|December)',  # Month names
        ]

        for pattern in date_patterns:
            dates = re.findall(pattern, text, re.IGNORECASE)
            context.mentioned_dates.extend(dates)

        # Track operations from AI responses
        if isinstance(msg, AIMessage):
            operation_keywords = ["created", "updated", "approved", "rejected", "deleted", "imported"]
            for keyword in operation_keywords:
                if keyword in text.lower():
                    context.previous_operations.append(f"{keyword} at turn {i}")

    # Detect unresolved references in current message
    current_text = extract_text_from_message(messages[-1])
    reference_patterns = ["they", "their", "them", "he", "she", "his", "her", "that employee", "this person"]

    for pattern in reference_patterns:
        if pattern in current_text.lower():
            context.unresolved_references.append(pattern)

    return context


def resolve_references(
    message: str,
    conversation_context: ConversationContext
) -> str:
    """Resolve pronouns and references using conversation context.

    Args:
        message: Current message with potential references.
        conversation_context: Context from conversation history.

    Returns:
        Message with resolved references (or original if can't resolve).
    """
    resolved = message

    # If there are unresolved references and we have mentioned employees
    if conversation_context.unresolved_references and conversation_context.mentioned_employees:
        # Get most recently mentioned employee
        if conversation_context.mentioned_employees:
            most_recent = max(
                conversation_context.mentioned_employees.items(),
                key=lambda x: x[1].get("mentioned_at", 0)
            )

            employee_ref = most_recent[0]
            employee_info = most_recent[1]

            # Simple pronoun replacement (basic implementation)
            pronouns = {
                "their": f"employee {employee_ref}'s",
                "them": f"employee {employee_ref}",
                "they": f"employee {employee_ref}",
            }

            for pronoun, replacement in pronouns.items():
                if pronoun in resolved.lower():
                    # Case-insensitive replacement
                    resolved = re.sub(
                        r'\b' + pronoun + r'\b',
                        replacement,
                        resolved,
                        flags=re.IGNORECASE
                    )

    return resolved


def build_conversation_summary(messages: list[BaseMessage], max_exchanges: int = 3) -> str:
    """Build a summary of recent conversation for context.

    Args:
        messages: Conversation messages.
        max_exchanges: Maximum number of exchanges to include.

    Returns:
        Formatted conversation summary.
    """
    if len(messages) <= 1:
        return "No prior conversation"

    # Get last N exchanges (exclude current message)
    recent = messages[max(0, len(messages) - max_exchanges * 2 - 1):-1]

    summary_lines = []
    for msg in recent:
        text = extract_text_from_message(msg)
        role = "User" if isinstance(msg, HumanMessage) else "Assistant"
        # Truncate long messages
        truncated = text[:150] + "..." if len(text) > 150 else text
        summary_lines.append(f"{role}: {truncated}")

    return "\n".join(summary_lines)
