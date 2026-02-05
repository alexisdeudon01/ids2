"""State Machine Integration Tests."""

from enum import Enum, auto

import pytest


class AgentState(Enum):
    """Agent states from docs/kl.md."""

    WAIT_USER = auto()
    START_COMMAND = auto()
    INITIALIZING = auto()
    COMPONENTS_STARTING = auto()
    SUPERVISOR_RUNNING = auto()
    STOPPING = auto()
    STOPPED = auto()


class AgentEvent(Enum):
    """Events that trigger state transitions."""

    USER_START = auto()
    INIT_BEGIN = auto()
    USER_CANCEL = auto()
    CONFIG_VALID = auto()
    CONFIG_INVALID = auto()
    COMPONENTS_STARTED = auto()
    COMPONENTS_FAILED = auto()
    STOP_REQUESTED = auto()
    STOP_COMPLETE = auto()


class StateMachine:
    """State machine implementation."""

    def __init__(self):
        self.current_state = AgentState.WAIT_USER
        self._transitions = {
            AgentState.WAIT_USER: {
                AgentEvent.USER_START: AgentState.START_COMMAND,
                AgentEvent.USER_CANCEL: AgentState.STOPPED,
            },
            AgentState.START_COMMAND: {
                AgentEvent.INIT_BEGIN: AgentState.INITIALIZING,
            },
            AgentState.INITIALIZING: {
                AgentEvent.CONFIG_VALID: AgentState.COMPONENTS_STARTING,
                AgentEvent.CONFIG_INVALID: AgentState.STOPPED,
            },
            AgentState.COMPONENTS_STARTING: {
                AgentEvent.COMPONENTS_STARTED: AgentState.SUPERVISOR_RUNNING,
                AgentEvent.COMPONENTS_FAILED: AgentState.STOPPED,
            },
            AgentState.SUPERVISOR_RUNNING: {
                AgentEvent.STOP_REQUESTED: AgentState.STOPPING,
            },
            AgentState.STOPPING: {
                AgentEvent.STOP_COMPLETE: AgentState.STOPPED,
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
        assert sm.current_state == AgentState.WAIT_USER

    @pytest.mark.unit
    def test_happy_path_to_monitoring(self, sm):
        assert sm.transition(AgentEvent.USER_START)
        assert sm.current_state == AgentState.START_COMMAND

        assert sm.transition(AgentEvent.INIT_BEGIN)
        assert sm.current_state == AgentState.INITIALIZING

        assert sm.transition(AgentEvent.CONFIG_VALID)
        assert sm.current_state == AgentState.COMPONENTS_STARTING

        assert sm.transition(AgentEvent.COMPONENTS_STARTED)
        assert sm.current_state == AgentState.SUPERVISOR_RUNNING

    @pytest.mark.unit
    def test_config_failure(self, sm):
        sm.transition(AgentEvent.USER_START)
        sm.transition(AgentEvent.INIT_BEGIN)
        assert sm.transition(AgentEvent.CONFIG_INVALID)
        assert sm.current_state == AgentState.STOPPED

    @pytest.mark.unit
    def test_stop_flow(self, sm):
        sm.transition(AgentEvent.USER_START)
        sm.transition(AgentEvent.INIT_BEGIN)
        sm.transition(AgentEvent.CONFIG_VALID)
        sm.transition(AgentEvent.COMPONENTS_STARTED)
        assert sm.transition(AgentEvent.STOP_REQUESTED)
        assert sm.current_state == AgentState.STOPPING
        assert sm.transition(AgentEvent.STOP_COMPLETE)
        assert sm.current_state == AgentState.STOPPED

    @pytest.mark.unit
    def test_invalid_transition(self, sm):
        result = sm.transition(AgentEvent.COMPONENTS_STARTED)
        assert result is False
        assert sm.current_state == AgentState.WAIT_USER
