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

# Создаем директорию для файлов если её нет
os.makedirs("downloads", exist_ok=True)

class ParseRequest(BaseModel):
    channel: str
    parseBio: bool
    parseUsername: bool

class TelegramParser:
    def __init__(self):
        self.client = None
        
    async def init_client(self):
        if not self.client:
            self.client = TelegramClient('anon', API_ID, API_HASH)
            await self.client.start()
            
    async def close_client(self):
        if self.client:
            await self.client.disconnect()
            self.client = None
            
    async def parse_channel(self, channel_link: str, parse_bio: bool, parse_username: bool):
        try:
            await self.init_client()
            
            # Получаем информацию о канале
            channel = await self.client.get_entity(channel_link)
            if not isinstance(channel, Channel):
                raise HTTPException(status_code=400, detail="Указанная ссылка не является каналом")
                
            # Получаем участников канала
            participants = []
            async for user in self.client.iter_participants(channel):
                if isinstance(user, User):
                    user_data = {
                        'id': user.id,
                        'first_name': user.first_name,
                        'last_name': user.last_name if user.last_name else '',
                    }
                    
                    if parse_username:
                        user_data['username'] = user.username if user.username else ''
                        
                    if parse_bio:
                        try:
                            full_user = await self.client(GetFullUserRequest(user))
                            user_data['bio'] = full_user.full_user.about if full_user.full_user.about else ''
                        except Exception as e:
                            user_data['bio'] = ''
                            
                    participants.append(user_data)
                    
            # Создаем DataFrame и сохраняем в Excel
            df = pd.DataFrame(participants)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            filename = f"downloads/participants_{channel.username}_{timestamp}.xlsx"
            df.to_excel(filename, index=False)
            
            return filename
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            await self.close_client()

parser = TelegramParser()

@app.post("/api/parse")
async def parse_channel(request: ParseRequest):
    try:
        filename = await parser.parse_channel(
            request.channel,
            request.parseBio,
            request.parseUsername
        )
        return FileResponse(
            filename,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=os.path.basename(filename)
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

@app.get("/api/test")
async def test():
    return {"status": "ok"}

# Для статических файлов
app.mount("/", StaticFiles(directory="public", html=True), name="static") 