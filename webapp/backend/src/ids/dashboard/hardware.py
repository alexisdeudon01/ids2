"""
Hardware control for Raspberry Pi (GPIO LED).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gpiozero import LED

logger = logging.getLogger(__name__)

GPIOZERO_AVAILABLE = False
try:
    from gpiozero import LED

    GPIOZERO_AVAILABLE = True
except ImportError:
    logger.warning("gpiozero not available. Install with: pip install gpiozero")


class HardwareController:
    """Control Raspberry Pi hardware (LED for alerts)."""

    def __init__(self, led_pin: int = 17) -> None:
        """
        Initialize hardware controller.

        Args:
            led_pin: GPIO pin number for the alert LED (default: 17)
        """
        self.led_pin = led_pin
        self._led: LED | None = None
        self._enabled = False

        if GPIOZERO_AVAILABLE:
            try:
                self._led = LED(led_pin)
                self._enabled = True
                logger.info(f"Hardware controller initialized (LED on pin {led_pin})")
            except Exception as e:
                logger.warning(f"Failed to initialize LED on pin {led_pin}: {e}")
                self._enabled = False
        else:
            logger.warning("gpiozero not available - hardware control disabled")

    def flash_led(self, duration: float = 0.5, count: int = 1) -> None:
        """
        Flash the LED for alert indication.

        Args:
            duration: Duration of each flash in seconds
            count: Number of flashes
        """
        if not self._enabled or not self._led:
            logger.debug("LED not available - skipping flash")
            return

        try:
            for _ in range(count):
                self._led.on()
                import time

                time.sleep(duration)
                self._led.off()
                if count > 1:
                    time.sleep(duration)

            logger.debug(f"LED flashed {count} times")

        except Exception as e:
            logger.error(f"Error flashing LED: {e}")

    def handle_alert(self, severity: int) -> None:
        """
        Handle an alert based on severity.

        Args:
            severity: Alert severity (1 = critical, flash LED)
        """
        if severity == 1:
            # Critical alert - flash LED
            self.flash_led(duration=0.3, count=3)
            logger.info("Critical alert detected - LED flashed")

    def cleanup(self) -> None:
        """Cleanup hardware resources."""
        if self._led:
            try:
                self._led.off()
                self._led.close()
                logger.info("Hardware controller cleaned up")
            except Exception as e:
                logger.error(f"Error cleaning up hardware: {e}")
