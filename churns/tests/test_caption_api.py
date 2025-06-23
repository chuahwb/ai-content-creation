"""
Integration tests for Caption API endpoints.

Tests the HTTP endpoints for caption generation and regeneration.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock
import json
import uuid
from datetime import datetime, timezone

from churns.api.main import app
from churns.api.database import RunStatus, get_session


class TestCaptionAPI:
    
    def setup_method(self):
        """Set up test client and mock data."""
        self.test_run_id = str(uuid.uuid4())
        self.test_image_id = "image_0"
        self.test_caption_id = str(uuid.uuid4())
    
    def test_generate_caption_success(self):
        """Test successful caption generation."""
        # Create mock session and run
        mock_session = Mock()
        mock_run = Mock()
        mock_run.status = RunStatus.COMPLETED
        mock_session.get.return_value = mock_run
        
        # Create mock task processor
        mock_task_processor = Mock()
        mock_task_processor.start_caption_generation = AsyncMock()
        
        # Override dependencies
        app.dependency_overrides[get_session] = lambda: mock_session
        
        with patch('churns.api.routers.task_processor', mock_task_processor):
            client = TestClient(app)
            
            # Test request
            request_data = {
                "image_id": self.test_image_id,
                "settings": {
                    "tone": "Friendly & Casual",
                    "include_emojis": True,
                    "hashtag_strategy": "Balanced Mix"
                }
            }
            
            response = client.post(
                f"/api/v1/runs/{self.test_run_id}/images/{self.test_image_id}/caption",
                json=request_data
            )
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["image_id"] == self.test_image_id
            assert data["status"] == "PENDING"
            assert data["version"] == 0
            assert data["text"] == "Caption generation in progress..."
            assert "caption_id" in data
            assert "created_at" in data
            
            # Verify task processor was called
            mock_task_processor.start_caption_generation.assert_called_once()
            
            # Check the call arguments
            call_args = mock_task_processor.start_caption_generation.call_args
            caption_id, caption_data = call_args[0]
            
            assert caption_data["run_id"] == self.test_run_id
            assert caption_data["image_id"] == self.test_image_id
            assert caption_data["version"] == 0
            assert caption_data["settings"]["tone"] == "Friendly & Casual"
        
        # Clean up dependency overrides
        app.dependency_overrides.clear()
    
    def test_generate_caption_auto_mode(self):
        """Test caption generation in auto mode (no settings provided)."""
        # Create mock session and run
        mock_session = Mock()
        mock_run = Mock()
        mock_run.status = RunStatus.COMPLETED
        mock_session.get.return_value = mock_run
        
        # Create mock task processor
        mock_task_processor = Mock()
        mock_task_processor.start_caption_generation = AsyncMock()
        
        # Override dependencies
        app.dependency_overrides[get_session] = lambda: mock_session
        
        with patch('churns.api.routers.task_processor', mock_task_processor):
            client = TestClient(app)
            
            # Test request with no settings (auto mode)
            request_data = {
                "image_id": self.test_image_id
            }
            
            response = client.post(
                f"/api/v1/runs/{self.test_run_id}/images/{self.test_image_id}/caption",
                json=request_data
            )
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["status"] == "PENDING"
            assert data["settings_used"]["include_emojis"] == True  # Default value
            
            # Verify task processor was called with empty settings
            call_args = mock_task_processor.start_caption_generation.call_args
            caption_id, caption_data = call_args[0]
            assert caption_data["settings"] == {}
        
        # Clean up dependency overrides
        app.dependency_overrides.clear()
    
    def test_generate_caption_run_not_found(self):
        """Test caption generation when run doesn't exist."""
        mock_session = Mock()
        mock_session.get.return_value = None  # Run not found
        
        # Override dependencies
        app.dependency_overrides[get_session] = lambda: mock_session
        
        client = TestClient(app)
        request_data = {"image_id": self.test_image_id}
        
        response = client.post(
            f"/api/v1/runs/{self.test_run_id}/images/{self.test_image_id}/caption",
            json=request_data
        )
        
        assert response.status_code == 404
        assert "Pipeline run not found" in response.json()["detail"]
        
        # Clean up dependency overrides
        app.dependency_overrides.clear()
    
    def test_generate_caption_run_not_completed(self):
        """Test caption generation when run is not completed."""
        mock_session = Mock()
        mock_run = Mock()
        mock_run.status = RunStatus.RUNNING  # Not completed
        mock_session.get.return_value = mock_run
        
        # Override dependencies
        app.dependency_overrides[get_session] = lambda: mock_session
        
        client = TestClient(app)
        request_data = {"image_id": self.test_image_id}
        
        response = client.post(
            f"/api/v1/runs/{self.test_run_id}/images/{self.test_image_id}/caption",
            json=request_data
        )
        
        assert response.status_code == 400
        assert "Pipeline must be completed" in response.json()["detail"]
        
        # Clean up dependency overrides
        app.dependency_overrides.clear()
    
    def test_regenerate_caption_success(self):
        """Test successful caption regeneration."""
        # Create mock session and run
        mock_session = Mock()
        mock_run = Mock()
        mock_run.status = RunStatus.COMPLETED
        mock_session.get.return_value = mock_run
        
        # Create mock task processor
        mock_task_processor = Mock()
        mock_task_processor.start_caption_generation = AsyncMock()
        
        # Override dependencies
        app.dependency_overrides[get_session] = lambda: mock_session
        
        with patch('churns.api.routers.task_processor', mock_task_processor):
            client = TestClient(app)
            
            # Test regeneration request
            request_data = {
                "settings": {
                    "tone": "Professional & Polished",
                    "call_to_action": "Shop now!"
                },
                "writer_only": False
            }
            
            response = client.post(
                f"/api/v1/runs/{self.test_run_id}/images/{self.test_image_id}/caption/0/regenerate",
                json=request_data
            )
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["image_id"] == self.test_image_id
            assert data["status"] == "PENDING"
            assert data["version"] == 1  # Incremented from 0
            assert data["settings_used"]["tone"] == "Professional & Polished"
            
            # Verify task processor was called
            mock_task_processor.start_caption_generation.assert_called_once()
            
            # Check the call arguments
            call_args = mock_task_processor.start_caption_generation.call_args
            caption_id, caption_data = call_args[0]
            
            assert caption_data["version"] == 1
            assert caption_data["writer_only"] == False  # New settings provided
            assert caption_data["previous_version"] == 0
        
        # Clean up dependency overrides
        app.dependency_overrides.clear()
    
    def test_regenerate_caption_writer_only(self):
        """Test caption regeneration in writer-only mode."""
        # Create mock session and run
        mock_session = Mock()
        mock_run = Mock()
        mock_run.status = RunStatus.COMPLETED
        mock_session.get.return_value = mock_run
        
        # Create mock task processor
        mock_task_processor = Mock()
        mock_task_processor.start_caption_generation = AsyncMock()
        
        # Override dependencies
        app.dependency_overrides[get_session] = lambda: mock_session
        
        with patch('churns.api.routers.task_processor', mock_task_processor):
            client = TestClient(app)
            
            # Test regeneration request with writer_only=True and no new settings
            request_data = {
                "writer_only": True
            }
            
            response = client.post(
                f"/api/v1/runs/{self.test_run_id}/images/{self.test_image_id}/caption/0/regenerate",
                json=request_data
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["version"] == 1
            
            # Check that writer_only was set correctly
            call_args = mock_task_processor.start_caption_generation.call_args
            caption_id, caption_data = call_args[0]
            assert caption_data["writer_only"] == True  # No new settings, so writer only
        
        # Clean up dependency overrides
        app.dependency_overrides.clear()
    
    def test_list_captions(self):
        """Test listing captions for an image."""
        mock_session = Mock()
        mock_run = Mock()
        mock_run.status = RunStatus.COMPLETED
        mock_session.get.return_value = mock_run
        
        # Override dependencies
        app.dependency_overrides[get_session] = lambda: mock_session
        
        client = TestClient(app)
        response = client.get(
            f"/api/v1/runs/{self.test_run_id}/images/{self.test_image_id}/captions"
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["run_id"] == self.test_run_id
        assert data["image_id"] == self.test_image_id
        assert "captions" in data
        assert "total_versions" in data
        
        # Clean up dependency overrides
        app.dependency_overrides.clear()
    
    def test_caption_request_validation(self):
        """Test request validation for caption endpoints."""
        client = TestClient(app)
        
        # Test invalid image_id (missing)
        response = client.post(
            f"/api/v1/runs/{self.test_run_id}/images//caption",
            json={}
        )
        assert response.status_code == 404  # Route not found due to empty image_id
        
        # Test invalid settings
        request_data = {
            "image_id": self.test_image_id,
            "settings": {
                "tone": "Invalid Tone",  # This should still work as validation is lenient
                "include_emojis": "not_a_boolean"  # This should fail
            }
        }
        
        response = client.post(
            f"/api/v1/runs/{self.test_run_id}/images/{self.test_image_id}/caption",
            json=request_data
        )
        
        # Should fail due to invalid boolean value
        assert response.status_code == 422 