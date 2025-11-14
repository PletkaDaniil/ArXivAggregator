import requests
import time
from app.logs.authors_logger import logger

BASE_URL = "https://api.semanticscholar.org/graph/v1"
DELAY = 3


def fetch_paper_data(paper_id: str, fields: str) -> dict | None:
    """
        Делаем запрос к Semantic Scholar API
    """
    logger.info(f"Начинаем запрос к Semantic Scholar для {paper_id}")
    attempts, delay = 0, DELAY
    while attempts < 5:
        try:
            response = requests.post(
                f"{BASE_URL}/paper/batch",
                params={"fields": fields},
                json={"ids": [paper_id]},
                timeout=30
            )

            if response.status_code == 200:
                logger.info(f"Данные для {paper_id} успешно получены")
                return response.json()

            if response.status_code == 429:
                logger.warning(f"Слишком много запросов к API. Ждём {delay} секунд...")
                time.sleep(delay)
                delay *= 2
                attempts += 1
                continue

            logger.error(f"Ошибка API ({response.status_code}): {response.text}")
            return None

        except requests.RequestException as e:
            logger.exception(f"Ошибка соединения при запросе {paper_id}: {e}")
            time.sleep(delay)
            delay *= 2
        attempts += 1

    logger.error(f"Не удалось получить данные для {paper_id} после {attempts} попыток")
    return None


def parse_paper_data(data: list) -> dict:
    """
        Преобразуем результат запроса в словарь
        Также берем числом цитирований статьи
    """
    if not data or not isinstance(data, list) or not data[0]:
        logger.warning("Пустой или некорректный ответ от API")
        return {}

    paper = data[0]
    authors = [
        {
            "name": author.get("name"),
            "authorId": author.get("authorId"),
            "hIndex": author.get("hIndex"),
            "paperCount": author.get("paperCount"),
            "citationCount": author.get("citationCount"),
        }
        for author in paper.get("authors", [])
    ]
    citation_count = paper.get("citationCount", 0)
    logger.info(f"Парсинг данных статьи {paper.get('paperId')}: {citation_count} цитирований, {len(authors)} авторов")
    return {
        "paper_id": paper.get("paperId"),
        "citation_count": citation_count,
        "authors": authors,
    }


def get_authors_meta(arxiv_id: str) -> dict:
    """
        Возвращаем подобный формат:
            {
                "paper_id": ...,
                "citation_count": ...,
                "authors": [ { name, authorId, hIndex, paperCount, citationCount }, ... ]
            }
    """
    if not arxiv_id:
        logger.warning("Пустой arXiv ID")
        return {}

    paper_id = f"ARXIV:{arxiv_id.split('v')[0]}"
    fields = "citationCount,authors.authorId,authors.name,authors.hIndex,authors.paperCount,authors.citationCount"
    logger.info(f"Получаем мета-данные для {paper_id}")
    data = fetch_paper_data(paper_id, fields)
    return parse_paper_data(data)
