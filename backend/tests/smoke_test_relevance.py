"""
Smoke tests for the LLM relevance classifier and content validation gates.

Run from the backend/ directory:
    pytest tests/smoke_test_relevance.py -v

To also run the live-LLM test (requires Ollama or GROQ_API_KEY configured):
    pytest tests/smoke_test_relevance.py -v -m "not live_llm"   # skip live
    pytest tests/smoke_test_relevance.py -v                      # run all
"""

import pytest
from unittest.mock import patch, MagicMock

# ---------------------------------------------------------------------------
# Sample transcripts
# ---------------------------------------------------------------------------

RELEVANT_TRANSCRIPT = """
Good afternoon everyone. Today I'm here to present our SaaS product that helps
sales teams close 40% more deals. Our platform integrates with Salesforce and
HubSpot to surface buying signals in real time. We've already onboarded 120
enterprise clients with an average contract value of $48,000. I'd like to walk
you through a quick demo and then discuss pricing options that fit your budget.
"""

IRRELEVANT_TRANSCRIPT = """
So today in our history class we'll be covering the causes of the First World War.
The alliance system, militarism, imperialism, and nationalism were all contributing
factors. Archduke Franz Ferdinand was assassinated in Sarajevo in 1914. This
triggered a chain of events that led to a global conflict. Please read chapters
five and six before next Tuesday's lecture.
"""

SHORT_TRANSCRIPT = "Hello world."  # too short

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_analyzer(llm_response: str = None, backend: str = "anthropic"):
    """Return a ContentAnalyzer whose _llm_generate is mocked."""
    from app.analyzers.content import ContentAnalyzer
    analyzer = ContentAnalyzer()
    analyzer._llm_backend = backend
    analyzer._llm_client = MagicMock() if backend == "ollama" else None
    analyzer._anthropic_client = MagicMock() if backend == "anthropic" else None
    analyzer._groq_client = MagicMock() if backend == "groq" else None

    if llm_response is not None:
        analyzer._llm_generate = MagicMock(return_value=llm_response)
    else:
        analyzer._llm_generate = MagicMock(return_value=None)

    return analyzer


# ---------------------------------------------------------------------------
# classify_relevance() unit tests
# ---------------------------------------------------------------------------

class TestClassifyRelevance:

    def test_relevant_transcript_returns_true(self):
        llm_json = '{"is_relevant": true, "confidence": 0.95, "reason": "Classic sales pitch with pricing and demo"}'
        analyzer = _make_analyzer(llm_json)
        result = analyzer.classify_relevance(RELEVANT_TRANSCRIPT)
        assert result["is_relevant"] is True
        assert result["confidence"] == pytest.approx(0.95)
        assert "reason" in result

    def test_irrelevant_transcript_returns_false(self):
        llm_json = '{"is_relevant": false, "confidence": 0.91, "reason": "Educational lecture with no commercial intent"}'
        analyzer = _make_analyzer(llm_json)
        result = analyzer.classify_relevance(IRRELEVANT_TRANSCRIPT)
        assert result["is_relevant"] is False
        assert result["confidence"] == pytest.approx(0.91)

    def test_llm_unavailable_defaults_to_relevant(self):
        """When LLM returns None (failure/timeout), we default to relevant."""
        analyzer = _make_analyzer(llm_response=None)
        result = analyzer.classify_relevance(RELEVANT_TRANSCRIPT)
        assert result["is_relevant"] is True
        assert result["confidence"] == pytest.approx(0.5)

    def test_no_backend_skips_check(self):
        """When no backend is configured, check is skipped with confidence=0."""
        from app.analyzers.content import ContentAnalyzer
        analyzer = ContentAnalyzer()
        analyzer._llm_backend = "none"
        result = analyzer.classify_relevance(RELEVANT_TRANSCRIPT)
        assert result["is_relevant"] is True
        assert result["confidence"] == pytest.approx(0.0)
        assert "skipped" in result["reason"].lower() or "no llm" in result["reason"].lower()

    def test_malformed_json_defaults_to_relevant(self):
        """Malformed LLM output should not crash and should default to relevant."""
        analyzer = _make_analyzer("not json at all !!!!")
        result = analyzer.classify_relevance(RELEVANT_TRANSCRIPT)
        assert result["is_relevant"] is True

    def test_partial_json_parsed_correctly(self):
        """LLM sometimes wraps JSON in prose — regex extraction should handle it."""
        llm_response = 'Sure! Here is the answer: {"is_relevant": false, "confidence": 0.88, "reason": "Random chatter"}'
        analyzer = _make_analyzer(llm_response)
        result = analyzer.classify_relevance(RELEVANT_TRANSCRIPT)
        assert result["is_relevant"] is False
        assert result["confidence"] == pytest.approx(0.88)

    def test_result_keys_always_present(self):
        """Return dict must always have the three expected keys."""
        for llm_out in [
            '{"is_relevant": true, "confidence": 0.9, "reason": "ok"}',
            None,
            "broken output",
        ]:
            analyzer = _make_analyzer(llm_out)
            result = analyzer.classify_relevance(RELEVANT_TRANSCRIPT)
            assert "is_relevant" in result
            assert "confidence" in result
            assert "reason" in result


# ---------------------------------------------------------------------------
# analyze() integration tests — gate enforcement
# ---------------------------------------------------------------------------

class TestAnalyzeRelevanceGate:

    def test_gate_disabled_skips_llm_call(self):
        """When relevance_check_enabled=False, _llm_generate must not be called for classification."""
        from app.analyzers.content import ContentAnalyzer
        analyzer = ContentAnalyzer()
        analyzer._llm_backend = "groq"
        analyzer._llm_generate = MagicMock(return_value=None)

        with patch("app.analyzers.content.settings") as mock_settings:
            mock_settings.relevance_check_enabled = False
            mock_settings.min_transcript_words = 0
            result = analyzer.analyze(RELEVANT_TRANSCRIPT, [])

        # _llm_generate may be called for key_points/feedback but NOT for relevance
        # so there must be no "relevance" key in the result
        assert "relevance" not in result

    def test_gate_enabled_relevant_content_passes(self):
        """Relevant content with gate enabled should return a full analysis result."""
        llm_json = '{"is_relevant": true, "confidence": 0.97, "reason": "Sales demo"}'
        analyzer = _make_analyzer(llm_json)

        with patch("app.analyzers.content.settings") as mock_settings:
            mock_settings.relevance_check_enabled = True
            mock_settings.min_transcript_words = 0
            result = analyzer.analyze(RELEVANT_TRANSCRIPT, [])

        assert result["relevance"]["is_relevant"] is True
        assert "overall_score" in result

    def test_gate_enabled_irrelevant_content_raises(self):
        """Irrelevant content should raise ContentNotRelevantError."""
        from app.core.exceptions import ContentNotRelevantError
        llm_json = '{"is_relevant": false, "confidence": 0.93, "reason": "History lecture"}'
        analyzer = _make_analyzer(llm_json)

        with patch("app.analyzers.content.settings") as mock_settings:
            mock_settings.relevance_check_enabled = True
            mock_settings.min_transcript_words = 0
            with pytest.raises(ContentNotRelevantError) as exc_info:
                analyzer.analyze(IRRELEVANT_TRANSCRIPT, [])

        assert exc_info.value.code == "CONTENT_NOT_RELEVANT"
        assert "History lecture" in exc_info.value.details.get("reason", "")

    def test_gate_enabled_llm_failure_does_not_block(self):
        """If LLM fails during relevance check, analysis must still complete."""
        analyzer = _make_analyzer(llm_response=None)  # LLM returns nothing

        with patch("app.analyzers.content.settings") as mock_settings:
            mock_settings.relevance_check_enabled = True
            mock_settings.min_transcript_words = 0
            result = analyzer.analyze(RELEVANT_TRANSCRIPT, [])

        # default fallback is relevant=True, so analysis should proceed
        assert "overall_score" in result

    def test_empty_transcript_returns_empty_result(self):
        """Empty transcript must short-circuit before any LLM call."""
        from app.analyzers.content import ContentAnalyzer
        analyzer = ContentAnalyzer()
        analyzer._llm_generate = MagicMock(return_value=None)

        with patch("app.analyzers.content.settings") as mock_settings:
            mock_settings.relevance_check_enabled = True
            mock_settings.min_transcript_words = 0
            result = analyzer.analyze("", [])

        assert result["overall_score"] == 0
        analyzer._llm_generate.assert_not_called()


# ---------------------------------------------------------------------------
# Live-LLM smoke test — skipped unless a backend is actually reachable
# ---------------------------------------------------------------------------

@pytest.mark.live_llm
class TestLiveLLMRelevance:
    """
    These tests make real LLM calls.
    They are skipped automatically when no backend is configured.
    Run explicitly with:  pytest tests/smoke_test_relevance.py -v -m live_llm
    """

    @pytest.fixture(autouse=True)
    def skip_if_no_backend(self):
        from app.analyzers.content import ContentAnalyzer
        analyzer = ContentAnalyzer()
        _ = analyzer.llm_client  # trigger backend detection
        if analyzer._llm_backend == "none":
            pytest.skip("No LLM backend configured (set OLLAMA or GROQ_API_KEY)")

    def test_live_relevant_transcript(self):
        from app.analyzers.content import ContentAnalyzer
        analyzer = ContentAnalyzer()
        result = analyzer.classify_relevance(RELEVANT_TRANSCRIPT)
        assert result["is_relevant"] is True, f"Expected relevant. Reason: {result['reason']}"

    def test_live_irrelevant_transcript(self):
        from app.analyzers.content import ContentAnalyzer
        analyzer = ContentAnalyzer()
        result = analyzer.classify_relevance(IRRELEVANT_TRANSCRIPT)
        assert result["is_relevant"] is False, f"Expected irrelevant. Reason: {result['reason']}"
