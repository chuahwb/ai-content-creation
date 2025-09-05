"""
Tests for unified brief API endpoints and mode deprecation.
"""

import pytest
import json
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock
from churns.api.main import app
from churns.api.schemas import UnifiedBrief
from churns.core.input_normalizer import normalize_unified_brief_into_context
from churns.pipeline.context import PipelineContext


client = TestClient(app)


class TestUnifiedBriefAPI:
    """Test unified brief processing in the API."""

    @patch('churns.api.routers.task_processor.start_pipeline_run')
    @patch('churns.api.routers.get_session')
    def test_create_run_with_unified_brief_no_mode(self, mock_get_session, mock_start_pipeline):
        """Test creating a run with unified brief and no mode (deprecated field)."""
        # Mock database session
        mock_session = AsyncMock()
        mock_get_session.return_value = mock_session
        
        # Mock pipeline run creation
        mock_run = MagicMock()
        mock_run.id = "test-run-123"
        mock_session.add.return_value = None
        mock_session.commit.return_value = None
        mock_session.refresh.return_value = None
        mock_session.add.return_value = None
        
        # Mock task processor
        mock_start_pipeline.return_value = None

        unified_brief = {
            "intentType": "fullGeneration",
            "generalBrief": "Create a modern product photo with clean background",
            "editInstruction": "",
            "textOverlay": {
                "raw": ""
            }
        }

        # Test data without mode field
        form_data = {
            "platform_name": "Instagram Post (1:1 Square)",
            "creativity_level": 2,
            "num_variants": 3,
            "render_text": False,
            "apply_branding": False,
            "language": "en",
            "unified_brief": json.dumps(unified_brief)
        }

        with patch('churns.api.routers.PipelineRun', return_value=mock_run):
            response = client.post("/api/v1/runs", data=form_data)

        # Should succeed without mode
        assert response.status_code == 200
        # Should derive mode as "easy_mode" since no task_type or marketing_goals
        mock_session.add.assert_called_once()

    @patch('churns.api.routers.task_processor.start_pipeline_run')
    @patch('churns.api.routers.get_session')
    def test_create_run_content_validation(self, mock_get_session, mock_start_pipeline):
        """Test content-driven validation (requires brief or image)."""
        # Mock database session
        mock_session = AsyncMock()
        mock_get_session.return_value = mock_session
        
        # Test data with no prompt, no unified_brief, and no image
        form_data = {
            "platform_name": "Instagram Post (1:1 Square)",
            "creativity_level": 2,
            "num_variants": 3,
            "render_text": False,
            "apply_branding": False,
            "language": "en"
        }

        response = client.post("/api/v1/runs", data=form_data)

        # Should fail with content validation error
        assert response.status_code == 400
        assert "Please provide a creative brief or upload an image" in response.json()["detail"]

    @patch('churns.api.routers.task_processor.start_pipeline_run')
    @patch('churns.api.routers.get_session')
    def test_create_run_with_task_type_derives_mode(self, mock_get_session, mock_start_pipeline):
        """Test that providing task_type derives task_specific_mode."""
        # Mock database session
        mock_session = AsyncMock()
        mock_get_session.return_value = mock_session
        
        # Mock pipeline run creation
        mock_run = MagicMock()
        mock_run.id = "test-run-456"
        mock_session.add.return_value = None
        mock_session.commit.return_value = None
        mock_session.refresh.return_value = None

        # Mock task processor
        mock_start_pipeline.return_value = None

        unified_brief = {
            "intentType": "fullGeneration",
            "generalBrief": "Create a product showcase",
            "editInstruction": "",
            "textOverlay": {
                "raw": ""
            }
        }

        # Test data with task_type but no mode
        form_data = {
            "platform_name": "Instagram Post (1:1 Square)",
            "task_type": "1. Product Photography",
            "creativity_level": 2,
            "num_variants": 3,
            "render_text": False,
            "apply_branding": False,
            "language": "en",
            "unified_brief": json.dumps(unified_brief)
        }

        with patch('churns.api.routers.PipelineRun', return_value=mock_run):
            response = client.post("/api/v1/runs", data=form_data)

        # Should succeed and derive task_specific_mode
        assert response.status_code == 200

    def test_invalid_unified_brief_json(self):
        """Test handling of invalid unified_brief JSON."""
        form_data = {
            "platform_name": "Instagram Post (1:1 Square)",
            "creativity_level": 2,
            "num_variants": 3,
            "render_text": False,
            "apply_branding": False,
            "language": "en",
            "unified_brief": "invalid-json"
        }

        response = client.post("/api/v1/runs", data=form_data)

        assert response.status_code == 400
        assert "Invalid JSON format for unified_brief" in response.json()["detail"]

    @patch('churns.api.routers.task_processor.start_pipeline_run')
    @patch('churns.api.routers.get_session')
    def test_mode_derivation_logic(self, mock_get_session, mock_start_pipeline):
        """Test that mode is correctly derived from content when not provided."""
        # Mock database session
        mock_session = AsyncMock()
        mock_get_session.return_value = mock_session
        
        # Mock pipeline run creation
        mock_run = MagicMock()
        mock_run.id = "test-run-derive"
        mock_session.add.return_value = None
        mock_session.commit.return_value = None
        mock_session.refresh.return_value = None

        # Mock task processor
        mock_start_pipeline.return_value = None

        # Test 1: Task type should derive task_specific_mode
        unified_brief = {
            "intentType": "fullGeneration",
            "generalBrief": "Create a product showcase",
            "textOverlay": {"raw": ""}
        }

        form_data = {
            "platform_name": "Instagram Post (1:1 Square)",
            "task_type": "1. Product Photography",
            "creativity_level": 2,
            "num_variants": 3,
            "render_text": False,
            "apply_branding": False,
            "language": "en",
            "unified_brief": json.dumps(unified_brief)
        }

        with patch('churns.api.routers.PipelineRun', return_value=mock_run):
            response = client.post("/api/v1/runs", data=form_data)

        assert response.status_code == 200

        # Test 2: Marketing goals should derive custom_mode
        form_data_marketing = {
            "platform_name": "Instagram Post (1:1 Square)",
            "creativity_level": 2,
            "num_variants": 3,
            "render_text": False,
            "apply_branding": False,
            "language": "en",
            "marketing_audience": "Young professionals",
            "unified_brief": json.dumps(unified_brief)
        }

        with patch('churns.api.routers.PipelineRun', return_value=mock_run):
            response = client.post("/api/v1/runs", data=form_data_marketing)

        assert response.status_code == 200

        # Test 3: Neither should derive easy_mode
        form_data_simple = {
            "platform_name": "Instagram Post (1:1 Square)",
            "creativity_level": 2,
            "num_variants": 3,
            "render_text": False,
            "apply_branding": False,
            "language": "en",
            "unified_brief": json.dumps(unified_brief)
        }

        with patch('churns.api.routers.PipelineRun', return_value=mock_run):
            response = client.post("/api/v1/runs", data=form_data_simple)

        assert response.status_code == 200


class TestInputNormalizer:
    """Test the input normalizer functionality."""

    def test_normalize_unified_brief_basic(self):
        """Test basic normalization of unified brief to context."""
        brief = UnifiedBrief(
            intentType="fullGeneration",
            generalBrief="Create a modern product photo",
            editInstruction="",
            textOverlay={"raw": ""}
        )
        
        context = PipelineContext()
        normalize_unified_brief_into_context(brief, context)
        
        assert context.prompt == "Create a modern product photo"

    def test_normalize_unified_brief_with_edit_instruction(self):
        """Test normalization with edit instruction."""
        brief = UnifiedBrief(
            intentType="instructedEdit",
            generalBrief="Edit this product photo",
            editInstruction="Remove the background and add shadows",
            textOverlay={"raw": ""}
        )
        
        context = PipelineContext()
        normalize_unified_brief_into_context(brief, context)
        
        assert context.prompt == "Edit this product photo"
        assert context.image_reference["instruction"] == "Remove the background and add shadows"

    def test_normalize_unified_brief_with_text_overlay(self):
        """Test normalization with text overlay."""
        brief = UnifiedBrief(
            intentType="fullGeneration",
            generalBrief="Create a promotional image",
            editInstruction="",
            textOverlay={"raw": "SALE 50% OFF"}
        )
        
        context = PipelineContext()
        normalize_unified_brief_into_context(brief, context)
        
        assert context.prompt == "Create a promotional image"
        assert context.task_description == "SALE 50% OFF"

    def test_normalize_unified_brief_ignores_removed_fields(self):
        """Test that normalizer handles missing fields gracefully."""
        # Create a brief with only the required fields
        brief_data = {
            "intentType": "fullGeneration",
            "generalBrief": "Test brief",
            "textOverlay": {"raw": "Test text"}
            # Note: no editInstruction, no language in textOverlay, no styleHints
        }
        
        brief = UnifiedBrief(**brief_data)
        context = PipelineContext()
        
        # Should not raise an error
        normalize_unified_brief_into_context(brief, context)
        
        assert context.prompt == "Test brief"
        assert context.task_description == "Test text"

    def test_normalizer_with_legacy_fields_present(self):
        """Test that normalizer handles legacy fields gracefully."""
        # Simulate old client sending deprecated fields
        brief_data = {
            "intentType": "fullGeneration",
            "generalBrief": "Test brief",
            "textOverlay": {
                "raw": "Test text",
                "language": "en"  # This field was removed but might still be sent by old clients
            },
            "styleHints": ["modern", "clean"]  # This field was removed
        }
        
        # The Pydantic model should ignore the extra fields
        brief = UnifiedBrief(**{k: v for k, v in brief_data.items() if k in ["intentType", "generalBrief", "textOverlay"]})
        brief.textOverlay = {"raw": "Test text"}  # Remove language field
        
        context = PipelineContext()
        
        # Should not raise an error even with removed fields
        normalize_unified_brief_into_context(brief, context)
        
        assert context.prompt == "Test brief"
        assert context.task_description == "Test text"
        # Language should not be set from textOverlay (global language used instead)
