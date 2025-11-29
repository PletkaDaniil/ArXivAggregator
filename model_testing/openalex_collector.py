import os
import json
import time
import requests
from model_testing.logs.model_logger import logger

ARXIV_SOURCE_ID = "S4306400194"
YEAR = 2025
LIMIT_PER_QUERY = 50
RESULT_LIMIT = 20
OUTPUT_FILE = "model_testing/datasets/openalex_dataset.json"
DELAY = 3


def decode_abstract(inv_index: dict) -> str:
    """
        Декодируем аннотацию из abstract_inverted_index от OpenAlex
    """
    positions = {}
    for word, idx_list in inv_index.items():
        for idx in idx_list:
            positions[idx] = word
    return " ".join(positions[ind] for ind in sorted(positions))


def fetch_openalex_results(query: str) -> list:
    """
        Запрашиваем статьи из OpenAlex по запросу и избавляемся от дубликатов
    """
    url = (
        "https://api.openalex.org/works"
        f"?filter=primary_location.source.id:{ARXIV_SOURCE_ID},publication_year:{YEAR},title_and_abstract.search:{query}"
        f"&sort=publication_date:desc&per-page={LIMIT_PER_QUERY}"
    )

    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        results = []
        pairs = set()  # title + abstract_prefix

        for item in data.get("results", []):
            title = item.get("title", "").strip()
            abstract_index = item.get("abstract_inverted_index")
            if title and abstract_index:
                abstract = decode_abstract(abstract_index).strip()
                abstract_prefix = abstract[:15].lower().strip()
                key = (title, abstract_prefix)

                # избегаем дубликатов
                if abstract and key not in pairs:
                    pairs.add(key)
                    results.append({
                        "id": item.get("id"),
                        "title": title,
                        "abstract": abstract,
                        "publication_year": item.get("publication_year"),
                    })

        return results[:RESULT_LIMIT]

    except Exception as e:
        logger.exception(f"Ошибка при запросе '{query}': {e}")
        return []


def build_openalex_dataset(topics_data: list):
    """
        Создаём датасет по списку тем и запросов
    """
    dataset = []
    total_queries = 0
    total_results = 0
    
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    for topic_block in topics_data:
        topic = topic_block.get("topic")
        queries = topic_block.get("queries", [])

        for query in queries:
            total_queries += 1
            logger.info(f"[{topic}] Запрос: {query}")

            results = fetch_openalex_results(query)

            if results:
                dataset.append({
                    "topic": topic,
                    "query": query,
                    "results": results
                })
                total_results += len(results)
                logger.info(f"Найдено статей: {len(results)}")

                # постепенное сохраняем датасет
                with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                    json.dump(dataset, f, ensure_ascii=False, indent=2)
            else:
                logger.error("Нет подходящих статей, пропуск...")

            time.sleep(DELAY)

    logger.info(f"Обработано запросов: {total_queries}.")
    logger.info(f"Добавлено в датасет: {len(dataset)} запросов.")
    logger.info(f"Всего статей собрано: {total_results}.")

    return OUTPUT_FILE
