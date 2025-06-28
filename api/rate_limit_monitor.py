"""Rate limit monitoring and alerting system."""
import asyncio
import json
import time
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from collections import defaultdict

import redis.asyncio as redis
from fastapi import APIRouter, Query, Depends, HTTPException
from pydantic import BaseModel

from utils.redis_mixin import RedisConnectionMixin
from utils.logging_config import get_logger
from api.middleware.auth import get_current_user, verify_api_key
from auth.rbac_manager import Permission
from api.middleware.rbac import require_permission

logger = get_logger(__name__)

# Pydantic models for API responses
class RateLimitStats(BaseModel):
    total_requests: int
    blocked_requests: int
    violations_24h: int
    top_violators: List[Dict[str, Any]]
    endpoint_stats: Dict[str, Dict[str, int]]


class RateLimitViolation(BaseModel):
    client_id: str
    endpoint: str
    timestamp: datetime
    penalty_minutes: int
    violation_count: int
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None


class RateLimitAlert(BaseModel):
    alert_type: str
    severity: str
    message: str
    timestamp: datetime
    data: Dict[str, Any]


class RateLimitMonitor(RedisConnectionMixin):
    """Monitor rate limiting metrics and generate alerts."""
    
    def __init__(self, redis_url: Optional[str] = None):
        super().__init__(redis_url)
        
        # Alert thresholds
        self.alert_thresholds = {
            'violation_spike': {
                'threshold': 10,  # 10 violations in 5 minutes
                'window_minutes': 5,
                'severity': 'WARNING'
            },
            'block_rate_high': {
                'threshold': 0.2,  # 20% of requests blocked
                'window_minutes': 10,
                'severity': 'CRITICAL'
            },
            'endpoint_attack': {
                'threshold': 50,   # 50 violations on same endpoint
                'window_minutes': 15,
                'severity': 'CRITICAL'
            },
            'user_excessive_violations': {
                'threshold': 5,    # 5 violations by same user
                'window_minutes': 30,
                'severity': 'WARNING'
            }
        }
    
    async def get_rate_limit_stats(self, hours: int = 24) -> RateLimitStats:
        """Get comprehensive rate limiting statistics."""
        r = await self._get_redis()
        
        # Get violations from specified time period
        cutoff_time = time.time() - (hours * 3600)
        
        # Collect stats from various keys
        total_requests = 0
        blocked_requests = 0
        violations = []
        endpoint_stats = defaultdict(lambda: {'requests': 0, 'blocks': 0})
        
        # Get all rate limit metrics
        violation_keys = await r.keys('rate_limit_metrics:rate_limit_violation')
        blocked_keys = await r.keys('rate_limit_metrics:rate_limit_blocked_attempt')
        
        # Process violations
        for key in violation_keys:
            entries = await r.lrange(key, 0, -1)
            for entry in entries:
                try:
                    data = json.loads(entry.decode())
                    if data['timestamp'] >= cutoff_time:
                        violations.append(data)
                        endpoint = data['data']['endpoint']
                        endpoint_stats[endpoint]['blocks'] += 1
                        blocked_requests += 1
                except (json.JSONDecodeError, KeyError):
                    continue
        
        # Process blocked attempts
        for key in blocked_keys:
            entries = await r.lrange(key, 0, -1)
            for entry in entries:
                try:
                    data = json.loads(entry.decode())
                    if data['timestamp'] >= cutoff_time:
                        blocked_requests += 1
                except (json.JSONDecodeError, KeyError):
                    continue
        
        # Get request counts from window keys
        window_keys = await r.keys('rate_limit:*:window:*')
        for key in window_keys:
            try:
                count = await r.get(key)
                if count:
                    total_requests += int(count.decode())
            except (ValueError, AttributeError):
                continue
        
        # Find top violators
        violator_counts = defaultdict(int)
        for violation in violations:
            endpoint = violation['data']['endpoint']
            client_type = violation['data']['client_type']
            violator_counts[f"{endpoint}:{client_type}"] += 1
        
        top_violators = [
            {'identifier': k, 'violations': v}
            for k, v in sorted(violator_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        ]
        
        return RateLimitStats(
            total_requests=total_requests,
            blocked_requests=blocked_requests,
            violations_24h=len(violations),
            top_violators=top_violators,
            endpoint_stats=dict(endpoint_stats)
        )
    
    async def get_recent_violations(self, limit: int = 100) -> List[RateLimitViolation]:
        """Get recent rate limit violations."""
        r = await self._get_redis()
        
        violations = []
        
        # Get all client violation keys
        violation_keys = await r.keys('rate_limit:*:violations')
        
        for key in violation_keys:
            # Extract client ID from key
            client_id = key.decode().split(':')[2]
            
            # Get recent violations for this client
            recent = await r.zrevrange(key, 0, limit - 1, withscores=True)
            
            for violation_data, timestamp in recent:
                try:
                    data = json.loads(violation_data.decode())
                    violations.append(RateLimitViolation(
                        client_id=client_id,
                        endpoint=data['endpoint'],
                        timestamp=datetime.fromtimestamp(timestamp),
                        penalty_minutes=data['penalty_minutes'],
                        violation_count=1,  # Could be enhanced to track cumulative count
                        user_agent=data.get('user_agent'),
                        ip_address=data.get('ip')
                    ))
                except (json.JSONDecodeError, KeyError, ValueError):
                    continue
        
        # Sort by timestamp and limit
        violations.sort(key=lambda x: x.timestamp, reverse=True)
        return violations[:limit]
    
    async def check_alert_conditions(self) -> List[RateLimitAlert]:
        """Check for alert conditions and generate alerts."""
        alerts = []
        r = await self._get_redis()
        current_time = time.time()
        
        # Check violation spike
        spike_window = current_time - (self.alert_thresholds['violation_spike']['window_minutes'] * 60)
        violation_keys = await r.keys('rate_limit_metrics:rate_limit_violation')
        recent_violations = 0
        
        for key in violation_keys:
            entries = await r.lrange(key, 0, -1)
            for entry in entries:
                try:
                    data = json.loads(entry.decode())
                    if data['timestamp'] >= spike_window:
                        recent_violations += 1
                except (json.JSONDecodeError, KeyError):
                    continue
        
        if recent_violations >= self.alert_thresholds['violation_spike']['threshold']:
            alerts.append(RateLimitAlert(
                alert_type='violation_spike',
                severity=self.alert_thresholds['violation_spike']['severity'],
                message=f"Rate limit violation spike detected: {recent_violations} violations in {self.alert_thresholds['violation_spike']['window_minutes']} minutes",
                timestamp=datetime.fromtimestamp(current_time),
                data={'violation_count': recent_violations, 'window_minutes': self.alert_thresholds['violation_spike']['window_minutes']}
            ))
        
        # Check endpoint-specific attacks
        endpoint_violations = defaultdict(int)
        attack_window = current_time - (self.alert_thresholds['endpoint_attack']['window_minutes'] * 60)
        
        for key in violation_keys:
            entries = await r.lrange(key, 0, -1)
            for entry in entries:
                try:
                    data = json.loads(entry.decode())
                    if data['timestamp'] >= attack_window:
                        endpoint = data['data']['endpoint']
                        endpoint_violations[endpoint] += 1
                except (json.JSONDecodeError, KeyError):
                    continue
        
        for endpoint, count in endpoint_violations.items():
            if count >= self.alert_thresholds['endpoint_attack']['threshold']:
                alerts.append(RateLimitAlert(
                    alert_type='endpoint_attack',
                    severity=self.alert_thresholds['endpoint_attack']['severity'],
                    message=f"Potential attack on endpoint {endpoint}: {count} violations in {self.alert_thresholds['endpoint_attack']['window_minutes']} minutes",
                    timestamp=datetime.fromtimestamp(current_time),
                    data={'endpoint': endpoint, 'violation_count': count, 'window_minutes': self.alert_thresholds['endpoint_attack']['window_minutes']}
                ))
        
        return alerts
    
    async def get_client_stats(self, client_id: str) -> Dict[str, Any]:
        """Get detailed statistics for a specific client."""
        r = await self._get_redis()
        
        # Get violation history
        violation_key = f"rate_limit:{client_id}:violations"
        violations = await r.zrevrange(violation_key, 0, -1, withscores=True)
        
        violation_history = []
        for violation_data, timestamp in violations:
            try:
                data = json.loads(violation_data.decode())
                violation_history.append({
                    'endpoint': data['endpoint'],
                    'timestamp': datetime.fromtimestamp(timestamp).isoformat(),
                    'penalty_minutes': data['penalty_minutes'],
                    'user_agent': data.get('user_agent'),
                    'ip': data.get('ip')
                })
            except (json.JSONDecodeError, KeyError, ValueError):
                continue
        
        # Check if currently blocked
        block_key = f"{client_id}:blocked"
        block_until = await r.get(block_key)
        
        # Get current window usage
        current_time = int(time.time())
        minute_window = current_time // 60
        window_key = f"{client_id}:window:{minute_window}"
        current_usage = await r.get(window_key)
        
        return {
            'client_id': client_id,
            'currently_blocked': bool(block_until),
            'block_until': int(block_until.decode()) if block_until else None,
            'current_minute_usage': int(current_usage.decode()) if current_usage else 0,
            'total_violations': len(violation_history),
            'violations_24h': len([v for v in violation_history if 
                                 datetime.fromisoformat(v['timestamp']) > datetime.now() - timedelta(hours=24)]),
            'violation_history': violation_history
        }
    
    async def clear_client_violations(self, client_id: str) -> bool:
        """Clear violation history for a client (admin function)."""
        r = await self._get_redis()
        
        # Remove violation history
        violation_key = f"rate_limit:{client_id}:violations"
        await r.delete(violation_key)
        
        # Remove current block
        block_key = f"{client_id}:blocked"
        await r.delete(block_key)
        
        # Remove current window
        current_time = int(time.time())
        minute_window = current_time // 60
        window_key = f"{client_id}:window:{minute_window}"
        await r.delete(window_key)
        
        logger.info(f"Cleared rate limit violations for client: {client_id}")
        return True


# API routes for rate limit monitoring
router = APIRouter(prefix="/api/rate-limits", tags=["rate-limiting"])

# Global monitor instance
rate_limit_monitor = RateLimitMonitor()


@router.get("/stats", response_model=RateLimitStats)
@require_permission(Permission.SYSTEM_AUDIT)
async def get_rate_limit_stats(
    hours: int = Query(24, ge=1, le=168, description="Hours of data to analyze"),
    current_user: dict = Depends(get_current_user)
):
    """Get rate limiting statistics for the dashboard."""
    return await rate_limit_monitor.get_rate_limit_stats(hours)


@router.get("/violations", response_model=List[RateLimitViolation])
@require_permission(Permission.SYSTEM_AUDIT)
async def get_recent_violations(
    limit: int = Query(100, ge=1, le=500, description="Maximum violations to return"),
    current_user: dict = Depends(get_current_user)
):
    """Get recent rate limit violations."""
    return await rate_limit_monitor.get_recent_violations(limit)


@router.get("/alerts", response_model=List[RateLimitAlert])
@require_permission(Permission.SYSTEM_AUDIT)
async def get_rate_limit_alerts(
    current_user: dict = Depends(get_current_user)
):
    """Check for rate limit alert conditions."""
    return await rate_limit_monitor.check_alert_conditions()


@router.get("/client/{client_id}")
@require_permission(Permission.SYSTEM_AUDIT)
async def get_client_rate_limit_stats(
    client_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get detailed rate limit statistics for a specific client."""
    return await rate_limit_monitor.get_client_stats(client_id)


@router.delete("/client/{client_id}/violations")
@require_permission(Permission.SYSTEM_CONFIG)
async def clear_client_violations(
    client_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Clear rate limit violations for a client (admin only)."""
    success = await rate_limit_monitor.clear_client_violations(client_id)
    if success:
        return {"message": f"Cleared violations for client: {client_id}"}
    else:
        raise HTTPException(status_code=500, detail="Failed to clear violations")


@router.get("/config")
@require_permission(Permission.SYSTEM_CONFIG)
async def get_rate_limit_config(
    current_user: dict = Depends(get_current_user)
):
    """Get current rate limiting configuration."""
    from api.middleware.enhanced_rate_limiting import EnhancedRateLimiter
    
    # Create limiter instance to get configuration
    limiter = EnhancedRateLimiter()
    
    return {
        'role_limits': {
            role.value: asdict(config) 
            for role, config in limiter.role_limits.items()
        },
        'default_limit': asdict(limiter.default_limit),
        'endpoint_modifiers': limiter.endpoint_modifiers,
        'alert_thresholds': rate_limit_monitor.alert_thresholds
    }


# Background monitoring task
async def monitor_rate_limits():
    """Background task to monitor rate limits and send alerts."""
    while True:
        try:
            alerts = await rate_limit_monitor.check_alert_conditions()
            
            for alert in alerts:
                logger.warning(
                    f"Rate limit alert: {alert.alert_type} - {alert.message}"
                )
                
                # Here you could send alerts to external systems
                # (Slack, email, monitoring systems, etc.)
                
                # Store alert in Redis for dashboard
                r = await rate_limit_monitor._get_redis()
                alert_key = "rate_limit_alerts"
                alert_data = {
                    'alert': asdict(alert),
                    'timestamp': time.time()
                }
                await r.lpush(alert_key, json.dumps(alert_data, default=str))
                await r.ltrim(alert_key, 0, 99)  # Keep last 100 alerts
                await r.expire(alert_key, 86400)  # 24 hours
            
            # Check every 60 seconds
            await asyncio.sleep(60)
            
        except Exception as e:
            logger.error(f"Error in rate limit monitoring: {e}")
            await asyncio.sleep(60)


def start_rate_limit_monitoring():
    """Start the background rate limit monitoring task."""
    asyncio.create_task(monitor_rate_limits())