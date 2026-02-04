"""Unit tests for domain models."""

from datetime import datetime

import pytest

from ids.domain.alerte import AlerteIDS, SeveriteAlerte, TypeAlerte


class TestAlerteIDS:
    """Tests for AlerteIDS dataclass."""

    @pytest.mark.unit
    def test_create_alerte_simple(self):
        """Test creating a simple alert."""
        alerte = AlerteIDS(
            severite=SeveriteAlerte.MOYENNE,
            type_alerte=TypeAlerte.INTRUSION,
            source_ip="192.168.1.100",
            destination_ip="10.0.0.1",
            port=443,
        )
        assert alerte.source_ip == "192.168.1.100"
        assert alerte.severite == SeveriteAlerte.MOYENNE

    @pytest.mark.unit
    def test_alerte_immutability(self):
        """Test that AlerteIDS is immutable (frozen=True)."""
        alerte = AlerteIDS()
        with pytest.raises(AttributeError):
            alerte.source_ip = "10.0.0.100"

    @pytest.mark.unit
    def test_severity_values(self):
        """Test severity enum values."""
        assert SeveriteAlerte.CRITIQUE.value == "critique"
        assert SeveriteAlerte.HAUTE.value == "haute"
        assert SeveriteAlerte.MOYENNE.value == "moyenne"
        assert SeveriteAlerte.BASSE.value == "basse"

    @pytest.mark.unit
    def test_type_alerte_values(self):
        """Test alert type enum values."""
        assert TypeAlerte.INTRUSION.value == "intrusion"
        assert TypeAlerte.ANOMALIE.value == "anomalie"
        assert TypeAlerte.CONFORMITE.value == "conformite"
