from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from qwen_agentic_ft.extract.filters import validate_chunk
from qwen_agentic_ft.extract.instructions import instruction_from_chunk
from qwen_agentic_ft.extract.notebooks import extract_notebook_chunks
from qwen_agentic_ft.extract.parser import code_hash, extract_chunks_from_file, iter_repo_source_files
from qwen_agentic_ft.config import PROCESSED_DIR, REPOS_DIR


@dataclass
class TrainingExample:
    messages: list[dict[str, str]]
    metadata: dict


def chunk_to_example(chunk, instruction: str, system_prompt: str) -> TrainingExample:
    return TrainingExample(
        messages=[
            {"role": "system", "content": system_prompt.strip()},
            {"role": "user", "content": instruction.strip()},
            {"role": "assistant", "content": chunk.code.strip()},
        ],
        metadata={
            "repo": chunk.repo_name,
            "framework": chunk.framework,
            "source_file": chunk.source_file,
            "chunk_type": chunk.chunk_type,
            "name": chunk.name,
            "patterns": chunk.patterns,
            "imports": chunk.imports,
            "code_hash": code_hash(chunk.code),
        },
    )


def write_jsonl(path: Path, rows: list[TrainingExample]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            payload = {"messages": row.messages, **row.metadata}
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def run_extraction(
    repo_config: dict,
    extraction_config: dict,
    repos_root: Path = REPOS_DIR,
    processed_dir: Path = PROCESSED_DIR,
) -> dict:
    defaults = repo_config.get("defaults", {})
    val_repo_names = {
        name.split("/")[-1] if "/" in name else name.replace("langchain-ai/", "")
        for name in repo_config.get("val_repos", [])
    }
    # Normalize val repo names to match repo `name` fields
    val_names = set()
    for val in repo_config.get("val_repos", []):
        slug = val.split("/")[-1]
        val_names.add(slug)

    system_prompt = extraction_config["system_prompt"]
    dedupe_cfg = extraction_config.get("dedupe_normalize", {})
    seen_hashes: set[str] = set()
    train_rows: list[TrainingExample] = []
    val_rows: list[TrainingExample] = []
    stats = {
        "files_scanned": 0,
        "chunks_found": 0,
        "accepted": 0,
        "rejected": {},
        "by_repo": {},
        "by_framework": {},
    }

    for repo in repo_config.get("repos", []):
        repo_name = repo["name"]
        repo_root = repos_root / repo_name
        if not repo_root.exists():
            stats["by_repo"][repo_name] = {"error": "repo_not_cloned"}
            continue

        repo_stats = {"files": 0, "accepted": 0, "rejected": {}}
        for path in iter_repo_source_files(repo_root, repo, defaults):
            stats["files_scanned"] += 1
            repo_stats["files"] += 1
            try:
                if path.suffix == ".ipynb":
                    chunks = extract_notebook_chunks(path, repo_root, repo_name, repo["framework"])
                else:
                    chunks = extract_chunks_from_file(path, repo_root, repo_name, repo["framework"])
            except (SyntaxError, json.JSONDecodeError):
                continue

            stats["chunks_found"] += len(chunks)
            for chunk in chunks:
                ok, reason = validate_chunk(
                    chunk,
                    min_code_chars=extraction_config["min_code_chars"],
                    max_code_chars=extraction_config["max_code_chars"],
                    required_import_markers=extraction_config["required_import_markers"],
                    deprecated_patterns=extraction_config["deprecated_patterns"],
                )
                if not ok:
                    stats["rejected"][reason or "unknown"] = stats["rejected"].get(reason or "unknown", 0) + 1
                    repo_stats["rejected"][reason or "unknown"] = repo_stats["rejected"].get(reason or "unknown", 0) + 1
                    continue

                digest = code_hash(chunk.code)
                if digest in seen_hashes:
                    stats["rejected"]["duplicate"] = stats["rejected"].get("duplicate", 0) + 1
                    continue
                seen_hashes.add(digest)

                instruction = instruction_from_chunk(chunk)
                if not instruction or len(instruction) < extraction_config["min_instruction_chars"]:
                    stats["rejected"]["weak_instruction"] = stats["rejected"].get("weak_instruction", 0) + 1
                    continue
                if len(instruction) > extraction_config["max_instruction_chars"]:
                    instruction = instruction[: extraction_config["max_instruction_chars"]].rsplit(" ", 1)[0] + "..."

                example = chunk_to_example(chunk, instruction, system_prompt)
                target = val_rows if repo_name in val_names else train_rows
                target.append(example)
                stats["accepted"] += 1
                repo_stats["accepted"] += 1
                stats["by_framework"][repo["framework"]] = stats["by_framework"].get(repo["framework"], 0) + 1

        stats["by_repo"][repo_name] = repo_stats

    output = extraction_config["output"]
    train_path = processed_dir / Path(output["train_file"]).name
    val_path = processed_dir / Path(output["val_file"]).name
    meta_path = processed_dir / Path(output["metadata_file"]).name

    write_jsonl(train_path, train_rows)
    write_jsonl(val_path, val_rows)

    metadata = {
        "train_count": len(train_rows),
        "val_count": len(val_rows),
        "stats": stats,
        "dedupe_normalize": dedupe_cfg,
        "val_repos": sorted(val_names),
    }
    meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    return {
        "train_path": str(train_path),
        "val_path": str(val_path),
        "metadata_path": str(meta_path),
        **metadata,
    }
