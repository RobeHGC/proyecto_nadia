# monitoring/recovery_health_check.py
"""Health check system for Recovery Agent monitoring."""
import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List

from database.models import DatabaseManager
from utils.recovery_config import get_recovery_config

logger = logging.getLogger(__name__)


class RecoveryHealthChecker:
    """Health monitoring system for Recovery Agent."""
    
    def __init__(self, database_manager: DatabaseManager):
        """Initialize health checker."""
        self.db = database_manager
        self.config = get_recovery_config()
        
        # Health thresholds
        self.max_operation_duration_minutes = 30
        self.max_errors_threshold = 5
        self.stale_cursor_threshold_hours = 24
        
    async def perform_health_check(self) -> Dict[str, Any]:
        """Perform comprehensive health check of Recovery Agent."""
        logger.info("🏥 Starting Recovery Agent health check...")
        
        health_report = {
            "timestamp": datetime.now().isoformat(),
            "overall_status": "healthy",
            "checks": {},
            "alerts": [],
            "metrics": {},
            "recommendations": []
        }
        
        try:
            # Check 1: Configuration validation
            await self._check_configuration(health_report)
            
            # Check 2: Database connectivity and schema
            await self._check_database_health(health_report)
            
            # Check 3: Recent operations analysis
            await self._check_recent_operations(health_report)
            
            # Check 4: Cursor freshness
            await self._check_cursor_freshness(health_report)
            
            # Check 5: Error rate analysis
            await self._check_error_rates(health_report)
            
            # Check 6: Performance metrics
            await self._check_performance_metrics(health_report)
            
            # Determine overall status
            health_report["overall_status"] = self._determine_overall_status(health_report)
            
            logger.info(f"✅ Health check completed: {health_report['overall_status']}")
            return health_report
            
        except Exception as e:
            logger.error(f"❌ Health check failed: {e}")
            health_report["overall_status"] = "critical"
            health_report["alerts"].append({
                "level": "critical",
                "message": f"Health check system failure: {str(e)}",
                "timestamp": datetime.now().isoformat()
            })
            return health_report
    
    async def _check_configuration(self, report: Dict[str, Any]):
        """Check Recovery Agent configuration."""
        try:
            validation_errors = self.config.validate()
            
            if validation_errors:
                report["checks"]["configuration"] = {
                    "status": "warning",
                    "errors": validation_errors,
                    "message": f"Configuration has {len(validation_errors)} validation errors"
                }
                report["alerts"].append({
                    "level": "warning",
                    "message": f"Configuration validation errors: {', '.join(validation_errors)}",
                    "timestamp": datetime.now().isoformat()
                })
            else:
                report["checks"]["configuration"] = {
                    "status": "healthy",
                    "message": "Configuration validated successfully"
                }
                
            # Check if recovery is enabled
            if not self.config.enabled:
                report["alerts"].append({
                    "level": "info",
                    "message": "Recovery Agent is disabled in configuration",
                    "timestamp": datetime.now().isoformat()
                })
                
        except Exception as e:
            report["checks"]["configuration"] = {
                "status": "error",
                "message": f"Configuration check failed: {str(e)}"
            }
    
    async def _check_database_health(self, report: Dict[str, Any]):
        """Check database connectivity and recovery tables."""
        try:
            # Test basic connectivity
            await self.db.get_recovery_stats()
            
            # Check if recovery tables exist and are accessible
            cursors = await self.db.get_all_user_cursors()
            operations = await self.db.get_recovery_operations(limit=1)
            
            report["checks"]["database"] = {
                "status": "healthy",
                "cursor_count": len(cursors),
                "operations_accessible": len(operations) >= 0,
                "message": "Database connectivity and schema verified"
            }
            
            report["metrics"]["total_tracked_users"] = len(cursors)
            
        except Exception as e:
            report["checks"]["database"] = {
                "status": "critical",
                "message": f"Database check failed: {str(e)}"
            }
            report["alerts"].append({
                "level": "critical",
                "message": f"Database connectivity issue: {str(e)}",
                "timestamp": datetime.now().isoformat()
            })
    
    async def _check_recent_operations(self, report: Dict[str, Any]):
        """Analyze recent recovery operations."""
        try:
            # Get operations from last 24 hours
            operations = await self.db.get_recovery_operations(limit=50)
            recent_ops = [
                op for op in operations 
                if self._is_recent(op.get("started_at"), hours=24)
            ]
            
            if not recent_ops:
                report["checks"]["recent_operations"] = {
                    "status": "warning",
                    "message": "No recovery operations in last 24 hours"
                }
                report["alerts"].append({
                    "level": "info",
                    "message": "No recovery operations detected in last 24 hours",
                    "timestamp": datetime.now().isoformat()
                })
                return
            
            # Analyze operation success rate
            completed_ops = [op for op in recent_ops if op.get("status") == "completed"]
            failed_ops = [op for op in recent_ops if op.get("status") == "failed"]
            
            success_rate = len(completed_ops) / len(recent_ops) if recent_ops else 0
            
            # Check for long-running operations
            long_running = []
            for op in recent_ops:
                if op.get("status") == "running":
                    duration = self._calculate_duration_minutes(op.get("started_at"))
                    if duration > self.max_operation_duration_minutes:
                        long_running.append(op)
            
            status = "healthy"
            messages = []
            
            if success_rate < 0.8:
                status = "warning"
                messages.append(f"Low success rate: {success_rate:.1%}")
            
            if long_running:
                status = "warning"
                messages.append(f"{len(long_running)} long-running operations detected")
            
            if failed_ops:
                messages.append(f"{len(failed_ops)} failed operations in 24h")
            
            report["checks"]["recent_operations"] = {
                "status": status,
                "total_operations": len(recent_ops),
                "success_rate": success_rate,
                "failed_operations": len(failed_ops),
                "long_running_operations": len(long_running),
                "message": "; ".join(messages) if messages else "Recent operations look healthy"
            }
            
            report["metrics"]["operations_24h"] = len(recent_ops)
            report["metrics"]["success_rate"] = success_rate
            
        except Exception as e:
            report["checks"]["recent_operations"] = {
                "status": "error",
                "message": f"Operations analysis failed: {str(e)}"
            }
    
    async def _check_cursor_freshness(self, report: Dict[str, Any]):
        """Check if user cursors are being updated regularly."""
        try:
            cursors = await self.db.get_all_user_cursors()
            
            if not cursors:
                report["checks"]["cursor_freshness"] = {
                    "status": "info",
                    "message": "No user cursors found"
                }
                return
            
            stale_cursors = []
            for cursor in cursors:
                last_check = cursor.get("last_recovery_check")
                if last_check:
                    hours_since = self._hours_since(last_check)
                    if hours_since > self.stale_cursor_threshold_hours:
                        stale_cursors.append({
                            "user_id": cursor["user_id"],
                            "hours_since_check": hours_since
                        })
            
            status = "healthy"
            message = f"All {len(cursors)} cursors are fresh"
            
            if stale_cursors:
                if len(stale_cursors) > len(cursors) * 0.5:  # More than 50% stale
                    status = "warning"
                else:
                    status = "info"
                message = f"{len(stale_cursors)} of {len(cursors)} cursors are stale (>{self.stale_cursor_threshold_hours}h)"
            
            report["checks"]["cursor_freshness"] = {
                "status": status,
                "total_cursors": len(cursors),
                "stale_cursors": len(stale_cursors),
                "message": message
            }
            
            if stale_cursors and len(stale_cursors) <= 5:  # Show details for small numbers
                report["checks"]["cursor_freshness"]["stale_details"] = stale_cursors
            
        except Exception as e:
            report["checks"]["cursor_freshness"] = {
                "status": "error",
                "message": f"Cursor freshness check failed: {str(e)}"
            }
    
    async def _check_error_rates(self, report: Dict[str, Any]):
        """Check error rates in recent operations."""
        try:
            operations = await self.db.get_recovery_operations(limit=20)
            recent_ops = [
                op for op in operations 
                if self._is_recent(op.get("started_at"), hours=6)
            ]
            
            if not recent_ops:
                report["checks"]["error_rates"] = {
                    "status": "info",
                    "message": "No recent operations to analyze"
                }
                return
            
            total_errors = sum(op.get("errors_encountered", 0) for op in recent_ops)
            total_messages = sum(op.get("messages_recovered", 0) + op.get("messages_skipped", 0) for op in recent_ops)
            
            error_rate = total_errors / max(total_messages, 1)
            
            status = "healthy"
            if error_rate > 0.1:  # >10% error rate
                status = "warning"
            elif error_rate > 0.05:  # >5% error rate
                status = "info"
            
            report["checks"]["error_rates"] = {
                "status": status,
                "total_errors": total_errors,
                "total_messages": total_messages,
                "error_rate": error_rate,
                "message": f"Error rate: {error_rate:.1%} ({total_errors} errors / {total_messages} messages)"
            }
            
            report["metrics"]["error_rate_6h"] = error_rate
            
        except Exception as e:
            report["checks"]["error_rates"] = {
                "status": "error",
                "message": f"Error rate analysis failed: {str(e)}"
            }
    
    async def _check_performance_metrics(self, report: Dict[str, Any]):
        """Check performance metrics and efficiency."""
        try:
            stats = await self.db.get_recovery_stats()
            
            total_recovered = stats.get("total_recovered_messages", 0)
            recent_ops = stats.get("recent_operations", {})
            
            # Calculate efficiency metrics
            completed_today = recent_ops.get("completed", 0)
            failed_today = recent_ops.get("failed", 0)
            
            report["checks"]["performance"] = {
                "status": "healthy",
                "total_recovered_all_time": total_recovered,
                "operations_completed_today": completed_today,
                "operations_failed_today": failed_today,
                "message": f"Total recovered: {total_recovered} messages"
            }
            
            report["metrics"]["total_recovered_messages"] = total_recovered
            
            # Add recommendations based on performance
            if total_recovered == 0:
                report["recommendations"].append(
                    "No messages recovered yet. Consider testing recovery functionality."
                )
            elif failed_today > completed_today:
                report["recommendations"].append(
                    "More operations failing than completing today. Check error logs."
                )
            
        except Exception as e:
            report["checks"]["performance"] = {
                "status": "error",
                "message": f"Performance check failed: {str(e)}"
            }
    
    def _determine_overall_status(self, report: Dict[str, Any]) -> str:
        """Determine overall system health status."""
        checks = report.get("checks", {})
        
        # Count status types
        critical_count = sum(1 for check in checks.values() if check.get("status") == "critical")
        error_count = sum(1 for check in checks.values() if check.get("status") == "error")
        warning_count = sum(1 for check in checks.values() if check.get("status") == "warning")
        
        if critical_count > 0:
            return "critical"
        elif error_count > 0:
            return "error"
        elif warning_count > 2:  # Multiple warnings = degraded
            return "degraded"
        elif warning_count > 0:
            return "warning"
        else:
            return "healthy"
    
    def _is_recent(self, timestamp_str: str, hours: int = 24) -> bool:
        """Check if timestamp is within the specified hours."""
        if not timestamp_str:
            return False
        
        try:
            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            cutoff = datetime.now() - timedelta(hours=hours)
            return timestamp > cutoff
        except Exception:
            return False
    
    def _hours_since(self, timestamp_str: str) -> float:
        """Calculate hours since timestamp."""
        try:
            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            delta = datetime.now() - timestamp
            return delta.total_seconds() / 3600
        except Exception:
            return float('inf')
    
    def _calculate_duration_minutes(self, started_at: str) -> float:
        """Calculate operation duration in minutes."""
        try:
            start_time = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
            delta = datetime.now() - start_time
            return delta.total_seconds() / 60
        except Exception:
            return 0.0


# Standalone health check function
async def run_recovery_health_check() -> Dict[str, Any]:
    """Run standalone recovery health check."""
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        return {
            "overall_status": "critical",
            "error": "DATABASE_URL not configured",
            "timestamp": datetime.now().isoformat()
        }
    
    db = DatabaseManager(database_url)
    try:
        await db.initialize()
        health_checker = RecoveryHealthChecker(db)
        result = await health_checker.perform_health_check()
        await db.close()
        return result
    except Exception as e:
        await db.close()
        return {
            "overall_status": "critical",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


if __name__ == "__main__":
    # Allow running as standalone script
    import asyncio
    import json
    
    async def main():
        result = await run_recovery_health_check()
        print(json.dumps(result, indent=2, default=str))
    
    asyncio.run(main())