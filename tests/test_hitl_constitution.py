# tests/test_hitl_constitution.py
"""Tests for HITL Constitution analysis functionality."""
from cognition.constitution import (
    Constitution,
    ConstitutionAnalysis,
    RecommendationType,
)


class TestConstitutionAnalysis:
    """Test the new analyze() method in Constitution."""

    def setup_method(self):
        """Setup test fixtures."""
        self.constitution = Constitution()

    def test_analyze_safe_message(self):
        """Test analyzing a safe message."""
        result = self.constitution.analyze("Hello! How are you today?")

        assert isinstance(result, ConstitutionAnalysis)
        assert result.risk_score == 0.0
        assert result.recommendation == RecommendationType.APPROVE
        assert len(result.violations) == 0
        assert len(result.flags) == 0

    def test_analyze_empty_message(self):
        """Test analyzing empty message."""
        result = self.constitution.analyze("")

        assert result.risk_score == 0.0
        assert result.recommendation == RecommendationType.APPROVE
        assert result.normalized_text == ""

    def test_analyze_romantic_keyword(self):
        """Test analyzing message with romantic keyword."""
        result = self.constitution.analyze("I love you so much!")

        assert result.risk_score > 0.0
        assert result.recommendation in [RecommendationType.REVIEW, RecommendationType.FLAG]
        assert len(result.violations) > 0
        assert any("loveyou" in violation for violation in result.violations)

    def test_analyze_manipulation_pattern(self):
        """Test analyzing message with manipulation pattern."""
        result = self.constitution.analyze("I can't live without you")

        assert result.risk_score > 0.0
        assert result.recommendation in [RecommendationType.REVIEW, RecommendationType.FLAG]
        assert len(result.violations) > 0

    def test_analyze_multiple_violations(self):
        """Test analyzing message with multiple violations."""
        result = self.constitution.analyze("I love you baby, you're my everything")

        assert result.risk_score > 0.4  # Multiple violations should increase score
        assert result.recommendation == RecommendationType.FLAG
        assert len(result.violations) >= 2

    def test_analyze_risk_score_calculation(self):
        """Test risk score calculation logic."""
        # Safe message
        safe_result = self.constitution.analyze("Hello there!")
        assert safe_result.risk_score == 0.0

        # One violation
        one_violation = self.constitution.analyze("I love you")
        assert 0.1 <= one_violation.risk_score <= 0.3

        # Multiple violations
        multi_violation = self.constitution.analyze("I love you baby, kiss me")
        assert multi_violation.risk_score > one_violation.risk_score

    def test_analyze_recommendation_thresholds(self):
        """Test recommendation thresholds."""
        # This should be APPROVE
        safe = self.constitution.analyze("How's the weather?")
        assert safe.recommendation == RecommendationType.APPROVE

        # This should be REVIEW or FLAG
        risky = self.constitution.analyze("I love you")
        assert risky.recommendation in [RecommendationType.REVIEW, RecommendationType.FLAG]

    def test_analyze_normalized_text_stored(self):
        """Test that normalized text is stored in result."""
        result = self.constitution.analyze("I LÖVE YOÜ!")

        assert result.normalized_text is not None
        assert result.normalized_text != "I LÖVE YOÜ!"
        assert "loveyou" in result.normalized_text.lower()

    def test_analyze_flags_format(self):
        """Test that flags are properly formatted."""
        result = self.constitution.analyze("I love you baby")

        if result.flags:
            for flag in result.flags:
                assert ":" in flag  # Should be in format "TYPE:value"
                assert flag.startswith(("KEYWORD:", "PATTERN:"))

    def test_backward_compatibility(self):
        """Test that original validate method still works."""
        # The old validate method should still work
        assert self.constitution.validate("Hello!") is True
        assert self.constitution.validate("I love you") is False
