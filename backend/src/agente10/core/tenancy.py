"""Tenant scoping helper for RLS.

Use inside an active transaction. The setting is reverted on commit/rollback,
so the tenant context never leaks across transactions or pool connections.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@asynccontextmanager
async def tenant_context(
    session: AsyncSession, tenant_id: UUID | str
) -> AsyncIterator[AsyncSession]:
    """Scope subsequent queries to the given tenant via PostgreSQL RLS.

    Must be called inside an active transaction (e.g., ``async with session.begin():``).
    Uses ``set_config(name, value, is_local=true)`` which is transaction-scoped —
    same semantics as ``SET LOCAL`` but supports parameter binding via asyncpg.
    """
    await session.execute(
        text("SELECT set_config('app.current_tenant_id', :tid, true)"),
        {"tid": str(tenant_id)},
    )
    yield session
