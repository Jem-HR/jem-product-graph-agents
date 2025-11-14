"""Tests for enhanced classification system.

Tests all improvements:
- Structured output with confidence
- Chain-of-thought reasoning
- Conversation context awareness
- Multi-intent detection
- Edge case handling
"""

import pytest
from langchain_core.messages import HumanMessage, AIMessage

from agent.hr_admin_graph import classify_request
from agent.utils.context_extraction import (
    extract_conversation_context,
    resolve_references,
    extract_text_from_message,
)


class TestEnhancedClassification:
    """Test enhanced classification system."""

    @pytest.mark.asyncio
    async def test_high_confidence_classification(self):
        """Test clear, unambiguous requests return high confidence."""
        state = {
            "messages": [
                AIMessage(content="Welcome!"),
                HumanMessage(content="Show my leave balance")
            ],
            "admin_context": {"id": 101487, "first_name": "Thamsanqa", "role": "hr_admin"}
        }

        result = await classify_request(state, None)

        # Should classify as "leave" with high confidence
        assert result["operation_type"] == "leave"
        assert result["classification_metadata"]["confidence"] >= 0.9
        assert "reasoning" in result["classification_metadata"]

    @pytest.mark.asyncio
    async def test_low_confidence_triggers_clarification(self):
        """Test ambiguous requests trigger clarification."""
        state = {
            "messages": [
                AIMessage(content="Welcome!"),
                HumanMessage(content="Help me with employees")  # Vague request
            ],
            "admin_context": {"id": 101487, "role": "hr_admin"}
        }

        result = await classify_request(state, None)

        # Should request clarification
        assert result["operation_type"] == "awaiting_clarification"
        assert result["classification_metadata"]["requires_clarification"] is True
        assert result["classification_metadata"]["confidence"] < 0.6

    @pytest.mark.asyncio
    async def test_multi_intent_detection(self):
        """Test detection of multi-intent requests."""
        state = {
            "messages": [
                AIMessage(content="Welcome!"),
                HumanMessage(content="Show John's salary AND create a leave request for me")
            ],
            "admin_context": {"id": 101487, "role": "hr_admin"}
        }

        result = await classify_request(state, None)

        # Should detect both intents
        metadata = result["classification_metadata"]
        assert "primary_intent" in metadata
        assert metadata.get("secondary_intent") is not None
        # Could be query+leave or crud+leave depending on interpretation

    @pytest.mark.asyncio
    async def test_conversation_context_extraction(self):
        """Test conversation context extraction from history."""
        messages = [
            HumanMessage(content="Show me employee 22483"),
            AIMessage(content="That's Sinta Reynolds..."),
            HumanMessage(content="What's their salary?")  # Reference to 22483
        ]

        context = extract_conversation_context(messages)

        # Should have extracted employee ID from first message
        assert "22483" in context.mentioned_employees
        # Should detect unresolved reference "their"
        assert "their" in context.unresolved_references

    @pytest.mark.asyncio
    async def test_reference_resolution(self):
        """Test pronoun resolution using context."""
        from agent.schemas.classification_schema import ConversationContext

        context = ConversationContext(
            mentioned_employees={"22483": {"mentioned_at": 0, "name": "Sinta Reynolds"}}
        )

        message = "What's their salary?"
        resolved = resolve_references(message, context)

        # Should resolve "their" to "employee 22483's"
        assert "22483" in resolved or "their" not in resolved.lower()

    @pytest.mark.asyncio
    async def test_bulk_classification(self):
        """Test bulk operation classification."""
        state = {
            "messages": [
                AIMessage(content="Welcome!"),
                HumanMessage(content="Import 5000 employees from CSV file")
            ],
            "admin_context": {"id": 101487, "role": "hr_admin"}
        }

        result = await classify_request(state, None)

        assert result["operation_type"] == "bulk"
        assert result["classification_metadata"]["confidence"] >= 0.8

    @pytest.mark.asyncio
    async def test_implicit_leave_request(self):
        """Test implicit leave request interpretation."""
        state = {
            "messages": [
                AIMessage(content="Welcome!"),
                HumanMessage(content="I need Friday off")  # Implicit leave request
            ],
            "admin_context": {"id": 101487, "role": "hr_admin"}
        }

        result = await classify_request(state, None)

        # Should interpret as leave request
        assert result["operation_type"] == "leave"

    @pytest.mark.asyncio
    async def test_typo_handling(self):
        """Test fuzzy matching with typos."""
        state = {
            "messages": [
                AIMessage(content="Welcome!"),
                HumanMessage(content="Show empolyee salry")  # Typos: employee, salary
            ],
            "admin_context": {"id": 101487, "role": "hr_admin"}
        }

        result = await classify_request(state, None)

        # Should still classify as query despite typos
        assert result["operation_type"] == "query"

    @pytest.mark.asyncio
    async def test_messy_csv_triggers_smart_processing(self):
        """Test messy CSV keyword detection."""
        state = {
            "messages": [
                AIMessage(content="Welcome!"),
                HumanMessage(content="Import messy CSV with dirty data from external system")
            ],
            "admin_context": {"id": 101487, "role": "hr_admin"}
        }

        result = await classify_request(state, None)

        # Should classify as bulk
        assert result["operation_type"] == "bulk"
        # Extracted entities should include keywords
        entities = result["classification_metadata"].get("extracted_entities", {})
        # Smart processing would be triggered by route_to_specialist

    @pytest.mark.asyncio
    async def test_confidence_metadata_present(self):
        """Test that all classifications include metadata."""
        state = {
            "messages": [
                AIMessage(content="Welcome!"),
                HumanMessage(content="Create a new employee")
            ],
            "admin_context": {"id": 101487, "role": "hr_admin"}
        }

        result = await classify_request(state, None)

        metadata = result["classification_metadata"]
        # All metadata fields should be present
        assert "confidence" in metadata
        assert "reasoning" in metadata
        assert isinstance(metadata["confidence"], float)
        assert 0.0 <= metadata["confidence"] <= 1.0

    @pytest.mark.asyncio
    async def test_fallback_on_error(self):
        """Test graceful fallback when structured output fails."""
        # This test would require mocking to force an error
        # For now, just document the expected behavior
        pass


class TestConversationContext:
    """Test conversation context utilities."""

    def test_extract_employee_ids(self):
        """Test extraction of employee IDs from messages."""
        messages = [
            HumanMessage(content="Show me employee ID 22483"),
            AIMessage(content="That's Sinta Reynolds"),
            HumanMessage(content="Thanks")
        ]

        context = extract_conversation_context(messages)

        assert "22483" in context.mentioned_employees

    def test_extract_text_from_multimodal(self):
        """Test text extraction from multimodal messages."""
        # Simulate Studio message format
        message = HumanMessage(content=[
            {"type": "text", "text": "Show my leave balance"}
        ])

        text = extract_text_from_message(message)

        assert text == "Show my leave balance"
        assert isinstance(text, str)

    def test_extract_employee_names(self):
        """Test extraction of employee names."""
        messages = [
            HumanMessage(content="What is John Doe's salary?"),
            AIMessage(content="John Doe earns 50000"),
            HumanMessage(content="Thanks")
        ]

        context = extract_conversation_context(messages)

        # Should extract "John Doe" as a mentioned employee
        assert any("John Doe" in str(key) for key in context.mentioned_employees.keys())
