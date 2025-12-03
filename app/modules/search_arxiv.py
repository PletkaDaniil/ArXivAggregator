import time
import requests
from bs4 import BeautifulSoup
from bs4.element import Tag
from urllib.parse import quote_plus
from app.logs.arxiv_logger import logger

USER_AGENT = "Mozilla/5.0"
PAGE_SIZE = 200
MAX_PAGES = 6
YEAR_FILTER = "2025"
DELAY = 3


def arxiv_url(query: str, page: int) -> str:
    """ 
        Формируем URL для запроса к arXiv
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
                f"Жду {delay} сек и пробую снова"
            )
            time.sleep(delay)
            delay *= 2
        attempts += 1

    logger.error(f"Все попытки исчерпаны: {url}")
    return None


def parse_article(item: Tag) -> dict | None:
    """ 
        Парсим статью и возвращаем словарь с готовыми данными
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
    """ 
        Парсим HTML страницы и возвращаем список статей 
    """
    soup = BeautifulSoup(html, "html.parser")
    items = soup.select("li.arxiv-result")
    if not items:
        logger.info("Результаты закончились.")
        return []

    articles = []
    for item in items:
        article = parse_article(item)
        if article:
            articles.append(article)

    return articles


def fetch_arxiv_for_query(query: str) -> list[dict]:
    """
        Ищем статьи по запросу
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
