from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import os
from .telegram_parser import TelegramParser
import asyncio
import logging

app = FastAPI()

# Убедимся, что путь к статическим файлам существует
static_path = os.path.join(os.path.dirname(__file__), "static")
templates_path = os.path.join(os.path.dirname(__file__), "templates")

# Монтируем статические файлы, если директория существует
if os.path.exists(static_path):
    app.mount("/static", StaticFiles(directory=static_path), name="static")

# Настраиваем шаблоны
templates = Jinja2Templates(directory=templates_path)

# Модель для запроса парсинга
class ParseRequest(BaseModel):
    channel_link: str
    parse_bio: bool = False
    parse_username: bool = False

# Главная страница
@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# API эндпоинт для парсинга
@app.post("/api/parse")
async def parse_channel(request: ParseRequest):
    try:
        parser = TelegramParser(
            parse_bio=request.parse_bio,
            parse_username=request.parse_username
        )
        
        result = await parser.parse_channel(request.channel_link)
        
        if result['success']:
            # Отправляем файл пользователю
            file_path = result['filename']
            return FileResponse(
                path=file_path,
                filename=os.path.basename(file_path),
                media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
        else:
            raise HTTPException(status_code=400, detail=result.get('error', 'Unknown error'))
            
    except Exception as e:
        logging.error(f"Error during parsing: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Обработка ошибок
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "error": exc.detail}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 