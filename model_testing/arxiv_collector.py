import json
import os
import re
import time
import requests
from bs4 import BeautifulSoup
from bs4.element import Tag
from urllib.parse import quote_plus
from model_testing.logs.model_logger import logger

PAGE_SIZE = 200
MAX_PAGES = 6
YEAR_FILTER = "2025"
DELAY = 3
OUTPUT_FILE = "model_testing/datasets/arxiv_dataset.json"
USER_AGENT = "Mozilla/5.0"


def normalize_text(text: str) -> str:
    """
        Нормализуем текст: убираем лишние пробелы и переносы строк
    """
    return re.sub(r"\s+", " ", text).strip()


def load_existing_dataset() -> list:
    """
        Загружаем уже существующий датасет (если он есть)
    """
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Не удалось прочитать датасет, создаем новый. Ошибка: {e}")
            return []
    return []


def is_query_done(dataset: list, topic: str, query: str) -> bool:
    """
        Проверяем, был ли уже обработан данный запрос
    """
    return any(row["topic"] == topic and row["query"] == query for row in dataset)


def arxiv_url(query: str, page: int) -> str:
    """
        Делаем запрос к arXiv
    """
    encoded = quote_plus(query)
    start = page * PAGE_SIZE
    return (
        f"https://arxiv.org/search/?query={encoded}&searchtype=all"
        f"&abstracts=show&order=-announced_date_first&size={PAGE_SIZE}&start={start}"
    )


def fetch_page(url: str) -> str | None:
    """
        Загружаем страницу с arXiv
    """
    attempts, delay = 0, DELAY
    while attempts < 5:
        try:
            response = requests.get(
                url,
                headers={"User-Agent": USER_AGENT},
                timeout=60
            )
            if response.status_code == 200:
                logger.info(f"Страница загружена: {url}")
                return response.text

            logger.error(f"Ошибка {response.status_code}; URL: {url}")
            return None

        except Exception as e:
            logger.warning(
                f"[{attempts}/{5}] Ошибка запроса: {e}. "
                f"Ждем {delay} сек и пробуем снова."
            )
            time.sleep(delay)
            delay *= 2
        attempts += 1

    logger.error(f"Все попытки исчерпаны: {url}")
    return None



def parse_article(item: Tag) -> dict | None:
    """
        Парсим статьи
    """

    title_el = item.select_one("p.title")
    abstract_el = item.select_one("span.abstract-full")
    link_el = item.select_one("p.list-title a")
    date_el = item.select_one("p.is-size-7")

    title = title_el.text.strip() if title_el else ""
    summary = abstract_el.text.strip().replace("\n", " ") if abstract_el else ""
    link = link_el["href"] if link_el and link_el.has_attr("href") else ""
    date_text = date_el.text.strip() if date_el else ""

    if YEAR_FILTER not in date_text:
        return None

    return {
        "title": title,
        "summary": summary,
        "link": link,
        "date": date_text,
    }


def parse_page(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    items = soup.select("li.arxiv-result")
    if not items:
        logger.info("Ничего нет на странице")
        return []

    articles = []
    for item in items:
        article = parse_article(item)
        if article:
            articles.append(article)
    return articles


def fetch_arxiv_for_query(query: str) -> list[dict]:
    """
        Собираем статьи по запросу пользователя
    """
    results = []
    logger.info(f"Начинаем поиск статей по запросу: '{query}'")

    for page in range(MAX_PAGES):
        url = arxiv_url(query, page)
        html = fetch_page(url)
        if html is None:
            break

        articles = parse_page(html)
        results.extend(articles)
        time.sleep(DELAY)

    logger.info(f"Поиск завершён, всего найдено {len(results)} статей по запросу '{query}'")
    return results


def build_arxiv_dataset(topics_data: list):
    """
        Создаём датасет
    """
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    dataset = load_existing_dataset()
    logger.info(f"Уже обработано запросов: {len(dataset)}")

    for block in topics_data:
        topic = block["topic"]
        queries = block["queries"]

        for query in queries:
            if is_query_done(dataset, topic, query):
                logger.info(f"[{topic}] '{query}' — уже есть, пропускаем.")
                continue

            logger.info(f"[{topic}] Новый запрос: '{query}'")

            try:
                results = fetch_arxiv_for_query(query)
            except Exception as e:
                logger.exception(f"Ошибка при сборе '{query}': {e}. Пропускаем.")
                continue

            entry = {
                "topic": topic,
                "query": query,
                "results": results
            }
            dataset.append(entry)

            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                json.dump(dataset, f, ensure_ascii=False, indent=2)

            logger.info(f"Добавлено статей: {len(results)}. Данные сохранены.")

    logger.info("Полный arXiv датасет собран.")
