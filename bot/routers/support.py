from datetime import datetime

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from config import settings
from db.base import async_session
from db.models import SupportTicket, User
from db.repo_users import get_or_create_user
from security.memory_store import remember_support_user, forget_support_user, get_real_id

router = Router(name="support")


@router.message(Command("support"))
async def cmd_support(message: Message):
    real_id = message.from_user.id
    user = await get_or_create_user(real_id)

    remember_support_user(user.fake_id, real_id)

    async with async_session() as session:
        ticket = SupportTicket(user_id=user.id, is_open=True)
        session.add(ticket)
        await session.commit()
        await session.refresh(ticket)

    await message.answer("Опишите вашу проблему. Наши администраторы скоро ответят вам.")

    text_admin = f"""📩 Обращение в поддержку
FAKE ID: {user.fake_id}
Ticket ID: {ticket.id}
"""

    for admin_id in settings.ADMINS:
        try:
            await message.bot.send_message(admin_id, text_admin)
        except Exception:
            pass


@router.callback_query(F.data == "support_close_user")
async def support_close_user(call: CallbackQuery):
    await call.answer("Обращение закрыто")

    real_id = call.from_user.id
    user = await get_or_create_user(real_id)

    async with async_session() as session:
        from sqlalchemy import select

        q = select(SupportTicket).where(
            SupportTicket.user_id == user.id,
            SupportTicket.is_open.is_(True)
        )
        res = await session.execute(q)
        tickets = res.scalars().all()

        if not tickets:
            await call.message.edit_text(
                "У вас нет активных обращений.",
                reply_markup=None
            )
            return

        for t in tickets:
            t.is_open = False
            t.closed_at = datetime.utcnow()

        await session.commit()

    forget_support_user(user.fake_id)

    try:
        await call.message.edit_text(
            "Ваше обращение закрыто.\n"
            "Если появятся новые вопросы — вы можете снова открыть поддержку.",
            reply_markup=None
        )
    except Exception:
        await call.message.answer(
            "Ваше обращение закрыто.\n"
            "Если появятся новые вопросы — вы можете снова открыть поддержку."
        )


@router.message(Command("close"), F.reply_to_message)
async def cmd_close_ticket(message: Message):
    if message.from_user.id not in settings.ADMINS:
        return

    replied = message.reply_to_message
    if not replied:
        return

    fake_id = None
    if replied.text:
        for word in replied.text.split():
            if word.isdigit() and len(word) == 8:
                fake_id = int(word)
                break

    if not fake_id:
        await message.answer("Не удалось определить FAKE ID.")
        return

    async with async_session() as session:
        from sqlalchemy import select

        q = select(User).where(User.fake_id == fake_id)
        res = await session.execute(q)
        user = res.scalars().first()

        if not user:
            await message.answer("Пользователь не найден.")
            return

        q2 = select(SupportTicket).where(
            SupportTicket.user_id == user.id,
            SupportTicket.is_open.is_(True),
        )
        res2 = await session.execute(q2)
        tickets = res2.scalars().all()

        for t in tickets:
            t.is_open = False
            t.closed_at = datetime.utcnow()

        await session.commit()

    forget_support_user(fake_id)

    await message.answer(f"Тикет пользователя {fake_id} закрыт.")


@router.message()
async def support_messages(message: Message):
    if message.from_user.id in settings.ADMINS and message.reply_to_message:
        replied = message.reply_to_message

        fake_id = None
        if replied.text:
            for word in replied.text.split():
                if word.isdigit() and len(word) == 8:
                    fake_id = int(word)
                    break

        if not fake_id:
            return

        real_id = get_real_id(fake_id)
        if not real_id:
            await message.answer("Не удалось доставить сообщение: real ID очищен.")
            return

        try:
            await message.bot.send_message(real_id, message.text or "")
        except Exception:
            pass

        return

    if message.text and not message.text.startswith("/"):
        real_id = message.from_user.id
        user = await get_or_create_user(real_id)

        if get_real_id(user.fake_id) is None:
            return

        async with async_session() as session:
            from sqlalchemy import select

            q = select(SupportTicket).where(
                SupportTicket.user_id == user.id,
                SupportTicket.is_open.is_(True),
            )
            res = await session.execute(q)
            ticket = res.scalars().first()

            if not ticket:
                ticket = SupportTicket(user.id, is_open=True)
                session.add(ticket)

            ticket.last_message = message.text
            await session.commit()
            await session.refresh(ticket)

        text_admin = f"""🆘 Сообщение в поддержку
FAKE ID: {user.fake_id}
Ticket ID: {ticket.id}

{message.text}
"""

        for admin_id in settings.ADMINS:
            try:
                await message.bot.send_message(admin_id, text_admin)
            except Exception:
                pass

        await message.answer("Ваше сообщение отправлено в поддержку ✅")
