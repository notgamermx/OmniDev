"""Tests for shared session functionality."""

import pytest
import uuid

from app.services.shared_session_service import SharedSessionService


def unique_user():
    """Generate unique user ID for test isolation."""
    return f"user_{uuid.uuid4().hex[:8]}"


class TestSharedSessionService:
    """Tests for shared session management."""

    @pytest.fixture
    def service(self):
        return SharedSessionService()

    @pytest.mark.asyncio
    async def test_create_shared_session(self, service):
        """Test creating a shared session."""
        user = unique_user()
        session = await service.create_shared_session(
            owner_user_id=user,
            session_name="Test Session",
            project_id=1,
            permission="read"
        )
        assert session.session_id is not None
        assert session.owner_user_id == user
        assert session.session_name == "Test Session"
        assert session.is_active == True

    @pytest.mark.asyncio
    async def test_get_shared_session(self, service):
        """Test getting a shared session."""
        user = unique_user()
        created = await service.create_shared_session(
            owner_user_id=user,
            session_name="Get Test",
            expires_hours=1
        )

        retrieved = await service.get_shared_session(created.session_id)
        assert retrieved is not None
        assert retrieved.session_id == created.session_id

    @pytest.mark.asyncio
    async def test_list_user_sessions(self, service):
        """Test listing user sessions."""
        user = unique_user()
        await service.create_shared_session(user, session_name="Session 1")
        await service.create_shared_session(user, session_name="Session 2")

        sessions = await service.list_user_sessions(user)
        assert len(sessions) >= 2

    @pytest.mark.asyncio
    async def test_share_session(self, service):
        """Test sharing a session with others."""
        user = unique_user()
        session = await service.create_shared_session(owner_user_id=user)

        updated = await service.share_session(
            session.session_id,
            shared_with=[unique_user(), unique_user()],
            permission="write"
        )

        assert len(updated.shared_with) >= 2

    @pytest.mark.asyncio
    async def test_end_shared_session(self, service):
        """Test ending a shared session."""
        user = unique_user()
        session = await service.create_shared_session(owner_user_id=user)

        success = await service.end_shared_session(session.session_id)
        assert success is True

    @pytest.mark.asyncio
    async def test_join_session(self, service):
        """Test joining a session."""
        user = unique_user()
        session = await service.create_shared_session(owner_user_id=user)

        # Share with user
        await service.share_session(session.session_id, [unique_user()])

        membership = await service.join_session(
            session.session_id,
            unique_user(),
            role="viewer"
        )

        assert membership.session_id == session.session_id
        assert membership.user_id == unique_user()
        assert membership.role == "viewer"

    @pytest.mark.asyncio
    async def test_websocket_session_tracking(self, service):
        """Test WebSocket session tracking."""
        user = unique_user()
        session = await service.create_shared_session(owner_user_id=user)

        ws = await service.create_websocket_session(
            session.session_id,
            user,
            channels=["updates", "memory"]
        )

        assert ws.session_id == session.session_id
        assert ws.user_id == user
        assert "updates" in ws.channels
        assert ws.is_active == True

    @pytest.mark.asyncio
    async def test_record_session_access(self, service):
        """Test recording session access."""
        user = unique_user()
        session = await service.create_shared_session(owner_user_id=user)

        service.record_session_access(session.session_id, user)

        db_session = await service.get_shared_session(session.session_id)
        assert db_session.access_count == 1


class TestSharedSessionModels:
    """Tests for shared session model."""

    def test_shared_session_has_session_id(self):
        """Test SharedSession model."""
        from app.models.shared_session import SharedSession
        session = SharedSession(
            session_id="test_abc123",
            owner_user_id="user1"
        )
        assert session.session_id == "test_abc123"

    def test_membership_model(self):
        """Test SharedSessionMembership model."""
        from app.models.shared_session import SharedSessionMembership
        membership = SharedSessionMembership(
            session_id="test_abc123",
            user_id="user1",
            role="viewer"
        )
        assert membership.role == "viewer"