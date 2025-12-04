import os
import json
import torch
from sentence_transformers import SentenceTransformer, util
from app.modules.search_arxiv import fetch_arxiv_for_query
from app.modules.authors_info import get_authors_meta
from app.modules.scoring import sort_articles
from app.logs.logger import logger

TOP_N_DEFAULT = 150
TOP_RESULT = 15
BATCH_SIZE = 32
MODEL_NAME = "model_testing/tuned_model"
RESULTS_DIR = "app/results"


def prepare_texts(arxiv_data: list[dict]) -> list[str]:
    """
        Объединяем заголовки и описания статей
    """
    return [f"{a['title']} {a['summary']}" for a in arxiv_data]


def compute_similarity(
    query: str, texts: list[str], model: SentenceTransformer
) -> torch.Tensor:
    """
        Вычисляем косинусное сходство между запросом и статьями
    """
    logger.info("Вычисление эмбеддингов и косинусного сходства")
    query_emb = model.encode(query, convert_to_tensor=True)
    doc_embs = model.encode(texts, convert_to_tensor=True, batch_size=BATCH_SIZE)
    scores = util.cos_sim(query_emb, doc_embs)[0]
    logger.info("Вычисления сходства завершены")
    return scores


def extract_top_results(
    scores: torch.Tensor, candidates: list[dict], top_n: int
) -> list[dict]:
    """
        Возвращаем топ статей с метаданными авторов
    """
    k_min = min(top_n, len(scores))
    topk = torch.topk(scores, k=k_min)

    results = []
    for idx, score in zip(topk.indices.tolist(), topk.values.tolist()):
        paper = candidates[idx]
        paper["score"] = float(score)
        paper["info"] = fetch_authors_metadata(paper)
        results.append(paper)

    logger.info(f"Выбрано {len(results)} статей с наивысшими оценками")
    return results


def fetch_authors_metadata(paper: dict) -> list[dict]:
    """
        Получаем метаданные об авторах статьи
    """
    try:
        link = paper.get("link", "")
        arxiv_id = link.split("/")[-1] if link else ""
        authors = get_authors_meta(arxiv_id)
        logger.info(f"Получены метаданные авторов для статьи '{paper.get('title', '')}'")
        return authors
    except Exception as e:
        logger.exception(f"Не удалось получить авторов для '{paper.get('title', '')}': {e}")
        return []


def save_results(results: list[dict], directory: str) -> str:
    """
        Сохраняем результаты в JSON файл
    """
    os.makedirs(directory, exist_ok=True)
    filepath = os.path.join(directory, "results.json")

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    logger.info(f"Результаты сохранены в {filepath}")
    return filepath


def get_recommendations(query: str) -> list[dict]:
    """
        Ищем и ранжируем статьи с arXiv по запросу пользователя
    """
    logger.info(f"Начало поиска статей по запросу: '{query}'")
    model = SentenceTransformer(MODEL_NAME)
    arxiv_candidates = fetch_arxiv_for_query(query)

    if not arxiv_candidates:
        logger.warning(f"Не найдено статей по запросу: '{query}'")
        return []

    texts = prepare_texts(arxiv_candidates)
    scores = compute_similarity(query, texts, model)
    top_results = extract_top_results(scores, arxiv_candidates, TOP_N_DEFAULT)
    save_results(top_results, RESULTS_DIR)
    ranked_articles = sort_articles(top_results, query, top_n=TOP_RESULT)
    logger.info(f"Поиск и ранжирование завершены для запроса: '{query}'")
    return ranked_articles
