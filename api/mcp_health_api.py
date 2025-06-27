"""
MCP Health API Endpoints
Exposes automated MCP health check results via REST API
"""

import asyncio
import json
import subprocess
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
import redis.asyncio as redis

from utils.redis_mixin import RedisConnectionMixin
from utils.datetime_helpers import now_iso, time_ago_text
from utils.error_handling import handle_errors

router = APIRouter(prefix="/mcp", tags=["MCP Health"])

class HealthStatus(BaseModel):
    status: str  # HEALTHY, WARNING, CRITICAL, UNKNOWN
    timestamp: str
    command: str
    issues: List[str] = []
    metrics: Dict[str, Any] = {}
    alerts: List[str] = []

class HealthSummary(BaseModel):
    overall_status: str
    last_check: str
    checks_summary: Dict[str, HealthStatus]
    active_alerts: int
    daemon_status: Optional[Dict[str, Any]] = None

class AlertInfo(BaseModel):
    timestamp: str
    type: str
    severity: str
    message: str
    daemon: str

class MCPHealthAPI(RedisConnectionMixin):
    """MCP Health API implementation"""
    
    def __init__(self):
        # Use environment variable with fallback to project-relative path
        project_root = os.environ.get('PYTHONPATH', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.script_path = os.environ.get(
            'MCP_SCRIPT_PATH',
            os.path.join(project_root, 'scripts', 'mcp-workflow.sh')
        )
    
    @handle_errors
    async def get_latest_health_status(self, command: str) -> Optional[HealthStatus]:
        """Get latest health status for a command"""
        try:
            r = await self._get_redis()
            latest_result = await r.lindex(f'mcp_health_{command.replace("-", "_")}', 0)
            
            if not latest_result:
                return None
            
            data = json.loads(latest_result)
            analysis = data.get('analysis', {})
            
            return HealthStatus(
                status=analysis.get('status', 'UNKNOWN'),
                timestamp=data.get('timestamp', now_iso()),
                command=command,
                issues=analysis.get('issues', []),
                metrics=analysis.get('metrics', {}),
                alerts=analysis.get('alerts', [])
            )
            
        except Exception as e:
            return HealthStatus(
                status='UNKNOWN',
                timestamp=now_iso(),
                command=command,
                issues=[f"Failed to fetch status: {str(e)}"]
            )
    
    @handle_errors
    async def get_health_history(self, command: str, limit: int = 10) -> List[HealthStatus]:
        """Get health check history for a command"""
        try:
            r = await self._get_redis()
            results = await r.lrange(f'mcp_health_{command.replace("-", "_")}', 0, limit - 1)
            
            history = []
            for result_json in results:
                data = json.loads(result_json)
                analysis = data.get('analysis', {})
                
                history.append(HealthStatus(
                    status=analysis.get('status', 'UNKNOWN'),
                    timestamp=data.get('timestamp', now_iso()),
                    command=command,
                    issues=analysis.get('issues', []),
                    metrics=analysis.get('metrics', {}),
                    alerts=analysis.get('alerts', [])
                ))
            
            return history
            
        except Exception as e:
            return [HealthStatus(
                status='UNKNOWN',
                timestamp=now_iso(),
                command=command,
                issues=[f"Failed to fetch history: {str(e)}"]
            )]
    
    @handle_errors
    async def get_recent_alerts(self, limit: int = 20) -> List[AlertInfo]:
        """Get recent health alerts"""
        try:
            r = await self._get_redis()
            alerts = await r.lrange('health_alerts', 0, limit - 1)
            
            alert_list = []
            for alert_json in alerts:
                alert_data = json.loads(alert_json)
                alert_list.append(AlertInfo(**alert_data))
            
            return alert_list
            
        except Exception as e:
            return [AlertInfo(
                timestamp=now_iso(),
                type="api_error",
                severity="ERROR",
                message=f"Failed to fetch alerts: {str(e)}",
                daemon="mcp_health_api"
            )]
    
    @handle_errors
    async def run_health_check(self, command: str) -> HealthStatus:
        """Run immediate health check"""
        try:
            process = await asyncio.create_subprocess_exec(
                self.script_path, command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            # Simple analysis of output
            success = process.returncode == 0
            output = stdout.decode('utf-8', errors='ignore')
            error_output = stderr.decode('utf-8', errors='ignore')
            
            status = 'HEALTHY' if success else 'CRITICAL'
            issues = []
            
            if not success:
                issues.append(f"Command failed: {error_output}")
            
            # Check for warning indicators in output
            output_lower = output.lower()
            if any(keyword in output_lower for keyword in ['warning', 'slow', 'high']):
                status = 'WARNING'
                issues.append("Performance or warning indicators detected")
            
            return HealthStatus(
                status=status,
                timestamp=now_iso(),
                command=command,
                issues=issues,
                metrics={},  # Could parse metrics from output
                alerts=[]
            )
            
        except Exception as e:
            return HealthStatus(
                status='CRITICAL',
                timestamp=now_iso(),
                command=command,
                issues=[f"Failed to run check: {str(e)}"],
                metrics={},
                alerts=[]
            )

# Initialize API instance
mcp_api = MCPHealthAPI()

@router.get("/health", response_model=HealthSummary)
async def get_health_summary():
    """Get overall MCP health summary"""
    commands = ['health-check', 'security-check', 'performance', 'redis-health']
    
    checks_summary = {}
    overall_status = 'HEALTHY'
    latest_timestamp = None
    active_alert_count = 0
    
    # Get status for each command
    for command in commands:
        status = await mcp_api.get_latest_health_status(command)
        if status:
            checks_summary[command] = status
            
            # Update overall status (CRITICAL > WARNING > HEALTHY)
            if status.status == 'CRITICAL':
                overall_status = 'CRITICAL'
            elif status.status == 'WARNING' and overall_status != 'CRITICAL':
                overall_status = 'WARNING'
            
            # Track latest timestamp
            if not latest_timestamp or status.timestamp > latest_timestamp:
                latest_timestamp = status.timestamp
            
            # Count alerts
            active_alert_count += len(status.alerts)
    
    return HealthSummary(
        overall_status=overall_status,
        last_check=latest_timestamp or now_iso(),
        checks_summary=checks_summary,
        active_alerts=active_alert_count
    )

@router.get("/health/{command}", response_model=HealthStatus)
async def get_command_health(command: str):
    """Get health status for specific command"""
    valid_commands = ['health-check', 'security-check', 'performance', 'redis-health']
    
    if command not in valid_commands:
        raise HTTPException(status_code=400, detail=f"Invalid command. Valid commands: {valid_commands}")
    
    status = await mcp_api.get_latest_health_status(command)
    if not status:
        raise HTTPException(status_code=404, detail=f"No health data found for {command}")
    
    return status

@router.get("/health/{command}/history", response_model=List[HealthStatus])
async def get_command_history(command: str, limit: int = 10):
    """Get health check history for specific command"""
    if limit > 50:
        limit = 50  # Limit to prevent excessive data
    
    history = await mcp_api.get_health_history(command, limit)
    return history

@router.get("/alerts", response_model=List[AlertInfo])
async def get_recent_alerts(limit: int = 20):
    """Get recent health alerts"""
    if limit > 100:
        limit = 100  # Limit to prevent excessive data
    
    alerts = await mcp_api.get_recent_alerts(limit)
    return alerts

@router.post("/health/{command}/run", response_model=HealthStatus)
async def run_immediate_check(command: str, background_tasks: BackgroundTasks):
    """Run immediate health check for command"""
    valid_commands = ['health-check', 'security-check', 'redis-health']
    
    if command not in valid_commands:
        raise HTTPException(status_code=400, detail=f"Invalid command. Valid commands: {valid_commands}")
    
    # Run check immediately
    result = await mcp_api.run_health_check(command)
    
    # Store result in background
    async def store_result():
        try:
            r = await mcp_api._get_redis()
            health_record = {
                'timestamp': result.timestamp,
                'command': command,
                'result': {
                    'success': result.status != 'CRITICAL',
                    'timestamp': result.timestamp
                },
                'analysis': {
                    'status': result.status,
                    'issues': result.issues,
                    'metrics': result.metrics,
                    'alerts': result.alerts
                }
            }
            await r.lpush(f'mcp_health_{command.replace("-", "_")}', json.dumps(health_record))
            await r.ltrim(f'mcp_health_{command.replace("-", "_")}', 0, 49)
        except Exception:
            pass  # Don't fail the API call if storage fails
    
    background_tasks.add_task(store_result)
    
    return result

@router.get("/daemon/status")
async def get_daemon_status():
    """Get MCP health daemon status"""
    try:
        # Try to get daemon status from Redis
        r = await mcp_api._get_redis()
        status_data = await r.get('mcp_daemon_status')
        
        if status_data:
            return json.loads(status_data)
        else:
            return {
                "status": "unknown",
                "message": "Daemon status not available",
                "suggestion": "Check if MCP health daemon is running"
            }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to get daemon status: {str(e)}"
        }

@router.get("/metrics")
async def get_health_metrics():
    """Get health check metrics and statistics"""
    try:
        r = await mcp_api._get_redis()
        
        # Get metrics for each command
        commands = ['health-check', 'security-check', 'redis-health']
        metrics = {}
        
        for command in commands:
            # Get recent results
            results = await r.lrange(f'mcp_health_{command.replace("-", "_")}', 0, 99)
            
            total_checks = len(results)
            successful_checks = 0
            failed_checks = 0
            
            for result_json in results:
                try:
                    data = json.loads(result_json)
                    if data.get('result', {}).get('success', False):
                        successful_checks += 1
                    else:
                        failed_checks += 1
                except:
                    continue
            
            success_rate = (successful_checks / total_checks * 100) if total_checks > 0 else 0
            
            metrics[command] = {
                'total_checks': total_checks,
                'successful_checks': successful_checks,
                'failed_checks': failed_checks,
                'success_rate': round(success_rate, 2)
            }
        
        # Get alert count
        alert_count = await r.llen('health_alerts')
        
        return {
            'command_metrics': metrics,
            'total_alerts': alert_count,
            'timestamp': now_iso()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get metrics: {str(e)}")

# Health check endpoint for load balancers
@router.get("/healthz")
async def health_check():
    """Simple health check endpoint"""
    return {"status": "ok", "timestamp": now_iso()}