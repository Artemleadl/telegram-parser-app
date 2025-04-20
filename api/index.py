from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import os
from telethon import TelegramClient
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.types import User, Channel
import pandas as pd
from datetime import datetime
import asyncio
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Конфигурация
API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')

app = FastAPI()

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ParseRequest(BaseModel):
    channel: str
    parseBio: bool
    parseUsername: bool

class TelegramParser:
    def __init__(self):
        self.client = None
        
    async def init_client(self):
        if not self.client:
            self.client = TelegramClient('parser_session', API_ID, API_HASH)
            await self.client.start()

    async def get_user_bio(self, user):
        try:
            full_user = await self.client(GetFullUserRequest(user))
            return full_user.full_user.about or ''
        except Exception as e:
            return ''

    async def process_users_batch(self, users_batch, parse_bio, parse_username):
        results = []
        for user in users_batch:
            if not isinstance(user, User):
                continue

            user_data = {
                'user_id': user.id,
                'first_name': user.first_name or '',
                'last_name': user.last_name or '',
                'username': user.username or '' if parse_username else '',
                'bio': await self.get_user_bio(user) if parse_bio else ''
            }
            results.append(user_data)
        return results

    async def parse_channel(self, channel_link: str, parse_bio: bool, parse_username: bool):
        try:
            await self.init_client()
            channel = await self.client.get_entity(channel_link)
            
            if not isinstance(channel, Channel):
                raise HTTPException(status_code=400, detail="Указанная ссылка не является каналом")

            users = []
            async for user in self.client.iter_participants(channel):
                users.append(user)

            all_results = []
            batch_size = 50
            for i in range(0, len(users), batch_size):
                batch = users[i:i + batch_size]
                results = await self.process_users_batch(batch, parse_bio, parse_username)
                all_results.extend(results)
                await asyncio.sleep(2)

            # Создание Excel файла
            df = pd.DataFrame(all_results)
            channel_name = channel_link.replace('@', '').replace('/', '_')
            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            filename = f'/tmp/participants_{channel_name}_{timestamp}.xlsx'
            df.to_excel(filename, index=False)

            return filename

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

parser = TelegramParser()

@app.post("/api/parse")
async def parse_channel(request: ParseRequest):
    try:
        filename = await parser.parse_channel(
            request.channel,
            request.parseBio,
            request.parseUsername
        )
        
        response = FileResponse(
            filename,
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            filename=os.path.basename(filename)
        )
        
        # Удаляем файл после отправки
        asyncio.create_task(cleanup_file(filename))
        
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def cleanup_file(filename: str):
    await asyncio.sleep(5)  # Ждем 5 секунд перед удалением
    try:
        os.remove(filename)
    except:
        pass

@app.get("/api/test")
async def test():
    return JSONResponse({"status": "ok", "message": "API работает"})

# Для статических файлов
app.mount("/", StaticFiles(directory="public", html=True), name="static") 