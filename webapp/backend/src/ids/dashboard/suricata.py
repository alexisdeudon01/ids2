"""
Suricata EVE log monitoring with async tailing.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path as Path
from typing import Any, AsyncIterator, Iterator

import logging
from ids.datastructures import AlertEvent

logger = logging.getLogger(__name__)

SURICATA_EVE_LOG = Path("/var/log/suricata/eve.json")

SURICATALOG_AVAILABLE = False
PYEVE_AVAILABLE = False
PYTHON_SURICATA_AVAILABLE = False
SuricataLogClient = None
Eve = None
suricata = None

try:
    from SuricataLog import SuricataLog as SuricataLogClient  # type: ignore
    SURICATALOG_AVAILABLE = True
except ImportError:
    logger.warning("SuricataLog not available. Install with: pip install SuricataLog")

try:
    from pyeve import Eve  # type: ignore
    PYEVE_AVAILABLE = True
except ImportError:
    logger.debug("pyeve not available (optional). Falling back to json parsing.")

try:
    import suricata  # type: ignore
    PYTHON_SURICATA_AVAILABLE = True
except ImportError:
    logger.debug("Suricata python bindings not available (optional).")


class SuricataLogMonitor:
    """Monitor Suricata EVE JSON log file for alert events."""

    def __init__(self, log_path: Path = SURICATA_EVE_LOG) -> None:
        """Initialize the monitor."""
        self.log_path = log_path
        self._running = False
        self._task: asyncio.Task | None = None
        self._position = 0
        self._suricata_log: Any | None = None
        if PYTHON_SURICATA_AVAILABLE and suricata is not None:
            if hasattr(suricata, "__version__"):  # type: ignore[unreachable]
                print(f"python-suricata detected (version {suricata.__version__})")

    async def start(self) -> None:
        """Start monitoring the log file."""
        if self._running:
            logger.warning("Suricata monitor already running")
            return

        if not self.log_path.exists():
            print(f"Suricata log file not found: {self.log_path}")
            return

        self._running = True
        if SURICATALOG_AVAILABLE and SuricataLogClient:
            try:  # type: ignore[unreachable]
                self._suricata_log = SuricataLogClient(str(self.log_path))
            except OSError as exc:
                print(f"Failed to initialize SuricataLog: {exc}")
                self._suricata_log = None

        # Get current file size to start from end
        if self.log_path.exists():
            self._position = self.log_path.stat().st_size

        print(f"Started Suricata log monitoring: {self.log_path}")

    async def stop(self) -> None:
        """Stop monitoring."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Stopped Suricata log monitoring")

    async def tail_alerts(self) -> AsyncIterator[AlertEvent]:
        """
        Async generator that yields alert events from the EVE log.

        Yields:
            AlertEvent objects for each 'alert' event type found
        """
        if not self.log_path.exists():
            print(f"Log file does not exist: {self.log_path}")
            return

        if self._suricata_log:
            async for alert in self._tail_with_suricatalog():
                yield alert

        while self._running:
            try:
                # Read new lines from current position
                with self.log_path.open(encoding="utf-8") as f:
                    f.seek(self._position)
                    new_lines = f.readlines()

                    for line in new_lines:
                        if not line.strip():
                            continue

                        event = self._parse_event_line(line)
                        if not event:
                            continue

                        event_type = event.get("event_type", "")

                        # Only process alert events
                        if event_type == "alert":
                            alert_data = event.get("alert", {})
                            alert_event = AlertEvent(
                                timestamp=datetime.fromisoformat(
                                    event.get("timestamp", "").replace("Z", "+00:00")
                                ),
                                event_type=event_type,
                                src_ip=event.get("src_ip"),
                                dest_ip=event.get("dest_ip"),
                                alert=alert_data,
                                severity=alert_data.get("severity", 0),
                                signature=alert_data.get("signature", ""),
                            )
                            yield alert_event

                            # Update position after successful read
                            self._position = f.tell()

                # Wait a bit before checking for new data
                await asyncio.sleep(0.1)

            except FileNotFoundError:
                print(f"Log file disappeared: {self.log_path}")
                await asyncio.sleep(1)
            except OSError as e:
                print(f"Error in tail_alerts: {e}")
                await asyncio.sleep(1)

    async def get_recent_alerts(self, limit: int = 100) -> list[AlertEvent]:
        """
        Get recent alert events from the log file.

        Args:
            limit: Maximum number of alerts to return

        Returns:
            List of recent AlertEvent objects
        """
        alerts: list[AlertEvent] = []

        if not self.log_path.exists():
            return alerts

        try:
            with self.log_path.open(encoding="utf-8") as f:
                # Read file in reverse (last lines first)
                lines = f.readlines()
                for line in reversed(lines[-limit * 2 :]):  # Read more to account for non-alert events
                    if not line.strip():
                        continue

                    event = self._parse_event_line(line)
                    if not event or event.get("event_type") != "alert":
                        continue

                    alert_data = event.get("alert", {})
                    alert_event = AlertEvent(
                        timestamp=datetime.fromisoformat(
                            event.get("timestamp", "").replace("Z", "+00:00")
                        ),
                        event_type="alert",
                        src_ip=event.get("src_ip"),
                        dest_ip=event.get("dest_ip"),
                        alert=alert_data,
                        severity=alert_data.get("severity", 0),
                        signature=alert_data.get("signature", ""),
                    )
                    alerts.append(alert_event)

                    if len(alerts) >= limit:
                        break

        except OSError as e:
            print(f"Error reading recent alerts: {e}")

        return list(reversed(alerts))  # Return in chronological order

    def _parse_event_line(self, line: str) -> dict[str, Any] | None:
        if not line.strip():
            return None

        if PYEVE_AVAILABLE and Eve:
            try:  # type: ignore[unreachable]
                parser = Eve() if hasattr(Eve, "__call__") else None
                if parser and hasattr(parser, "loads"):
                    data = parser.loads(line)
                elif parser and hasattr(parser, "parse"):
                    data = parser.parse(line)
                else:
                    data = json.loads(line)
                if isinstance(data, dict):
                    return data
            except (ValueError, TypeError) as e:
                print(f"Failed to parse with pyeve: {e}")

        try:
            return json.loads(line)
        except json.JSONDecodeError as e:
            print(f"Failed to parse JSON line: {e}")
            return None

    async def _tail_with_suricatalog(self) -> AsyncIterator[AlertEvent]:
        iterator = self._get_suricatalog_iterator()
        if not iterator:
            logger.warning("SuricataLog iterator unavailable, falling back to file tailing")
            return

        while self._running:
            try:
                event: Any = await asyncio.to_thread(lambda: next(iter(iterator)))
            except StopIteration:
                await asyncio.sleep(0.1)
                continue
            except OSError as exc:
                print(f"Error reading SuricataLog stream: {exc}")
                await asyncio.sleep(0.5)
                continue

            if isinstance(event, str):
                event = self._parse_event_line(event)
            if not isinstance(event, dict):
                continue

            if event.get("event_type") != "alert":
                continue

            alert_data = event.get("alert", {})
            yield AlertEvent(
                timestamp=datetime.fromisoformat(event.get("timestamp", "").replace("Z", "+00:00")),
                event_type=event.get("event_type", "alert"),
                src_ip=event.get("src_ip"),
                dest_ip=event.get("dest_ip"),
                alert=alert_data,
                severity=alert_data.get("severity", 0),
                signature=alert_data.get("signature", ""),
            )

    def _get_suricatalog_iterator(self) -> Iterator[Any] | None:
        if not self._suricata_log:
            return None
        for method_name in ("tail", "follow", "__iter__"):
            if hasattr(self._suricata_log, method_name):
                method = getattr(self._suricata_log, method_name)
                try:
                    result = method() if callable(method) else method
                    return iter(result) if result is not None else None
                except (OSError, AttributeError) as exc:
                    print(f"SuricataLog method {method_name} failed: {exc}")
        return None
