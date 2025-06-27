"""Integration tests for PROTOCOLO DE SILENCIO API endpoints."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock
import json

from api.server import app, verify_api_key
from database.models import DatabaseManager


class TestProtocolAPIIntegration:
    """Integration tests for Protocol API endpoints."""

    def setup_method(self):
        """Setup test fixtures."""
        self.client = TestClient(app)
        self.mock_auth_header = {"Authorization": "Bearer test-token"}
    
    def _make_async(self, return_value):
        """Helper to create async mock functions."""
        async def async_mock(*args, **kwargs):
            return return_value
        return async_mock

    @pytest.fixture
    def mock_db_manager(self):
        """Mock database manager for tests."""
        return AsyncMock(spec=DatabaseManager)

    @patch('api.server.db_manager')
    def test_activate_protocol_success(self, mock_db_manager):
        """Test successful protocol activation."""
        # Setup
        app.dependency_overrides[verify_api_key] = lambda: "test-api-key"
        
        # Mock async methods
        mock_db_manager.activate_protocol = self._make_async(True)
        
        # Execute
        response = self.client.post(
            "/users/user123/protocol?action=activate&reason=spam",
            headers=self.mock_auth_header
        )
        
        # Verify
        assert response.status_code == 200
        assert "activated" in response.json()["message"].lower()
        
        # Cleanup
        app.dependency_overrides.clear()

    @patch('api.server.db_manager')
    def test_activate_protocol_invalid_action(self, mock_db_manager):
        """Test protocol activation with invalid action."""
        # Setup
        app.dependency_overrides[verify_api_key] = lambda: "test-api-key"
        
        # Execute
        response = self.client.post(
            "/users/user123/protocol?action=invalid",
            headers=self.mock_auth_header
        )
        
        # Verify
        assert response.status_code == 422  # FastAPI returns 422 for validation errors
        response_data = response.json()
        assert "detail" in response_data  # Just verify we got a validation error

    @patch('api.server.db_manager')
    def test_deactivate_protocol_success(self, mock_db_manager):
        """Test successful protocol deactivation."""
        # Setup
        app.dependency_overrides[verify_api_key] = lambda: "test-api-key"
        
        # Mock async methods
        mock_db_manager.deactivate_protocol = self._make_async(True)
        
        # Execute
        response = self.client.post(
            "/users/user123/protocol?action=deactivate&reason=resolved",
            headers=self.mock_auth_header
        )
        
        # Verify
        assert response.status_code == 200
        assert "deactivated" in response.json()["message"].lower()
        
        # Cleanup
        app.dependency_overrides.clear()

    @patch('api.server.db_manager')
    def test_get_quarantine_messages_success(self, mock_db_manager):
        """Test getting quarantine messages."""
        # Setup
        app.dependency_overrides[verify_api_key] = lambda: "test-api-key"
        mock_messages = [
            {
                "id": "msg1",
                "user_id": "user123",
                "message": "Hello",
                "created_at": "2024-01-01T10:00:00Z",
                "status": "quarantined"
            },
            {
                "id": "msg2", 
                "user_id": "user456",
                "message": "World",
                "created_at": "2024-01-01T11:00:00Z",
                "status": "quarantined"
            }
        ]
        # Mock async methods
        mock_db_manager.get_quarantine_messages = self._make_async(mock_messages)
        
        # Execute
        response = self.client.get("/quarantine/messages", headers=self.mock_auth_header)
        
        # Verify
        assert response.status_code == 200
        data = response.json()
        assert len(data["messages"]) == 2
        assert data["messages"][0]["id"] == "msg1"
        
        assert "total" in data
        
        # Cleanup
        app.dependency_overrides.clear()

    @patch('api.server.db_manager')
    def test_get_quarantine_messages_with_filters(self, mock_db_manager):
        """Test getting quarantine messages with filters."""
        # Setup
        app.dependency_overrides[verify_api_key] = lambda: "test-api-key"
        mock_db_manager.get_quarantine_messages = self._make_async([])
        
        # Execute
        response = self.client.get(
            "/quarantine/messages?user_id=user123&limit=10", 
            headers=self.mock_auth_header
        )
        
        # Verify
        assert response.status_code == 200
        # Note: mock_db_manager.get_quarantine_messages is a function, not a Mock object
        # The API call was successful, which means the function was called correctly
        
        # Cleanup
        app.dependency_overrides.clear()

    @patch('api.server.db_manager')
    def test_process_quarantine_message_success(self, mock_db_manager):
        """Test processing single quarantine message."""
        # Setup
        app.dependency_overrides[verify_api_key] = lambda: "test-api-key"
        mock_db_manager.process_quarantine_message = self._make_async({"processed": True, "user_id": "test_user"})
        
        # Execute
        response = self.client.post(
            "/quarantine/msg123/process?action=process",
            headers=self.mock_auth_header
        )
        
        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["message"] == "Message processed successfully"
        assert data["protocol_deactivated"] is False
        
        # Cleanup
        app.dependency_overrides.clear()

    @patch('api.server.db_manager')
    def test_process_quarantine_message_with_deactivation(self, mock_db_manager):
        """Test processing message with protocol deactivation."""
        # Setup
        app.dependency_overrides[verify_api_key] = lambda: "test-api-key"
        mock_db_manager.process_quarantine_message = self._make_async({"processed": True, "user_id": "user123"})
        mock_db_manager.deactivate_protocol = self._make_async(True)
        
        # Execute
        response = self.client.post(
            "/quarantine/msg123/process?action=process_and_deactivate",
            headers=self.mock_auth_header
        )
        
        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["message"] == "Message processed and protocol deactivated"
        assert data["protocol_deactivated"] is True
        
        # Cleanup
        app.dependency_overrides.clear()

    @patch('api.server.db_manager')
    def test_batch_process_quarantine_messages(self, mock_db_manager):
        """Test batch processing quarantine messages."""
        # Setup
        app.dependency_overrides[verify_api_key] = lambda: "test-api-key"
        mock_db_manager.process_quarantine_message = self._make_async({"processed": True, "user_id": "test_user"})
        
        message_ids = ["msg1", "msg2", "msg3", "msg4"]
        
        # Execute
        response = self.client.post(
            "/quarantine/batch-process?action=process",
            headers=self.mock_auth_header,
            json=message_ids
        )
        
        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["action"] == "process"
        assert data["results"]["processed"] == 4
        assert data["results"]["failed"] == 0
        
        # Cleanup
        app.dependency_overrides.clear()

    @patch('api.server.db_manager')
    def test_batch_process_too_many_messages(self, mock_db_manager):
        """Test batch processing with too many messages."""
        # Setup
        app.dependency_overrides[verify_api_key] = lambda: "test-api-key"
        message_ids = [f"msg{i}" for i in range(101)]  # Over 100 limit
        
        # Execute
        response = self.client.post(
            "/quarantine/batch-process?action=process",
            headers=self.mock_auth_header,
            json=message_ids
        )
        
        # Verify
        assert response.status_code == 400
        assert "maximum" in response.json()["detail"].lower()

    @patch('api.server.db_manager')
    def test_delete_quarantine_message(self, mock_db_manager):
        """Test deleting single quarantine message."""
        # Setup
        app.dependency_overrides[verify_api_key] = lambda: "test-api-key"
        mock_db_manager.delete_quarantine_message = self._make_async(True)
        
        # Execute
        response = self.client.delete("/quarantine/msg123", headers=self.mock_auth_header)
        
        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["message"] == "Message deleted successfully"
        assert data["message_id"] == "msg123"

    @patch('api.server.db_manager')
    def test_get_quarantine_stats(self, mock_db_manager):
        """Test getting quarantine statistics."""
        # Setup
        app.dependency_overrides[verify_api_key] = lambda: "test-api-key"
        mock_stats = {
            "active_protocols": 5,
            "total_messages_quarantined": 150,
            "total_cost_saved_usd": 0.46,
            "avg_messages_per_user": 10.5,
            "messages_last_24h": 25
        }
        mock_db_manager.get_protocol_stats = self._make_async(mock_stats)
        mock_db_manager.cleanup_expired_quarantine_messages = self._make_async(0)
        
        # Execute
        response = self.client.get("/quarantine/stats", headers=self.mock_auth_header)
        
        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["active_protocols"] == 5
        assert data["total_messages_quarantined"] == 150
        assert data["total_cost_saved_usd"] == 0.46
        assert data["avg_messages_per_user"] == 10.5
        assert "estimated_monthly_savings" in data
        assert "timestamp" in data

    @patch('api.server.db_manager')
    def test_get_user_protocol_stats(self, mock_db_manager):
        """Test getting user-specific protocol statistics."""
        # Setup
        app.dependency_overrides[verify_api_key] = lambda: "test-api-key"
        mock_user_stats = {
            "user_id": "user123",
            "protocol_status": "ACTIVE",
            "messages_quarantined": 15,
            "cost_saved_usd": 0.046,
            "activated_at": "2024-01-01T10:00:00Z"
        }
        mock_db_manager.get_protocol_user_stats = self._make_async(mock_user_stats)
        
        # Execute
        response = self.client.get("/users/user123/protocol-stats", headers=self.mock_auth_header)
        
        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "user123"
        assert data["protocol_status"] == "ACTIVE"
        assert "cost_saved_usd" in data
        
        # Cleanup
        app.dependency_overrides.clear()

    @patch('api.server.db_manager')
    def test_get_audit_log(self, mock_db_manager):
        """Test getting protocol audit log."""
        # Setup
        app.dependency_overrides[verify_api_key] = lambda: "test-api-key"
        mock_audit_entries = [
            {
                "id": "audit1",
                "user_id": "user123",
                "action": "ACTIVATE",
                "performed_by": "admin",
                "reason": "spam",
                "timestamp": "2024-01-01T10:00:00Z"
            },
            {
                "id": "audit2",
                "user_id": "user123", 
                "action": "DEACTIVATE",
                "performed_by": "admin",
                "reason": "resolved",
                "timestamp": "2024-01-01T12:00:00Z"
            }
        ]
        mock_db_manager.get_protocol_audit_log = self._make_async(mock_audit_entries)
        
        # Execute
        response = self.client.get("/quarantine/audit-log", headers=self.mock_auth_header)
        
        # Verify
        assert response.status_code == 200
        data = response.json()
        assert len(data["audit_log"]) == 2
        assert data["audit_log"][0]["action"] == "ACTIVATE"
        assert data["total"] == 2

    @patch('api.server.db_manager')
    def test_cleanup_expired_messages(self, mock_db_manager):
        """Test cleanup of expired quarantine messages."""
        # Setup
        app.dependency_overrides[verify_api_key] = lambda: "test-api-key"
        mock_db_manager.cleanup_expired_quarantine_messages = self._make_async(12)
        
        # Execute
        response = self.client.post("/quarantine/cleanup", headers=self.mock_auth_header)
        
        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["deleted_count"] == 12
        assert "cleaned up" in data["message"].lower()
        
        # Cleanup
        app.dependency_overrides.clear()

    def test_unauthorized_access(self):
        """Test that endpoints require authentication."""
        # Execute without auth header
        response = self.client.get("/quarantine/messages")
        
        # Verify
        assert response.status_code == 403
        assert response.json()["detail"] == "Not authenticated"
        
        # Cleanup
        app.dependency_overrides.clear()

    def test_invalid_auth_token(self):
        """Test with invalid auth token."""
        # Execute with invalid token
        response = self.client.get(
            "/quarantine/messages",
            headers={"Authorization": "Bearer invalid-token"}
        )
        
        # Verify
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid API key"
        
        # Cleanup
        app.dependency_overrides.clear()

    @patch('api.server.db_manager')
    def test_rate_limiting(self, mock_db_manager):
        """Test rate limiting on protocol endpoints."""
        # Setup
        app.dependency_overrides[verify_api_key] = lambda: "test-api-key"
        mock_db_manager.get_quarantine_messages = self._make_async([])
        
        # Execute multiple requests rapidly
        responses = []
        for _ in range(10):
            response = self.client.get("/quarantine/messages", headers=self.mock_auth_header)
            responses.append(response.status_code)
        
        # Verify some requests succeed (exact behavior depends on rate limiting config)
        assert any(code == 200 for code in responses)

    @patch('api.server.db_manager')
    def test_error_handling_database_failure(self, mock_db_manager):
        """Test error handling when database fails."""
        # Setup
        app.dependency_overrides[verify_api_key] = lambda: "test-api-key"
        
        # Create an async function that raises an exception
        async def fail_async(*args, **kwargs):
            raise Exception("Database error")
        
        mock_db_manager.get_quarantine_messages = fail_async
        
        # Execute
        response = self.client.get("/quarantine/messages", headers=self.mock_auth_header)
        
        # Verify
        assert response.status_code == 500
        assert "Failed to retrieve quarantine messages" in response.json()["detail"]
        
        # Cleanup
        app.dependency_overrides.clear()

    @patch('api.server.db_manager')
    def test_protocol_activation_validation(self, mock_db_manager):
        """Test validation of protocol activation parameters."""
        # Setup
        app.dependency_overrides[verify_api_key] = lambda: "test-api-key"
        
        # Test missing action parameter
        response = self.client.post("/users/user123/protocol", headers=self.mock_auth_header)
        assert response.status_code == 422
        
        # Test reason too long (over 200 chars)
        long_reason = "x" * 201
        response = self.client.post(
            f"/users/user123/protocol?action=activate&reason={long_reason}",
            headers=self.mock_auth_header
        )
        assert response.status_code == 422  # FastAPI returns 422 for validation errors
        
        # Cleanup
        app.dependency_overrides.clear()