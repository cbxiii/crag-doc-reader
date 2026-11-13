"""Evaluate retrieval against synthetic evidence, optionally using RAGAS."""
import argparse
import asyncio
import csv
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import time
import unicodedata


def normalize(text: str) -> str:
    """Normalize Unicode and whitespace without changing wording."""
    return ' '.join(unicodedata.normalize('NFC', text).split())


def source_key(value: str, root: Path) -> str:
    """Resolve a source relative to the corpus root."""
    return str((root / value).resolve())


def evidence_scores(record: dict, contexts: list[dict], k: int, root: Path) -> dict:
    """Calculate conservative exact-evidence metrics."""
    evidence = list(dict.fromkeys(map(normalize, record['ground_truth_chunks'])))
    matches = [[i for i, text in enumerate(evidence)
                if text in normalize(context['text'])]
               if source_key(context['file_path'], root) == source_key(record['source_path'], root)
               else [] for context in contexts[:k]]
    covered = {i for match in matches for i in match}
    return {'hit_rate': int(bool(covered)),
            'evidence_precision': sum(bool(m) for m in matches) / k,
            'evidence_recall': len(covered) / len(evidence), 'matches': matches}


def load_records(path: Path) -> list[dict]:
    """Read and validate the complete dataset before any model calls."""
    records = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
    seen = set()
    for record in records:
        for key in ('record_id', 'question', 'ground_truth_answer', 'source_path'):
            if not isinstance(record.get(key), str) or not record[key].strip():
                raise ValueError(f'Invalid {key}')
        chunks = record.get('ground_truth_chunks')
        if not isinstance(chunks, list) or not chunks or any(not isinstance(c, str) or not c.strip() for c in chunks):
            raise ValueError('Invalid evidence')
        if record['record_id'] in seen:
            raise ValueError('Duplicate record ID')
        seen.add(record['record_id'])
    if not records:
        raise ValueError('Empty dataset')
    return records


class Judge:
    """Optional, bounded RAGAS adapter; no candidate response is generated."""

    def __init__(self, model: str):
        from langchain_openai import ChatOpenAI
        from ragas.llms import LangchainLLMWrapper
        from ragas.metrics import LLMContextPrecisionWithReference, LLMContextRecall
        llm = LangchainLLMWrapper(ChatOpenAI(model=model, temperature=0, timeout=60, max_retries=2))
        self.precision = LLMContextPrecisionWithReference(llm=llm)
        self.recall = LLMContextRecall(llm=llm)

    async def score(self, record: dict, contexts: list[dict], cutoffs: list[int]) -> dict:
        from ragas import SingleTurnSample
        verdicts = []
        async def measure(metric, texts):
            sample = SingleTurnSample(user_input=record['question'], reference=record['ground_truth_answer'], retrieved_contexts=texts)
            return float(await asyncio.wait_for(metric.single_turn_ascore(sample), timeout=120))
        for context in contexts:
            verdicts.append(await measure(self.precision, [context['text']]))
        result = {}
        for k in cutoffs:
            texts = [c['text'] for c in contexts[:k]]
            result[str(k)] = {'judged_precision': sum(verdicts[:k]) / k,
                              'context_precision': await measure(self.precision, texts) if texts else 0.0,
                              'context_recall': await measure(self.recall, texts) if texts else 0.0}
        return result


def main() -> int:
    """Run retrieval once per record and save inspectable reports."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, default=Path('synthetic_ground_truth/dataset.jsonl'))
    parser.add_argument('--store-dir', type=Path, default=Path('/media/volume/crag-vectorstore'))
    parser.add_argument('--corpus-root', type=Path, default=Path.cwd())
    parser.add_argument('--k', type=int, nargs='+', default=[1, 3, 5, 10])
    parser.add_argument('--limit', type=int)
    parser.add_argument('--output-dir', type=Path, default=Path('evaluation_results'))
    parser.add_argument('--judge', action='store_true')
    parser.add_argument('--judge-model', default='gpt-4o-mini')
    args = parser.parse_args()
    if min(args.k) < 1 or (args.limit is not None and args.limit < 1):
        parser.error('K and limit must be positive')
    records = load_records(args.dataset)
    if args.limit:
        records = records[:args.limit]
    from retrieval import search
    from vector_store_utils import load_existing_data
    sentences, _, index, _ = load_existing_data(args.store_dir)
    if index is None or not sentences or index.ntotal != len(sentences):
        raise ValueError('Missing or inconsistent index and metadata')
    judge = Judge(args.judge_model) if args.judge else None
    cutoffs = sorted(set(args.k))
    destination = args.output_dir / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    destination.mkdir(parents=True)
    rows = []
    retrieval_failures = judge_failures = 0
    with (destination / 'results.jsonl').open('w', encoding='utf-8') as output:
        for record in records:
            result = {'record_id': record['record_id'], 'question': record['question']}
            started = time.monotonic()
            try:
                contexts = [dict(asdict(chunk), score=score, rank=i + 1)
                            for i, (chunk, score) in enumerate(search(index, sentences, record['question'], max(cutoffs)))]
                result['retrieval_seconds'] = time.monotonic() - started
                result['contexts'] = contexts
                result['unmatchable_evidence'] = [e for e in record['ground_truth_chunks'] if not any(
                    source_key(s.file_path, args.corpus_root) == source_key(record['source_path'], args.corpus_root)
                    and normalize(e) in normalize(s.text) for s in sentences)]
                metrics = {str(k): evidence_scores(record, contexts, k, args.corpus_root) for k in cutoffs}
                if judge:
                    try:
                        judged = asyncio.run(judge.score(record, contexts, cutoffs))
                        for k in cutoffs:
                            metrics[str(k)].update(judged[str(k)])
                    except Exception as error:
                        judge_failures += 1
                        result['judge_error'] = str(error)
                result['metrics'] = metrics
                for k, scores in metrics.items():
                    rows.append({'record_id': record['record_id'], 'k': k, **{key: value for key, value in scores.items() if key != 'matches'}})
            except Exception as error:
                retrieval_failures += 1
                result['retrieval_error'] = str(error)
            output.write(json.dumps(result, ensure_ascii=False, allow_nan=False) + '\n')
            output.flush()
    fields = ['record_id', 'k', 'hit_rate', 'evidence_precision', 'evidence_recall', 'judged_precision', 'context_precision', 'context_recall']
    with (destination / 'metrics.csv').open('w', newline='', encoding='utf-8') as output:
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    def digest(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()
    summary = {'total': len(records), 'retrieval_failures': retrieval_failures, 'judge_failures': judge_failures,
               'complete': not (retrieval_failures or judge_failures), 'configuration': vars(args).copy(),
               'matching_policy': 'NFC whitespace normalized, case-sensitive same-source substring',
               'fingerprints': {name: digest(path) for name, path in [('dataset', args.dataset), ('index', args.store_dir / 'index.faiss'), ('metadata', args.store_dir / 'metadata.json')]},
               'versions': {package: importlib.metadata.version(package) for package in ['numpy', 'faiss-cpu'] + (['ragas'] if judge else [])},
               'embedding_model': json.loads((args.store_dir / 'metadata.json').read_text()).get('embedding_model', 'unknown'), 'metrics': {}}
    for k in cutoffs:
        summary['metrics'][str(k)] = {}
        for metric in fields[2:]:
            values = [row[metric] for row in rows if row['k'] == str(k) and metric in row]
            summary['metrics'][str(k)][metric] = {'mean': sum(values) / len(values) if values else None, 'count': len(values)}
    (destination / 'summary.json').write_text(json.dumps(summary, default=str, indent=2), encoding='utf-8')
    print(destination)
    return int(not summary['complete'])


if __name__ == '__main__':
    raise SystemExit(main())
