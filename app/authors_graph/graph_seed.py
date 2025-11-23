import requests
import networkx as nx
import time
from app.logs.graph_logger import logger

API_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
LIMIT = 20
DELAY = 3


def fetch_papers_for_topic(topic: str) -> list:
    """
        Возвращаем список статей, отсортированных по числу цитирований
    """
    logger.info(f"Запрос статей для темы: '{topic}', limit={LIMIT}")
    attempts, delay = 0, DELAY
    parameters = {
        "query": topic,
        "limit": LIMIT,
        "fields": "paperId,title,citationCount,authors",
        "sort": "citationCount:desc"
    }

    while attempts < 5:
        try:
            response = requests.get(
                API_URL, 
                params=parameters,
                timeout=30
            )
            if response.status_code == 200:
                data = response.json()
                papers = data.get("data", [])
                logger.info(
                    f"Тема '{topic}': получено статей={len(papers)}. "
                    f"Топовая статья: {papers[0]['title'] if papers else '—'}"
                )
                
                return papers
            
            if response.status_code == 429:
                logger.warning(f"Слишком много запросов к API. Ждём {delay} секунд...")
                time.sleep(delay)
                delay *= 2
                attempts += 1
                continue
            
            logger.error(f"Ошибка API ({response.status_code}): {response.text}")
            return None
        
        except requests.RequestException as e:
            logger.error(f"Ошибка соединения при запросе тематики '{topic}': {e}")
            time.sleep(delay)
            delay *= 2
            attempts += 1 
        attempts += 1 

    logger.error(f"Превышено число попыток для темы '{topic}'")
    return []


def add_paper_to_graph(G: nx.Graph, paper: dict):
    """
        Добавляем всех авторов статьи в граф + рёбра между ними
    """
    title = paper.get("title")
    paper_id = paper.get("paperId")
    authors = paper.get("authors", [])
    logger.info(f"Добавление статьи '{title}', id: {paper_id}, авторов={len(authors)}")
    author_nodes = []

    # добавляем узлы авторов
    for author in authors:
        author_id = str(author.get("authorId"))
        author_name = author.get("name", "Unknown")

        if author_id is None:
            logger.warning(f"Пропуск автора без ID: {author}")
            continue

        if author_id not in G:
            G.add_node(author_id, name=author_name, is_seed=1)

        author_nodes.append(author_id)

    # создаём рёбра между всеми парами авторов одной статьи
    for ind in range(len(author_nodes)):
        for jnd in range(ind + 1, len(author_nodes)):
            u = author_nodes[ind]
            v = author_nodes[jnd]

            if G.has_edge(u, v):
                G[u][v]['weight'] += 3
            else:
                G.add_edge(u, v, weight=3)


def build_author_seed_graph(topics: list) -> nx.Graph:
    """
        Строим граф авторов, исспользуя популярные статьи (по заданным темам)
    """
    logger.info("Начинаем построение стартового графа авторов...")

    G = nx.Graph()

    for topic in topics:
        papers = fetch_papers_for_topic(topic)
        logger.info(f"Обработка {len(papers)} статей по теме '{topic}'")

        for paper in papers:
            add_paper_to_graph(G, paper)

    logger.info(
        f"Стартовый граф создан: число вершин={G.number_of_nodes()}, число рёбер={G.number_of_edges()}"
    )

    return G
