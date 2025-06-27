#!/usr/bin/env python3
"""
MCP Health Check Daemon
Automated monitoring using Health MCP server with scheduling and alerting
"""

import asyncio
import json
import logging
import os
import sys
import time
import signal
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
import subprocess

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from utils.logging_config import setup_logging
from utils.redis_mixin import RedisConnectionMixin
from utils.datetime_helpers import now_iso, time_ago_text
from utils.constants import HEALTH_CHECK_INTERVAL, ALERT_THRESHOLD_HIGH, ALERT_THRESHOLD_CRITICAL
from monitoring.mcp_alert_manager import MCPAlertManager

class MCPHealthDaemon(RedisConnectionMixin):
    """Automated MCP health monitoring daemon"""
    
    def __init__(self, config_path: str = "monitoring/health_config.json"):
        self.config_path = config_path
        self.config = self._load_config()
        self.running = False
        self.logger = setup_logging("mcp_health_daemon")
        
        # Health check history
        self.health_history: List[Dict] = []
        self.max_history = 100
        
        # Alert state tracking
        self.alert_states: Dict[str, Dict] = {}
        
        # Initialize alert manager
        self.alert_manager = MCPAlertManager()
        
        # Performance metrics
        self.metrics = {
            'checks_run': 0,
            'alerts_sent': 0,
            'failures': 0,
            'uptime_start': now_iso()
        }
        
    def _load_config(self) -> Dict[str, Any]:
        """Load daemon configuration"""
        default_config = {
            "schedules": {
                "health_check": {"interval": 300, "enabled": True},  # 5 minutes
                "security_scan": {"interval": 14400, "enabled": True},  # 4 hours
                "performance_baseline": {"interval": 43200, "enabled": True},  # 12 hours
                "redis_health": {"interval": 600, "enabled": True}  # 10 minutes
            },
            "alerts": {
                "webhooks": [],
                "email": {"enabled": False},
                "slack": {"enabled": False, "webhook_url": ""},
                "thresholds": {
                    "consecutive_failures": 3,
                    "cpu_threshold": 80,
                    "memory_threshold": 85,
                    "queue_threshold": 1000
                }
            },
            "retention": {
                "health_logs_days": 30,
                "metrics_days": 90
            }
        }
        
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                # Merge with defaults
                for key, value in default_config.items():
                    if key not in config:
                        config[key] = value
                return config
            else:
                return default_config
        except Exception as e:
            print(f"Error loading config: {e}")
            return default_config
    
    def _save_config(self):
        """Save current configuration"""
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save config: {e}")
    
    async def _run_mcp_command(self, command: str) -> Dict[str, Any]:
        """Execute MCP workflow command and return results"""
        try:
            script_path = Path(__file__).parent.parent / "scripts" / "mcp-workflow.sh"
            
            process = await asyncio.create_subprocess_exec(
                str(script_path), command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            result = {
                'command': command,
                'timestamp': now_iso(),
                'exit_code': process.returncode,
                'stdout': stdout.decode('utf-8', errors='ignore'),
                'stderr': stderr.decode('utf-8', errors='ignore'),
                'success': process.returncode == 0
            }
            
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to run MCP command {command}: {e}")
            return {
                'command': command,
                'timestamp': now_iso(),
                'exit_code': -1,
                'stdout': '',
                'stderr': str(e),
                'success': False
            }
    
    async def _analyze_health_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze health check result and determine status"""
        analysis = {
            'status': 'HEALTHY',
            'issues': [],
            'metrics': {},
            'alerts': []
        }
        
        if not result['success']:
            analysis['status'] = 'CRITICAL'
            analysis['issues'].append(f"Command failed: {result['stderr']}")
            return analysis
        
        output = result['stdout'].lower()
        
        # Check for critical issues
        critical_keywords = ['error', 'failed', 'critical', 'down', 'unavailable']
        warning_keywords = ['warning', 'slow', 'degraded', 'high usage']
        
        for keyword in critical_keywords:
            if keyword in output:
                analysis['status'] = 'CRITICAL'
                analysis['issues'].append(f"Critical issue detected: {keyword}")
        
        if analysis['status'] != 'CRITICAL':
            for keyword in warning_keywords:
                if keyword in output:
                    analysis['status'] = 'WARNING'
                    analysis['issues'].append(f"Warning detected: {keyword}")
        
        # Extract metrics if available
        lines = result['stdout'].split('\n')
        for line in lines:
            if 'cpu:' in line.lower():
                try:
                    cpu_val = float(line.split(':')[1].strip().rstrip('%'))
                    analysis['metrics']['cpu_usage'] = cpu_val
                    if cpu_val > self.config['alerts']['thresholds']['cpu_threshold']:
                        analysis['alerts'].append(f"High CPU usage: {cpu_val}%")
                except:
                    pass
                    
            if 'memory:' in line.lower():
                try:
                    mem_val = float(line.split(':')[1].strip().rstrip('%'))
                    analysis['metrics']['memory_usage'] = mem_val
                    if mem_val > self.config['alerts']['thresholds']['memory_threshold']:
                        analysis['alerts'].append(f"High memory usage: {mem_val}%")
                except:
                    pass
        
        return analysis
    
    async def _send_alert(self, alert_type: str, message: str, severity: str = "WARNING"):
        """Send alert notification"""
        try:
            alert_data = {
                'timestamp': now_iso(),
                'type': alert_type,
                'severity': severity,
                'message': message,
                'daemon': 'mcp_health_daemon'
            }
            
            # Store alert in Redis
            r = await self._get_redis()
            await r.lpush('health_alerts', json.dumps(alert_data))
            await r.ltrim('health_alerts', 0, 99)  # Keep last 100 alerts
            
            # Log alert
            log_func = self.logger.critical if severity == "CRITICAL" else self.logger.warning
            log_func(f"ALERT [{severity}] {alert_type}: {message}")
            
            # Send through alert manager
            success = await self.alert_manager.process_alert(alert_data)
            if success:
                self.metrics['alerts_sent'] += 1
            
        except Exception as e:
            self.logger.error(f"Failed to send alert: {e}")
    
    async def _check_alert_conditions(self, command: str, result: Dict, analysis: Dict):
        """Check if alert conditions are met"""
        alert_key = f"{command}_failures"
        
        if not result['success'] or analysis['status'] == 'CRITICAL':
            # Track consecutive failures
            if alert_key not in self.alert_states:
                self.alert_states[alert_key] = {'count': 0, 'first_failure': now_iso()}
            
            self.alert_states[alert_key]['count'] += 1
            
            threshold = self.config['alerts']['thresholds']['consecutive_failures']
            if self.alert_states[alert_key]['count'] >= threshold:
                await self._send_alert(
                    f"{command}_failure",
                    f"MCP {command} has failed {self.alert_states[alert_key]['count']} consecutive times",
                    "CRITICAL"
                )
        else:
            # Reset failure count on success
            if alert_key in self.alert_states:
                if self.alert_states[alert_key]['count'] > 0:
                    self.logger.info(f"MCP {command} recovered after {self.alert_states[alert_key]['count']} failures")
                del self.alert_states[alert_key]
        
        # Check for specific alert conditions
        for alert in analysis.get('alerts', []):
            await self._send_alert(f"{command}_threshold", alert, "WARNING")
        
        # Check threshold violations using alert manager
        if 'cpu_usage' in analysis.get('metrics', {}):
            cpu_usage = analysis['metrics']['cpu_usage']
            threshold = self.alert_manager.config.get('thresholds', {}).get('cpu_threshold', 80)
            if cpu_usage > threshold:
                alert = await self.alert_manager.create_threshold_alert(
                    'cpu_usage', cpu_usage, threshold, 'WARNING' if cpu_usage < threshold * 1.2 else 'CRITICAL'
                )
                await self.alert_manager.process_alert(alert)
        
        if 'memory_usage' in analysis.get('metrics', {}):
            memory_usage = analysis['metrics']['memory_usage']
            threshold = self.alert_manager.config.get('thresholds', {}).get('memory_threshold', 85)
            if memory_usage > threshold:
                alert = await self.alert_manager.create_threshold_alert(
                    'memory_usage', memory_usage, threshold, 'WARNING' if memory_usage < threshold * 1.2 else 'CRITICAL'
                )
                await self.alert_manager.process_alert(alert)
    
    async def _run_scheduled_check(self, command: str):
        """Run a scheduled health check"""
        try:
            self.logger.info(f"Running scheduled MCP check: {command}")
            
            result = await self._run_mcp_command(command)
            analysis = await self._analyze_health_result(result)
            
            # Store result
            health_record = {
                'timestamp': now_iso(),
                'command': command,
                'result': result,
                'analysis': analysis
            }
            
            self.health_history.append(health_record)
            if len(self.health_history) > self.max_history:
                self.health_history.pop(0)
            
            # Store in Redis
            r = await self._get_redis()
            await r.lpush(f'mcp_health_{command}', json.dumps(health_record))
            await r.ltrim(f'mcp_health_{command}', 0, 49)  # Keep last 50 results
            
            # Check alert conditions
            await self._check_alert_conditions(command, result, analysis)
            
            self.metrics['checks_run'] += 1
            
            if not result['success']:
                self.metrics['failures'] += 1
            
            self.logger.info(f"MCP check {command} completed: {analysis['status']}")
            
        except Exception as e:
            self.logger.error(f"Error in scheduled check {command}: {e}")
            self.metrics['failures'] += 1
    
    async def _cleanup_old_data(self):
        """Clean up old health data"""
        try:
            r = await self._get_redis()
            
            # Clean up old alerts
            alerts = await r.lrange('health_alerts', 0, -1)
            cutoff_time = datetime.now() - timedelta(days=self.config['retention']['health_logs_days'])
            
            valid_alerts = []
            for alert_json in alerts:
                try:
                    alert = json.loads(alert_json)
                    alert_time = datetime.fromisoformat(alert['timestamp'].replace('Z', '+00:00'))
                    if alert_time > cutoff_time:
                        valid_alerts.append(alert_json)
                except:
                    continue
            
            if len(valid_alerts) < len(alerts):
                await r.delete('health_alerts')
                for alert in valid_alerts:
                    await r.lpush('health_alerts', alert)
                self.logger.info(f"Cleaned up {len(alerts) - len(valid_alerts)} old alerts")
                
        except Exception as e:
            self.logger.error(f"Error cleaning up old data: {e}")
    
    async def get_status(self) -> Dict[str, Any]:
        """Get daemon status"""
        return {
            'running': self.running,
            'uptime': time_ago_text(self.metrics['uptime_start']),
            'metrics': self.metrics.copy(),
            'active_alerts': len(self.alert_states),
            'last_health_check': self.health_history[-1]['timestamp'] if self.health_history else None,
            'health_status': self.health_history[-1]['analysis']['status'] if self.health_history else 'UNKNOWN'
        }
    
    async def start(self):
        """Start the health check daemon"""
        self.logger.info("Starting MCP Health Daemon")
        self.running = True
        
        # Initialize last run times
        last_runs = {}
        for command in self.config['schedules']:
            last_runs[command] = 0
        
        try:
            while self.running:
                current_time = time.time()
                
                # Check each scheduled command
                for command, schedule in self.config['schedules'].items():
                    if not schedule.get('enabled', True):
                        continue
                    
                    interval = schedule['interval']
                    if current_time - last_runs[command] >= interval:
                        await self._run_scheduled_check(command.replace('_', '-'))
                        last_runs[command] = current_time
                
                # Cleanup old data every hour
                if current_time % 3600 < 60:  # Rough hourly check
                    await self._cleanup_old_data()
                
                # Sleep for 1 minute between cycles
                await asyncio.sleep(60)
                
        except Exception as e:
            self.logger.error(f"Daemon error: {e}")
        finally:
            self.running = False
            self.logger.info("MCP Health Daemon stopped")
    
    def stop(self):
        """Stop the daemon"""
        self.logger.info("Stopping MCP Health Daemon")
        self.running = False


async def main():
    """Main function"""
    daemon = MCPHealthDaemon()
    
    # Signal handlers
    def signal_handler(signum, frame):
        print(f"\nReceived signal {signum}, stopping daemon...")
        daemon.stop()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start daemon
    await daemon.start()


if __name__ == "__main__":
    asyncio.run(main())