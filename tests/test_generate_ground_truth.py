import argparse
import json
from pathlib import Path

import pytest

import generate_ground_truth as gt


def words(count=90):
    return " ".join(f"word{i}" for i in range(count))


def test_nested_headings_exact_line_ranges():
    text = "preface\n# **Intro**\nbody one\n## Methods\nbody two\n"
    sections = gt.parse_sections(text, "paper.md")
    assert [(s.heading, s.start_line, s.end_line, s.text) for s in sections] == [
        ("paper.md", 1, 1, "preface\n"),
        ("Intro", 2, 3, "# **Intro**\nbody one\n"),
        ("Methods", 4, 5, "## Methods\nbody two\n"),
    ]


def test_heading_free_fallback_and_empty():
    section = gt.parse_sections("plain text\nsecond line\n", "paper.md")[0]
    assert (section.heading, section.start_line, section.end_line) == ("paper.md", 1, 2)
    assert section.text == "plain text\nsecond line\n"
    assert gt.parse_sections("", "paper.md") == []


def test_exclusions_front_matter_and_word_minimum():
    text = f"{words()}\n# Contents\n{words()}\n# Acknowledgments\n{words()}\n# Methods\nshort"
    assert [s.heading for s in gt.eligible_sections(text, "p.md", 80)] == ["p.md"]
    assert gt.eligible_sections(f"# Methods\n{words(79)}", "p.md", 80) == []


def test_even_selection_spans_document():
    sections = [gt.Section(str(i), i + 1, i + 1, "x") for i in range(21)]
    selected = gt.select_sections(sections, 10)
    assert [s.heading for s in selected] == ["0", "2", "4", "7", "9", "11", "13", "16", "18", "20"]


def test_exact_unicode_markdown_chunk_and_bad_chunks_retry(monkeypatch):
    exact = "**Coral reefs** support ʻāina — and *fish*."
    section = gt.Section("Results", 1, 1, exact)

    class FakeAgent:
        def __init__(self):
            self.calls = []

        def run_sync(self, prompt):
            self.calls.append(prompt)
            chunk = "altered" if len(self.calls) == 1 else exact
            return type("Result", (), {"output": gt.GroundTruthResponse(
                question="What do coral reefs support?", ground_truth_answer="ʻāina.", ground_truth_chunks=[chunk]
            )})()

    agent = FakeAgent()
    response, attempts, error = gt.request_record(agent, section, set(), 2)
    assert attempts == 2 and error is None
    assert response.ground_truth_chunks == [exact]
    assert "exact substring" in agent.calls[1]


def test_duplicate_question_is_rejected():
    section = gt.Section("Methods", 1, 1, "Evidence")
    response = gt.GroundTruthResponse(question="How?", ground_truth_answer="Here", ground_truth_chunks=["Evidence"])
    with pytest.raises(ValueError, match="duplicates"):
        gt.validate_response(response, section, {gt.question_key("HOW ?")})


def test_persistent_failure_continues_and_aggregates_sorted(tmp_path, monkeypatch):
    source_dir, output_dir = tmp_path / "output", tmp_path / "synthetic_ground_truth"
    source_dir.mkdir()
    text = f"# Methods\n{words()}\n# Results\n{words()}\n"
    (source_dir / "b.md").write_text(text, encoding="utf-8")
    (source_dir / "a.md").write_text(text, encoding="utf-8")

    class FakeAgent:
        def run_sync(self, prompt):
            if "Methods" in prompt:
                raise RuntimeError("provider unavailable")
            return type("Result", (), {"output": gt.GroundTruthResponse(
                question="What is reported?", ground_truth_answer="Results are reported.",
                ground_truth_chunks=[words()],
            )})()

    args = argparse.Namespace(force=False, min_section_words=80, max_sections_per_paper=10,
                               max_retries=1, model="openai:gpt-4o-mini")
    for path in sorted(source_dir.glob("*.md")):
        gt.process_paper(path, source_dir, output_dir, args, FakeAgent())
    gt.build_aggregates(output_dir)
    dataset = [json.loads(line) for line in (output_dir / "dataset.jsonl").read_text().splitlines()]
    failures = [json.loads(line) for line in (output_dir / "failures.jsonl").read_text().splitlines()]
    assert len(dataset) == 2 and len(failures) == 2
    assert [row["source_path"] for row in dataset] == ["output/a.md", "output/b.md"]
    assert all(row["attempt_count"] == 2 for row in failures)


def test_resume_force_and_source_change(tmp_path):
    source_dir, output_dir = tmp_path / "output", tmp_path / "synthetic_ground_truth"
    source_dir.mkdir()
    path = source_dir / "paper.md"
    path.write_text(f"# Methods\n{words()}\n", encoding="utf-8")
    args = argparse.Namespace(force=False, min_section_words=80, max_sections_per_paper=10,
                               max_retries=0, model="openai:gpt-4o-mini")

    class FakeAgent:
        calls = 0

        def run_sync(self, prompt):
            self.calls += 1
            return type("Result", (), {"output": gt.GroundTruthResponse(
                question=f"What is described {self.calls}?", ground_truth_answer="The method.",
                ground_truth_chunks=[words()],
            )})()

    agent = FakeAgent()
    gt.process_paper(path, source_dir, output_dir, args, agent)
    assert gt.process_paper(path, source_dir, output_dir, args, agent)["skipped"]
    assert agent.calls == 1
    args.force = True
    gt.process_paper(path, source_dir, output_dir, args, agent)
    assert agent.calls == 2
    args.force = False
    path.write_text(f"# Methods\n{words()}\nextra\n", encoding="utf-8")
    gt.process_paper(path, source_dir, output_dir, args, agent)
    assert agent.calls == 3


def test_atomic_write_and_validate_only_no_llm(tmp_path, monkeypatch):
    source_dir, output_dir = tmp_path / "output", tmp_path / "synthetic_ground_truth"
    source_dir.mkdir()
    path = source_dir / "paper.md"
    path.write_text(f"# Methods\n{words()}\n", encoding="utf-8")
    args = argparse.Namespace(force=False, min_section_words=80, max_sections_per_paper=10,
                               max_retries=0, model="openai:gpt-4o-mini")
    response = gt.GroundTruthResponse(question="What is described?", ground_truth_answer="The method.", ground_truth_chunks=[words()])
    section = gt.eligible_sections(path.read_text(), path.name, 80)[0]
    record = {"record_id": gt.record_identifier("paper", section), "paper_id": "paper", "source_path": "output/paper.md",
              "section_heading": section.heading, "section_start_line": section.start_line, "section_end_line": section.end_line,
              "model": args.model, "question": response.question, "ground_truth_answer": response.ground_truth_answer,
              "ground_truth_chunks": response.ground_truth_chunks}
    artifact = {"schema_version": gt.SCHEMA_VERSION, "source_path": "output/paper.md", "source_sha256": gt.sha256_text(path.read_text()),
                "status": "complete", "records": [record], "failures": []}
    target = gt.output_path_for(path, source_dir, output_dir)
    gt.atomic_json(target, artifact)
    assert json.loads(target.read_text()) == artifact
    assert not list(target.parent.glob("*.tmp"))
    gt.build_aggregates(output_dir)
    monkeypatch.setattr(gt, "make_agent", lambda _: (_ for _ in ()).throw(AssertionError("LLM constructed")))
    monkeypatch.setattr("sys.argv", ["generate_ground_truth.py", "--input-dir", str(source_dir), "--output-dir", str(output_dir), "--validate-only"])
    assert gt.main() == 0


def test_dry_run_no_llm_or_writes(tmp_path, monkeypatch, capsys):
    source_dir, output_dir = tmp_path / "output", tmp_path / "synthetic_ground_truth"
    source_dir.mkdir()
    (source_dir / "paper.md").write_text(f"# Methods\n{words()}\n", encoding="utf-8")
    monkeypatch.setattr(gt, "make_agent", lambda _: (_ for _ in ()).throw(AssertionError("LLM constructed")))
    monkeypatch.setattr("sys.argv", ["generate_ground_truth.py", "--input-dir", str(source_dir), "--output-dir", str(output_dir), "--dry-run"])
    assert gt.main() == 0
    assert "estimated_llm_calls=1" in capsys.readouterr().out
    assert not output_dir.exists()
