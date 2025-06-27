#!/usr/bin/env python3
"""
MCP Alert Manager
Handles alerting for MCP health check failures and threshold violations
"""

import asyncio
import json
import logging
import os
import smtplib
import sys
from datetime import datetime, timedelta
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart
from pathlib import Path
from typing import Dict, List, Optional, Any
import aiohttp
import subprocess

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from utils.logging_config import setup_logging
from utils.redis_mixin import RedisConnectionMixin
from utils.datetime_helpers import now_iso, time_ago_text
from utils.constants import ALERT_THRESHOLD_HIGH, ALERT_THRESHOLD_CRITICAL

class AlertChannel:
    """Base class for alert channels"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.enabled = config.get('enabled', False)
        self.logger = setup_logging(f"alert_channel_{self.__class__.__name__.lower()}")
    
    async def send_alert(self, alert: Dict[str, Any]) -> bool:
        """Send alert through this channel. Returns True if successful."""
        raise NotImplementedError

class SlackAlertChannel(AlertChannel):
    """Slack webhook alert channel"""
    
    async def send_alert(self, alert: Dict[str, Any]) -> bool:
        if not self.enabled or not self.config.get('webhook_url'):
            return False
        
        try:
            color_map = {
                'CRITICAL': '#DC3545',
                'WARNING': '#FFC107',
                'INFO': '#17A2B8'
            }
            
            color = color_map.get(alert['severity'], '#6C757D')
            
            payload = {
                "username": "MCP Health Monitor",
                "icon_emoji": ":warning:",
                "attachments": [{
                    "color": color,
                    "title": f"🚨 MCP Alert - {alert['severity']}",
                    "text": alert['message'],
                    "fields": [
                        {
                            "title": "Type",
                            "value": alert['type'],
                            "short": True
                        },
                        {
                            "title": "Time",
                            "value": alert['timestamp'],
                            "short": True
                        }
                    ],
                    "footer": "NADIA MCP Monitoring",
                    "ts": int(datetime.fromisoformat(alert['timestamp'].replace('Z', '+00:00')).timestamp())
                }]
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.config['webhook_url'],
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        self.logger.info(f"Slack alert sent successfully: {alert['type']}")
                        return True
                    else:
                        self.logger.error(f"Slack alert failed: HTTP {response.status}")
                        return False
                        
        except Exception as e:
            self.logger.error(f"Failed to send Slack alert: {e}")
            return False

class DiscordAlertChannel(AlertChannel):
    """Discord webhook alert channel"""
    
    async def send_alert(self, alert: Dict[str, Any]) -> bool:
        if not self.enabled or not self.config.get('webhook_url'):
            return False
        
        try:
            color_map = {
                'CRITICAL': 0xDC3545,
                'WARNING': 0xFFC107,
                'INFO': 0x17A2B8
            }
            
            color = color_map.get(alert['severity'], 0x6C757D)
            
            payload = {
                "username": "MCP Health Monitor",
                "avatar_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/26a0.png",
                "embeds": [{
                    "title": f"🚨 MCP Alert - {alert['severity']}",
                    "description": alert['message'],
                    "color": color,
                    "fields": [
                        {
                            "name": "Type",
                            "value": alert['type'],
                            "inline": True
                        },
                        {
                            "name": "Time",
                            "value": alert['timestamp'],
                            "inline": True
                        }
                    ],
                    "footer": {
                        "text": "NADIA MCP Monitoring"
                    },
                    "timestamp": alert['timestamp']
                }]
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.config['webhook_url'],
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status in [200, 204]:
                        self.logger.info(f"Discord alert sent successfully: {alert['type']}")
                        return True
                    else:
                        self.logger.error(f"Discord alert failed: HTTP {response.status}")
                        return False
                        
        except Exception as e:
            self.logger.error(f"Failed to send Discord alert: {e}")
            return False

class EmailAlertChannel(AlertChannel):
    """Email alert channel"""
    
    async def send_alert(self, alert: Dict[str, Any]) -> bool:
        if not self.enabled:
            return False
        
        try:
            # Run email sending in thread to avoid blocking
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._send_email_sync, alert)
        except Exception as e:
            self.logger.error(f"Failed to send email alert: {e}")
            return False
    
    def _send_email_sync(self, alert: Dict[str, Any]) -> bool:
        """Synchronous email sending"""
        try:
            smtp_server = self.config.get('smtp_server', 'localhost')
            smtp_port = self.config.get('smtp_port', 587)
            username = self.config.get('username')
            password = self.config.get('password')
            from_email = self.config.get('from_email', username)
            to_emails = self.config.get('to_emails', [])
            
            if not to_emails:
                self.logger.warning("No recipient emails configured")
                return False
            
            # Create message
            msg = MimeMultipart()
            msg['From'] = from_email
            msg['To'] = ', '.join(to_emails)
            msg['Subject'] = f"MCP Alert - {alert['severity']}: {alert['type']}"
            
            # Create HTML body
            html_body = f"""
            <html>
            <body>
                <h2 style="color: {'#DC3545' if alert['severity'] == 'CRITICAL' else '#FFC107'};">
                    🚨 MCP Health Alert - {alert['severity']}
                </h2>
                <p><strong>Type:</strong> {alert['type']}</p>
                <p><strong>Time:</strong> {alert['timestamp']}</p>
                <p><strong>Message:</strong></p>
                <div style="background: #f8f9fa; padding: 10px; border-left: 4px solid #007bff;">
                    {alert['message']}
                </div>
                <hr>
                <p style="color: #666; font-size: 12px;">
                    NADIA MCP Monitoring System<br>
                    Generated at {alert['timestamp']}
                </p>
            </body>
            </html>
            """
            
            msg.attach(MimeText(html_body, 'html'))
            
            # Send email
            server = smtplib.SMTP(smtp_server, smtp_port)
            if username and password:
                server.starttls()
                server.login(username, password)
            
            server.send_message(msg)
            server.quit()
            
            self.logger.info(f"Email alert sent successfully: {alert['type']}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send email: {e}")
            return False

class WebhookAlertChannel(AlertChannel):
    """Generic webhook alert channel"""
    
    async def send_alert(self, alert: Dict[str, Any]) -> bool:
        if not self.enabled or not self.config.get('url'):
            return False
        
        try:
            headers = self.config.get('headers', {})
            headers.setdefault('Content-Type', 'application/json')
            
            # Add authentication if configured
            if self.config.get('auth_header') and self.config.get('auth_token'):
                headers[self.config['auth_header']] = self.config['auth_token']
            
            payload = {
                'alert': alert,
                'source': 'nadia_mcp_monitor',
                'timestamp': alert['timestamp']
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.config['url'],
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if 200 <= response.status < 300:
                        self.logger.info(f"Webhook alert sent successfully: {alert['type']}")
                        return True
                    else:
                        self.logger.error(f"Webhook alert failed: HTTP {response.status}")
                        return False
                        
        except Exception as e:
            self.logger.error(f"Failed to send webhook alert: {e}")
            return False

class SystemCommandChannel(AlertChannel):
    """Execute system command on alert"""
    
    async def send_alert(self, alert: Dict[str, Any]) -> bool:
        if not self.enabled or not self.config.get('command'):
            return False
        
        try:
            command = self.config['command']
            
            # Replace placeholders in command
            command = command.replace('{severity}', alert['severity'])
            command = command.replace('{type}', alert['type'])
            command = command.replace('{message}', alert['message'])
            command = command.replace('{timestamp}', alert['timestamp'])
            
            # Execute command
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                self.logger.info(f"System command executed successfully: {command}")
                return True
            else:
                self.logger.error(f"System command failed: {command}, error: {stderr.decode()}")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to execute system command: {e}")
            return False

class MCPAlertManager(RedisConnectionMixin):
    """Main MCP alert manager"""
    
    def __init__(self, config_path: str = "monitoring/alert_config.json"):
        self.config_path = config_path
        self.config = self._load_config()
        self.logger = setup_logging("mcp_alert_manager")
        
        # Initialize alert channels
        self.channels = {}
        self._init_channels()
        
        # Alert state tracking
        self.alert_states = {}
        self.sent_alerts = {}  # Track sent alerts to avoid spam
        
    def _load_config(self) -> Dict[str, Any]:
        """Load alert configuration"""
        default_config = {
            "global": {
                "alert_cooldown_minutes": 30,
                "max_alerts_per_hour": 10,
                "enable_alert_grouping": True
            },
            "channels": {
                "slack": {
                    "enabled": False,
                    "webhook_url": "",
                    "severity_filter": ["CRITICAL", "WARNING"]
                },
                "discord": {
                    "enabled": False,
                    "webhook_url": "",
                    "severity_filter": ["CRITICAL", "WARNING"]
                },
                "email": {
                    "enabled": False,
                    "smtp_server": "smtp.gmail.com",
                    "smtp_port": 587,
                    "username": "",
                    "password": "",
                    "from_email": "",
                    "to_emails": [],
                    "severity_filter": ["CRITICAL"]
                },
                "webhook": {
                    "enabled": False,
                    "url": "",
                    "headers": {},
                    "auth_header": "",
                    "auth_token": "",
                    "severity_filter": ["CRITICAL", "WARNING"]
                },
                "system_command": {
                    "enabled": False,
                    "command": "echo 'MCP Alert: {severity} - {type}' >> /var/log/mcp-alerts.log",
                    "severity_filter": ["CRITICAL"]
                }
            },
            "thresholds": {
                "consecutive_failures": 3,
                "cpu_threshold": 80,
                "memory_threshold": 85,
                "queue_threshold": 1000,
                "disk_threshold": 90,
                "response_time_threshold": 5000
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
                    elif isinstance(value, dict) and key in config:
                        for subkey, subvalue in value.items():
                            if subkey not in config[key]:
                                config[key][subkey] = subvalue
                return config
            else:
                return default_config
        except Exception as e:
            self.logger.error(f"Error loading alert config: {e}")
            return default_config
    
    def _save_config(self):
        """Save current configuration"""
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save alert config: {e}")
    
    def _init_channels(self):
        """Initialize alert channels"""
        channel_classes = {
            'slack': SlackAlertChannel,
            'discord': DiscordAlertChannel,
            'email': EmailAlertChannel,
            'webhook': WebhookAlertChannel,
            'system_command': SystemCommandChannel
        }
        
        for channel_name, channel_config in self.config.get('channels', {}).items():
            if channel_name in channel_classes:
                try:
                    self.channels[channel_name] = channel_classes[channel_name](channel_config)
                    if channel_config.get('enabled', False):
                        self.logger.info(f"Initialized alert channel: {channel_name}")
                except Exception as e:
                    self.logger.error(f"Failed to initialize channel {channel_name}: {e}")
    
    async def process_alert(self, alert: Dict[str, Any]) -> bool:
        """Process and send alert through configured channels"""
        try:
            # Check if we should send this alert
            if not await self._should_send_alert(alert):
                return False
            
            # Store alert in Redis
            await self._store_alert(alert)
            
            # Send through all enabled channels
            sent_count = 0
            total_channels = 0
            
            for channel_name, channel in self.channels.items():
                if not channel.enabled:
                    continue
                
                # Check severity filter
                severity_filter = channel.config.get('severity_filter', ['CRITICAL', 'WARNING'])
                if alert['severity'] not in severity_filter:
                    continue
                
                total_channels += 1
                try:
                    if await channel.send_alert(alert):
                        sent_count += 1
                except Exception as e:
                    self.logger.error(f"Channel {channel_name} failed: {e}")
            
            # Update sent alerts tracking
            self._track_sent_alert(alert)
            
            success = sent_count > 0
            self.logger.info(f"Alert processed: {alert['type']} - sent to {sent_count}/{total_channels} channels")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Failed to process alert: {e}")
            return False
    
    async def _should_send_alert(self, alert: Dict[str, Any]) -> bool:
        """Determine if alert should be sent based on cooldown and rate limiting"""
        alert_key = f"{alert['type']}_{alert['severity']}"
        current_time = datetime.fromisoformat(alert['timestamp'].replace('Z', '+00:00'))
        
        # Check cooldown
        cooldown_minutes = self.config.get('global', {}).get('alert_cooldown_minutes', 30)
        if alert_key in self.sent_alerts:
            last_sent = self.sent_alerts[alert_key]['last_sent']
            if current_time - last_sent < timedelta(minutes=cooldown_minutes):
                self.logger.debug(f"Alert {alert_key} in cooldown period")
                return False
        
        # Check rate limiting
        max_per_hour = self.config.get('global', {}).get('max_alerts_per_hour', 10)
        one_hour_ago = current_time - timedelta(hours=1)
        
        recent_alerts = 0
        for sent_alert in self.sent_alerts.values():
            if sent_alert['last_sent'] > one_hour_ago:
                recent_alerts += sent_alert.get('count_last_hour', 0)
        
        if recent_alerts >= max_per_hour:
            self.logger.warning(f"Rate limit reached: {recent_alerts} alerts in last hour")
            return False
        
        return True
    
    def _track_sent_alert(self, alert: Dict[str, Any]):
        """Track sent alert for cooldown and rate limiting"""
        alert_key = f"{alert['type']}_{alert['severity']}"
        current_time = datetime.fromisoformat(alert['timestamp'].replace('Z', '+00:00'))
        
        if alert_key not in self.sent_alerts:
            self.sent_alerts[alert_key] = {
                'count_total': 0,
                'count_last_hour': 0,
                'first_sent': current_time,
                'last_sent': current_time
            }
        
        self.sent_alerts[alert_key]['count_total'] += 1
        self.sent_alerts[alert_key]['count_last_hour'] += 1
        self.sent_alerts[alert_key]['last_sent'] = current_time
        
        # Clean up old hourly counts
        one_hour_ago = current_time - timedelta(hours=1)
        for key, data in self.sent_alerts.items():
            if data['last_sent'] < one_hour_ago:
                data['count_last_hour'] = 0
    
    async def _store_alert(self, alert: Dict[str, Any]):
        """Store alert in Redis"""
        try:
            r = await self._get_redis()
            await r.lpush('mcp_processed_alerts', json.dumps(alert))
            await r.ltrim('mcp_processed_alerts', 0, 499)  # Keep last 500 alerts
        except Exception as e:
            self.logger.error(f"Failed to store alert in Redis: {e}")
    
    async def create_threshold_alert(self, metric_name: str, current_value: float, threshold: float, severity: str = "WARNING") -> Dict[str, Any]:
        """Create a threshold violation alert"""
        return {
            'timestamp': now_iso(),
            'type': f'threshold_{metric_name}',
            'severity': severity,
            'message': f'{metric_name.replace("_", " ").title()} threshold exceeded: {current_value} > {threshold}',
            'daemon': 'mcp_alert_manager',
            'details': {
                'metric': metric_name,
                'current_value': current_value,
                'threshold': threshold,
                'percentage': round((current_value / threshold) * 100, 2)
            }
        }
    
    async def create_failure_alert(self, component: str, failure_count: int, severity: str = "CRITICAL") -> Dict[str, Any]:
        """Create a component failure alert"""
        return {
            'timestamp': now_iso(),
            'type': f'component_failure_{component}',
            'severity': severity,
            'message': f'{component.replace("_", " ").title()} has failed {failure_count} consecutive times',
            'daemon': 'mcp_alert_manager',
            'details': {
                'component': component,
                'failure_count': failure_count,
                'suggestion': 'Check component logs and restart if necessary'
            }
        }
    
    async def test_channels(self) -> Dict[str, bool]:
        """Test all configured alert channels"""
        results = {}
        
        test_alert = {
            'timestamp': now_iso(),
            'type': 'test_alert',
            'severity': 'INFO',
            'message': 'This is a test alert from MCP Alert Manager',
            'daemon': 'mcp_alert_manager'
        }
        
        for channel_name, channel in self.channels.items():
            if not channel.enabled:
                results[channel_name] = False
                continue
            
            try:
                results[channel_name] = await channel.send_alert(test_alert)
            except Exception as e:
                self.logger.error(f"Test failed for channel {channel_name}: {e}")
                results[channel_name] = False
        
        return results
    
    async def get_alert_stats(self) -> Dict[str, Any]:
        """Get alerting statistics"""
        try:
            r = await self._get_redis()
            
            # Get recent alerts
            recent_alerts = await r.lrange('mcp_processed_alerts', 0, 99)
            
            stats = {
                'total_alerts': len(recent_alerts),
                'alerts_by_severity': {},
                'alerts_by_type': {},
                'channels_enabled': sum(1 for c in self.channels.values() if c.enabled),
                'last_alert': None
            }
            
            for alert_json in recent_alerts:
                try:
                    alert = json.loads(alert_json)
                    
                    # Count by severity
                    severity = alert.get('severity', 'UNKNOWN')
                    stats['alerts_by_severity'][severity] = stats['alerts_by_severity'].get(severity, 0) + 1
                    
                    # Count by type
                    alert_type = alert.get('type', 'unknown')
                    stats['alerts_by_type'][alert_type] = stats['alerts_by_type'].get(alert_type, 0) + 1
                    
                    # Track latest
                    if not stats['last_alert'] or alert['timestamp'] > stats['last_alert']:
                        stats['last_alert'] = alert['timestamp']
                        
                except json.JSONDecodeError:
                    continue
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Failed to get alert stats: {e}")
            return {'error': str(e)}


# Standalone functions for easy integration
async def send_mcp_alert(alert_type: str, message: str, severity: str = "WARNING", details: Dict = None):
    """Convenience function to send an MCP alert"""
    alert_manager = MCPAlertManager()
    
    alert = {
        'timestamp': now_iso(),
        'type': alert_type,
        'severity': severity,
        'message': message,
        'daemon': 'mcp_system',
        'details': details or {}
    }
    
    return await alert_manager.process_alert(alert)

async def send_threshold_alert(metric_name: str, current_value: float, threshold: float, severity: str = "WARNING"):
    """Send a threshold violation alert"""
    alert_manager = MCPAlertManager()
    alert = await alert_manager.create_threshold_alert(metric_name, current_value, threshold, severity)
    return await alert_manager.process_alert(alert)

async def send_failure_alert(component: str, failure_count: int, severity: str = "CRITICAL"):
    """Send a component failure alert"""
    alert_manager = MCPAlertManager()
    alert = await alert_manager.create_failure_alert(component, failure_count, severity)
    return await alert_manager.process_alert(alert)


if __name__ == "__main__":
    async def main():
        """Test the alert manager"""
        manager = MCPAlertManager()
        
        # Test channels
        print("Testing alert channels...")
        results = await manager.test_channels()
        for channel, success in results.items():
            status = "✓" if success else "✗"
            print(f"  {status} {channel}")
        
        # Send test alert
        await send_mcp_alert(
            "test_alert",
            "This is a test alert from MCP Alert Manager",
            "INFO"
        )
        
        print("Alert manager test completed")
    
    asyncio.run(main())