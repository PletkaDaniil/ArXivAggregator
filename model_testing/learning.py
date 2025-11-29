import os
import re
import json
from torch.utils.data import DataLoader
from model_testing.logs.model_logger import logger
from model_testing.arxiv_collector import build_arxiv_dataset
from model_testing.openalex_collector import build_openalex_dataset
from sentence_transformers import SentenceTransformer, InputExample, losses, util

OPENALEX_DATASET = "model_testing/datasets/openalex_dataset.json"
ARXIV_DATASET = "model_testing/datasets/arxiv_dataset.json"
QUERIES_FILE = "model_testing/queries.json"
TUNED_MODEL_DIR = "model_testing/tuned_model"
RECALL_LOG_FILE = "model_testing/recall_results.json"

MODEL_NAME = "all-MiniLM-L6-v2"
BATCH_SIZE = 32
EPOCHS = 3
TOP = 150


def train_model(openalex_data: list):
    """
        Обучаем модель (в нашем случае на разделе Computer Science)
    """
    logger.info("Начинаем обучение модели")

    model = SentenceTransformer(MODEL_NAME)

    train_examples = []
    cs_blocks = [block for block in openalex_data if block["topic"].lower() == "computer science"]
    logger.info(f"Найдено CS-блоков: {len(cs_blocks)}")

    for block in cs_blocks:
        query = block["query"]
        for item in block.get("results", []):
            if item.get("abstract"):
                paper_title = f"{item['title']}"
                # можно сделать иначе (немного сложнее) -> рассматривать и abstract тоже: 
                # texts = f"{item['title']}. {item['abstract']}" 
                # train_examples.append(InputExample(texts=[query, texts], label=1.0))
                train_examples.append(InputExample(texts=[query, paper_title], label=1.0))

    logger.info(f"Сформировано {len(train_examples)} обучающих примеров")

    if train_examples:
        split_idx = int(len(train_examples) * 0.7)
        train_data = train_examples[:split_idx]

        logger.info(f"Train: {len(train_data)} примеров (Общее количество примеров: {len(train_examples)})")

        train_loader = DataLoader(train_data, shuffle=True)
        loss = losses.CosineSimilarityLoss(model)

        logger.info("Запуск обучения")
        model.fit(
            train_objectives=[(train_loader, loss)],
            epochs=EPOCHS,
            show_progress_bar=True,
            output_path=TUNED_MODEL_DIR,
        )

        logger.info("Дообученная модель сохранена")
        

def normalize_title(title: str) -> str:
    """
        Нормализуем заголовок
    """
    return re.sub(r"[^a-zA-Z0-9]+", "", title.lower())


def prepare_texts(arxiv_data: list[dict]) -> list[str]:
    """
        Строим тексты, которые будем подавать модели на построение эмбеддингов
    """
    return [
        f"{data['title']}. {data['summary']}"
        for data in arxiv_data
        if data.get("summary")
    ]


def compute_embeddings(model, query: str, paper_texts: list[str]) -> tuple:
    """
        Строим эмбеддинги запроса и статей
    """
    logger.info(f"Строим эмбеддинги для запроса: {query}")
    query_emb = model.encode(query, convert_to_tensor=True)
    paper_embs = model.encode(
        paper_texts,
        convert_to_tensor=True,
        batch_size=BATCH_SIZE
    )
    return query_emb, paper_embs


def compute_recall(openalex_norm: set, arxiv_results: list, scores, top: int) -> float:
    """
        Считаем recall для одного запроса
    """
    top_idx = scores.topk(top).indices.tolist()
    top_titles = [arxiv_results[ind]["title"] for ind in top_idx]
    top_norm = {normalize_title(title) for title in top_titles}

    overlap = len(openalex_norm.intersection(top_norm))
    recall = overlap / len(openalex_norm) if openalex_norm else 0.0
    return recall


def validate_arxiv_block(query: str, arxiv_results: list, source: str, topic: str) -> bool:
    """
        Проверяем наличие данных arXiv для запроса
    """
    if not arxiv_results:
        logger.warning(f"Нет результатов arXiv по запросу '{query}'")
        append_recall_to_file(source, topic, query, 0.0, "no_arXiv_results")
        return False

    paper_texts = prepare_texts(arxiv_results)
    if not paper_texts:
        logger.warning(f"Нет summary у arXiv-результатов по запросу '{query}'")
        append_recall_to_file(source, topic, query, 0.0, "no_summary")
        return False

    return True


def evaluate_recall(current_model, openalex_data: list, arxiv_data: list, source: str):
    """ 
        Возвращаем и сохраняем значение recall по каждому запросу 
    """
    arxiv_by_query = {item["query"]: item["results"] for item in arxiv_data}

    for block in openalex_data:
        topic = block["topic"]
        query = block["query"]

        openalex_titles = [r["title"] for r in block.get("results", [])]
        openalex_norm = {normalize_title(t) for t in openalex_titles}

        arxiv_results = arxiv_by_query.get(query, [])
        if not validate_arxiv_block(query, arxiv_results, source, topic):
            continue

        paper_texts = prepare_texts(arxiv_results)
        query_emb, paper_embs = compute_embeddings(current_model, query, paper_texts)
        scores = util.cos_sim(query_emb, paper_embs)[0]
        k = min(TOP, len(scores))

        recall = compute_recall(openalex_norm, arxiv_results, scores, k)
        append_recall_to_file(source, topic, query, recall, "ok")


def append_recall_to_file(source: str, topic: str, query: str, recall: float, status: str):
    """
        Записываем значения recall в файлик
    """
    entry = {
        "source": source,
        "topic": topic,
        "query": query,
        "recall": recall,
        "status": status
    }
    if os.path.exists(RECALL_LOG_FILE):
        try:
            with open(RECALL_LOG_FILE, "r", encoding="utf-8") as f:
                dataset = json.load(f)
        except json.JSONDecodeError:
            dataset = []
    else:
        dataset = []

    dataset.append(entry)
    with open(RECALL_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(dataset, f, ensure_ascii=False, indent=2)


def check_dataset_exists(file_path: str) -> bool:
    """
        Проверяем, существует ли датасета
    """
    return os.path.exists(file_path)


def compute_average_recall(source: str) -> dict:
    """
        Считаем средний recall для запросов со статусом "ok" (по каждому разделу отдельно)
    """
    if not os.path.exists(RECALL_LOG_FILE):
        logger.warning(f"Файл логов с значениями recall не найден: {RECALL_LOG_FILE}")
        return {}

    with open(RECALL_LOG_FILE, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    recalls_by_topic = {}
    counts_by_topic = {}

    for entry in dataset:
        if entry["source"] == source and entry["status"] == "ok":
            topic = entry["topic"]
            recalls_by_topic[topic] = recalls_by_topic.get(topic, 0.0) + entry["recall"]
            counts_by_topic[topic] = counts_by_topic.get(topic, 0) + 1

    # вычисляем среднее
    avg_by_topic = {topic: recalls_by_topic[topic] / counts_by_topic[topic] 
                    for topic in recalls_by_topic}

    return avg_by_topic



def main():
    logger.info("Запуск main()")
    # на случай если нужно очистить автоматически прошлые результаты по recall-ам
    # if os.path.exists(RECALL_LOG_FILE):
    #     os.remove(RECALL_LOG_FILE)

    # читаем запросы
    if not os.path.exists(QUERIES_FILE):
        logger.error(f"Не найден файл с запросами: {QUERIES_FILE}")
        raise FileNotFoundError(f"Не найден файл: {QUERIES_FILE}")
    
    with open(QUERIES_FILE, "r", encoding="utf-8") as f:
        topics_data = json.load(f)

    # формируем датасеты (с arXiv и OpenAlex)
    if not check_dataset_exists(OPENALEX_DATASET):
        logger.info("Создаём датасет OpenAlex")
        build_openalex_dataset(topics_data)

    logger.info("Создаём датасет arXiv")
    build_arxiv_dataset(topics_data)

    with open(OPENALEX_DATASET, "r", encoding="utf-8") as f:
        openalex_data = json.load(f)

    with open(ARXIV_DATASET, "r", encoding="utf-8") as f:
        arxiv_data = json.load(f)

    # тестируем результаты модели
    # потом сравним с дообученной моделью

    logger.info("Загружаем базовую модель")
    base_model = SentenceTransformer(MODEL_NAME)
    evaluate_recall(
        base_model,
        openalex_data,
        arxiv_data,
        source="base_model"
    )

    train_model(openalex_data)

    logger.info("Загружаем дообученную модель")
    fine_model = SentenceTransformer(TUNED_MODEL_DIR)

    evaluate_recall(
        fine_model,
        openalex_data,
        arxiv_data,
        source="tuned_model"
    )

    avg_base = compute_average_recall("base_model")
    avg_tuned = compute_average_recall("tuned_model")

    for topic, avg in avg_base.items():
        logger.info(f"Средний Recall базовой модели для {topic}: {avg:.4f}")
    for topic, avg in avg_tuned.items():
        logger.info(f"Средний Recall дообученной модели для {topic}: {avg:.4f}")
    logger.info("Работа завершена")


if __name__ == "__main__":
    main()
