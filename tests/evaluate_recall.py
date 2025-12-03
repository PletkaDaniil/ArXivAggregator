import json

# загружаем данные
with open("tests/datasets/ground_truth.json", "r", encoding="utf-8") as f:
    gt = json.load(f)

with open("tests/datasets/real_results.json", "r", encoding="utf-8") as f:
    results = json.load(f)

results_dict = {item["query"]: set(item.get("results", [])) for item in results}

all_true_positives = 0
all_gt_titles = 0

# обрабатываем каждый запрос
for item in gt:
    query = item["query"]
    gt_titles = {res["title"] for res in item.get("predicted", [])}
    results_titles = results_dict.get(query, set())

    true_positives = gt_titles.intersection(results_titles)
    recall = len(true_positives) / len(gt_titles) if gt_titles else 0.0

    print(f"Запрос: {query}")
    print("Recall:", recall)
    print("-" * 30)

    all_true_positives += len(true_positives)
    all_gt_titles += len(gt_titles)


# считаем общий (средний) recall
overall_recall = all_true_positives / all_gt_titles if all_gt_titles else 0.0
print("Общий recall по всем запросам:", overall_recall)