import os
import json
import networkx as nx
from app.authors_graph.graph_seed import build_author_seed_graph
from app.logs.graph_logger import logger

GRAPH_FILE = "app/results/graph.gexf"
JSON_FILE = "app/results/results.json"


def build_graph(topics: list) -> nx.Graph:
    """
        Строит граф соавторов
    """

    # создаём стартовый граф (или загружаем из файла)
    if os.path.exists(GRAPH_FILE):
        logger.info(f"Загружаем готовый граф из файла {GRAPH_FILE}")
        G = nx.read_gexf(GRAPH_FILE)
    else:
        logger.info("Файл с графом не найден. Строим стартовый граф авторов...")
        G = build_author_seed_graph(topics)
        logger.info(f"Сохраняем новый стартовый граф в файл {GRAPH_FILE}")
        nx.write_gexf(G, GRAPH_FILE)

    # добавляем новых авторов
    if os.path.exists(JSON_FILE):
        logger.info(f"Добавляем статьи из файла {JSON_FILE}")

        with open(JSON_FILE, "r", encoding="utf-8") as f:
            papers = json.load(f)

        for paper in papers:
            authors = paper.get("info", {}).get("authors", [])
            if authors:
                add_coauthor_edges(G, authors)

        logger.info(
            f"После добавления статей: число вершин={G.number_of_nodes()}, число рёбер={G.number_of_edges()}"
        )
    else:
        logger.warning(f"JSON файл {JSON_FILE} не найден. Новые статьи не добавлены.")

    nx.write_gexf(G, GRAPH_FILE)
    logger.info(f"Граф успешно сохранён в {GRAPH_FILE}")

    return G



def add_coauthor_edges(G: nx.Graph, authors: list):
    """
        Добавляем вершины и рёбра между всеми парами авторов статьи (с нужным весом)
    """
    nodes = []
    for author in authors:
        name = author.get("name")
        author_id = str(author.get("authorId"))
        is_seed = author.get("is_seed", 0)
        if not name or not author_id:
            continue

        if author_id not in G:
            logger.info(f"Добавляем в граф нового автора: {name} (ID: {author_id})")
            G.add_node(author_id, name=name, is_seed=is_seed)

        nodes.append(author_id)

    for ind in range(len(nodes)):
        for jnd in range(ind + 1, len(nodes)):
            u, v = nodes[ind], nodes[jnd]

            # вес = 3 если один из авторов seed, иначе 1
            edge_weight = 3 if (
                G.nodes[u]["is_seed"] == 1 or G.nodes[v]["is_seed"] == 1
            ) else 1

            if G.has_edge(u, v):
                G[u][v]['weight'] += edge_weight
            else:
                G.add_edge(u, v, weight=edge_weight)

