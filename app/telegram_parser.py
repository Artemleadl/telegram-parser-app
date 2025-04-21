import asyncio
from telethon import TelegramClient
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.types import User, Channel
import pandas as pd
from datetime import datetime
import logging

# Telegram API credentials
API_ID = '28355456'
API_HASH = '5abc8c86bf772fe864987b761289d974'

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TelegramParser:
    def __init__(self, parse_bio=False, parse_username=False):
        self.api_id = API_ID
        self.api_hash = API_HASH
        self.client = None
        self.parse_bio = parse_bio
        self.parse_username = parse_username
        
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

    async def parse_channel(self, channel_link):
        try:
            if not self.client:
                self.client = TelegramClient('parser_session', self.api_id, self.api_hash)
                await self.client.start()

            channel = await self.client.get_entity(channel_link)
            if not isinstance(channel, Channel):
                raise ValueError(f"{channel_link} не является каналом")

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
            channel_name = channel_link.replace('@', '').replace('/', '_')
            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            filename = f'participants_{channel_name}_{timestamp}.xlsx'
            df.to_excel(filename, index=False)
            
            await self.client.disconnect()
            return {
                'success': True,
                'filename': filename,
                'total_users': len(all_results)
            }

        except Exception as e:
            if self.client:
                await self.client.disconnect()
            raise Exception(f"Ошибка при парсинге канала {channel_link}: {str(e)}") 