"""
AI-powered error healing using Anthropic Claude.
"""

from __future__ import annotations

import asyncio
import logging
import traceback
from datetime import datetime
from typing import Any

from ids.datastructures import AIHealingResponse

logger = logging.getLogger(__name__)

ANTHROPIC_AVAILABLE = False
try:
    from anthropic import Anthropic

    ANTHROPIC_AVAILABLE = True
except ImportError:
    logger.warning("anthropic not available. Install with: pip install anthropic")


class AIHealingService:
    """AI-powered error diagnosis and healing suggestions."""

    def __init__(self, api_key: str | None = None) -> None:
        """
        Initialize AI healing service.

        Args:
            api_key: Anthropic API key (or set ANTHROPIC_API_KEY env var)
        """
        self.api_key = api_key
        self._client: Any = None

        if ANTHROPIC_AVAILABLE:
            try:
                self._client = Anthropic(api_key=api_key)
                logger.info("AI Healing service initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Anthropic client: {e}")
        else:
            logger.warning("Anthropic SDK not available - AI healing disabled")

    async def diagnose_error(
        self,
        error_type: str,
        error_message: str,
        context: dict[str, Any] | None = None,
    ) -> AIHealingResponse:
        """
        Diagnose an error and get AI-powered healing suggestions.

        Args:
            error_type: Type of error (e.g., "SuricataStartError")
            error_message: Error message
            context: Additional context (system info, logs, etc.)

        Returns:
            AIHealingResponse with suggestions and commands
        """
        if not self._client:
            return AIHealingResponse(
                error_type=error_type,
                error_message=error_message,
                suggestion="AI healing service not available. Install anthropic package.",
                timestamp=datetime.now(),
            )

        try:
            context_str = ""
            if context:
                context_str = "\n".join(f"{k}: {v}" for k, v in context.items())

            prompt = f"""You are a senior security engineer troubleshooting a Raspberry Pi IDS system.

Error Type: {error_type}
Error Message: {error_message}

Context:
{context_str}

The system architecture:
- Router connected to TP-Link TL-SG108E switch (Port 1)
- Raspberry Pi connected to switch (Port 5/eth0)
- Port mirroring: Port 1 → Port 5
- Suricata monitoring eth0 in promiscuous mode
- Vector forwarding logs to Elasticsearch

Provide:
1. A clear diagnosis of the problem
2. Specific commands to fix it (Linux commands for Raspberry Pi)
3. Confidence level (0.0-1.0)

Format your response as:
DIAGNOSIS: [your diagnosis]
COMMANDS:
- [command 1]
- [command 2]
CONFIDENCE: [0.0-1.0]
"""

            message = await asyncio.to_thread(
                self._client.messages.create,
                model="claude-3-5-sonnet-20241022",
                max_tokens=1024,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
            )

            response_text = message.content[0].text if message.content else ""

            # Parse response
            suggestion = response_text
            commands: list[str] = []
            confidence = 0.5

            # Extract commands
            if "COMMANDS:" in response_text:
                cmd_section = response_text.split("COMMANDS:")[1].split("CONFIDENCE:")[0]
                for line in cmd_section.split("\n"):
                    line = line.strip()
                    if line.startswith("-"):
                        commands.append(line[1:].strip())

            # Extract confidence
            if "CONFIDENCE:" in response_text:
                try:
                    conf_str = response_text.split("CONFIDENCE:")[1].strip().split()[0]
                    confidence = float(conf_str)
                except (ValueError, IndexError):
                    pass

            return AIHealingResponse(
                error_type=error_type,
                error_message=error_message,
                suggestion=suggestion,
                commands=commands,
                confidence=confidence,
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Error in AI diagnosis: {e}")
            return AIHealingResponse(
                error_type=error_type,
                error_message=error_message,
                suggestion=f"AI diagnosis failed: {str(e)}",
                timestamp=datetime.now(),
            )

    async def handle_pipeline_error(
        self,
        component: str,
        error: Exception,
        logs: str | None = None,
    ) -> AIHealingResponse:
        """
        Handle a pipeline component error with AI healing.

        Args:
            component: Component name (suricata, vector, elasticsearch)
            error: Exception that occurred
            logs: Optional log output

        Returns:
            AIHealingResponse with healing suggestions
        """
        error_type = f"{component.capitalize()}Error"
        error_message = str(error)
        traceback_str = traceback.format_exc()

        context = {
            "component": component,
            "traceback": traceback_str,
        }

        if logs:
            context["logs"] = logs

        # Add system info
        try:
            import psutil

            context["cpu_percent"] = psutil.cpu_percent(interval=1)
            context["memory_percent"] = psutil.virtual_memory().percent
        except Exception:
            pass

        return await self.diagnose_error(error_type, error_message, context)
