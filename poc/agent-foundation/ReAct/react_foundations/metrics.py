"""HotpotQA exact-match and token F1 (Yang et al., 2018 / official ReAct wrappers)."""

from __future__ import annotations

import re
import string
from collections import Counter


def normalize_answer(text: str) -> str:
    def remove_articles(value: str) -> str:
        return re.sub(r"\b(a|an|the)\b", " ", value)

    def white_space_fix(value: str) -> str:
        return " ".join(value.split())

    def remove_punc(value: str) -> str:
        return "".join(ch for ch in value if ch not in set(string.punctuation))

    return white_space_fix(remove_articles(remove_punc(text.lower())))


def exact_match(prediction: str | None, ground_truth: str) -> bool:
    if prediction is None:
        return False
    return normalize_answer(prediction) == normalize_answer(ground_truth)


def f1_score(prediction: str | None, ground_truth: str) -> float:
    if prediction is None:
        return 0.0
    pred = normalize_answer(prediction)
    gold = normalize_answer(ground_truth)
    if pred in {"yes", "no", "noanswer"} and pred != gold:
        return 0.0
    if gold in {"yes", "no", "noanswer"} and pred != gold:
        return 0.0
    pred_tokens = pred.split()
    gold_tokens = gold.split()
    common = Counter(pred_tokens) & Counter(gold_tokens)
    num_same = sum(common.values())
    if num_same == 0:
        return 0.0
    precision = num_same / len(pred_tokens)
    recall = num_same / len(gold_tokens)
    return (2 * precision * recall) / (precision + recall)
