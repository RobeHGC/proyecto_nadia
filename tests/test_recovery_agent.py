"""Unit tests for RecoveryAgent - Zero message loss system."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from typing import List, Dict

from agents.recovery_agent import RecoveryAgent
from utils.recovery_config import RecoveryConfig, RecoveryTier
from database.models import DatabaseManager


class TestRecoveryAgent:
    """Test suite for RecoveryAgent functionality."""

    @pytest.fixture
    def mock_db(self):
        """Mock database manager."""
        db = AsyncMock()  # Remove spec to avoid attribute errors
        # Default return values
        db.get_last_message_per_user.return_value = {}
        db.start_recovery_operation.return_value = "op_123"
        db.update_recovery_operation.return_value = None
        db.get_recovery_operations.return_value = []
        return db

    @pytest.fixture
    def mock_telegram_history(self):
        """Mock Telegram history manager."""
        history = AsyncMock()
        history.scan_all_dialogs.return_value = []
        history.get_missing_messages.return_value = []
        return history

    @pytest.fixture
    def recovery_config(self):
        """Recovery configuration."""
        return RecoveryConfig()

    @pytest.fixture
    def recovery_agent(self, mock_telegram_history, mock_db, recovery_config):
        """Create RecoveryAgent instance."""
        agent = RecoveryAgent(
            database_manager=mock_db,
            telegram_history=mock_telegram_history,
            supervisor_agent=AsyncMock(),
            config=recovery_config
        )
        return agent

    @pytest.mark.asyncio
    async def test_initialization(self, recovery_agent, mock_db):
        """Test RecoveryAgent initialization."""
        assert recovery_agent.telegram_history is not None
        assert recovery_agent.db == mock_db
        assert recovery_agent.config is not None
        assert recovery_agent.supervisor is not None

    @pytest.mark.asyncio
    async def test_classify_message_priority(self, recovery_agent):
        """Test message priority classification."""
        
        # Test TIER_1 (<= 2 hours)
        tier = recovery_agent._classify_message_priority(1.0)
        assert tier == RecoveryTier.TIER_1
        
        # Test TIER_2 (> 2 hours, <= 12 hours)  
        tier = recovery_agent._classify_message_priority(4.0)
        assert tier == RecoveryTier.TIER_2
        
        # Test TIER_2 (boundary case - exactly 12 hours)
        tier = recovery_agent._classify_message_priority(12.0)
        assert tier == RecoveryTier.TIER_2
        
        # Test SKIP (> max_message_age_hours, which is 12 by default)
        tier = recovery_agent._classify_message_priority(13.0)
        assert tier == RecoveryTier.SKIP

    @pytest.mark.asyncio
    async def test_startup_recovery_check(self, recovery_agent, mock_db):
        """Test startup recovery check process."""
        # Mock telegram history scan
        recovery_agent.telegram_history.scan_all_dialogs.return_value = ["user1", "user2"]
        
        # Mock database last messages
        mock_db.get_last_message_per_user.return_value = {
            "user1": 90,  # Gap of 10 messages
            "user2": 200  # No gap
        }
        
        # Mock database operations
        mock_db.start_recovery_operation.return_value = 1
        mock_db.update_recovery_operation.return_value = None
        
        # Run startup recovery
        result = await recovery_agent.startup_recovery_check()
        
        # Verify database operations were called
        mock_db.start_recovery_operation.assert_called_once()
        mock_db.get_last_message_per_user.assert_called_once()
        
        # Verify result structure
        assert "operation_id" in result
        assert "users_scanned" in result

    @pytest.mark.asyncio
    async def test_identify_recovery_gaps(self, recovery_agent, mock_db):
        """Test gap identification logic."""
        telegram_data = {
            "user1": {
                "last_message_id": 100,
                "last_message_date": datetime.now() - timedelta(hours=1),
                "username": "testuser1"
            },
            "user2": {
                "last_message_id": 200,
                "last_message_date": datetime.now() - timedelta(hours=15),  # Too old
                "username": "testuser2"
            },
            "user3": {
                "last_message_id": 300,
                "last_message_date": datetime.now() - timedelta(hours=2),
                "username": "testuser3"
            }
        }
        
        db_data = {
            "user1": 90,   # Gap exists
            "user2": 199,  # Gap exists but too old
            # user3 not in DB - new user
        }
        
        gaps = recovery_agent._identify_recovery_gaps(telegram_data, db_data)
        
        # Should identify user1 and user3, but not user2 (too old)
        assert len(gaps) == 2
        assert any(g["user_id"] == "user1" for g in gaps)
        assert any(g["user_id"] == "user3" for g in gaps)
        assert not any(g["user_id"] == "user2" for g in gaps)

    @pytest.mark.asyncio
    async def test_process_recovery_batch(self, recovery_agent, mock_telegram, mock_db):
        """Test batch recovery processing."""
        # Mock Telegram messages
        mock_messages = [
            MagicMock(id=101, text="Hello", date=datetime.now()),
            MagicMock(id=102, text="How are you?", date=datetime.now())
        ]
        mock_telegram.get_messages.return_value = mock_messages
        
        # Create recovery batch
        batch = [{
            "user_id": "user1",
            "start_message_id": 100,
            "end_message_id": 105,
            "priority": RecoveryTier.TIER_1,
            "username": "testuser1"
        }]
        
        # Process batch
        await recovery_agent._process_recovery_batch(batch)
        
        # Verify Telegram API was called
        mock_telegram.get_messages.assert_called()
        
        # Verify recovery operation was created
        mock_db.create_recovery_operation.assert_called()

    @pytest.mark.asyncio
    async def test_rate_limiting(self, recovery_agent):
        """Test rate limiting functionality."""
        # First call should not be limited
        should_limit = await recovery_agent._check_rate_limit("user1")
        assert should_limit is False
        
        # Immediate second call should be limited
        should_limit = await recovery_agent._check_rate_limit("user1")
        assert should_limit is True

    @pytest.mark.asyncio
    async def test_health_check(self, recovery_agent, mock_db):
        """Test health check endpoint data."""
        mock_db.get_recovery_status.return_value = [
            {
                "status": "completed",
                "created_at": datetime.now() - timedelta(minutes=5)
            },
            {
                "status": "failed",
                "created_at": datetime.now() - timedelta(minutes=10)
            }
        ]
        
        health = await recovery_agent.get_health_status()
        
        assert health["is_healthy"] is True
        assert health["total_operations"] == 2
        assert health["failed_operations"] == 1
        assert "success_rate" in health

    @patch('agents.recovery_agent.ProtocolManager')
    @pytest.mark.asyncio
    async def test_quarantine_skip(self, mock_protocol, recovery_agent, mock_db):
        """Test that quarantined users are skipped."""
        # Mock protocol manager
        protocol_instance = AsyncMock()
        protocol_instance.is_user_quarantined.return_value = True
        mock_protocol.return_value = protocol_instance
        
        # Create gap for quarantined user
        gaps = [{
            "user_id": "quarantined_user",
            "start_message_id": 100,
            "end_message_id": 105,
            "priority": RecoveryTier.TIER_1,
            "username": "blocked"
        }]
        
        # Process should skip quarantined user
        processed = await recovery_agent._filter_quarantined_users(gaps)
        
        assert len(processed) == 0

    @pytest.mark.asyncio
    async def test_error_handling(self, recovery_agent, mock_telegram, mock_db):
        """Test error handling in recovery process."""
        # Mock Telegram error
        mock_telegram.get_messages.side_effect = Exception("Network error")
        
        batch = [{
            "user_id": "user1",
            "start_message_id": 100,
            "end_message_id": 105,
            "priority": RecoveryTier.TIER_1,
            "username": "testuser1"
        }]
        
        # Should handle error gracefully
        await recovery_agent._process_recovery_batch(batch)
        
        # Verify recovery was marked as failed
        calls = mock_db.update_recovery_status.call_args_list
        assert any("failed" in str(call) for call in calls)

    @pytest.mark.asyncio
    async def test_max_message_age_limit(self, recovery_agent):
        """Test maximum message age enforcement."""
        now = datetime.now()
        old_date = now - timedelta(hours=25)  # Older than 24 hours
        
        # Should categorize as SKIP
        tier = recovery_agent._categorize_recovery_priority(old_date)
        assert tier == RecoveryTier.SKIP

    @pytest.mark.asyncio
    async def test_concurrent_recovery_limit(self, recovery_agent):
        """Test concurrent recovery session limits."""
        recovery_agent._active_recoveries = {"user1", "user2", "user3"}
        recovery_agent.config.max_concurrent_recoveries = 3
        
        # Should not allow new recovery
        can_recover = recovery_agent._can_start_recovery("user4")
        assert can_recover is False
        
        # Should allow existing user
        can_recover = recovery_agent._can_start_recovery("user1")
        assert can_recover is True