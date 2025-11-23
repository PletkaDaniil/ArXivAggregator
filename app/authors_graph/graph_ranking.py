import networkx as nx
from app.authors_graph.graph_builder import build_graph
from app.logs.graph_logger import logger

TOPICS = [
    "LLM",
    "LLM Training & Optimization",
    "LLM-Agents",
    "Benchmarks for LLMs",
    "Prompt Engineering",
    "Information Retrieval Systems",
    "Artificial Intelligence",
    "Machine Learning",
    "Computer Science",
    "Natural Language Processing"
]

def graph_builder() -> nx.Graph:
    """
        Возвращаем граф авторов
    """
    return build_graph(TOPICS)


def get_author_rank(G: nx.graph, author_id: str) -> float:
    """
        Возвращаем PageRank автора
    """
    pr = nx.pagerank(G, weight="weight")

    # ищем вершину по author_id
    for node, score in pr.items():
        node_id = node[1] if isinstance(node, tuple) else str(node)
        if node_id == author_id:
            return score

    logger.warning(f"Автор с ID {author_id} не найден в графе")
    return 0.0
