import os
import asyncio
from telethon import TelegramClient, events, Button
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.types import User, Channel
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
import logging
import time
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация
BOT_TOKEN = os.getenv('BOT_TOKEN')  # Токен вашего бота
API_ID = '24185391'
API_HASH = '9c4e8e4e1a2e7e2f0d5e8e4e1a2e7e2f'

# Инициализация бота и хранилища состояний
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Определение состояний
class ParserStates(StatesGroup):
    waiting_for_channel = State()
    waiting_for_bio_choice = State()
    waiting_for_username_choice = State()

class TelegramParser:
    def __init__(self):
        self.client = None
        self.parse_bio = False
        self.parse_username = False

    async def init_client(self):
        if not self.client:
            self.client = TelegramClient('parser_session', API_ID, API_HASH)
            await self.client.start()

    async def get_user_bio(self, user):
        try:
            full_user = await self.client(GetFullUserRequest(user))
            return full_user.full_user.about or ''
        except Exception as e:
            logger.debug(f"Failed to get bio for user {user.id}: {str(e)}")
            return ''

    async def process_users_batch(self, users_batch):
        results = []
        for user in users_batch:
            if not isinstance(user, User):
                continue

            user_data = {
                'user_id': user.id,
                'first_name': user.first_name or '',
                'last_name': user.last_name or '',
                'username': user.username or '' if self.parse_username else '',
                'bio': await self.get_user_bio(user) if self.parse_bio else ''
            }
            results.append(user_data)
        return results

    async def parse_channel(self, channel_link, message: types.Message):
        try:
            await self.init_client()
            channel = await self.client.get_entity(channel_link)
            
            if not isinstance(channel, Channel):
                await message.answer("Ошибка: указанная ссылка не является каналом")
                return

            status_message = await message.answer(f"Получение участников из канала {channel.title}...")
            
            users = []
            async for user in self.client.iter_participants(channel):
                users.append(user)
                if len(users) % 50 == 0:
                    await status_message.edit_text(f"Найдено пользователей: {len(users)}")

            await status_message.edit_text(f"Найдено пользователей: {len(users)}\nПолучение информации о пользователях...")

            all_results = []
            batch_size = 50
            for i in range(0, len(users), batch_size):
                batch = users[i:i + batch_size]
                results = await self.process_users_batch(batch)
                all_results.extend(results)
                await status_message.edit_text(f"Обработано пользователей: {i + len(batch)} из {len(users)}")
                await asyncio.sleep(2)

            # Создание Excel файла
            df = pd.DataFrame(all_results)
            channel_name = channel_link.replace('@', '').replace('/', '_')
            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            filename = f'participants_{channel_name}_{timestamp}.xlsx'
            df.to_excel(filename, index=False)

            # Отправка файла
            await message.answer_document(
                types.InputFile(filename),
                caption="Готово! Вот результаты парсинга."
            )

            # Удаление временного файла
            os.remove(filename)

        except Exception as e:
            await message.answer(f"Произошла ошибка при парсинге канала: {str(e)}")

parser = TelegramParser()

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    await message.answer(
        "Привет! Я бот для парсинга участников Telegram каналов.\n"
        "Используйте команду /parse для начала парсинга."
    )

@dp.message_handler(commands=['parse'])
async def cmd_parse(message: types.Message):
    await ParserStates.waiting_for_channel.set()
    await message.answer(
        "Пожалуйста, отправьте ссылку на канал в формате:\n"
        "@channel_name или t.me/channel_name"
    )

@dp.message_handler(state=ParserStates.waiting_for_channel)
async def process_channel_link(message: types.Message, state: FSMContext):
    await state.update_data(channel_link=message.text)
    
    markup = InlineKeyboardMarkup().add(
        InlineKeyboardButton("Да", callback_data="bio_yes"),
        InlineKeyboardButton("Нет", callback_data="bio_no")
    )
    
    await ParserStates.waiting_for_bio_choice.set()
    await message.answer("Парсить био пользователей?", reply_markup=markup)

@dp.callback_query_handler(state=ParserStates.waiting_for_bio_choice)
async def process_bio_choice(callback_query: types.CallbackQuery, state: FSMContext):
    parser.parse_bio = callback_query.data == "bio_yes"
    
    markup = InlineKeyboardMarkup().add(
        InlineKeyboardButton("Да", callback_data="username_yes"),
        InlineKeyboardButton("Нет", callback_data="username_no")
    )
    
    await ParserStates.waiting_for_username_choice.set()
    await callback_query.message.edit_text("Парсить username пользователей?", reply_markup=markup)

@dp.callback_query_handler(state=ParserStates.waiting_for_username_choice)
async def process_username_choice(callback_query: types.CallbackQuery, state: FSMContext):
    parser.parse_username = callback_query.data == "username_yes"
    
    data = await state.get_data()
    channel_link = data.get('channel_link')
    
    await state.finish()
    await callback_query.message.edit_text("Начинаю парсинг...")
    await parser.parse_channel(channel_link, callback_query.message)

async def main():
    await dp.start_polling()

if __name__ == '__main__':
    asyncio.run(main()) 