from aiogram import Router, F, Bot
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    FSInputFile,
    PreCheckoutQuery,
)

from db.repo_users import get_or_create_user, get_user_by_fakeid
from db.repo_subs import (
    get_user_last_subscription,
    create_subscription_inf,
    create_subscription,
    deactivate_user_subscriptions,
)

from services.payments import TARIFFS, build_prices, handle_successful_payment
from services.payments_refund import refund_stars
from services.xui_client import delete_xui_client

from config import ADMINS, settings


router = Router()


def main_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Plus", callback_data="menu_plus")],
        [InlineKeyboardButton(text="Proxy", callback_data="menu_proxy")],
        [InlineKeyboardButton(text="Профиль", callback_data="menu_profile")],
        [InlineKeyboardButton(text="Support", callback_data="menu_support")],
    ])


def profile_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu_home")],
    ])


def proxy_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🔗 Подключиться",
            url=(
                "https://t.me/socks?"
                "server=37.114.37.147&port=33475&user=KynixVPN&pass=KynixVPNfreesocks5"
            )
        )],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_home")],
    ])


@router.message(F.text == "/start")
async def cmd_start(message: Message):
    user = await get_or_create_user(message.from_user.id)

    photo = FSInputFile("images/start.jpg")

    text = (
        "<b>Добро пожаловать в Kynix VPN 💜</b>\n\n"
        "<b>📦 Тарифный план:</b>\n\n"
        "<b>Plus</b>\n"
        "- Безлимитный трафик\n"
        "- 10 устройств\n"
        "- Цена: 100⭐ / месяц\n\n"
        f"Ваш Fake ID: <code>{user.fake_id}</code>"
    )

    await message.answer_photo(photo, caption=text, reply_markup=main_menu_kb())


@router.callback_query(F.data == "menu_plus")
async def menu_plus(call: CallbackQuery):
    await call.answer()

    photo = FSInputFile("images/plus.jpg")
    text = (
        "<b>Тариф Plus</b>\n\n"
        "- Безлимитный трафик\n"
        "- До 10 устройств\n"
        "- Приоритетная поддержка\n\n"
        "Нажатие на кнопку «Купить» или последующая покупка "
        "подразумевает согласие с:\n"
        "- <a href=\"https://telegra.ph/Politika-konfidencialnosti-Kynix-VPN-08-24\">Политикой конфиденциальности</a>\n"
        "- <a href=\"https://telegra.ph/Pravila-ispolzovaniya-servisa-Kynix-VPN-02-03\">Правилами использования</a>\n\n"
        "Цена: 100⭐ / месяц"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Купить", callback_data="menu_buy_plus")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu_home")],
    ])

    await call.message.answer_photo(photo, caption=text, reply_markup=kb)
    await call.message.delete()


@router.callback_query(F.data == "menu_proxy")
async def menu_proxy(call: CallbackQuery):
    await call.answer()

    photo = FSInputFile("images/proxy.jpg")

    text = (
        "<b>Бесплатный Telegram прокси от Kynix VPN</b>\n\n"
        "Только для Telegram, сайты через него не откроются.\n\n"
        "Мы не собираем ваши данные.\n\n"
        "Нажмите кнопку ниже 👇"
    )

    await call.message.answer_photo(photo, caption=text, reply_markup=proxy_menu_kb())
    await call.message.delete()


@router.callback_query(F.data == "menu_buy_plus")
async def menu_buy_plus(call: CallbackQuery):
    await call.answer()

    tariff = TARIFFS[0]

    await call.message.answer_invoice(
        title=f"Kynix VPN — {tariff.title}",
        description=tariff.description,
        payload="vpn_plus",
        provider_token="",
        currency="XTR",
        prices=build_prices(tariff),
    )


@router.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout_q: PreCheckoutQuery):
    await pre_checkout_q.answer(ok=True)


@router.message(F.successful_payment)
async def process_successful_payment(message: Message):
    user = await get_or_create_user(message.from_user.id)
    tariff = TARIFFS[0]

    await handle_successful_payment(
        bot=message.bot,
        message=message,
        user=user,
        tariff=tariff
    )


@router.callback_query(F.data == "menu_profile")
async def menu_profile(call: CallbackQuery):
    await call.answer()

    user = await get_or_create_user(call.from_user.id)
    sub = await get_user_last_subscription(user.id)

    sub_type = "Нет"
    expires = "Нет"

    if sub and sub.active:
        sub_type = "Infinite ♾️" if sub.expires_at is None else "Plus"
        if sub.expires_at:
            expires = sub.expires_at.strftime("%Y-%m-%d %H:%M")

    photo = FSInputFile("images/start.jpg")

    text = (
        "<b>Ваш профиль</b>\n\n"
        f"- FakeID: <code>{user.fake_id}</code>\n"
        f"- Тип подписки: {sub_type}\n"
        f"- Срок окончания: {expires}"
    )

    await call.message.answer_photo(photo, caption=text, reply_markup=profile_menu_kb())
    await call.message.delete()


@router.callback_query(F.data == "menu_support")
async def menu_support(call: CallbackQuery):
    await call.answer()

    photo = FSInputFile("images/support.jpg")
    text = "✉️ <b>Поддержка</b>\n\nМы всегда на связи 💜"

    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_home")]]
    )

    await call.message.answer_photo(photo, caption=text, reply_markup=kb)
    await call.message.delete()


@router.message(F.text.startswith("/inf"))
async def cmd_inf(message: Message):
    if message.from_user.id not in ADMINS:
        return await message.answer("❌ У вас нет прав.")

    parts = message.text.split()
    if len(parts) != 2:
        return await message.answer("Использование: /inf FAKE_ID")

    fake_id = int(parts[1])
    user = await get_user_by_fakeid(fake_id)

    if not user:
        return await message.answer("❌ Пользователь не найден.")

    sub = await create_subscription_inf(user.id, fake_id)

    return await message.answer(
        "🎁 Выдана <b>бессрочная подписка</b>!\n\n"
        f"<code>{sub.xui_config}</code>"
    )


@router.message(F.text.startswith("/refund"))
async def cmd_refund(message: Message):
    if message.from_user.id not in ADMINS:
        return await message.answer("❌ У вас нет прав.")

    parts = message.text.split()
    if len(parts) != 4:
        return await message.answer(
            "Использование:\n"
            "<code>/refund FAKE_ID REAL_ID CHARGE_ID</code>"
        )

    try:
        fake_id = int(parts[1])
        real_id = int(parts[2])
    except ValueError:
        return await message.answer("❌ FAKE_ID и REAL_ID должны быть числами.")

    charge_id = parts[3]

    user = await get_user_by_fakeid(fake_id)
    if not user:
        return await message.answer("❌ Пользователь с таким FAKE_ID не найден.")

    sub = await get_user_last_subscription(user.id)
    if not sub or not sub.active:
        return await message.answer("❌ У пользователя нет активной подписки.")

    if getattr(sub, "expires_at", None) is None:
        inbound_id = int(settings.XUI_INBOUND_ID_INF)
    else:
        inbound_id = int(settings.XUI_INBOUND_ID)

    try:
        await delete_xui_client(email=str(fake_id), inbound_id=inbound_id)
    except Exception as e:
        return await message.answer(
            "❌ Ошибка при удалении конфига в X-UI:\n"
            f"<code>{e}</code>"
        )

    await deactivate_user_subscriptions(user.id)

    result = await refund_stars(
        user_id=real_id,
        charge_id=charge_id
    )

    if result.get("ok"):
        return await message.answer(
            "✅ Возврат выполнен!\n"
            "- Конфиг удалён\n"
            "- Подписка деактивирована\n"
            "- Средства возвращены пользователю"
        )
    else:
        desc = result.get("description", "Неизвестная ошибка Telegram")
        return await message.answer(
            "❌ Telegram отклонил возврат:\n"
            f"<code>{desc}</code>"
        )


@router.callback_query(F.data == "menu_home")
async def menu_home(call: CallbackQuery):
    await call.answer()

    user = await get_or_create_user(call.from_user.id)
    photo = FSInputFile("images/start.jpg")

    text = (
        "<b>Добро пожаловать в Kynix VPN 💜</b>\n\n"
        "<b>Plus</b>\n"
        "- Безлимитный VPN\n"
        "- 10 устройств\n"
        "- Цена: 100⭐ / месяц\n\n"
        f"Ваш FakeID: <code>{user.fake_id}</code>"
    )

    await call.message.answer_photo(photo, caption=text, reply_markup=main_menu_kb())
    await call.message.delete()
