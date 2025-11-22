import asyncio
from typing import Dict

from config import settings

real_ids: Dict[int, int] = {}

support_real_ids: Dict[int, int] = {}


def remember_user(fake_id: int, real_tg_id: int) -> None:
    real_ids[fake_id] = real_tg_id


def remember_support_user(fake_id: int, real_tg_id: int) -> None:
    support_real_ids[fake_id] = real_tg_id


def forget_support_user(fake_id: int) -> None:
    support_real_ids.pop(fake_id, None)


def get_real_id(fake_id: int) -> int | None:
    return real_ids.get(fake_id) or support_real_ids.get(fake_id)


async def clean_memory():
    while True:
        await asyncio.sleep(settings.MEMORY_CLEAN_INTERVAL_HOURS * 3600)
        real_ids.clear()


def start_schedulers():
    asyncio.create_task(clean_memory())
