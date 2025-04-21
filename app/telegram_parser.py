import asyncio
from telethon import TelegramClient
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.types import User, Channel
from telethon.tl.functions.channels import JoinChannelRequest, LeaveChannelRequest
from telethon.errors import SessionPasswordNeededError, ChannelPrivateError
import pandas as pd
from datetime import datetime
import logging
import os
from dotenv import load_dotenv
import tempfile
import re

# Load environment variables
load_dotenv()

# Telegram API credentials
API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')

# Validate API credentials
if not API_ID or not API_HASH:
    raise ValueError("API_ID and API_HASH must be set in environment variables")

try:
    API_ID = int(API_ID)
except ValueError:
    raise ValueError("API_ID must be a number")

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TelegramParser:
    def __init__(self, parse_bio=False, parse_username=False, auto_join=True):
        self.api_id = API_ID
        self.api_hash = API_HASH
        self.client = None
        self.parse_bio = parse_bio
        self.parse_username = parse_username
        self.auto_join = auto_join
        # Используем постоянную директорию для сессии
        self.session_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'sessions')
        os.makedirs(self.session_dir, exist_ok=True)
        # Временная директория для файлов
        self.temp_dir = tempfile.mkdtemp()
        
    def _extract_channel_username(self, channel_link):
        """Извлекает юзернейм канала из разных форматов ссылок"""
        # Паттерны для разных форматов
        patterns = [
            r'@(\w+)',  # @username
            r't\.me/(\w+)',  # t.me/username или https://t.me/username
            r'telegram\.me/(\w+)',  # telegram.me/username
        ]
        
        for pattern in patterns:
            match = re.search(pattern, channel_link)
            if match:
                return '@' + match.group(1)
                
        # Если это ID канала
        if channel_link.startswith('-100'):
            return channel_link
            
        return channel_link
        
    async def _connect(self):
        """Устанавливает соединение с Telegram"""
        if not self.client:
            session_file = os.path.join(self.session_dir, 'user_session')
            self.client = TelegramClient(session_file, self.api_id, self.api_hash)
        
        if not self.client.is_connected():
            await self.client.connect()
            
        if not await self.client.is_user_authorized():
            logger.info("Требуется авторизация. Сессия будет сохранена для последующих запусков.")
            phone = input("Введите ваш номер телефона (в формате +7XXXXXXXXXX): ")
            await self.client.send_code_request(phone)
            try:
                code = input('Введите код, который пришел в Telegram: ')
                await self.client.sign_in(phone, code)
            except SessionPasswordNeededError:
                password = input('Введите пароль двухфакторной аутентификации: ')
                await self.client.sign_in(password=password)
            logger.info("Авторизация успешна!")
        
    async def join_channel(self, channel_entity):
        """Автоматически вступает в канал если нужно"""
        try:
            # Проверяем, являемся ли мы участником
            participants = await self.client.get_participants(channel_entity, limit=1)
            logger.info("Уже являемся участником канала")
            return True
        except Exception:
            if self.auto_join:
                try:
                    await self.client(JoinChannelRequest(channel_entity))
                    logger.info("Успешно вступили в канал")
                    return True
                except Exception as e:
                    logger.error(f"Не удалось вступить в канал: {str(e)}")
                    return False
            else:
                logger.error("Нет доступа к каналу и автоматическое вступление отключено")
                return False
        
    async def leave_channel(self, channel_entity):
        """Выходит из канала"""
        try:
            await self.client(LeaveChannelRequest(channel_entity))
            logger.info("Успешно вышли из канала")
        except Exception as e:
            logger.error(f"Ошибка при выходе из канала: {str(e)}")
            
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

            try:
                user_data = {
                    'user_id': user.id,
                    'first_name': user.first_name or '',
                    'last_name': user.last_name or '',
                    'username': user.username or '' if self.parse_username else '',
                    'bio': await self.get_user_bio(user) if self.parse_bio else ''
                }
                results.append(user_data)
            except Exception as e:
                logger.error(f"Error processing user {user.id}: {str(e)}")
                continue
            
        return results

    async def parse_channel(self, channel_link):
        try:
            # Подключаемся к Telegram
            await self._connect()
            
            # Обрабатываем ссылку на канал
            channel_link = self._extract_channel_username(channel_link)
            logger.info(f"Обрабатываем канал: {channel_link}")

            # Получаем информацию о канале
            try:
                channel = await self.client.get_entity(channel_link)
            except ValueError as e:
                raise ValueError(f"Не удалось найти канал {channel_link}: {str(e)}")
            except ChannelPrivateError:
                raise ValueError(f"Канал {channel_link} является приватным")
                
            if not isinstance(channel, Channel):
                raise ValueError(f"{channel_link} не является каналом")

            # Пробуем вступить в канал если нужно
            if not await self.join_channel(channel):
                raise ValueError("Не удалось получить доступ к каналу")

            try:
                # Получаем список участников
                users = []
                async for user in self.client.iter_participants(channel):
                    users.append(user)

                all_results = []
                batch_size = 50
                for i in range(0, len(users), batch_size):
                    batch = users[i:i + batch_size]
                    results = await self.process_users_batch(batch)
                    all_results.extend(results)
                    await asyncio.sleep(2)  # Delay between batches

                # Create DataFrame and save to Excel
                df = pd.DataFrame(all_results)
                channel_name = str(channel.id) if channel_link.startswith('-100') else channel_link.replace('@', '').replace('/', '_')
                timestamp = datetime.now().strftime("%Y%m%d_%H%M")
                filename = os.path.join(self.temp_dir, f'participants_{channel_name}_{timestamp}.xlsx')
                df.to_excel(filename, index=False)
                
                # Выходим из канала если автоматически вступали
                if self.auto_join:
                    await self.leave_channel(channel)
                
                return {
                    'success': True,
                    'filename': filename,
                    'total_users': len(all_results)
                }

            except Exception as e:
                # В случае ошибки тоже пытаемся выйти из канала
                if self.auto_join:
                    await self.leave_channel(channel)
                raise e

        except Exception as e:
            raise Exception(f"Ошибка при парсинге канала {channel_link}: {str(e)}")
        finally:
            if self.client and self.client.is_connected():
                await self.client.disconnect()
            
    def cleanup(self):
        """Clean up temporary files"""
        try:
            import shutil
            shutil.rmtree(self.temp_dir)
        except Exception as e:
            logger.error(f"Error cleaning up temporary files: {str(e)}") 