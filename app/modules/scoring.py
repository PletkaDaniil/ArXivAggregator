import re
import numpy as np
import networkx as nx
from app.modules.pdf_processing import process_paper
from app.authors_graph.graph_ranking import get_author_rank, graph_builder
from app.logs.compute_logger import logger


AUTHOR_WEIGHTS = {
    "h_index": 0.5,
    "author_rank": 0.3,
    "paper_count": 0.1,
    "citations": 0.1,
}

GLOBAL_WEIGHTS = {
    "article_citations": 0.4,
    "author_score": 0.3,
    "paper_analysis": 0.3
}


def extract_arxiv_id(link: str) -> str:
    """
        Извлекает arXiv ID из ссылки на статью
    """
    if not link:
        return ""

    parts = link.rstrip("/").split("/")
    arxiv_id = parts[-1] if parts else ""
    logger.info(f"Извлечён arXiv ID: {arxiv_id}")
    return arxiv_id


def normalize(values: list) -> list:
    """
        Min-max нормализация данных
    """
    if not values:
        return [0.0]

    v_min, v_max = min(values), max(values)
    if v_min == v_max:
        return [0.5] * len(values)

    return [(v - v_min) / (v_max - v_min) for v in values]


def compute_author_scores(articles: list[dict]) -> list:
    """
        Считаем средний авторский score для каждой статьи
    """
    logger.info("Начат расчёт авторских оценок")

    all_h, all_p, all_c, all_r = [], [], [], []

    G = graph_builder()
    logger.info(f"Граф авторов загружен")

    # собираем все метрики
    for art in articles:
        for a in art.get("info", {}).get("authors", []):
            all_h.append(a.get("hIndex", 0))
            all_p.append(a.get("paperCount", 0))
            all_c.append(a.get("citationCount", 0))
            all_r.append(get_author_rank(G, a.get("authorId", "")))

    norm_h = normalize(all_h)
    norm_p = normalize(all_p)
    norm_c = normalize(all_c)
    norm_r = normalize(all_r)

    ind = 0
    author_means = []

    # пересчёт нормированных значений обратно в авторов
    for art in articles:
        authors = art.get("info", {}).get("authors", [])
        for a in authors:
            a["author_score"] = (
                AUTHOR_WEIGHTS["h_index"] * norm_h[ind] +
                AUTHOR_WEIGHTS["paper_count"] * norm_p[ind] +
                AUTHOR_WEIGHTS["citations"] * norm_c[ind] +
                AUTHOR_WEIGHTS["author_rank"] * norm_r[ind]
            )
            ind += 1

        mean_score = np.mean([a["author_score"] for a in authors]) if authors else 0
        author_means.append(mean_score)

    logger.info("Расчёт авторских оценок завершён")
    return author_means


def compute_llm_scores(articles: dict, user_query: str) -> list:
    """
        Получает финальный score от выбранной LLM модели для каждой статьи
    """
    logger.info("Начат расчёт LLM-оценок статей")

    llm_scores = []

    for art in articles:
        arxiv_id = extract_arxiv_id(art.get("link", ""))

        if not arxiv_id:
            llm_scores.append(0)
            art["llm_score"] = 0
            continue

        raw = process_paper(arxiv_id, user_query)
        text = str(raw).strip()

        score = 0.5
        try:
            match = re.search(r"([0-1]\.\d+)", text)
            if match:
                score = float(match.group())
        except:
            pass

        art["llm_score"] = score
        llm_scores.append(score)

    logger.info("Расчёт LLM-оценок завершён")
    return llm_scores


def compute_article_scores(articles: list[dict], user_query: str) -> list:
    """
        Считаем итоговый score статьи
    """
    logger.info("Начат расчёт итоговых оценок статей")

    if not articles:
        logger.error("Статей нет — расчёт невозможен")
        return []

    citations = [a.get("info", {}).get("citation_count", 0) for a in articles]
    author_means = compute_author_scores(articles)
    llm_scores = compute_llm_scores(articles, user_query)

    norm_citations = normalize(citations)
    norm_authors = normalize(author_means)
    norm_llm = normalize(llm_scores)

    for ind, art in enumerate(articles):
        logger.info(f"Статья: {art.get('title', 'Без названия')}, "
                    f"Норм. цитирования: {norm_citations[ind]:.4f}, "
                    f"Норм. авторский score: {norm_authors[ind]:.4f}, "
                    f"Норм. LLM score: {norm_llm[ind]:.4f}")
        art["criteria_score"] = round(
            GLOBAL_WEIGHTS["article_citations"] * norm_citations[ind] +
            GLOBAL_WEIGHTS["author_score"] * norm_authors[ind] +
            GLOBAL_WEIGHTS["paper_analysis"] * norm_llm[ind], 4
        )

    logger.info("Итоговые оценки статей рассчитаны")
    return articles


def sort_articles(articles: list[dict], user_query: str, top_n: int) -> list:
    logger.info(f"Сортировка статей. Требуемое количество: {top_n}")

    articles = compute_article_scores(articles, user_query)
    articles.sort(key=lambda x: x.get("criteria_score", 0), reverse=True)

    logger.info("Сортировка статей завершена")
    return articles[:top_n]
