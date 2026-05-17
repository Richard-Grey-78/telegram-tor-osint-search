#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import socks
import socket
import argparse
import json
import re
import os
import time
import random
from bs4 import BeautifulSoup
from datetime import datetime
from stem import Signal
from stem.control import Controller

# Настройки
TOR_SOCKS_PORT = 9050
TOR_CONTROL_PORT = 9051
TOR_CONTROL_PASSWORD = ""  # Пароль для управления Tor, если установлен
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Safari/605.1.15',
]
TIMEOUT = 30  # Таймаут для запросов в секундах

# Поисковые системы Tor
SEARCH_ENGINES = {
    'ahmia': 'http://juhanurmihxlp77nkq76byazcldy2hlmovfu2epvl5ankdibsot4csyd.onion/search/?q={query}',
    'torch': 'http://xmh57jrzrnw6insl.onion/4a1f6b371c/search.cgi?q={query}&cmd=Search',
    'darksearchio': 'http://darksearch.io/search?query={query}',  # Не .onion, но ищет в даркнете
    'notevil': 'http://hss3uro2hsxfogfq.onion/index.php?q={query}',
    'candle': 'http://gjobqjj7wyczbqie.onion/search?q={query}',
}

# Глобальные переменные
session = None


def setup_tor_connection():
    """Настраивает соединение через Tor"""
    global session
    
    # Настройка SOCKS прокси
    socks.set_default_proxy(socks.SOCKS5, "127.0.0.1", TOR_SOCKS_PORT)
    socket.socket = socks.socksocket
    
    # Создание сессии
    session = requests.Session()
    session.headers.update({
        'User-Agent': random.choice(USER_AGENTS),
        'Accept-Language': 'en-US,en;q=0.9,ru;q=0.8',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    })
    
    # Проверка соединения с Tor
    try:
        response = session.get('https://check.torproject.org/', timeout=TIMEOUT)
        if "Congratulations. This browser is configured to use Tor." in response.text:
            print("✅ Соединение с Tor установлено успешно.")
            return True
        else:
            print("❌ Соединение с Tor не работает корректно.")
            return False
    except Exception as e:
        print(f"❌ Ошибка при подключении к Tor: {str(e)}")
        return False


def renew_tor_ip():
    """Запрашивает новый IP-адрес через контроллер Tor"""
    try:
        with Controller.from_port(port=TOR_CONTROL_PORT) as controller:
            if TOR_CONTROL_PASSWORD:
                controller.authenticate(password=TOR_CONTROL_PASSWORD)
            else:
                controller.authenticate()
            
            controller.signal(Signal.NEWNYM)
            print("🔄 IP-адрес Tor обновлен.")
            # Даем время на обновление цепочки
            time.sleep(5)
            return True
    except Exception as e:
        print(f"❌ Не удалось обновить IP-адрес Tor: {str(e)}")
        return False


def search_onion_site(site_url, keyword, max_pages=3):
    """Поиск по конкретному .onion сайту"""
    results = []
    
    try:
        print(f"🔍 Поиск на {site_url}...")
        response = session.get(site_url, timeout=TIMEOUT)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Поиск по тексту страницы
            text_content = soup.get_text().lower()
            if keyword.lower() in text_content:
                print(f"✅ Ключевое слово найдено на {site_url}")
                
                # Извлечение заголовка
                title = soup.title.string if soup.title else "Без заголовка"
                
                # Извлечение описания
                description = ""
                meta_desc = soup.find('meta', attrs={'name': 'description'})
                if meta_desc:
                    description = meta_desc.get('content', '')
                
                # Поиск контекста (текст вокруг ключевого слова)
                context = ""
                for text in soup.stripped_strings:
                    if keyword.lower() in text.lower():
                        context = text.strip()
                        if len(context) > 200:
                            start = max(0, context.lower().find(keyword.lower()) - 50)
                            end = min(len(context), context.lower().find(keyword.lower()) + len(keyword) + 50)
                            context = "..." + context[start:end] + "..."
                        break
                
                # Формирование результата
                result = {
                    'url': site_url,
                    'title': title,
                    'description': description,
                    'context': context,
                    'keyword': keyword,
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                
                results.append(result)
        
        # Поиск ссылок для дальнейшего обхода
        if max_pages > 1:
            links = soup.find_all('a', href=True)
            internal_links = []
            
            base_domain = site_url.split('/')[2]
            
            for link in links:
                href = link['href']
                
                # Преобразование относительных ссылок в абсолютные
                if href.startswith('/'):
                    # Получаем схему и домен из оригинального URL
                    parts = site_url.split('/')
                    absolute_url = f"{parts[0]}//{parts[2]}{href}"
                elif href.startswith('http') and base_domain in href:
                    absolute_url = href
                else:
                    continue
                
                if absolute_url not in internal_links and '.onion' in absolute_url:
                    internal_links.append(absolute_url)
            
            # Рекурсивный поиск по внутренним ссылкам
            visited = 1
            for link in internal_links:
                if visited >= max_pages:
                    break
                
                try:
                    sub_results = search_onion_site(link, keyword, 1)  # Глубина 1 для подстраниц
                    results.extend(sub_results)
                    visited += 1
                    # Небольшая задержка между запросами
                    time.sleep(random.uniform(1, 3))
                except Exception as e:
                    print(f"Ошибка при поиске на {link}: {str(e)}")
    
    except Exception as e:
        print(f"❌ Ошибка при поиске на {site_url}: {str(e)}")
    
    return results


def search_engine(engine_name, query, max_results=10):
    """Поиск через поисковую систему даркнета"""
    results = []
    
    if engine_name not in SEARCH_ENGINES:
        print(f"❌ Поисковая система {engine_name} не поддерживается.")
        return results
    
    search_url = SEARCH_ENGINES[engine_name].format(query=query.replace(' ', '+'))
    
    try:
        print(f"🔍 Поиск через {engine_name}: {search_url}")
        response = session.get(search_url, timeout=TIMEOUT)
        
        if response.status_code != 200:
            print(f"❌ Ошибка при запросе к {engine_name}: {response.status_code}")
            return results
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Обработка результатов разных поисковых систем
        if engine_name == 'ahmia':
            search_results = soup.select('.ahmia-result')
            for result_div in search_results[:max_results]:
                try:
                    title_elem = result_div.select_one('h4')
                    link_elem = result_div.select_one('a')
                    desc_elem = result_div.select_one('p')
                    
                    title = title_elem.text.strip() if title_elem else "Без заголовка"
                    url = link_elem['href'] if link_elem else ""
                    description = desc_elem.text.strip() if desc_elem else ""
                    
                    if url:
                        result = {
                            'url': url,
                            'title': title,
                            'description': description,
                            'search_engine': engine_name,
                            'keyword': query,
                            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        }
                        results.append(result)
                except Exception as e:
                    print(f"Ошибка при обработке результата Ahmia: {str(e)}")
        
        elif engine_name == 'torch':
            search_results = soup.select('dl')
            for result_dl in search_results[:max_results]:
                try:
                    title_elem = result_dl.select_one('dt a')
                    desc_elem = result_dl.select_one('dd')
                    
                    if not title_elem:
                        continue
                    
                    title = title_elem.text.strip()
                    url = title_elem['href']
                    description = desc_elem.text.strip() if desc_elem else ""
                    
                    result = {
                        'url': url,
                        'title': title,
                        'description': description,
                        'search_engine': engine_name,
                        'keyword': query,
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }
                    results.append(result)
                except Exception as e:
                    print(f"Ошибка при обработке результата Torch: {str(e)}")
        
        elif engine_name == 'notevil':
            search_results = soup.select('div.result')
            for result_div in search_results[:max_results]:
                try:
                    title_elem = result_div.select_one('h5 a')
                    desc_elem = result_div.select_one('span.url-title')
                    
                    title = title_elem.text.strip() if title_elem else "Без заголовка"
                    url = title_elem['href'] if title_elem else ""
                    description = desc_elem.text.strip() if desc_elem else ""
                    
                    result = {
                        'url': url,
                        'title': title,
                        'description': description,
                        'search_engine': engine_name,
                        'keyword': query,
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }
                    results.append(result)
                except Exception as e:
                    print(f"Ошибка при обработке результата NotEvil: {str(e)}")
        
        # Для других поисковых систем можно добавить обработчики по аналогии
        
        print(f"✅ Найдено {len(results)} результатов через {engine_name}")
    
    except Exception as e:
        print(f"❌ Ошибка при поиске через {engine_name}: {str(e)}")
    
    return results


def save_results(results, filename=None):
    """Сохраняет результаты в JSON-файл"""
    if not results:
        print("⚠️ Нет результатов для сохранения.")
        return None
    
    if filename is None:
        filename = f'tor_search_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Результаты сохранены в файл: {filename}")
    return filename


def main():
    parser = argparse.ArgumentParser(description='Поиск в сети Tor по ключевым словам')
    parser.add_argument('--query', '-q', type=str, help='Поисковый запрос')
    parser.add_argument('--engines', '-e', type=str, default='ahmia,darksearchio', 
                      help='Поисковые системы через запятую (ahmia,torch,notevil,darksearchio,candle)')
    parser.add_argument('--sites', '-s', type=str, help='Конкретные .onion сайты для поиска, через запятую')
    parser.add_argument('--depth', '-d', type=int, default=2, 
                      help='Глубина поиска по сайтам (количество страниц для обхода)')
    parser.add_argument('--maxresults', '-m', type=int, default=10, 
                      help='Максимальное количество результатов от каждой поисковой системы')
    parser.add_argument('--renew-ip', '-r', action='store_true', 
                      help='Обновлять IP-адрес Tor между запросами')
    
    args = parser.parse_args()
    
    # Если аргументы не переданы, запрашиваем интерактивно
    if not args.query:
        print("=== Поиск в сети Tor ===")
        args.query = input("Введите поисковый запрос: ")
        
        engines_input = input("Введите поисковые системы через запятую (по умолчанию: ahmia,darksearchio): ")
        if engines_input.strip():
            args.engines = engines_input
        
        sites_input = input("Введите конкретные .onion сайты для поиска через запятую (опционально): ")
        if sites_input.strip():
            args.sites = sites_input
    
    if not args.query:
        print("❌ Поисковый запрос не указан.")
        return
    
    # Настройка соединения с Tor
    if not setup_tor_connection():
        print("❌ Не удалось установить соединение с Tor. Убедитесь, что Tor запущен и работает на порту 9050.")
        return
    
    all_results = []
    engines_list = [engine.strip() for engine in args.engines.split(',')]
    
    # Поиск через указанные поисковые системы
    for engine in engines_list:
        if args.renew_ip:
            renew_tor_ip()
        
        results = search_engine(engine, args.query, args.maxresults)
        all_results.extend(results)
        
        # Небольшая пауза между запросами к разным поисковым системам
        time.sleep(random.uniform(2, 5))
    
    # Поиск по конкретным сайтам
    if args.sites:
        sites_list = [site.strip() for site in args.sites.split(',')]
        for site in sites_list:
            if not site.startswith('http'):
                site = 'http://' + site
            
            if args.renew_ip:
                renew_tor_ip()
            
            results = search_onion_site(site, args.query, args.depth)
            all_results.extend(results)
            
            # Небольшая пауза между запросами к разным сайтам
            time.sleep(random.uniform(2, 5))
    
    # Удаление дубликатов по URL
    unique_results = []
    urls = set()
    for result in all_results:
        if result['url'] not in urls:
            urls.add(result['url'])
            unique_results.append(result)
    
    print(f"\n✅ Всего найдено уникальных результатов: {len(unique_results)}")
    
    # Сохранение результатов
    if unique_results:
        filename = save_results(unique_results)
        
        # Вывод краткой информации о результатах
        for idx, result in enumerate(unique_results, 1):
            print(f"\n{idx}. {result['title']}")
            print(f"   URL: {result['url']}")
            if 'description' in result and result['description']:
                desc = result['description']
                print(f"   Описание: {desc[:100]}..." if len(desc) > 100 else f"   Описание: {desc}")
            if 'context' in result and result['context']:
                print(f"   Контекст: {result['context']}")
            if 'search_engine' in result:
                print(f"   Найдено через: {result['search_engine']}")
    else:
        print("⚠️ По вашему запросу ничего не найдено.")
        print("Советы:")
        print("1. Попробуйте использовать более общие ключевые слова")
        print("2. Проверьте подключение к Tor")
        print("3. Используйте другие поисковые системы")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⚠️ Поиск прерван пользователем")
    except Exception as e:
        print(f"\n❌ Произошла ошибка: {str(e)}") 