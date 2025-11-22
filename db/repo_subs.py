from datetime import datetime, timedelta

from sqlalchemy import select, update
from db.base import async_session
from db.models import Subscription, User
from services.xui_client import create_client_inf, create_client_for_user

async def get_user_last_subscription(user_id: int):
    async with async_session() as session:
        q = (
            select(Subscription)
            .where(Subscription.user_id == user_id)
            .order_by(Subscription.id.desc())
            .limit(1)
        )
        res = await session.execute(q)
        return res.scalar_one_or_none()

async def deactivate_user_subscriptions(user_id: int):
    """
    Полностью деактивирует все подписки пользователя.
    Используется при возврате средств или выдаче новой INFINITE.
    """
    async with async_session() as session:
        await session.execute(
            update(Subscription)
            .where(Subscription.user_id == user_id)
            .values(active=False)
        )
        await session.commit()

async def create_subscription(user_id: int, days: int):
    async with async_session() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one()

        xui = await create_client_for_user(user.fake_id, days=days)

        sub = Subscription(
            user_id=user_id,
            active=True,
            expires_at=datetime.utcnow() + timedelta(days=days),
            xui_client_id=xui["uuid"],
            xui_email=xui["email"],
            xui_config=xui["vless"],
            created_at=datetime.utcnow(),
        )

        session.add(sub)
        await session.commit()
        await session.refresh(sub)
        return sub


async def create_subscription_inf(user_id: int, fake_id: int):
    async with async_session() as session:

        await session.execute(
            update(Subscription)
            .where(Subscription.user_id == user_id)
            .values(active=False)
        )

        xui = await create_client_inf(fake_id)

        new_sub = Subscription(
            user_id=user_id,
            active=True,
            expires_at=None,
            xui_client_id=xui["uuid"],
            xui_email=xui["email"],
            xui_config=xui["vless"],
            created_at=datetime.utcnow(),
        )

        session.add(new_sub)
        await session.commit()
        await session.refresh(new_sub)
        return new_sub
