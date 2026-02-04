"""
Logging utilities with optimized formatting and error handling.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, TypeVar

T = TypeVar('T')


@dataclass
class LogMessage:
    """Structured log message with lazy formatting."""
    template: str
    args: tuple[Any, ...] = ()
    
    def format(self) -> str:
        """Format the message only when needed."""
        return self.template % self.args if self.args else self.template


class SafeLogger:
    """Logger wrapper with optimized formatting and built-in error handling."""
    
    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger
    
    def _log_safe(self, level: int, msg: LogMessage, exc_info: bool = False) -> None:
        """Safely log with lazy formatting."""
        if self.logger.isEnabledFor(level):
            try:
                self.logger.log(level, msg.template, *msg.args, exc_info=exc_info)
            except Exception:
                # Fallback to basic logging if formatting fails
                self.logger.log(level, "Logging error occurred")
    
    def debug(self, template: str, *args: Any) -> None:
        """Debug log with lazy formatting."""
        self._log_safe(logging.DEBUG, LogMessage(template, args))
    
    def info(self, template: str, *args: Any) -> None:
        """Info log with lazy formatting."""
        self._log_safe(logging.INFO, LogMessage(template, args))
    
    def warning(self, template: str, *args: Any) -> None:
        """Warning log with lazy formatting."""
        self._log_safe(logging.WARNING, LogMessage(template, args))
    
    def error(self, template: str, *args: Any, exc_info: bool = False) -> None:
        """Error log with lazy formatting."""
        self._log_safe(logging.ERROR, LogMessage(template, args), exc_info)


def safe_execute(func: Callable[[], T], logger: SafeLogger, error_msg: str = "Operation failed: %s") -> T | None:
    """Execute function with automatic error logging."""
    try:
        return func()
    except Exception as e:
        logger.error(error_msg, str(e), exc_info=True)
        return None


async def safe_execute_async(func: Callable[[], Awaitable[T]], logger: SafeLogger, error_msg: str = "Async operation failed: %s") -> T | None:
    """Execute async function with automatic error logging."""
    try:
        result: T = await func()
        return result
    except Exception as e:
        logger.error(error_msg, str(e), exc_info=True)
        return None