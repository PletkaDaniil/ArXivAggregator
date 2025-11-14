import io
import os
import fitz
import time
import requests
from openai import OpenAI
from dotenv import load_dotenv
from app.logs.arxiv_logger import logger


MODEL = "openai/gpt-4o-mini"
ARXIV_PDF_URL = "https://arxiv.org/pdf/{id}.pdf"


def fetch_pdf_text(arxiv_id: str) -> str:
    """
        Скачиваем и извлекаем содержание статьи по arXiv ID (без сохранения)
    """
    pdf_url = ARXIV_PDF_URL.format(id=arxiv_id)
    logger.info(f"Скачивание PDF: {pdf_url}")

    try:
        response = requests.get(pdf_url)
        if response.status_code != 200:
            logger.error(f"Не удалось загрузить PDF: {pdf_url} (status {response.status_code})")
            raise RuntimeError(f"Не удалось загрузить PDF: {pdf_url}")

        with fitz.open(stream=io.BytesIO(response.content), filetype="pdf") as doc:
            text = "\n".join(page.get_text("text") for page in doc)

        logger.info(f"PDF успешно загружен и обработан: {arxiv_id}")
        return text

    except Exception as e:
        logger.exception(f"Ошибка при загрузке PDF {arxiv_id}: {e}")
        raise


def request_to_model(text: str, user_query: str) -> str:
    """
        Формируем запрос к модели для оценки статьи
        Поддержка retry и таймаута для предотвращения зависания
    """
    logger.info("Начало оценки статьи моделью")
    prompt = (
        "Evaluate this paper on a scale from 0 to 1.\n\n"
        "Important: give only the numeric score as output. Like '0.8' or '0.35'.\n"
        "Criteria:\n"
        "- Alignment with the user's query\n"
        "- Novelty, originality, and potential to influence future research trends\n"
        "- Papers that bring new perspectives or evidence should receive higher scores\n"
        "- Papers that mainly summarize background or well-known information should receive lower scores\n\n"
        f"User query: {user_query}\n\n"
        f"Paper text:\n{text}"
    )

    for attempt in range(5):
        try:
            
            load_dotenv()
            client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=os.getenv("OPENROUTER_API_KEY"),
            )

            completion = client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
                timeout=30
            )

            result = completion.choices[0].message.content.strip()
            logger.info(f"Оценка статьи завершена успешно. Результат: {result}")
            return result

        except Exception as e:
            logger.warning(f"Ошибка при обращении к модели: {e}, попытка {attempt+1}/{5}")
            time.sleep(2 ** attempt)

    logger.error("Не удалось получить результат от модели после всех попыток")
    return "error"



def process_paper(arxiv_id: str, user_query: str) -> str:
    """
        Получаем и извлекаем полный текст статьи по arXiv ID
        Потом возвращаем результат оценки модели
    """
    try:
        text = fetch_pdf_text(arxiv_id)
        evaluation = request_to_model(text, user_query)
        return evaluation
    except Exception as e:
        logger.error(f"Не удалось обработать статью {arxiv_id}: {e}")
        return "error"
