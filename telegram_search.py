from telethon import TelegramClient
from telethon.tl.functions.messages import SearchGlobalRequest, GetHistoryRequest, SearchRequest
from telethon.tl.functions.contacts import SearchRequest as ContactsSearchRequest
from telethon.tl.functions.channels import GetChannelsRequest, GetFullChannelRequest
from telethon.tl.types import InputMessagesFilterEmpty, Channel, Chat, InputPeerEmpty
from telethon.errors import PeerIdInvalidError, ChannelInvalidError, SessionPasswordNeededError
from telethon.sessions import StringSession
import asyncio
import json
import re
import os
import sys
from datetime import datetime
from config import API_ID, API_HASH, PHONE

# Путь к файлу для хранения строки сессии
SESSION_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "telegram_session.txt")

async def connect_client():
    """Создает и подключает клиент Telegram с надежным сохранением сессии"""
    # Проверяем наличие сохраненной строки сессии
    session_string = None
    if os.path.exists(SESSION_FILE):
        try:
            with open(SESSION_FILE, 'r') as file:
                session_string = file.read().strip()
            print("Найден файл сессии")
        except Exception as e:
            print(f"Ошибка при чтении файла сессии: {str(e)}")
            # Если файл поврежден, удаляем его
            try:
                os.remove(SESSION_FILE)
                print("Поврежденный файл сессии удален")
            except:
                pass
    
    # Создаем клиент с сессией (строковой или новой)
    if session_string:
        client = TelegramClient(StringSession(session_string), API_ID, API_HASH)
    else:
        client = TelegramClient(StringSession(), API_ID, API_HASH)
    
    # Подключаемся к Telegram
    try:
        await client.connect()
        
        # Проверяем авторизацию
        if not await client.is_user_authorized():
            print("Требуется авторизация...")
            try:
                await client.send_code_request(PHONE)
                code = input('Введите код из сообщения Telegram: ')
                await client.sign_in(PHONE, code)
            except SessionPasswordNeededError:
                # Если включена двухфакторная аутентификация
                password = input('Введите пароль двухфакторной аутентификации: ')
                await client.sign_in(password=password)
            
            # Сохраняем строку сессии в файл
            session_str = client.session.save()
            with open(SESSION_FILE, 'w') as file:
                file.write(session_str)
            print("Авторизация успешна, сессия сохранена")
        else:
            # Обновляем файл сессии при каждом успешном подключении
            session_str = client.session.save()
            with open(SESSION_FILE, 'w') as file:
                file.write(session_str)
            print("Сессия успешно восстановлена")
    
    except Exception as e:
        print(f"Ошибка при подключении: {str(e)}")
        # Если возникла ошибка, удаляем файл сессии и пробуем заново
        if os.path.exists(SESSION_FILE):
            os.remove(SESSION_FILE)
        print("Файл сессии удален. Пожалуйста, запустите скрипт снова.")
        sys.exit(1)
    
    print(f"Подключение установлено: {await client.is_user_authorized()}")
    return client

async def search_by_dialogs(client, keywords, limit=100):
    """Поиск групп среди диалогов пользователя"""
    results = []
    processed_peers = set()
    
    print("Поиск среди диалогов...")
    try:
        async for dialog in client.iter_dialogs(limit=limit):
            try:
                if not dialog.is_group and not dialog.is_channel:
                    continue
                
                entity = dialog.entity
                peer_id = entity.id
                
                if peer_id in processed_peers:
                    continue
                
                processed_peers.add(peer_id)
                
                # Проверка соответствия ключевым словам
                matched_in = []
                if hasattr(entity, 'title'):
                    if any(kw.lower() in entity.title.lower() for kw in keywords):
                        matched_in.append('title')
                
                # Получение дополнительной информации
                about = ''
                members_count = 'Unknown'
                
                try:
                    if isinstance(entity, Channel):
                        full_channel = await client(GetFullChannelRequest(channel=entity))
                        about = getattr(full_channel.full_chat, 'about', '')
                        members_count = getattr(full_channel.full_chat, 'participants_count', 'Unknown')
                except Exception as e:
                    print(f"Не удалось получить полную информацию о канале {peer_id}: {str(e)}")
                
                # Проверка описания
                if about and any(kw.lower() in about.lower() for kw in keywords):
                    matched_in.append('description')
                
                # Проверка сообщений
                sample_message = None
                try:
                    if isinstance(entity, (Channel, Chat)):
                        messages = await client.get_messages(entity, limit=20)
                        for msg in messages:
                            if hasattr(msg, 'message') and msg.message:
                                for kw in keywords:
                                    if kw.lower() in msg.message.lower():
                                        if 'messages' not in matched_in:
                                            matched_in.append('messages')
                                        if not sample_message:
                                            sample_message = msg.message
                                        break
                                
                                if 'messages' in matched_in:
                                    break
                except Exception as e:
                    print(f"Не удалось получить сообщения из группы {peer_id}: {str(e)}")
                
                # Добавляем результат, если есть совпадения
                if matched_in:
                    creation_date = None
                    if hasattr(entity, 'date'):
                        creation_date = entity.date.strftime('%Y-%m-%d %H:%M:%S')
                    
                    result = {
                        'chat_id': peer_id,
                        'title': getattr(entity, 'title', 'Unknown'),
                        'username': getattr(entity, 'username', None),
                        'members_count': members_count,
                        'description': about,
                        'type': str(type(entity).__name__),
                        'creation_date': creation_date,
                        'keyword': ','.join([kw for kw in keywords if any(kw.lower() in text.lower() for text in [getattr(entity, 'title', ''), about] if text)]),
                        'matched_in': matched_in,
                        'found_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }
                    
                    if sample_message:
                        result['sample_message'] = sample_message
                    
                    results.append(result)
            except Exception as e:
                print(f"Ошибка при обработке диалога: {str(e)}")
    except Exception as e:
        print(f"Ошибка при получении диалогов: {str(e)}")
    
    return results

async def search_by_contacts(client, keywords):
    """Поиск групп через контакты"""
    results = []
    processed_peers = set()
    
    print("Поиск через контакты...")
    for keyword in keywords:
        try:
            contacts = await client(ContactsSearchRequest(q=keyword, limit=100))
            for chat in contacts.chats:
                peer_id = chat.id
                
                if peer_id in processed_peers:
                    continue
                
                processed_peers.add(peer_id)
                
                # Проверка соответствия ключевым словам
                matched_in = []
                if hasattr(chat, 'title'):
                    if any(kw.lower() in chat.title.lower() for kw in keywords):
                        matched_in.append('title')
                
                # Получение дополнительной информации
                about = ''
                members_count = 'Unknown'
                
                try:
                    if isinstance(chat, Channel):
                        full_channel = await client(GetFullChannelRequest(channel=chat))
                        about = getattr(full_channel.full_chat, 'about', '')
                        members_count = getattr(full_channel.full_chat, 'participants_count', 'Unknown')
                except Exception as e:
                    print(f"Не удалось получить полную информацию о канале {peer_id}: {str(e)}")
                
                # Проверка описания
                if about and any(kw.lower() in about.lower() for kw in keywords):
                    matched_in.append('description')
                
                # Добавляем результат, если есть совпадения
                if matched_in:
                    creation_date = None
                    if hasattr(chat, 'date'):
                        creation_date = chat.date.strftime('%Y-%m-%d %H:%M:%S')
                    
                    result = {
                        'chat_id': peer_id,
                        'title': getattr(chat, 'title', 'Unknown'),
                        'username': getattr(chat, 'username', None),
                        'members_count': members_count,
                        'description': about,
                        'type': str(type(chat).__name__),
                        'creation_date': creation_date,
                        'keyword': keyword,
                        'matched_in': matched_in,
                        'found_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }
                    
                    results.append(result)
        except Exception as e:
            print(f"Ошибка при поиске контактов по ключевому слову {keyword}: {str(e)}")
    
    return results

async def search_local(client, keywords, limit=100):
    """Поиск по локальным сообщениям и чатам"""
    results = []
    processed_peers = set()
    
    print("Выполняется локальный поиск...")
    
    async for dialog in client.iter_dialogs(limit=None):
        try:
            if not dialog.is_group and not dialog.is_channel:
                continue
            
            entity = dialog.entity
            peer_id = entity.id
            
            if peer_id in processed_peers:
                continue
            
            processed_peers.add(peer_id)
            
            # Сначала поищем по названию и сохраним соответствующие чаты
            title_match = False
            if hasattr(entity, 'title') and entity.title:
                if any(kw.lower() in entity.title.lower() for kw in keywords):
                    title_match = True
            
            # Если совпадение по названию не найдено, поищем по сообщениям
            if not title_match:
                message_match = False
                sample_message = None
                for keyword in keywords:
                    try:
                        messages = await client.search_messages(entity, keyword, limit=5)
                        if messages and len(messages) > 0:
                            message_match = True
                            if not sample_message and hasattr(messages[0], 'message') and messages[0].message:
                                sample_message = messages[0].message
                            break
                    except Exception as e:
                        print(f"Не удалось найти сообщения по ключевому слову {keyword} в чате {peer_id}: {str(e)}")
                        continue
                
                if not message_match:
                    continue
            
            # Получаем дополнительную информацию о группе/канале
            matched_in = []
            about = ''
            members_count = 'Unknown'
            
            if title_match:
                matched_in.append('title')
            
            try:
                if isinstance(entity, Channel):
                    try:
                        full_channel = await client(GetFullChannelRequest(channel=entity))
                        about = getattr(full_channel.full_chat, 'about', '')
                        members_count = getattr(full_channel.full_chat, 'participants_count', 'Unknown')
                    except Exception as e:
                        print(f"Не удалось получить полную информацию о канале {peer_id}: {str(e)}")
            except Exception as e:
                print(f"Ошибка при получении информации о чате {peer_id}: {str(e)}")
            
            # Проверяем описание
            if about and any(kw.lower() in about.lower() for kw in keywords):
                matched_in.append('description')
            
            # Если у нас есть совпадение по сообщениям и нет по названию/описанию
            if not matched_in and message_match:
                matched_in.append('messages')
            
            # Создаем результат
            creation_date = None
            if hasattr(entity, 'date'):
                creation_date = entity.date.strftime('%Y-%m-%d %H:%M:%S')
            
            matching_keyword = next((kw for kw in keywords if hasattr(entity, 'title') and entity.title and kw.lower() in entity.title.lower()), keywords[0])
            
            result = {
                'chat_id': peer_id,
                'title': getattr(entity, 'title', 'Unknown'),
                'username': getattr(entity, 'username', None),
                'members_count': members_count,
                'description': about,
                'type': str(type(entity).__name__),
                'creation_date': creation_date,
                'keyword': matching_keyword,
                'matched_in': matched_in,
                'found_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            if 'messages' in matched_in and sample_message:
                result['sample_message'] = sample_message
            
            results.append(result)
        except Exception as e:
            print(f"Ошибка при обработке диалога {dialog.id}: {str(e)}")
    
    return results

def save_results(results, filename=None):
    if filename is None:
        filename = f'telegram_groups_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    return filename

async def main():
    # Здесь можно задать свои ключевые слова
    print("Расширенный поиск групп в Telegram")
    print("==================================")
    print("Введите ключевые слова для поиска групп в Telegram")
    print("Примеры: python, программирование, 'data science', 'базы данных'")
    print("Фразы из нескольких слов можно вводить в кавычках или без них")
    user_input = input('Ключевые слова (через запятую): ')
    
    # Обработка ввода - сохраняем фразы в кавычках и разделяем остальное по запятым
    keywords = []
    # Находим все фразы в кавычках
    quoted_phrases = re.findall(r'"([^"]*)"', user_input) + re.findall(r"'([^']*)'", user_input)
    # Удаляем найденные фразы из ввода
    for phrase in quoted_phrases:
        user_input = user_input.replace(f"'{phrase}'", "").replace(f'"{phrase}"', "")
    # Добавляем фразы в кавычках к ключевым словам
    keywords.extend(quoted_phrases)
    # Разделяем оставшийся ввод по запятым
    keywords.extend([k.strip() for k in user_input.split(',') if k.strip()])
    
    if not keywords:
        keywords = ['python', 'программирование', 'coding']  # Значения по умолчанию
        print(f"Используются ключевые слова по умолчанию: {', '.join(keywords)}")
    else:
        print(f"Поиск будет выполнен по ключевым словам/фразам: {', '.join(keywords)}")
    
    print("\nПоиск может занять некоторое время...")
    print("Выполняется подключение к Telegram API...")
    
    # Подключение к Telegram с улучшенным сохранением сессии
    client = await connect_client()
    
    # Выполняем поиск разными методами
    all_results = []
    
    try:
        # Метод 1: Поиск по диалогам
        dialog_results = await search_by_dialogs(client, keywords)
        if dialog_results:
            print(f"Найдено {len(dialog_results)} групп через диалоги")
            all_results.extend(dialog_results)
        
        # Метод 2: Поиск по контактам
        contact_results = await search_by_contacts(client, keywords)
        if contact_results:
            # Фильтруем дубликаты
            new_contacts = [r for r in contact_results if r['chat_id'] not in [ex['chat_id'] for ex in all_results]]
            print(f"Найдено {len(new_contacts)} новых групп через контакты")
            all_results.extend(new_contacts)
        
        # Метод 3: Локальный поиск по сообщениям
        local_results = await search_local(client, keywords)
        if local_results:
            # Фильтруем дубликаты
            new_local = [r for r in local_results if r['chat_id'] not in [ex['chat_id'] for ex in all_results]]
            print(f"Найдено {len(new_local)} новых групп через локальный поиск")
            all_results.extend(new_local)
    except Exception as e:
        print(f"Ошибка при выполнении поиска: {str(e)}")
    finally:
        # Отключаемся от Telegram БЕЗ выхода из аккаунта
        # Обновляем строку сессии перед отключением
        try:
            session_str = client.session.save()
            with open(SESSION_FILE, 'w') as file:
                file.write(session_str)
            print("Завершение сеанса поиска (сессия сохранена)...")
        except Exception as e:
            print(f"Ошибка при сохранении сессии: {str(e)}")
        
        await client.disconnect()
    
    # Сохраняем результаты в файл
    if all_results:
        # Сортируем по количеству участников (если доступно)
        try:
            all_results.sort(key=lambda x: int(x['members_count']) if str(x['members_count']).isdigit() else 0, reverse=True)
        except:
            pass
        
        filename = save_results(all_results)
        print(f"\nРезультаты сохранены в файл: {filename}")
        
        # Выводим информацию о найденных группах
        print(f"\nНайдено групп: {len(all_results)}")
        for result in all_results:
            print(f"Группа: {result['title']}")
            print(f"Username: @{result['username']}" if result['username'] else "Username: отсутствует")
            print(f"Участников: {result['members_count']}")
            print(f"Создана: {result['creation_date']}" if result['creation_date'] else "Дата создания: неизвестна")
            print(f"Тип: {result['type']}")
            print(f"Ключевое слово найдено в: {', '.join(result['matched_in'])}")
            if 'sample_message' in result:
                print(f"Пример сообщения: {result['sample_message'][:100]}..." if len(result['sample_message']) > 100 else f"Пример сообщения: {result['sample_message']}")
            print(f"Найдено по запросу: {result['keyword']}")
            print("-" * 50)
    else:
        print("\nПо вашему запросу не найдено групп.")
        print("Советы:")
        print("1. Попробуйте использовать более общие ключевые слова")
        print("2. Используйте слова на разных языках (английский, русский)")
        print("3. Присоединитесь к нескольким группам по интересующей вас теме чтобы расширить результаты поиска")
        print("4. Для поиска фраз используйте кавычки: 'data leak'")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nПоиск прерван пользователем")
    except Exception as e:
        print(f"\nПроизошла ошибка: {str(e)}")
        print("Для подробной информации об ошибке запустите скрипт с флагом отладки.") 