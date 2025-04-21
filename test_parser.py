import asyncio
from app.telegram_parser import TelegramParser
import logging

# Настраиваем логирование
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_parser():
    # Список каналов для теста
    channels_to_test = [
        "-1001751373900",  # Тестируем по ID
        "https://t.me/my_digital_nomad",  # Тестируем по ссылке
        "@my_digital_nomad"  # Тестируем по юзернейму
    ]
    
    parser = None
    try:
        # Создаем парсер с автоматическим вступлением
        parser = TelegramParser(
            parse_bio=True,
            parse_username=True,
            auto_join=True
        )
        
        # Тестируем каждый канал
        for channel in channels_to_test:
            logger.info(f"\n{'='*50}")
            logger.info(f"Тестируем канал: {channel}")
            try:
                result = await parser.parse_channel(channel)
                if result['success']:
                    logger.info(f"✅ Успешно получили {result['total_users']} участников")
                    logger.info(f"Файл сохранен: {result['filename']}")
                else:
                    logger.error(f"❌ Не удалось получить участников")
            except Exception as e:
                logger.error(f"❌ Ошибка при парсинге канала {channel}: {str(e)}")
            logger.info(f"{'='*50}\n")
                
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {str(e)}")
    finally:
        if parser:
            parser.cleanup()

if __name__ == "__main__":
    try:
        asyncio.run(test_parser())
    except KeyboardInterrupt:
        logger.info("\n⚠️ Тест прерван пользователем")
    except Exception as e:
        logger.error(f"\n❌ Неожиданная ошибка: {str(e)}") 