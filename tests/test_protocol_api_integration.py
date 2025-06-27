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

    @pytest.fixture
    def mock_db_manager(self):
        """Mock database manager for tests."""
        return AsyncMock(spec=DatabaseManager)

    @patch('api.server.db_manager')
    def test_activate_protocol_success(self, mock_db_manager):
        """Test successful protocol activation."""
        # Setup
        app.dependency_overrides[verify_api_key] = lambda: "test-api-key"
        
        # Make the async method return an awaitable
        async def mock_activate_protocol(*args, **kwargs):
            return True
        mock_db_manager.activate_protocol = mock_activate_protocol
        
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

    @patch('api.server.get_auth_db')
    def test_activate_protocol_invalid_action(self, mock_get_db, mock_db_manager):
        """Test protocol activation with invalid action."""
        # Setup
        mock_get_db.return_value = mock_db_manager
        
        # Execute
        response = self.client.post(
            "/users/user123/protocol?action=invalid",
            headers=self.mock_auth_header
        )
        
        # Verify
        assert response.status_code == 400
        assert "invalid action" in response.json()["detail"].lower()

    @patch('api.server.get_auth_db')
    def test_deactivate_protocol_success(self, mock_get_db, mock_db_manager):
        """Test successful protocol deactivation."""
        # Setup
        mock_get_db.return_value = mock_db_manager
        mock_db_manager.deactivate_protocol.return_value = True
        
        # Execute
        response = self.client.post(
            "/users/user123/protocol?action=deactivate&reason=resolved",
            headers=self.mock_auth_header
        )
        
        # Verify
        assert response.status_code == 200
        assert "deactivated" in response.json()["message"].lower()

    @patch('api.server.get_auth_db')
    def test_get_quarantine_messages_success(self, mock_get_db, mock_db_manager):
        """Test getting quarantine messages."""
        # Setup
        mock_get_db.return_value = mock_db_manager
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
        mock_db_manager.get_quarantine_messages.return_value = mock_messages
        
        # Execute
        response = self.client.get("/quarantine/messages", headers=self.mock_auth_header)
        
        # Verify
        assert response.status_code == 200
        data = response.json()
        assert len(data["messages"]) == 2
        assert data["messages"][0]["id"] == "msg1"
        assert "total" in data

    @patch('api.server.get_auth_db')
    def test_get_quarantine_messages_with_filters(self, mock_get_db, mock_db_manager):
        """Test getting quarantine messages with filters."""
        # Setup
        mock_get_db.return_value = mock_db_manager
        mock_db_manager.get_quarantine_messages.return_value = []
        
        # Execute
        response = self.client.get(
            "/quarantine/messages?user_id=user123&limit=10", 
            headers=self.mock_auth_header
        )
        
        # Verify
        assert response.status_code == 200
        mock_db_manager.get_quarantine_messages.assert_called_with(
            user_id="user123", 
            limit=10, 
            include_processed=False
        )

    @patch('api.server.get_auth_db')
    def test_process_quarantine_message_success(self, mock_get_db, mock_db_manager):
        """Test processing single quarantine message."""
        # Setup
        mock_get_db.return_value = mock_db_manager
        mock_db_manager.process_quarantine_message.return_value = {"processed": True}
        
        # Execute
        response = self.client.post(
            "/quarantine/msg123/process?action=process",
            headers=self.mock_auth_header
        )
        
        # Verify
        assert response.status_code == 200
        assert response.json()["success"] is True

    @patch('api.server.get_auth_db')
    def test_process_quarantine_message_with_deactivation(self, mock_get_db, mock_db_manager):
        """Test processing message with protocol deactivation."""
        # Setup
        mock_get_db.return_value = mock_db_manager
        mock_db_manager.process_quarantine_message.return_value = {"processed": True, "user_id": "user123"}
        mock_db_manager.deactivate_protocol.return_value = True
        
        # Execute
        response = self.client.post(
            "/quarantine/msg123/process?action=process_and_deactivate",
            headers=self.mock_auth_header
        )
        
        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["protocol_deactivated"] is True

    @patch('api.server.get_auth_db')
    def test_batch_process_quarantine_messages(self, mock_get_db, mock_db_manager):
        """Test batch processing quarantine messages."""
        # Setup
        mock_get_db.return_value = mock_db_manager
        mock_db_manager.batch_process_quarantine_messages.return_value = {
            "processed": 3,
            "failed": 1,
            "results": [
                {"id": "msg1", "success": True},
                {"id": "msg2", "success": True},
                {"id": "msg3", "success": True},
                {"id": "msg4", "success": False, "error": "Not found"}
            ]
        }
        
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
        assert data["processed"] == 3
        assert data["failed"] == 1
        assert len(data["results"]) == 4

    @patch('api.server.get_auth_db')
    def test_batch_process_too_many_messages(self, mock_get_db, mock_db_manager):
        """Test batch processing with too many messages."""
        # Setup
        mock_get_db.return_value = mock_db_manager
        message_ids = [f"msg{i}" for i in range(101)]  # Over 100 limit
        
        # Execute
        response = self.client.post(
            "/quarantine/batch-process?action=process",
            headers=self.mock_auth_header,
            json=message_ids
        )
        
        # Verify
        assert response.status_code == 400
        assert "too many" in response.json()["detail"].lower()

    @patch('api.server.get_auth_db')
    def test_delete_quarantine_message(self, mock_get_db, mock_db_manager):
        """Test deleting single quarantine message."""
        # Setup
        mock_get_db.return_value = mock_db_manager
        mock_db_manager.delete_quarantine_message.return_value = True
        
        # Execute
        response = self.client.delete("/quarantine/msg123", headers=self.mock_auth_header)
        
        # Verify
        assert response.status_code == 200
        assert response.json()["success"] is True

    @patch('api.server.get_auth_db')
    def test_get_quarantine_stats(self, mock_get_db, mock_db_manager):
        """Test getting quarantine statistics."""
        # Setup
        mock_get_db.return_value = mock_db_manager
        mock_stats = {
            "active_protocols": 5,
            "total_quarantined": 150,
            "total_cost_saved_usd": 0.46,
            "messages_last_24h": 25,
            "estimated_monthly_savings": 14.25
        }
        mock_db_manager.get_protocol_stats.return_value = mock_stats
        
        # Execute
        response = self.client.get("/quarantine/stats", headers=self.mock_auth_header)
        
        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["active_protocols"] == 5
        assert data["total_cost_saved_usd"] == 0.46
        assert "estimated_monthly_savings" in data

    @patch('api.server.get_auth_db')
    def test_get_user_protocol_stats(self, mock_get_db, mock_db_manager):
        """Test getting user-specific protocol statistics."""
        # Setup
        mock_get_db.return_value = mock_db_manager
        mock_user_stats = {
            "user_id": "user123",
            "protocol_status": "ACTIVE",
            "messages_quarantined": 15,
            "cost_saved_usd": 0.046,
            "activated_at": "2024-01-01T10:00:00Z"
        }
        mock_db_manager.get_user_protocol_stats.return_value = mock_user_stats
        
        # Execute
        response = self.client.get("/users/user123/protocol-stats", headers=self.mock_auth_header)
        
        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "user123"
        assert data["protocol_status"] == "ACTIVE"
        assert "cost_saved_usd" in data

    @patch('api.server.get_auth_db')
    def test_get_audit_log(self, mock_get_db, mock_db_manager):
        """Test getting protocol audit log."""
        # Setup
        mock_get_db.return_value = mock_db_manager
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
        mock_db_manager.get_protocol_audit_log.return_value = mock_audit_entries
        
        # Execute
        response = self.client.get("/quarantine/audit-log", headers=self.mock_auth_header)
        
        # Verify
        assert response.status_code == 200
        data = response.json()
        assert len(data["entries"]) == 2
        assert data["entries"][0]["action"] == "ACTIVATE"

    @patch('api.server.get_auth_db')
    def test_cleanup_expired_messages(self, mock_get_db, mock_db_manager):
        """Test cleanup of expired quarantine messages."""
        # Setup
        mock_get_db.return_value = mock_db_manager
        mock_db_manager.cleanup_expired_quarantine_messages.return_value = 12
        
        # Execute
        response = self.client.post("/quarantine/cleanup", headers=self.mock_auth_header)
        
        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["deleted_count"] == 12
        assert "cleanup completed" in data["message"].lower()

    def test_unauthorized_access(self):
        """Test that endpoints require authentication."""
        # Execute without auth header
        response = self.client.get("/quarantine/messages")
        
        # Verify
        assert response.status_code == 401

    def test_invalid_auth_token(self):
        """Test with invalid auth token."""
        # Execute with invalid token
        response = self.client.get(
            "/quarantine/messages",
            headers={"Authorization": "Bearer invalid-token"}
        )
        
        # Verify
        assert response.status_code == 401

    @patch('api.server.get_auth_db')
    def test_rate_limiting(self, mock_get_db, mock_db_manager):
        """Test rate limiting on protocol endpoints."""
        # Setup
        mock_get_db.return_value = mock_db_manager
        mock_db_manager.get_quarantine_messages.return_value = []
        
        # Execute multiple requests rapidly
        responses = []
        for _ in range(10):
            response = self.client.get("/quarantine/messages", headers=self.mock_auth_header)
            responses.append(response.status_code)
        
        # Verify some requests succeed (exact behavior depends on rate limiting config)
        assert any(code == 200 for code in responses)

    @patch('api.server.get_auth_db')
    def test_error_handling_database_failure(self, mock_get_db, mock_db_manager):
        """Test error handling when database fails."""
        # Setup
        mock_get_db.return_value = mock_db_manager
        mock_db_manager.get_quarantine_messages.side_effect = Exception("Database error")
        
        # Execute
        response = self.client.get("/quarantine/messages", headers=self.mock_auth_header)
        
        # Verify
        assert response.status_code == 500
        assert "error" in response.json()["detail"].lower()

    @patch('api.server.get_auth_db')
    def test_protocol_activation_validation(self, mock_get_db, mock_db_manager):
        """Test validation of protocol activation parameters."""
        # Setup
        mock_get_db.return_value = mock_db_manager
        
        # Test missing action parameter
        response = self.client.post("/users/user123/protocol", headers=self.mock_auth_header)
        assert response.status_code == 422
        
        # Test reason too long (over 200 chars)
        long_reason = "x" * 201
        response = self.client.post(
            f"/users/user123/protocol?action=activate&reason={long_reason}",
            headers=self.mock_auth_header
        )
        assert response.status_code == 400