import os
import asyncio
from telethon import TelegramClient, functions
from telethon.tl.functions.users import GetFullUserRequest, GetUsersRequest
from telethon.tl.types import User, Channel
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
import logging
import time

# Telegram API credentials
API_ID = '28355456'
API_HASH = '5abc8c86bf772fe864987b761289d974'

# Загрузка переменных окружения
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ConsoleParser:
    def __init__(self):
        self.api_id = API_ID
        self.api_hash = API_HASH
        self.client = None
        self.parse_bio = False
        self.parse_username = False
        
    def print_progress(self, current, total, status=''):
        bar_length = 50
        progress = float(current) / float(total)
        arrow = '=' * int(round(progress * bar_length) - 1) + '>'
        spaces = ' ' * (bar_length - len(arrow))
        print(f'\rПрогресс: [{arrow + spaces}] {int(progress * 100)}% {status}', end='', flush=True)
        
    async def get_user_bio_method1(self, user):
        try:
            full_user = await self.client(GetFullUserRequest(user))
            return full_user.full_user.about or ''
        except Exception as e:
            logger.debug(f"Method 1 failed for user {user.id}: {str(e)}")
            return None

    async def get_user_bio_method2(self, user):
        try:
            users = await self.client(GetUsersRequest([user.id]))
            if users and users[0].about:
                return users[0].about
        except Exception as e:
            logger.debug(f"Method 2 failed for user {user.id}: {str(e)}")
            return None

    async def get_user_bio_method3(self, user):
        try:
            if hasattr(user, 'about') and user.about:
                return user.about
        except Exception as e:
            logger.debug(f"Method 3 failed for user {user.id}: {str(e)}")
            return None

    async def get_user_bio(self, user):
        bio = None
        methods = [
            self.get_user_bio_method1,
            self.get_user_bio_method2,
            self.get_user_bio_method3
        ]
        
        for method in methods:
            bio = await method(user)
            if bio is not None:
                return bio
            await asyncio.sleep(0.5)  # Small delay between attempts
        
        return ''  # Return empty string if all methods fail

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

    async def parse_channel(self, channel_link):
        try:
            channel = await self.client.get_entity(channel_link)
            if not isinstance(channel, Channel):
                print(f"Ошибка: {channel_link} не является каналом")
                return

            print(f"\nПолучение участников из канала {channel.title}...")
            
            users = []
            async for user in self.client.iter_participants(channel):
                users.append(user)
                self.print_progress(len(users), len(users), f"Найдено пользователей: {len(users)}")

            print(f"\nНайдено пользователей: {len(users)}")
            print("Получение информации о пользователях...")

            all_results = []
            batch_size = 50
            for i in range(0, len(users), batch_size):
                batch = users[i:i + batch_size]
                results = await self.process_users_batch(batch)
                all_results.extend(results)
                self.print_progress(i + len(batch), len(users), f"Обработано пользователей: {i + len(batch)}")
                await asyncio.sleep(2)  # Delay between batches

            # Create DataFrame and save to Excel
            df = pd.DataFrame(all_results)
            channel_name = channel_link.replace('@', '').replace('/', '_')
            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            filename = f'participants_{channel_name}_{timestamp}.xlsx'
            df.to_excel(filename, index=False)
            print(f"\nДанные сохранены в файл: {filename}")

        except Exception as e:
            print(f"Ошибка при парсинге канала {channel_link}: {str(e)}")

    async def start(self):
        print("Введите ссылки на каналы Telegram (по одной на строку)")
        print("Примеры форматов:")
        print("  @channel_name")
        print("  t.me/channel_name")
        print("Нажмите Enter дважды, когда закончите ввод")

        channel_links = []
        while True:
            link = input().strip()
            if not link:
                break
            channel_links.append(link)

        if not channel_links:
            print("Не введено ни одной ссылки")
            return

        self.parse_bio = input("Парсить био пользователей? (y/n): ").lower() == 'y'
        self.parse_username = input("Парсить username пользователей? (y/n): ").lower() == 'y'

        print("\nАвторизация в Telegram...")
        self.client = TelegramClient('parser_session', self.api_id, self.api_hash)
        await self.client.start()

        for link in channel_links:
            await self.parse_channel(link)

        await self.client.disconnect()

if __name__ == '__main__':
    parser = ConsoleParser()
    asyncio.run(parser.start()) 