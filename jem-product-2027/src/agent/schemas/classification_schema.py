"""Pydantic schemas for structured classification results.

Provides type-safe classification outputs with confidence scoring,
reasoning traces, and multi-intent detection.
"""

from __future__ import annotations

from typing import Literal, Optional, Any
from pydantic import BaseModel, Field


class ClassificationResult(BaseModel):
    """Structured classification result with confidence and reasoning.

    Attributes:
        primary_intent: Main classification category.
        confidence: Confidence score (0.0 = uncertain, 1.0 = certain).
        reasoning: Step-by-step reasoning explaining the classification.
        secondary_intent: Secondary classification if request has multiple parts.
        requires_clarification: Whether the request needs user clarification.
        clarification_question: Question to ask if clarification needed.
        extracted_entities: Key entities mentioned in the request.
    """

    primary_intent: Literal["query", "crud", "leave", "bulk"] = Field(
        description="Primary classification category based on the user's main intent"
    )

    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score between 0.0 (very uncertain) and 1.0 (very certain)"
    )

    reasoning: str = Field(
        description="Step-by-step reasoning explaining how this classification was determined"
    )

    secondary_intent: Optional[Literal["query", "crud", "leave", "bulk"]] = Field(
        default=None,
        description="Secondary intent if the request contains multiple operations"
    )

    requires_clarification: bool = Field(
        default=False,
        description="True if the request is ambiguous and needs user clarification"
    )

    clarification_question: Optional[str] = Field(
        default=None,
        description="Specific question to ask the user if clarification is needed"
    )

    extracted_entities: dict[str, Any] = Field(
        default_factory=dict,
        description="Key entities mentioned: employee_ids, names, dates, file_paths, numbers"
    )


class ConversationContext(BaseModel):
    """Extracted context from conversation history.

    Attributes:
        mentioned_employees: Employee IDs and names mentioned in conversation.
        mentioned_dates: Dates referenced in conversation.
        previous_operations: Recent operations performed.
        unresolved_references: Pronouns or references needing resolution.
    """

    mentioned_employees: dict[str, Any] = Field(
        default_factory=dict,
        description="Employees mentioned: {id: {'name': '...', 'mentioned_at': ...}}"
    )

    mentioned_dates: list[str] = Field(
        default_factory=list,
        description="Dates referenced in conversation"
    )

    previous_operations: list[str] = Field(
        default_factory=list,
        description="Recent operations performed (last 5)"
    )

    unresolved_references: list[str] = Field(
        default_factory=list,
        description="Pronouns or references that need resolution: 'their', 'his', 'that employee'"
    )
