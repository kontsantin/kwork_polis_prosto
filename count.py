import json
import openpyxl
from openpyxl import Workbook

def count_characters_in_articles(json_file):
    try:
        with open(json_file, 'r', encoding='utf-8') as file:
            data = json.load(file)

        results = []

        for article in data[1:]:  # Пропускаем заголовок
            url = article[1]  # URL
            title = article[4]  # Title
            content_html = article[6]  # content_html
            text = article[7]  # Text

            content_html_length = len(content_html)
            text_length = len(text)

            article_result = {
                'URL': url,
                'Title': title,
                'Content_HTML_Length': content_html_length,
                'Text_Length': text_length
            }
            results.append(article_result)

        return results

    except Exception as e:
        print(f"Ошибка при обработке файла JSON: {e}")
        return []

def write_to_excel(data, excel_file):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Articles"

    # Заголовок таблицы
    headers = ["URL", "Title", "Content_HTML_Length", "Text_Length"]
    sheet.append(headers)

    # Данные
    for article in data:
        row = [
            article['URL'],
            article['Title'],
            article['Content_HTML_Length'],
            article['Text_Length']
        ]
        sheet.append(row)

    # Сохранение файла
    workbook.save(excel_file)

# Пример использования
json_file = 'polis.json'
excel_file = 'polis_lengths.xlsx'

article_lengths = count_characters_in_articles(json_file)
write_to_excel(article_lengths, excel_file)

print(f"Данные успешно сохранены в {excel_file}")
