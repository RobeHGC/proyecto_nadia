"""
Unit tests for MCP Health API
Addresses code review feedback about missing test coverage
"""

import pytest
import asyncio
import json
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

from api.mcp_health_api import MCPHealthAPI, HealthStatus


class TestMCPHealthAPI:
    """Test suite for MCP Health API functionality"""
    
    @pytest.fixture
    def mcp_api(self):
        """Create MCP Health API instance for testing"""
        return MCPHealthAPI()
    
    @pytest.fixture
    def mock_redis(self):
        """Mock Redis connection"""
        mock_redis = AsyncMock()
        return mock_redis
    
    def test_mcp_api_initialization(self, mcp_api):
        """Test MCP API initializes correctly"""
        assert mcp_api.script_path is not None
        assert "mcp-workflow.sh" in mcp_api.script_path
    
    @pytest.mark.asyncio
    async def test_get_latest_health_status_success(self, mcp_api, mock_redis):
        """Test successful health status retrieval"""
        # Mock Redis data
        mock_health_data = {
            'timestamp': '2025-01-27T10:00:00Z',
            'command': 'health-check',
            'analysis': {
                'status': 'HEALTHY',
                'issues': [],
                'metrics': {'cpu_usage': 50},
                'alerts': []
            }
        }
        
        mock_redis.lindex.return_value = json.dumps(mock_health_data)
        
        with patch.object(mcp_api, '_get_redis', return_value=mock_redis):
            result = await mcp_api.get_latest_health_status('health-check')
        
        assert result is not None
        assert result.status == 'HEALTHY'
        assert result.command == 'health-check'
        assert len(result.issues) == 0
        assert result.metrics['cpu_usage'] == 50
    
    @pytest.mark.asyncio
    async def test_get_latest_health_status_no_data(self, mcp_api, mock_redis):
        """Test health status retrieval when no data exists"""
        mock_redis.lindex.return_value = None
        
        with patch.object(mcp_api, '_get_redis', return_value=mock_redis):
            result = await mcp_api.get_latest_health_status('health-check')
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_health_history(self, mcp_api, mock_redis):
        """Test health history retrieval"""
        # Mock Redis data
        mock_history = [
            json.dumps({
                'timestamp': '2025-01-27T10:00:00Z',
                'analysis': {'status': 'HEALTHY', 'issues': [], 'metrics': {}, 'alerts': []}
            }),
            json.dumps({
                'timestamp': '2025-01-27T09:55:00Z',
                'analysis': {'status': 'WARNING', 'issues': ['High CPU'], 'metrics': {}, 'alerts': []}
            })
        ]
        
        mock_redis.lrange.return_value = mock_history
        
        with patch.object(mcp_api, '_get_redis', return_value=mock_redis):
            result = await mcp_api.get_health_history('health-check', 2)
        
        assert len(result) == 2
        assert result[0].status == 'HEALTHY'
        assert result[1].status == 'WARNING'
        assert len(result[1].issues) == 1
    
    @pytest.mark.asyncio
    async def test_run_health_check_success(self, mcp_api):
        """Test running immediate health check successfully"""
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (b"Health check passed", b"")
        
        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            result = await mcp_api.run_health_check('health-check')
        
        assert result.status == 'HEALTHY'
        assert result.command == 'health-check'
        assert len(result.issues) == 0
    
    @pytest.mark.asyncio
    async def test_run_health_check_failure(self, mcp_api):
        """Test running immediate health check with failure"""
        mock_process = AsyncMock()
        mock_process.returncode = 1
        mock_process.communicate.return_value = (b"", b"Health check failed")
        
        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            result = await mcp_api.run_health_check('health-check')
        
        assert result.status == 'CRITICAL'
        assert result.command == 'health-check'
        assert len(result.issues) > 0
        assert "Command failed" in result.issues[0]
    
    @pytest.mark.asyncio
    async def test_get_recent_alerts(self, mcp_api, mock_redis):
        """Test retrieving recent alerts"""
        mock_alerts = [
            json.dumps({
                'timestamp': '2025-01-27T10:00:00Z',
                'type': 'test_alert',
                'severity': 'WARNING',
                'message': 'Test alert message',
                'daemon': 'test_daemon'
            })
        ]
        
        mock_redis.lrange.return_value = mock_alerts
        
        with patch.object(mcp_api, '_get_redis', return_value=mock_redis):
            result = await mcp_api.get_recent_alerts(10)
        
        assert len(result) == 1
        assert result[0].type == 'test_alert'
        assert result[0].severity == 'WARNING'
    
    @pytest.mark.asyncio
    async def test_redis_connection_error(self, mcp_api):
        """Test handling Redis connection errors"""
        with patch.object(mcp_api, '_get_redis', side_effect=Exception("Redis connection failed")):
            result = await mcp_api.get_latest_health_status('health-check')
        
        # Should return a status indicating the error
        assert result.status == 'UNKNOWN'
        assert len(result.issues) > 0
        assert "Failed to fetch status" in result.issues[0]


class TestHealthStatus:
    """Test suite for HealthStatus model"""
    
    def test_health_status_creation(self):
        """Test HealthStatus object creation"""
        status = HealthStatus(
            status='HEALTHY',
            timestamp='2025-01-27T10:00:00Z',
            command='health-check',
            issues=[],
            metrics={'cpu': 50},
            alerts=[]
        )
        
        assert status.status == 'HEALTHY'
        assert status.command == 'health-check'
        assert status.metrics['cpu'] == 50
        assert len(status.issues) == 0
        assert len(status.alerts) == 0
    
    def test_health_status_with_issues(self):
        """Test HealthStatus with issues and alerts"""
        status = HealthStatus(
            status='WARNING',
            timestamp='2025-01-27T10:00:00Z',
            command='security-check',
            issues=['Potential vulnerability found'],
            metrics={},
            alerts=['High CPU usage detected']
        )
        
        assert status.status == 'WARNING'
        assert len(status.issues) == 1
        assert len(status.alerts) == 1
        assert 'vulnerability' in status.issues[0]


if __name__ == '__main__':
    # Run tests if executed directly
    pytest.main([__file__, '-v'])