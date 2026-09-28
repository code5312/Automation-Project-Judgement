from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.patent_evidence.bm25 import BM25Index, tokenize, tokenize_korean_ngrams
from src.patent_evidence.cli import load_jsonl, validate_corpus, validate_eval
from src.patent_evidence.metrics import evaluate_cases, recall_at_k, reciprocal_rank


class BaselineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corpus = load_jsonl(ROOT / "data" / "corpus_fixture.jsonl")
        cls.eval_rows = load_jsonl(ROOT / "data" / "eval_fixture.jsonl")
        validate_corpus(cls.corpus)
        validate_eval(cls.eval_rows, {row["doc_id"] for row in cls.corpus})
        cls.index = BM25Index(cls.corpus)

    def test_korean_tokenizer_is_deterministic(self):
        self.assertEqual(
            tokenize("웨이퍼-map, 결함! 123"),
            ["웨이퍼", "map", "결함", "123"],
        )

    def test_ngram_tokenizer_handles_surface_variation_but_not_synonyms(self):
        self.assertIn("ko:냉각", tokenize_korean_ngrams("냉각장치"))
        self.assertIn("ko:냉각", tokenize_korean_ngrams("냉각 시스템"))
        self.assertFalse(set(tokenize_korean_ngrams("냉각")) &
                         set(tokenize_korean_ngrams("열관리")))

    def test_fixture_queries_retrieve_a_gold_document_at_rank_1(self):
        for case in self.eval_rows:
            ranked = self.index.search(case["query"])
            self.assertIn(ranked[0].doc_id, set(case["gold_doc_ids"]))

    def test_metrics(self):
        ranked = ["a", "b", "c"]
        gold = {"b", "c"}
        self.assertEqual(recall_at_k(ranked, gold, 1), 0.0)
        self.assertEqual(recall_at_k(ranked, gold, 2), 0.5)
        self.assertEqual(reciprocal_rank(ranked, gold), 0.5)

    def test_evaluate_cases_has_expected_shape(self):
        raw = []
        for case in self.eval_rows:
            ranked = self.index.search(case["query"])
            raw.append({
                "case_id": case["case_id"],
                "query": case["query"],
                "gold_doc_ids": case["gold_doc_ids"],
                "ranked_ids": [r.doc_id for r in ranked],
            })
        result = evaluate_cases(raw)
        self.assertIn("mrr", result["aggregate"])
        self.assertIn("recall@5", result["aggregate"])
        self.assertEqual(len(result["cases"]), len(self.eval_rows))


if __name__ == "__main__":
    unittest.main()
