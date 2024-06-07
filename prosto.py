import json
import re
import os
from urllib.parse import urlparse
from selenium import webdriver
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, TimeoutException, ElementNotInteractableException, WebDriverException, InvalidSessionIdException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
from bs4 import BeautifulSoup
import markdownify as md
import pandas as pd

# Настройки для EdgeDriver
options = webdriver.EdgeOptions()
options.add_argument("user-agent=Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:84.0) Gecko/20100101 Firefox/84.0")
options.add_argument("--disable-blink-features=AutomationControlled")

# Отключение загрузки изображений
prefs = {
    "profile.managed_default_content_settings.images": 2
}
options.add_experimental_option("prefs", prefs)
s = EdgeService(executable_path="C:\\edgedriver\\msedgedriver.exe")
driver = webdriver.Edge(service=s, options=options)

def clean_markdown(text):
    """Очистка маркдауна от изображений и ссылок"""
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)  # Удаляем изображения
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)  # Удаляем ссылки, зашитые в слова
    text = re.sub(r'<h[1-6]>(.*?)<\/h[1-6]>', r'### \1', text)  # Преобразуем заголовки в формат ###
    return text

def extract_domain(url):
    """Извлечение домена из URL"""
    parsed_url = urlparse(url)
    return parsed_url.netloc

def get_article_links(driver):
    try:
        # Ждем загрузки статей на странице
        WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, '.page-main_content')))
        
        # Получаем все элементы <a> с классом 'card-news card card_link'
        article_elements = driver.find_elements(By.CSS_SELECTOR, '.page-main_content .card-news.card.card_link')
        article_links = [element.get_attribute('href') for element in article_elements]
        
        # Убираем дублирующиеся ссылки
        article_links = list(dict.fromkeys(article_links)) 
        
        return article_links

    except NoSuchElementException:
        print("Не удалось найти элементы статей.")
        return []
    except Exception as e:
        print(f"Ошибка при получении ссылок на статьи: {e}")
        return []

def parse_article(url, driver, max_articles=None):
    articles_data = []
    parsed_titles = set()
    article_counter = 0

    try:
        driver.get(url)
        # Ожидание после загрузки главной страницы
        time.sleep(1)

        # Заголовок для структуры данных
        header = [
            "domain",
            "URL",
            "content_type",
            "publication_date",
            "Title",
            "h1",
            "content_html",
            "Text"
        ]

        # Получаем ссылки на статьи
        article_links = get_article_links(driver)

        while True:
            for article_link in article_links:
                if max_articles is not None and article_counter >= max_articles:
                    print(f"Достигнуто максимальное количество статей: {max_articles}. Парсинг завершен.")
                    return [header] + articles_data

                # Открываем статью в новой вкладке
                driver.execute_script("window.open(arguments[0], '_blank');", article_link)
                driver.switch_to.window(driver.window_handles[-1])

                try:
                    # Ждем загрузки заголовка статьи
                    WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.CSS_SELECTOR, 'h1')))
                    
                    title_element = driver.find_element(By.CSS_SELECTOR, 'h1')
                    title = title_element.text.strip()

                    if title in parsed_titles:
                        driver.close()  # Закрываем вкладку с текущей статьей
                        driver.switch_to.window(driver.window_handles[0])  # Переключаемся обратно на основную вкладку
                        continue

                    content_element = driver.find_element(By.CSS_SELECTOR, '.magazine-article-text')

                    # Получаем содержимое статьи без указанных блоков
                    soup = BeautifulSoup(content_element.get_attribute('outerHTML'), 'html.parser')
                    main_content = soup.find('div', class_='magazine-article-text')
                    metadata = main_content.find('div', class_='single_date')
                    if metadata:
                        metadata.decompose()  # Удаляем блок single_date
                    # Удаляем блок <ol class="menu">
                    menu = main_content.find('ol', class_='menu')
                    if menu:
                        menu.decompose()

                    # Удаляем блоки nav-bookmarks__item_title и single_views
                    for bookmark in main_content.find_all('div', class_='nav-bookmarks__item nav-bookmarks__item_title'):
                        bookmark.decompose()
                    for views in main_content.find_all('span', class_='single_views'):
                        views.decompose()

                    content_html = str(main_content).strip()
                    content_html = clean_markdown(content_html)  # Убираем изображения из HTML

                    # Получаем lead_html
                    lead_element = driver.find_element(By.CSS_SELECTOR, '.single_subheader') if driver.find_elements(By.CSS_SELECTOR, '.single_subheader') else None
                    publication_date_element = driver.find_element(By.CSS_SELECTOR, '.single_date') if driver.find_elements(By.CSS_SELECTOR, '.single_date') else None

                    lead_html = lead_element.get_attribute('outerHTML') if lead_element else ''

                    # Получаем текст даты
                    if publication_date_element:
                        publication_date_text = publication_date_element.text.strip()
                        # Используем регулярное выражение для извлечения даты
                        match = re.search(r'\b(\d{1,2}\.\d{1,2}\.\d{4})\b', publication_date_text)
                        if match:
                            publication_date = match.group(1)
                        else:
                            publication_date = 'unknown'
                    else:
                        publication_date_text = ''
                        publication_date = 'unknown'

                    # Удаляем строки, содержащие title, lead_html и publication_date из content_html
                    content_html = re.sub(fr'<h1[^>]*>{re.escape(title)}</h1>', '', content_html, flags=re.IGNORECASE)
                    content_html = re.sub(re.escape(lead_html), '', content_html)
                    content_html = re.sub(re.escape(publication_date_text), '', content_html)

                    # Преобразуем HTML в Markdown
                    content_markdown = md.markdownify(content_html)
                    content_markdown = clean_markdown(content_markdown)  # Чистим Markdown от изображений и ссылок

                    h1 = title
                    lead_markdown = md.markdownify(lead_html)

                    # Сохраняем данные в список
                    article_data = [
                        extract_domain(article_link),
                        article_link,
                        'article',
                        publication_date,
                        title,
                        h1,
                        lead_html + content_html,
                        lead_markdown + content_markdown
                    ]                  

                    if content_markdown.strip():
                        articles_data.append(article_data)

                    parsed_titles.add(title)
                    article_counter += 1

                except Exception as e:
                    print(f"Ошибка при обработке элемента: {e}")
                finally:
                    driver.close()  # Закрываем вкладку с текущей статьей
                    driver.switch_to.window(driver.window_handles[0])  # Переключаемся обратно на основную вкладку

            # Проверяем наличие пагинации
            try:
                paginator = driver.find_element(By.CLASS_NAME, 'page-nav')
                next_page_button = paginator.find_element(By.XPATH, './/button[contains(@class, "button") and contains(text(), "Вперед")]')
                if 'button_disabled' in next_page_button.get_attribute('class'):
                    print("Достигнута последняя страница. Парсинг завершен.")
                    break
                driver.execute_script("arguments[0].click();", next_page_button)
                WebDriverWait(driver, 10).until(EC.staleness_of(driver.find_element(By.CSS_SELECTOR, '.page-main_content .card-news.card.card_link')))  # Ожидаем загрузки следующей страницы
                article_links = get_article_links(driver)  # Обновляем список ссылок на статьи
            except NoSuchElementException:
                print("Пагинация не найдена. Парсинг завершен.")
                break  # Если пагинация не найдена, выходим из цикла

        final_article_count = len(articles_data)
        print(f"Успешно спарсено и сохранено статей: {final_article_count}")

    except InvalidSessionIdException as e:
        print(f"Ошибка сессии: {e}")
    except WebDriverException as e:
        print(f"Ошибка при парсинге страницы: {e}")

    return [header] + articles_data
 
def save_to_json(data, filename):
    """Сохранение данных в JSON-файл"""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            try:
                existing_data = json.load(f)
            except json.JSONDecodeError:
                existing_data = []
    except FileNotFoundError:
        existing_data = []

    existing_data.extend(data)

    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(existing_data, f, ensure_ascii=False, indent=4)

    print(f"Данные сохранены в файл: {filename}")

def main():
    try:
        url_file = 'urls.txt'
        json_file = 'prosto.json'
        max_articles = None  # Установите None для парсинга всех статей или задайте максимальное количество статей

        if not os.path.exists(url_file):
            print(f"Файл {url_file} не найден.")
            return

        with open(url_file, 'r', encoding='utf-8') as f:
            urls = [line.strip() for line in f if line.strip()]

        for url in urls:
            articles_data = parse_article(url, driver, max_articles)
            if articles_data:
                save_to_json(articles_data, json_file)

        # Валидировать JSON-файл
        try:
            df = pd.read_json(json_file)
            print("JSON-файл сформирован корректно.")
        except ValueError as e:
            print(f"Ошибка при валидации JSON-файла: {e}")

    except Exception as ex:
        print(ex)
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
