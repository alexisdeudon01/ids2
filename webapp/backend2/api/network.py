"""Network statistics endpoint."""

import psutil
from datetime import datetime
from fastapi import APIRouter
from models.schemas import NetworkStats

router = APIRouter()


@router.get("/api/network/stats")
async def get_network_stats(interface: str = "eth0") -> NetworkStats:
    """Get network interface statistics."""
    stats = psutil.net_io_counters(pernic=True).get(interface)
    
    if not stats:
        # Return zeros if interface not found
        return NetworkStats(
            interface=interface,
            bytes_sent=0,
            bytes_recv=0,
            packets_sent=0,
            packets_recv=0,
            bitrate_sent=0.0,
            bitrate_recv=0.0,
            timestamp=datetime.now().isoformat(),
        )
    
    # Calculate bitrate (simplified - would need time delta for accuracy)
    bitrate_sent = stats.bytes_sent * 8 / 1_000_000  # Mbps
    bitrate_recv = stats.bytes_recv * 8 / 1_000_000  # Mbps
    
    return NetworkStats(
        interface=interface,
        bytes_sent=stats.bytes_sent,
        bytes_recv=stats.bytes_recv,
        packets_sent=stats.packets_sent,
        packets_recv=stats.packets_recv,
        bitrate_sent=bitrate_sent,
        bitrate_recv=bitrate_recv,
        timestamp=datetime.now().isoformat(),
    )
