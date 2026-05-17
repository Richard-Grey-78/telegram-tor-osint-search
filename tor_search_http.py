#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import argparse
import json
import re
import os
import time
import random
from bs4 import BeautifulSoup
from datetime import datetime

# Настройки для HTTP-прокси Tor
# По умолчанию Privoxy с Tor работает на порту 8118
TOR_HTTP_PROXY = "127.0.0.1:8118"
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Safari/605.1.15',
]
TIMEOUT = 30  # Таймаут для запросов в секундах

# Поисковые системы Tor
SEARCH_ENGINES = {
    'ahmia': 'https://ahmia.fi/search/?q={query}',  # Используем зеркало на обычном интернете
    'darksearchio': 'https://darksearch.io/search?query={query}',
    'torgle': 'https://torgle.com/?q={query}'  # Еще один поисковик
}

# Глобальные переменные
session = None

def setup_tor_connection():
    """Настраивает соединение через HTTP-прокси Tor"""
    global session
    
    # Настройка HTTP-прокси
    proxies = {
        'http': f'http://{TOR_HTTP_PROXY}',
        'https': f'http://{TOR_HTTP_PROXY}'
    }
    
    # Создание сессии
    session = requests.Session()
    session.proxies = proxies
    session.headers.update({
        'User-Agent': random.choice(USER_AGENTS),
        'Accept-Language': 'en-US,en;q=0.9,ru;q=0.8',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    })
    
    # Проверка соединения с Tor
    try:
        print("Проверка соединения с Tor...")
        response = session.get('https://check.torproject.org/', timeout=TIMEOUT)
        if "Congratulations. This browser is configured to use Tor." in response.text:
            print("✅ Соединение с Tor установлено успешно.")
            return True
        else:
            print(f"❌ Соединение с Tor не работает корректно. Ответ: {response.text[:100]}...")
            # Попробуем без прокси для проверки соединения
            try:
                print("Проверка обычного интернет-соединения...")
                direct_session = requests.Session()
                direct_response = direct_session.get('https://www.google.com', timeout=TIMEOUT)
                if direct_response.status_code == 200:
                    print("✅ Обычное интернет-соединение работает.")
                    print("🔄 Продолжаем без Tor (результаты не будут анонимными).")
                    session = direct_session
                    return True
            except Exception as e:
                print(f"❌ Ошибка при проверке обычного соединения: {str(e)}")
            return False
    except Exception as e:
        print(f"❌ Ошибка при проверке соединения с Tor: {str(e)}")
        # Попробуем без прокси как запасной вариант
        try:
            print("Проверка обычного интернет-соединения...")
            direct_session = requests.Session()
            direct_response = direct_session.get('https://www.google.com', timeout=TIMEOUT)
            if direct_response.status_code == 200:
                print("✅ Обычное интернет-соединение работает.")
                print("🔄 Продолжаем без Tor (результаты не будут анонимными).")
                session = direct_session
                return True
        except Exception as e:
            print(f"❌ Ошибка при проверке обычного соединения: {str(e)}")
        return False


def search_onion_site(site_url, keyword, max_pages=3):
    """Поиск по конкретному сайту"""
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
            
            try:
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
                    
                    if absolute_url not in internal_links:
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
                print(f"Ошибка при обработке ссылок: {str(e)}")
    
    except Exception as e:
        print(f"❌ Ошибка при поиске на {site_url}: {str(e)}")
    
    return results


def search_engine(engine_name, query, max_results=10):
    """Поиск через поисковую систему"""
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
            search_results = soup.select('.result')
            for result_div in search_results[:max_results]:
                try:
                    title_elem = result_div.select_one('h4 a')
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
        
        elif engine_name == 'darksearchio':
            search_results = soup.select('.search-result')
            for result_div in search_results[:max_results]:
                try:
                    title_elem = result_div.select_one('h5 a')
                    desc_elem = result_div.select_one('.description')
                    
                    title = title_elem.text.strip() if title_elem else "Без заголовка"
                    url = title_elem['href'] if title_elem else ""
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
                    print(f"Ошибка при обработке результата DarkSearch: {str(e)}")
        
        elif engine_name == 'torgle':
            search_results = soup.select('.result')
            for result_div in search_results[:max_results]:
                try:
                    title_elem = result_div.select_one('h3 a')
                    desc_elem = result_div.select_one('.snippet')
                    
                    title = title_elem.text.strip() if title_elem else "Без заголовка"
                    url = title_elem['href'] if title_elem else ""
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
                    print(f"Ошибка при обработке результата Torgle: {str(e)}")
        
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


def google_search(query, max_results=10):
    """Резервный метод: Поиск через Google как обычная веб-страница"""
    results = []
    search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
    
    try:
        print(f"🔍 Резервный поиск через Google: {search_url}")
        response = session.get(search_url, timeout=TIMEOUT)
        
        if response.status_code != 200:
            print(f"❌ Ошибка при запросе Google: {response.status_code}")
            return results
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Поиск результатов Google
        search_results = soup.select('.g')
        for result_div in search_results[:max_results]:
            try:
                title_elem = result_div.select_one('h3')
                link_elem = result_div.select_one('a')
                desc_elem = result_div.select_one('.VwiC3b')
                
                title = title_elem.text.strip() if title_elem else "Без заголовка"
                url = link_elem['href'] if link_elem and 'href' in link_elem.attrs else ""
                description = desc_elem.text.strip() if desc_elem else ""
                
                if url and url.startswith('http'):
                    result = {
                        'url': url,
                        'title': title,
                        'description': description,
                        'search_engine': 'google',
                        'keyword': query,
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }
                    results.append(result)
            except Exception as e:
                print(f"Ошибка при обработке результата Google: {str(e)}")
        
        print(f"✅ Найдено {len(results)} результатов через Google")
    
    except Exception as e:
        print(f"❌ Ошибка при поиске через Google: {str(e)}")
    
    return results


def main():
    parser = argparse.ArgumentParser(description='Поиск в сети по ключевым словам')
    parser.add_argument('--query', '-q', type=str, help='Поисковый запрос')
    parser.add_argument('--engines', '-e', type=str, default='ahmia,darksearchio,torgle', 
                      help='Поисковые системы через запятую')
    parser.add_argument('--sites', '-s', type=str, help='Конкретные сайты для поиска, через запятую')
    parser.add_argument('--depth', '-d', type=int, default=2, 
                      help='Глубина поиска по сайтам (количество страниц для обхода)')
    parser.add_argument('--maxresults', '-m', type=int, default=10, 
                      help='Максимальное количество результатов от каждой поисковой системы')
    parser.add_argument('--proxy', '-p', type=str, help='HTTP-прокси в формате host:port, например 127.0.0.1:8118')
    
    args = parser.parse_args()
    
    # Если аргументы не переданы, запрашиваем интерактивно
    if not args.query:
        print("=== Поиск по ключевым словам ===")
        args.query = input("Введите поисковый запрос: ")
        
        engines_input = input("Введите поисковые системы через запятую (по умолчанию: ahmia,darksearchio,torgle): ")
        if engines_input.strip():
            args.engines = engines_input
        
        sites_input = input("Введите конкретные сайты для поиска через запятую (опционально): ")
        if sites_input.strip():
            args.sites = sites_input
            
        proxy_input = input("Введите HTTP-прокси (по умолчанию: 127.0.0.1:8118, пусто для прямого соединения): ")
        if proxy_input.strip():
            args.proxy = proxy_input
    
    if not args.query:
        print("❌ Поисковый запрос не указан.")
        return
    
    # Настройка прокси, если указан
    global TOR_HTTP_PROXY
    if args.proxy:
        TOR_HTTP_PROXY = args.proxy
        
    # Настройка соединения
    if not setup_tor_connection():
        print("❌ Не удалось установить соединение через прокси.")
        retry = input("Продолжить поиск без анонимности? (да/нет): ").lower()
        if retry != 'да' and retry != 'y' and retry != 'yes':
            return
        
        # Создаем обычную сессию без прокси
        global session
        session = requests.Session()
        session.headers.update({
            'User-Agent': random.choice(USER_AGENTS),
        })
    
    all_results = []
    engines_list = [engine.strip().lower() for engine in args.engines.split(',')]
    
    # Поиск через указанные поисковые системы
    for engine in engines_list:
        results = search_engine(engine, args.query, args.maxresults)
        all_results.extend(results)
        
        # Небольшая пауза между запросами
        time.sleep(random.uniform(2, 5))
    
    # Поиск по конкретным сайтам
    if args.sites:
        sites_list = [site.strip() for site in args.sites.split(',')]
        for site in sites_list:
            if not site.startswith('http'):
                site = 'http://' + site
            
            results = search_onion_site(site, args.query, args.depth)
            all_results.extend(results)
            
            # Небольшая пауза между запросами к разным сайтам
            time.sleep(random.uniform(2, 5))
    
    # Если результаты отсутствуют, попробуем обычный поиск в Google
    if not all_results and 'google' not in engines_list:
        print("⚠️ Результаты не найдены через указанные поисковые системы.")
        retry = input("Попробовать обычный поиск в Google? (да/нет): ").lower()
        if retry == 'да' or retry == 'y' or retry == 'yes':
            results = google_search(args.query, args.maxresults)
            all_results.extend(results)
    
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
        print("2. Проверьте подключение к интернету")
        print("3. Проверьте настройки прокси")
        print("4. Используйте другие поисковые системы")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⚠️ Поиск прерван пользователем")
    except Exception as e:
        print(f"\n❌ Произошла ошибка: {str(e)}") 