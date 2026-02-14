# ABOUTME: Unit tests for TraceMetadata dataclass.
# ABOUTME: Covers creation, defaults, auto-generation, and dict conversion.

import uuid

import pytest

from autobots_devtools_shared_lib.common.observability.trace_metadata import TraceMetadata


class TestTraceMetadataCreate:
    def test_create_with_all_params(self):
        """All fields are set correctly when provided."""
        tm = TraceMetadata.create(
            session_id="test-session",
            app_name="test-app",
            user_id="test-user",
            tags=["tag1", "tag2"],
        )
        assert tm.session_id == "test-session"
        assert tm.app_name == "test-app"
        assert tm.user_id == "test-user"
        assert tm.tags == ["tag1", "tag2"]

    def test_create_with_defaults(self):
        """Default values are applied when params not provided."""
        tm = TraceMetadata.create()
        assert tm.session_id  # Should be auto-generated
        assert tm.app_name == "default"
        assert tm.user_id == "default"
        assert tm.tags == []

    def test_create_auto_generates_session_id(self):
        """session_id is auto-generated as valid UUID if None."""
        tm = TraceMetadata.create()
        # Should be a valid UUID
        parsed = uuid.UUID(tm.session_id)
        assert parsed.version == 4

    def test_create_truncates_session_id_to_200_chars(self):
        """session_id is truncated to 200 characters for Langfuse limit."""
        long_id = "x" * 300
        tm = TraceMetadata.create(session_id=long_id)
        assert len(tm.session_id) == 200
        assert tm.session_id == "x" * 200

    def test_create_preserves_short_session_id(self):
        """session_id under 200 chars is not truncated."""
        short_id = "short-session-id"
        tm = TraceMetadata.create(session_id=short_id)
        assert tm.session_id == short_id


class TestTraceMetadataFromDict:
    def test_from_dict_with_all_fields(self):
        """Creates TraceMetadata from complete dict."""
        data = {
            "session_id": "dict-session",
            "app_name": "dict-app",
            "user_id": "dict-user",
            "tags": ["tag-a", "tag-b"],
        }
        tm = TraceMetadata.from_dict(data)
        assert tm.session_id == "dict-session"
        assert tm.app_name == "dict-app"
        assert tm.user_id == "dict-user"
        assert tm.tags == ["tag-a", "tag-b"]

    def test_from_dict_with_partial_fields(self):
        """Uses defaults for missing fields."""
        data = {"session_id": "partial-session"}
        tm = TraceMetadata.from_dict(data)
        assert tm.session_id == "partial-session"
        assert tm.app_name == "default"
        assert tm.user_id == "default"
        assert tm.tags == []

    def test_from_dict_with_none(self):
        """Creates with defaults when None is passed."""
        tm = TraceMetadata.from_dict(None)
        assert tm.app_name == "default"
        assert tm.user_id == "default"
        assert tm.tags == []
        # Session ID should be auto-generated
        assert tm.session_id
        uuid.UUID(tm.session_id)  # Should be valid UUID

    def test_from_dict_with_empty_dict(self):
        """Creates with defaults when empty dict is passed."""
        tm = TraceMetadata.from_dict({})
        assert tm.app_name == "default"
        assert tm.user_id == "default"
        assert tm.tags == []
        # Session ID should be auto-generated
        assert tm.session_id


class TestTraceMetadataToDict:
    def test_to_dict_contains_all_fields(self):
        """to_dict returns all fields as dict."""
        tm = TraceMetadata(
            session_id="test-session",
            app_name="test-app",
            user_id="test-user",
            tags=["tag1"],
        )
        result = tm.to_dict()
        assert result == {
            "session_id": "test-session",
            "app_name": "test-app",
            "user_id": "test-user",
            "tags": ["tag1"],
        }

    def test_to_dict_roundtrip(self):
        """Creating from dict and converting back preserves data."""
        original = {
            "session_id": "roundtrip-session",
            "app_name": "roundtrip-app",
            "user_id": "roundtrip-user",
            "tags": ["rt-tag"],
        }
        tm = TraceMetadata.from_dict(original)
        result = tm.to_dict()
        assert result == original


class TestTraceMetadataDirectConstruction:
    def test_direct_construction(self):
        """Can construct directly without create method."""
        tm = TraceMetadata(
            session_id="direct-session",
            app_name="direct-app",
            user_id="direct-user",
            tags=["direct-tag"],
        )
        assert tm.session_id == "direct-session"
        assert tm.app_name == "direct-app"
        assert tm.user_id == "direct-user"
        assert tm.tags == ["direct-tag"]

    def test_session_id_required_in_direct_construction(self):
        """session_id is required when constructing directly."""
        with pytest.raises(TypeError):
            TraceMetadata()  # Missing required session_id
