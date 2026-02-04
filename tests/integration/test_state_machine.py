"""State Machine Integration Tests."""

from enum import Enum, auto

import pytest


class AgentState(Enum):
    """Agent states from state machine diagram."""

    CHECKING_CONFIG = auto()
    VALIDATING_CONFIGURATION = auto()
    SPINNING_UP_CONTAINERS = auto()
    PREPARING_ENVIRONMENT = auto()
    STARTING_SERVICES = auto()
    MONITORING = auto()
    CHECKING_SERVICE_HEALTH = auto()
    NORMAL_MONITORING = auto()
    RESOURCE_LIMIT_EXCEEDED = auto()
    PAUSED_ALERT_SENT = auto()
    ATTEMPT_RECOVERY = auto()
    RESTARTING_CONTAINERS = auto()


class AgentEvent(Enum):
    """Events that trigger state transitions."""

    INIT_COMPLETE = auto()
    CONFIG_VALID = auto()
    DOCKER_HEALTHY = auto()
    DOCKER_FAILED = auto()
    ENV_READY = auto()
    SERVICES_READY = auto()
    SERVICES_FAILED = auto()
    HIGH_CPU = auto()
    HIGH_MEM = auto()
    NORMAL_RESOURCES = auto()
    SCHEDULE_CHECK = auto()
    OK = auto()
    INTERRUPT = auto()
    MAX_RETRIES = auto()
    PI_API_OK = auto()
    RECOVERY_ATTEMPTED = auto()


class StateMachine:
    """State machine implementation."""

    def __init__(self):
        self.current_state = AgentState.CHECKING_CONFIG
        self._transitions = {
            AgentState.CHECKING_CONFIG: {
                AgentEvent.INIT_COMPLETE: AgentState.VALIDATING_CONFIGURATION,
            },
            AgentState.VALIDATING_CONFIGURATION: {
                AgentEvent.CONFIG_VALID: AgentState.SPINNING_UP_CONTAINERS,
            },
            AgentState.SPINNING_UP_CONTAINERS: {
                AgentEvent.DOCKER_HEALTHY: AgentState.PREPARING_ENVIRONMENT,
                AgentEvent.DOCKER_FAILED: AgentState.ATTEMPT_RECOVERY,
            },
            AgentState.PREPARING_ENVIRONMENT: {
                AgentEvent.ENV_READY: AgentState.STARTING_SERVICES,
            },
            AgentState.STARTING_SERVICES: {
                AgentEvent.SERVICES_READY: AgentState.MONITORING,
                AgentEvent.SERVICES_FAILED: AgentState.ATTEMPT_RECOVERY,
            },
            AgentState.MONITORING: {
                AgentEvent.SCHEDULE_CHECK: AgentState.CHECKING_SERVICE_HEALTH,
                AgentEvent.HIGH_CPU: AgentState.RESOURCE_LIMIT_EXCEEDED,
                AgentEvent.HIGH_MEM: AgentState.RESOURCE_LIMIT_EXCEEDED,
            },
            AgentState.CHECKING_SERVICE_HEALTH: {
                AgentEvent.OK: AgentState.NORMAL_MONITORING,
                AgentEvent.INTERRUPT: AgentState.PAUSED_ALERT_SENT,
            },
            AgentState.NORMAL_MONITORING: {
                AgentEvent.HIGH_CPU: AgentState.RESOURCE_LIMIT_EXCEEDED,
                AgentEvent.SCHEDULE_CHECK: AgentState.CHECKING_SERVICE_HEALTH,
            },
            AgentState.RESOURCE_LIMIT_EXCEEDED: {
                AgentEvent.NORMAL_RESOURCES: AgentState.NORMAL_MONITORING,
                AgentEvent.INTERRUPT: AgentState.PAUSED_ALERT_SENT,
            },
            AgentState.ATTEMPT_RECOVERY: {
                AgentEvent.RECOVERY_ATTEMPTED: AgentState.STARTING_SERVICES,
                AgentEvent.MAX_RETRIES: AgentState.PAUSED_ALERT_SENT,
            },
            AgentState.PAUSED_ALERT_SENT: {
                AgentEvent.PI_API_OK: AgentState.RESTARTING_CONTAINERS,
            },
            AgentState.RESTARTING_CONTAINERS: {
                AgentEvent.SERVICES_READY: AgentState.MONITORING,
            },
        }

    def transition(self, event: AgentEvent) -> bool:
        if self.current_state not in self._transitions:
            return False
        if event not in self._transitions[self.current_state]:
            return False
        self.current_state = self._transitions[self.current_state][event]
        return True


@pytest.mark.state_machine
class TestStateMachine:
    """Tests for state machine transitions."""

    @pytest.fixture
    def sm(self):
        return StateMachine()

    @pytest.mark.unit
    def test_initial_state(self, sm):
        assert sm.current_state == AgentState.CHECKING_CONFIG

    @pytest.mark.unit
    def test_happy_path_to_monitoring(self, sm):
        assert sm.transition(AgentEvent.INIT_COMPLETE)
        assert sm.current_state == AgentState.VALIDATING_CONFIGURATION

        assert sm.transition(AgentEvent.CONFIG_VALID)
        assert sm.current_state == AgentState.SPINNING_UP_CONTAINERS

        assert sm.transition(AgentEvent.DOCKER_HEALTHY)
        assert sm.current_state == AgentState.PREPARING_ENVIRONMENT

        assert sm.transition(AgentEvent.ENV_READY)
        assert sm.current_state == AgentState.STARTING_SERVICES

        assert sm.transition(AgentEvent.SERVICES_READY)
        assert sm.current_state == AgentState.MONITORING

    @pytest.mark.unit
    def test_docker_failure_recovery(self, sm):
        sm.transition(AgentEvent.INIT_COMPLETE)
        sm.transition(AgentEvent.CONFIG_VALID)

        assert sm.transition(AgentEvent.DOCKER_FAILED)
        assert sm.current_state == AgentState.ATTEMPT_RECOVERY

    @pytest.mark.unit
    def test_resource_limit_exceeded(self, sm):
        # Get to monitoring
        sm.transition(AgentEvent.INIT_COMPLETE)
        sm.transition(AgentEvent.CONFIG_VALID)
        sm.transition(AgentEvent.DOCKER_HEALTHY)
        sm.transition(AgentEvent.ENV_READY)
        sm.transition(AgentEvent.SERVICES_READY)

        assert sm.transition(AgentEvent.HIGH_CPU)
        assert sm.current_state == AgentState.RESOURCE_LIMIT_EXCEEDED

        assert sm.transition(AgentEvent.NORMAL_RESOURCES)
        assert sm.current_state == AgentState.NORMAL_MONITORING

    @pytest.mark.unit
    def test_invalid_transition(self, sm):
        result = sm.transition(AgentEvent.SERVICES_READY)
        assert result is False
        assert sm.current_state == AgentState.CHECKING_CONFIG
