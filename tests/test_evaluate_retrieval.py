from pathlib import Path
import json
import pytest
from evaluate_retrieval import evidence_scores, load_records, normalize


def test_scores_and_source_identity():
    record = {'source_path': 'a.md', 'ground_truth_chunks': ['First fact.', 'Second fact.']}
    contexts = [{'file_path': 'a.md', 'text': 'First  fact.'}, {'file_path': 'b.md', 'text': 'Second fact.'}]
    scores = evidence_scores(record, contexts, 3, Path.cwd())
    assert scores['hit_rate'] == 1
    assert scores['evidence_precision'] == 1 / 3
    assert scores['evidence_recall'] == 0.5
    assert evidence_scores(record, [], 1, Path.cwd())['hit_rate'] == 0


def test_duplicates_and_split_evidence():
    record = {'source_path': 'a', 'ground_truth_chunks': ['one two', 'one two']}
    contexts = [{'file_path': 'a', 'text': text} for text in ['one', 'two']]
    assert evidence_scores(record, contexts, 2, Path.cwd())['evidence_recall'] == 0
    assert normalize('e\u0301\n x') == 'é x'


def test_dataset_validation(tmp_path):
    path = tmp_path / 'data.jsonl'
    record = dict(record_id='id', question='q', ground_truth_answer='a', source_path='p', ground_truth_chunks=['e'])
    path.write_text(json.dumps(record) + '\n' + json.dumps(record))
    with pytest.raises(ValueError, match='Duplicate'):
        load_records(path)
