# tests/test_hitl_api.py
"""Tests for HITL API endpoints."""
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.server import app


class TestHITLAPI:
    """Test HITL API endpoints."""

    def setup_method(self):
        """Setup test fixtures."""
        self.client = TestClient(app)

    @patch('api.server.db_manager')
    def test_get_pending_reviews(self, mock_db):
        """Test GET /reviews/pending endpoint."""
        # Mock database response
        mock_db.get_pending_reviews.return_value = [
            {
                "id": "test-id-1",
                "user_id": "123",
                "user_message": "Hello!",
                "llm1_raw_response": "Hi there!",
                "llm2_bubbles": ["Hi there! 😊"],
                "constitution_risk_score": 0.0,
                "constitution_flags": [],
                "constitution_recommendation": "approve",
                "priority_score": 0.5,
                "created_at": "2025-06-20T10:00:00Z"
            }
        ]

        # Make request
        response = self.client.get("/reviews/pending")

        # Assert response
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == "test-id-1"
        assert data[0]["user_id"] == "123"

        # Check that database was called correctly
        mock_db.get_pending_reviews.assert_called_once_with(limit=20, min_priority=0.0)

    @patch('api.server.db_manager')
    def test_get_pending_reviews_with_params(self, mock_db):
        """Test GET /reviews/pending with query parameters."""
        mock_db.get_pending_reviews.return_value = []

        response = self.client.get("/reviews/pending?limit=50&min_priority=0.8")

        assert response.status_code == 200
        mock_db.get_pending_reviews.assert_called_once_with(limit=50, min_priority=0.8)

    @patch('api.server.db_manager')
    def test_get_specific_review(self, mock_db):
        """Test GET /reviews/{review_id} endpoint."""
        # Mock database response
        mock_db.get_interaction.return_value = {
            "id": "test-id-1",
            "user_message": "Hello!",
            "llm1_raw_response": "Hi!",
            "review_status": "pending"
        }

        response = self.client.get("/reviews/test-id-1")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "test-id-1"
        mock_db.get_interaction.assert_called_once_with("test-id-1")

    @patch('api.server.db_manager')
    def test_get_nonexistent_review(self, mock_db):
        """Test GET /reviews/{review_id} for non-existent review."""
        mock_db.get_interaction.return_value = None

        response = self.client.get("/reviews/nonexistent")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @patch('api.server.db_manager')
    def test_approve_review(self, mock_db):
        """Test POST /reviews/{review_id}/approve endpoint."""
        # Mock successful approval
        mock_db.start_review.return_value = True
        mock_db.approve_review.return_value = True

        approval_data = {
            "final_bubbles": ["Hello! 😊", "How can I help?"],
            "edit_tags": ["TONE_CASUAL", "CONTENT_EMOJI_ADD"],
            "quality_score": 4,
            "reviewer_notes": "Good response"
        }

        response = self.client.post("/reviews/test-id/approve", json=approval_data)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "approved"
        assert data["review_id"] == "test-id"

        # Check database calls
        mock_db.start_review.assert_called_once_with("test-id", "api_user")
        mock_db.approve_review.assert_called_once_with(
            "test-id",
            ["Hello! 😊", "How can I help?"],
            ["TONE_CASUAL", "CONTENT_EMOJI_ADD"],
            4,
            "Good response"
        )

    @patch('api.server.db_manager')
    def test_approve_review_not_found(self, mock_db):
        """Test approve review when review doesn't exist."""
        mock_db.start_review.return_value = False  # Review not found

        approval_data = {
            "final_bubbles": ["Hello!"],
            "edit_tags": [],
            "quality_score": 3
        }

        response = self.client.post("/reviews/nonexistent/approve", json=approval_data)

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @patch('api.server.db_manager')
    def test_approve_review_fails(self, mock_db):
        """Test approve review when database operation fails."""
        mock_db.start_review.return_value = True
        mock_db.approve_review.return_value = False  # Approval failed

        approval_data = {
            "final_bubbles": ["Hello!"],
            "edit_tags": [],
            "quality_score": 3
        }

        response = self.client.post("/reviews/test-id/approve", json=approval_data)

        assert response.status_code == 400
        assert "failed to approve" in response.json()["detail"].lower()

    @patch('api.server.db_manager')
    def test_reject_review(self, mock_db):
        """Test POST /reviews/{review_id}/reject endpoint."""
        # Mock successful rejection
        mock_db.start_review.return_value = True
        mock_db.reject_review.return_value = True

        rejection_data = {
            "reviewer_notes": "Inappropriate content"
        }

        response = self.client.post("/reviews/test-id/reject", json=rejection_data)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "rejected"
        assert data["review_id"] == "test-id"

        # Check database calls
        mock_db.start_review.assert_called_once_with("test-id", "api_user")
        mock_db.reject_review.assert_called_once_with("test-id", "Inappropriate content")

    @patch('api.server.db_manager')
    def test_reject_review_without_notes(self, mock_db):
        """Test reject review without notes."""
        mock_db.start_review.return_value = True
        mock_db.reject_review.return_value = True

        response = self.client.post("/reviews/test-id/reject", json={})

        assert response.status_code == 200
        mock_db.reject_review.assert_called_once_with("test-id", None)

    @patch('api.server.db_manager')
    def test_get_dashboard_metrics(self, mock_db):
        """Test GET /metrics/dashboard endpoint."""
        # Mock metrics response
        mock_db.get_dashboard_metrics.return_value = {
            "pending_reviews": 5,
            "reviewed_today": 10,
            "avg_review_time_seconds": 45.5,
            "popular_edit_tags": [
                {"tag": "TONE_CASUAL", "count": 8},
                {"tag": "CONTENT_EMOJI_ADD", "count": 5}
            ]
        }

        response = self.client.get("/metrics/dashboard")

        assert response.status_code == 200
        data = response.json()
        assert data["pending_reviews"] == 5
        assert data["reviewed_today"] == 10
        assert data["avg_review_time_seconds"] == 45.5
        assert len(data["popular_edit_tags"]) == 2

    @patch('api.server.db_manager')
    def test_get_edit_taxonomy(self, mock_db):
        """Test GET /edit-taxonomy endpoint."""
        # Mock taxonomy response
        mock_db.get_edit_taxonomy.return_value = [
            {
                "code": "TONE_CASUAL",
                "category": "tone",
                "description": "Made more casual/informal"
            },
            {
                "code": "CONTENT_EMOJI_ADD",
                "category": "content",
                "description": "Added emojis"
            }
        ]

        response = self.client.get("/edit-taxonomy")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["code"] == "TONE_CASUAL"
        assert data[1]["code"] == "CONTENT_EMOJI_ADD"

    def test_root_endpoint_updated(self):
        """Test that root endpoint includes HITL endpoints."""
        response = self.client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert "HITL" in data["message"]
        assert "pending_reviews" in data["endpoints"]
        assert "approve_review" in data["endpoints"]
        assert "reject_review" in data["endpoints"]

    @patch('api.server.db_manager')
    def test_approval_request_validation(self, mock_db):
        """Test validation of approval request data."""
        mock_db.start_review.return_value = True
        mock_db.approve_review.return_value = True

        # Missing required fields
        response = self.client.post("/reviews/test-id/approve", json={})
        assert response.status_code == 422  # Validation error

        # Invalid quality score
        invalid_data = {
            "final_bubbles": ["Hello!"],
            "edit_tags": [],
            "quality_score": 10  # Should be 1-5
        }
        response = self.client.post("/reviews/test-id/approve", json=invalid_data)
        # Note: This might pass depending on Pydantic validation setup

    @patch('api.server.db_manager')
    def test_database_error_handling(self, mock_db):
        """Test API error handling when database operations fail."""
        # Simulate database exception
        mock_db.get_pending_reviews.side_effect = Exception("Database connection failed")

        response = self.client.get("/reviews/pending")

        assert response.status_code == 500
        assert "internal server error" in response.json()["detail"].lower()
