import aiogram

from main import bot, dp
from aiogram import Router, F
from aiogram import filters
from filters import *
from typing import List
from MyMiddleware import MyMiddleware
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from config import CHAT_ID, CHANEL_ID
from data_base import User, Messages

router = Router(name=__name__)

dp.include_router(router)
dp.message.middleware(MyMiddleware())


class Application(StatesGroup):
    create_application_state = State()


create_application_btn = KeyboardButton(text="Сделать заявку")
Keyboard = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[[create_application_btn]])


# команды пользователей
@dp.message(filters.Command(commands=['start']))
async def send_welcome(message: types.Message) -> None:
    try:
        User.get_or_create(tg_id=message.from_user.id)
        await message.answer(
            f"Привет {message.from_user.full_name}!\nЕсли хочешь написать пост, нажми на кнопку ниже. Если "
            f"хочешь написать админам, просто напиши сообщение боту.",
            reply_markup=Keyboard)
    except Exception as err:
        print(err)


# взаимодейсвие с чатом админов
@dp.message(filters.Command(commands=['mute']), TypeChatFilter("supergroup"), F.chat.id == CHAT_ID)
async def mute(message: types.Message) -> None:
    try:
        tg_id = int(message.text.split()[1])
        user = User.get(tg_id=tg_id)
        user.is_mute = True
        user.save()
        await message.answer("Пользователь в теперь муте")
    except Exception as err:
        print(err)
        await message.answer("Произошла ошибка")


@dp.message(filters.Command(commands=['unmute']), TypeChatFilter("supergroup"), F.chat.id == CHAT_ID)
async def unmute(message: types.Message) -> None:
    try:
        tg_id = int(message.text.split()[1])
        user = User.get(tg_id=tg_id)
        user.is_mute = False
        user.save()
        await message.answer("Пользователь теперь не в муте")
    except Exception as err:
        print(err)
        await message.answer("Произошла ошибка")


@dp.message(filters.Command(commands=['muted']), TypeChatFilter("supergroup"), F.chat.id == CHAT_ID)
async def list_of_muted(message: types.Message) -> None:
    try:
        text_to_send = 'Список дурачков:\n'
        users = User.select().where(User.is_mute == True)

        if not users:
            await message.answer('Дурачков нет')
            return

        for user in users:
            profile = await bot.get_chat_member(user.tg_id, user.tg_id)
            text_to_send += f"<a href='tg://user?id={user.tg_id}'>@{profile.user.username}</a> {profile.user.full_name} (#ID{user.tg_id})\n"
        await message.answer(text=text_to_send)

    except Exception as err:
        print(err)
        await message.answer("Произошла ошибка")


# Рассылка сообщений по всем чатам
@dp.message(filters.Command(commands=['send']), IsReplyMessage(), TypeChatFilter("supergroup"), F.chat.id == CHAT_ID)
async def send(message: types.Message) -> None:
    for user in User.select():
        try:
            await message.reply_to_message.copy_to(user.tg_id)
        except Exception as err:
            print(err)
            continue


# Ответ на сообщение
@dp.message(TypeChatFilter("supergroup"), F.chat.id == CHAT_ID, IsReplyMessage())
async def reply(message: types.Message, album: List[types.Message] = None) -> None:
    try:
        if message.reply_to_message.from_user.id == bot.id:
            msg = Messages.get(message_id=message.reply_to_message.message_id)
            user_id = msg.tg_id
            if message.media_group_id:
                media_group = []
                for msg in album:
                    if msg.photo:
                        file_id = msg.photo[-1].file_id
                        caption = msg.caption
                        media_group.append(types.InputMediaPhoto(media=file_id, caption=caption))
                    elif msg.video:
                        file_id = msg.video.file_id
                        caption = msg.caption
                        media_group.append(types.InputMediaVideo(media=file_id, caption=caption))
                await bot.send_media_group(user_id, media_group)
            else:
                await message.copy_to(user_id)
    except Exception as err:
        print(err)
        await message.answer("Произошла ошибка")


@dp.callback_query()
async def post(callback_query: types.CallbackQuery) -> None:
    try:
        i = int(callback_query.data)
        media_group = []
        await callback_query.message.delete_reply_markup()
        while True:
            msg = await bot.forward_message(CHAT_ID, CHAT_ID, i,
                                            disable_notification=True)
            if msg.photo:
                file_id = msg.photo[-1].file_id
                caption = msg.caption
                media_group.append(types.InputMediaPhoto(media=file_id, caption=caption))
            elif msg.video:
                file_id = msg.video.file_id
                caption = msg.caption
                media_group.append(types.InputMediaVideo(media=file_id, caption=caption))
            else:
                await msg.delete()
                break
            await msg.delete()
            i += 1
        if len(media_group) != 0:
            await bot.send_media_group(CHANEL_ID, media_group)
        else:
            await bot.copy_message(CHANEL_ID, CHAT_ID, i)
    except Exception as err:
        print(err)


# взаимодейсвие пользователей с ботом
@dp.message(TypeChatFilter(chat_type="private"), F.text == create_application_btn.text)
async def press_button(message: types.Message, state: FSMContext) -> None:
    await message.answer("Напиши свой пост для канала. Помни, что запрещён самопиар, посты про учителей, пост не "
                         "связанный с тематикой канала.")
    await state.set_state(Application.create_application_state)


@dp.message(TypeChatFilter(chat_type="private"), Application.create_application_state)
async def create_application(message: types.Message, state: FSMContext, album: List[types.Message] = None) -> None:
    try:
        user, is_create = User.get_or_create(tg_id=message.from_user.id)
        if not user.is_mute:
            if message.media_group_id:
                media_group = []
                for msg in album:
                    if msg.photo:
                        file_id = msg.photo[-1].file_id
                        caption = msg.caption
                        media_group.append(types.InputMediaPhoto(media=file_id, caption=caption))
                    elif msg.video:
                        file_id = msg.video.file_id
                        caption = msg.caption
                        media_group.append(types.InputMediaVideo(media=file_id, caption=caption))
                m = await bot.send_media_group(CHAT_ID, media_group)
                m = m[0]
                btn = InlineKeyboardButton(text="Разместить", callback_data=str(m.message_id))
            else:
                m = await message.copy_to(CHAT_ID)
                btn = InlineKeyboardButton(text="Разместить", callback_data=str(m.message_id))
            markup = InlineKeyboardMarkup(inline_keyboard=[[btn]])
            if album is not None:
                for i in range(len(album)):
                    Messages.create(tg_id=message.from_user.id, message_id=m.message_id + i)
            else:
                Messages.create(tg_id=message.from_user.id, message_id=m.message_id)
            await bot.send_message(CHAT_ID,
                                   f"<a href='tg://user?id={message.from_user.id}'>{message.from_user.full_name}</a>," + (
                                       f" @{message.from_user.username}," if message.from_user.username else "") + f" (#ID{message.from_user.id})",
                                   reply_markup=markup)
            await message.answer("Заявка принята, жди свою запись в канале 40 Глаз", reply_markup=Keyboard)
        else:
            await message.answer("Вы в муте")
        await state.clear()
    except Exception as err:
        print(err)
        await message.answer("Произошла ошибка")


@dp.message(TypeChatFilter(chat_type="private"))
async def send_message_for_admin(message: types.Message, album: List[types.Message] = None) -> None:
    try:
        user, is_create = User.get_or_create(tg_id=message.from_user.id)
        if is_create:
            await message.answer(
                "Мы обновились! Нажимай но кнопку снизу, если хочешь оставить заявку на пост в канале. Если хочешь "
                "написать админам, просто напиши сообщение боту.",
                reply_markup=Keyboard)
        else:
            if not user.is_mute:
                if message.media_group_id:
                    media_group = []
                    for msg in album:
                        if msg.photo:
                            file_id = msg.photo[-1].file_id
                            caption = msg.caption
                            media_group.append(types.InputMediaPhoto(media=file_id, caption=caption))
                        elif msg.video:
                            file_id = msg.video.file_id
                            caption = msg.caption
                            media_group.append(types.InputMediaVideo(media=file_id, caption=caption))
                    m = await bot.send_media_group(CHAT_ID, media_group)
                    m = m[0]
                else:
                    m = await message.copy_to(CHAT_ID)
                if album is not None:
                    for i in range(len(album)):
                        Messages.create(tg_id=message.from_user.id, message_id=m.message_id + i)
                else:
                    Messages.create(tg_id=message.from_user.id, message_id=m.message_id)
                await bot.send_message(CHAT_ID,
                                       f"<b>Сообщение от:</b>\n\n<a href='tg://user?id={message.from_user.id}'>{message.from_user.full_name}</a>," + (
                                           f" @{message.from_user.username}," if message.from_user.username else "") + f"(#ID{message.from_user.id})")
            else:
                await message.answer("Вы в муте")
    except Exception as err:
        print(err)
        await message.answer("Произошла ошибка")
