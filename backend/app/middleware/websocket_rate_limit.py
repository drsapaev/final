"""
Rate limiting middleware for WebSocket connections
"""
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, Tuple

logger = logging.getLogger(__name__)


class WebSocketRateLimiter:
    """Rate limiter for WebSocket connections"""
    
    def __init__(self):
        # Track connections per IP
        self.connections_per_ip: Dict[str, int] = defaultdict(int)
        self.connection_timestamps: Dict[str, list] = defaultdict(list)
        
        # Rate limits
        self.max_connections_per_ip = 10  # Max 10 connections per IP
        self.max_connections_per_minute = 5  # Max 5 new connections per minute per IP
        self.connection_timeout_seconds = 300  # 5 minutes
        
        # Cleanup interval
        self.last_cleanup = datetime.utcnow()
        self.cleanup_interval = timedelta(minutes=5)
    
    def _cleanup_old_connections(self):
        """Remove old connection records"""
        now = datetime.utcnow()
        if now - self.last_cleanup < self.cleanup_interval:
            return
        
        cutoff_time = now - timedelta(seconds=self.connection_timeout_seconds)
        
        for ip in list(self.connection_timestamps.keys()):
            # Remove old timestamps
            self.connection_timestamps[ip] = [
                ts for ts in self.connection_timestamps[ip] if ts > cutoff_time
            ]
            
            # Update connection count
            self.connections_per_ip[ip] = len(self.connection_timestamps[ip])
            
            # Remove empty entries
            if not self.connection_timestamps[ip]:
                del self.connection_timestamps[ip]
                if ip in self.connections_per_ip:
                    del self.connections_per_ip[ip]
        
        self.last_cleanup = now
    
    def check_rate_limit(self, ip_address: str) -> Tuple[bool, str]:
        """
        Check if IP address is within rate limits
        
        Returns:
            (allowed, reason): Tuple of (bool, str)
        """
        self._cleanup_old_connections()
        
        # Check total connections per IP
        if self.connections_per_ip.get(ip_address, 0) >= self.max_connections_per_ip:
            logger.warning(f"Rate limit exceeded: IP {ip_address} has too many connections")
            return False, f"Too many connections from this IP (max {self.max_connections_per_ip})"
        
        # Check connections per minute
        now = datetime.utcnow()
        minute_ago = now - timedelta(minutes=1)
        
        recent_connections = [
            ts for ts in self.connection_timestamps.get(ip_address, [])
            if ts > minute_ago
        ]
        
        if len(recent_connections) >= self.max_connections_per_minute:
            logger.warning(f"Rate limit exceeded: IP {ip_address} connected too frequently")
            return False, f"Too many connection attempts (max {self.max_connections_per_minute} per minute)"
        
        return True, ""
    
    def record_connection(self, ip_address: str):
        """Record a new connection"""
        now = datetime.utcnow()
        self.connection_timestamps[ip_address].append(now)
        self.connections_per_ip[ip_address] = len(self.connection_timestamps[ip_address])
    
    def remove_connection(self, ip_address: str):
        """Remove a connection record"""
        if ip_address in self.connection_timestamps and self.connection_timestamps[ip_address]:
            # Remove the oldest connection
            self.connection_timestamps[ip_address].pop(0)
            self.connections_per_ip[ip_address] = len(self.connection_timestamps[ip_address])
            
            # Clean up if empty
            if not self.connection_timestamps[ip_address]:
                del self.connection_timestamps[ip_address]
                if ip_address in self.connections_per_ip:
                    del self.connections_per_ip[ip_address]


# Global rate limiter instance
websocket_rate_limiter = WebSocketRateLimiter()


