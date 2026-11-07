"""Tests for the Memory Service."""

import pytest
import uuid
import json

from app.services.memory_service import MemoryService, get_memory_service
from app.models.memory import (
    SessionMemory,
    ProjectMemory,
    LongTermPreference,
    ContextRetrieval,
    ProjectUnderstanding,
)


def unique_user():
    """Generate unique user ID for test isolation."""
    return f"user_{uuid.uuid4().hex[:8]}"


class TestSessionMemory:
    """Tests for session-level memory."""

    @pytest.fixture
    def service(self, isolated_service_db):
        return MemoryService()

    @pytest.mark.asyncio
    async def test_set_and_get_session_memory(self, service):
        """Test setting and retrieving session memory."""
        memory = await service.set_session_memory("test_key", value="test_value")
        assert memory.key == "test_key"
        assert memory.value == "test_value"

        retrieved = await service.get_session_memory("test_key")
        assert retrieved is not None
        assert retrieved.value == "test_value"

    @pytest.mark.asyncio
    async def test_session_memory_with_data(self, service):
        """Test session memory with JSON data."""
        data = {"foo": "bar", "nested": {"key": "value"}}
        memory = await service.set_session_memory("json_key", data=data)
        assert memory.data == data

    @pytest.mark.asyncio
    async def test_update_session_memory(self, service):
        """Test updating existing session memory."""
        await service.set_session_memory("update_key", value="old")
        memory = await service.set_session_memory("update_key", value="new")
        assert memory.value == "new"

    @pytest.mark.asyncio
    async def test_delete_session_memory(self, service):
        """Test deleting session memory."""
        await service.set_session_memory("delete_key", value="value")
        success = await service.delete_session_memory("delete_key")
        assert success is True

        memory = await service.get_session_memory("delete_key")
        assert memory is None

    @pytest.mark.asyncio
    async def test_list_session_memories(self, service):
        """Test listing all session memories."""
        await service.set_session_memory("list_key1", value="val1")
        await service.set_session_memory("list_key2", value="val2")

        memories = await service.list_session_memories()
        assert len(memories) >= 2


class TestProjectMemory:
    """Tests for project-level memory."""

    @pytest.fixture
    def service(self, isolated_service_db):
        return MemoryService()

    @pytest.mark.asyncio
    async def test_set_and_get_project_memory(self, service):
        """Test setting and retrieving project memory."""
        memory = await service.set_project_memory(1, "project_key", value="proj_value")
        assert memory.project_id == 1
        assert memory.key == "project_key"
        assert memory.value == "proj_value"

        retrieved = await service.get_project_memory(1, "project_key")
        assert retrieved is not None
        assert retrieved.value == "proj_value"

    @pytest.mark.asyncio
    async def test_project_memory_with_importance(self, service):
        """Test project memory with importance level."""
        memory = await service.set_project_memory(1, "important_key", importance=100)
        assert memory.importance == 100

    @pytest.mark.asyncio
    async def test_delete_project_memory(self, service):
        """Test deleting project memory."""
        await service.set_project_memory(99, "del_key_99", value="value_del_99")
        success = await service.delete_project_memory(99, "del_key_99")
        assert success is True


class TestLongTermPreference:
    """Tests for long-term preferences."""

    @pytest.fixture
    def service(self, isolated_service_db):
        return MemoryService()

    @pytest.mark.asyncio
    async def test_set_and_get_preference(self, service):
        """Test setting and retrieving preferences."""
        user = unique_user()
        pref = await service.set_preference(user, "editor", "theme", value="dark")
        assert pref.user_id == user
        assert pref.category == "editor"
        assert pref.key == "theme"
        assert pref.value == "dark"
        assert pref.scope == "global"

        retrieved = await service.get_preference(user, "editor", "theme")
        assert retrieved is not None
        assert retrieved.value == "dark"

    @pytest.mark.asyncio
    async def test_preference_scopes(self, service):
        """Test different scope options."""
        user = unique_user()
        await service.set_preference(user, "llm", "model", value="gpt-4", scope="global")
        await service.set_preference(user, "llm", "model", value="gpt-4o", scope="project")

        global_pref = await service.get_preference(user, "llm", "model")
        assert global_pref.scope == "project"  # More specific wins

    @pytest.mark.asyncio
    async def test_list_preferences(self, service):
        """Test listing preferences."""
        user = unique_user()
        await service.set_preference(user, "editor", "font", value="monospace")
        await service.set_preference(user, "llm", "provider", value="openai")

        prefs = await service.list_preferences(user)
        assert len(prefs) >= 2

    @pytest.mark.asyncio
    async def test_list_preferences_by_category(self, service):
        """Test listing preferences filtered by category."""
        user = unique_user()
        await service.set_preference(user, "editor", "font_unique", value="mono_unique")
        await service.set_preference(user, "llm", "provider_unique", value="openai_unique")

        editor_prefs = await service.list_preferences(user, category="editor")
        assert len(editor_prefs) == 1
        assert editor_prefs[0].key == "font_unique"


class TestContextRetrieval:
    """Tests for context retrieval history."""

    @pytest.fixture
    def service(self, isolated_service_db):
        return MemoryService()

    @pytest.mark.asyncio
    async def test_record_context_retrieval(self, service):
        """Test recording a context retrieval."""
        results = {"hits": [{"id": 1, "score": 0.9}]}
        record = await service.record_context_retrieval(
            "test_query_retrieval", results, similarity=0.95
        )
        assert record.query == "test_query_retrieval"
        assert record.similarity == "0.95"
        assert record.used is False

    @pytest.mark.asyncio
    async def test_mark_retrieval_as_used(self, service):
        """Test marking a retrieval as used."""
        record = await service.record_context_retrieval("query_mark", {"hits": []})
        success = await service.mark_retrieval_as_used(record.id)
        assert success is True

    @pytest.mark.asyncio
    async def test_get_recent_context_retrievals(self, service):
        """Test getting recent retrievals."""
        for i in range(5):
            await service.record_context_retrieval(f"query_recent_{i}", {"hits": []})

        recent = await service.get_recent_context_retrievals(limit=3)
        assert len(recent) == 3


class TestProjectUnderstanding:
    """Tests for project understanding."""

    @pytest.fixture
    def service(self, isolated_service_db):
        return MemoryService()

    @pytest.mark.asyncio
    async def test_set_and_get_project_understanding(self, service):
        """Test setting and retrieving project understanding."""
        project_id = 999  # Use unique project ID
        understanding = {
            "structure": {"src": "source", "tests": "test files"},
            "conventions": {"formatting": "black", "import_style": "google"},
            "important_files": ["main.py", "config.py"]
        }

        pu = await service.set_project_understanding(project_id, understanding, "Initial analysis")
        assert pu.project_id == project_id
        assert pu.understanding == understanding
        assert pu.update_reason == "Initial analysis"

        retrieved = await service.get_project_understanding(project_id)
        assert retrieved is not None
        assert retrieved.understanding == understanding

    @pytest.mark.asyncio
    async def test_update_project_understanding(self, service):
        """Test updating project understanding."""
        project_id = 1000  # Use unique project ID
        initial = {"initial_key": True, "another_key": "value"}
        await service.set_project_understanding(project_id, initial, "Initial setup")

        # Get fresh service to avoid singleton cache issues
        fresh_service = MemoryService()
        updated = await fresh_service.update_project_understanding(
            project_id, {"new_key_update": "new_value"}, "Added new insight"
        )
        assert updated is not None, "Failed to update project understanding"
        # Check that initial keys are still there
        assert "initial_key" in updated.understanding, "initial_key should persist"
        assert "another_key" in updated.understanding, "another_key should persist"
        # Check that new key was added
        assert "new_key_update" in updated.understanding, "new_key_update should be added"
        assert updated.understanding["new_key_update"] == "new_value"


class TestRecallProjectContext:
    """Tests for AI-powered context recall."""

    @pytest.fixture
    def service(self, isolated_service_db):
        return MemoryService()

    @pytest.mark.asyncio
    async def test_recall_project_context(self, service):
        """Test context recall with keyword matching."""
        project_id = 1111
        # Create some project memories
        await service.set_project_memory(project_id, "config", value="API configuration", importance=10)
        await service.set_project_memory(project_id, "db_schema", value="Database schema", importance=5)
        await service.set_project_memory(project_id, "other", value="Other data")

        result = await service.recall_project_context(project_id, "API", max_items=5)
        assert result["project_id"] == project_id
        assert result["query"] == "API"
        assert len(result["results"]) >= 1
        # Should find the "config" memory with "API" in value
        assert any(r["key"] == "config" for r in result["results"])


class TestMemoryServiceSingleton:
    """Tests for memory service singleton."""

    def test_get_memory_service_returns_singleton(self):
        """Test that get_memory_service returns a singleton."""
        service1 = get_memory_service()
        service2 = get_memory_service()
        assert service1 is service2

    def test_memory_service_has_session_id(self):
        """Test that memory service has session ID management."""
        service = MemoryService()
        sid = service.get_session_id()
        assert sid is not None
        assert isinstance(sid, str)