from telethon import TelegramClient
import asyncio
import os
from dotenv import load_dotenv
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.types import PeerChannel

async def test_connection():
    # Загружаем переменные окружения
    load_dotenv(override=True)
    
    # Проверяем все переменные окружения
    print("\nПроверка всех переменных окружения:")
    for key in os.environ:
        if 'API' in key:
            print(f"{key}: {os.environ[key]}")
    
    api_id = os.getenv('API_ID')
    api_hash = os.getenv('API_HASH')
    
    print(f"\nЗначения для подключения:")
    print(f"API_ID: {api_id}")
    print(f"API_HASH: {api_hash}")
    
    try:
        # Создаем клиент
        client = TelegramClient('test_session', int(api_id), api_hash)
        
        # Пробуем подключиться
        print("\nПытаемся подключиться к Telegram...")
        await client.connect()
        
        # Проверяем авторизацию
        if not await client.is_user_authorized():
            print("Требуется авторизация. Сейчас придет код на ваш Telegram.")
            phone = input("Введите ваш номер телефона (в формате +7XXXXXXXXXX): ")
            await client.send_code_request(phone)
            code = input('Введите код, который пришел в Telegram: ')
            await client.sign_in(phone, code)
        
        # Проверяем успешность авторизации
        if await client.is_user_authorized():
            print("✅ Успешно подключились и авторизовались!")
            me = await client.get_me()
            print(f"Подключены как: {me.first_name} (@{me.username})")
            
            # Тестируем канал по PEER ID
            peer_id = -1001751373900
            print(f"\nТестируем канал по PEER ID: {peer_id}")
            
            try:
                # Создаем PeerChannel объект
                peer = PeerChannel(peer_id if peer_id > 0 else abs(peer_id) - 1000000000000)
                
                # Получаем информацию о канале
                channel = await client.get_entity(peer)
                print(f"\nИнформация о канале:")
                print(f"Название: {channel.title}")
                print(f"ID: {channel.id}")
                print(f"Username: @{channel.username or 'отсутствует'}")
                print(f"Описание: {getattr(channel, 'about', 'отсутствует')}")
                
                # Пробуем получить детальную информацию о канале
                try:
                    full_channel = await client(GetFullChannelRequest(channel))
                    print(f"Количество участников: {full_channel.full_chat.participants_count}")
                    print(f"Количество администраторов: {getattr(full_channel.full_chat, 'admins_count', 'неизвестно')}")
                except Exception as e:
                    print(f"❌ Не удалось получить детальную информацию: {str(e)}")
                
                # Пробуем получить участников
                print("\nПолучаем список участников...")
                try:
                    participants = await client.get_participants(channel, limit=5)
                    print(f"✅ Успешно получили {len(participants)} участников!")
                    print("\nПример данных о первых участниках:")
                    for user in participants:
                        print(f"- {user.first_name} {user.last_name or ''} (@{user.username or 'без username'})")
                except Exception as e:
                    print(f"❌ Не удалось получить список участников: {str(e)}")
                
                # Пробуем получить последние сообщения
                print("\nПолучаем последние сообщения...")
                try:
                    messages = await client.get_messages(channel, limit=3)
                    print(f"✅ Получили {len(messages)} сообщений:")
                    for msg in messages:
                        if msg.message:
                            print(f"- [{msg.id}] {msg.message[:100]}...")
                except Exception as e:
                    print(f"❌ Не удалось получить сообщения: {str(e)}")
                    
            except Exception as e:
                print(f"❌ Ошибка при работе с каналом: {str(e)}")
                print("\nВозможные причины:")
                print("1. Неверный PEER ID")
                print("2. У вас нет доступа к этому каналу")
                print("3. Канал был удален или заблокирован")
                
        else:
            print("❌ Не удалось авторизоваться")
            
    except Exception as e:
        print(f"❌ Ошибка при подключении: {str(e)}")
    finally:
        if client:
            await client.disconnect()

if __name__ == "__main__":
    asyncio.run(test_connection()) 