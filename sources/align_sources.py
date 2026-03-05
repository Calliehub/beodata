"""Produce canonical 6-way aligned-sources.txt from the 6 source model classes."""

import re
import tempfile
from pathlib import Path
from typing import List, NamedTuple, Tuple

from assets import get_asset_path
from beowulf_mcp.db import BeoDB
from logging_config import get_logger
from sources.brunetti import Brunetti

logger = get_logger()


class Token(NamedTuple):
    """A single token from an edition stream."""

    id_str: str  # e.g. "0001a1"
    text: str  # e.g. "Hwæt!"


def tokenize_edition_line(line_num: int, oe_text: str) -> List[Token]:
    """Tokenize a single edition line into Token objects.

    Splits on 5-space caesura into a/b halves, then whitespace within each half.

    ID offset rules (position starts at 0 per half):
    - @ gap: offset = position (no advance) — gaps don't consume a word slot
    - _ join: advance by 1 + count("_"), offset = pre-advance position + 1
    - Normal: advance by 1, offset = position
    """
    line_str = str(line_num).zfill(4)
    tokens: List[Token] = []

    parts = re.split(r"     ", oe_text, maxsplit=1)
    halves = [("a", parts[0])]
    if len(parts) > 1:
        halves.append(("b", parts[1]))

    for half_label, half_text in halves:
        words = half_text.split()
        position = 0
        for word in words:
            if word == "@":
                offset = position
            elif "_" in word:
                position += 1
                offset = position
                position += word.count("_")
            else:
                position += 1
                offset = position
            tokens.append(Token(f"{line_str}{half_label}{offset}", word))

    return tokens


def tokenize_simple_edition(lines: List[dict]) -> List[Token]:
    """Tokenize a full edition (list of {line, oe} dicts) into a flat token stream."""
    tokens: List[Token] = []
    for line_data in lines:
        tokens.extend(tokenize_edition_line(line_data["line"], line_data["oe"]))
    return tokens


def read_txt_edition(asset_name: str) -> List[dict]:
    """Read a text-file edition asset directly into [{line, oe}] dicts.

    For editions whose source class loads from a txt asset anyway (MIT, McMaster,
    eBeowulf, Perseus, Heorot-txt), this skips the DB round-trip entirely.
    """
    path = get_asset_path(asset_name)
    lines: List[dict] = []
    with open(path, encoding="utf-8") as f:
        for raw in f:
            raw = raw.rstrip("\n")
            if not raw.strip():
                continue
            match = re.match(r"^(\d+)\s+(.*)", raw)
            if match:
                lines.append({"line": int(match.group(1)), "oe": match.group(2)})
    return lines


def extract_brunetti_surface(oe_line: str, half_line: str, token_offset: int) -> str:
    """Extract the surface word from a Brunetti oe_line at the given position.

    Splits on 4-space caesura, takes the appropriate half, then extracts
    the N-th real word (skipping bracketed editorial text and non-letter tokens).
    """
    parts = re.split(r"    ", oe_line, maxsplit=1)
    if half_line == "a":
        half_text = parts[0]
    else:
        half_text = parts[1] if len(parts) > 1 else ""

    clean = re.sub(r"\[.*?\]", "", half_text)
    words = [w for w in clean.split() if re.search(r"[a-zA-ZæþðÆÞÐ]", w)]

    idx = token_offset - 1
    if 0 <= idx < len(words):
        return words[idx]
    return "@"


def load_brunetti_tokens(brunetti: Brunetti) -> List[Token]:
    """Load Brunetti tokens with surface text extracted from oe_line."""
    all_rows = brunetti.get_lines()
    tokens: List[Token] = []
    for row in all_rows:
        id_str = f"{row['line_id']}{row['half_line']}{row['token_offset']}"
        text = extract_brunetti_surface(
            row["oe_line"], row["half_line"], row["token_offset"]
        )
        tokens.append(Token(id_str, text))
    return tokens


def parse_mit_id(id_str: str) -> Tuple[int, str, int]:
    """Parse '0001a1' → (1, 'a', 1) for tuple comparison."""
    return (int(id_str[:4]), id_str[4], int(id_str[5:]))


def align_all(
    edition_streams: List[List[Token]],
    brunetti_tokens: List[Token],
) -> List[str]:
    """Align 5 text-file editions positionally and merge Brunetti via cursor walk.

    edition_streams order: [mit, mcmaster, heorot, ebeowulf, perseus]
    Output: 12 columns per line (6 IDs + 6 texts), space-separated.
    """
    counts = [len(s) for s in edition_streams]
    assert all(c == counts[0] for c in counts), f"Token count mismatch: {counts}"

    num_rows = counts[0]
    cursor = 0
    num_bru = len(brunetti_tokens)
    sentinel: Tuple[int, str, int] = (99999, "z", 99999)
    output_lines: List[str] = []

    for i in range(num_rows):
        row_tokens = [stream[i] for stream in edition_streams]
        mit_id = parse_mit_id(row_tokens[0].id_str)

        # Is this a join row? (any non-@ text contains _)
        is_join = any("_" in t.text for t in row_tokens if t.text != "@")

        # Compute range_end: mit_id of the first later row that differs
        if i + 1 < num_rows:
            next_mit = parse_mit_id(edition_streams[0][i + 1].id_str)
            if next_mit != mit_id:
                range_end = next_mit
            else:
                # mit stuck on same ID (@ gap) — scan forward
                range_end = sentinel
                for j in range(i + 2, num_rows):
                    candidate = parse_mit_id(edition_streams[0][j].id_str)
                    if candidate != mit_id:
                        range_end = candidate
                        break
        else:
            range_end = sentinel

        # Skip Brunetti tokens that fall before this row's mit_id
        while (
            cursor < num_bru and parse_mit_id(brunetti_tokens[cursor].id_str) < mit_id
        ):
            cursor += 1

        # Collect matching Brunetti tokens
        collected: List[Token] = []
        if is_join:
            # Grab all tokens in [mit_id, range_end)
            while (
                cursor < num_bru
                and parse_mit_id(brunetti_tokens[cursor].id_str) < range_end
            ):
                collected.append(brunetti_tokens[cursor])
                cursor += 1
        else:
            # Grab at most one token in [mit_id, range_end)
            if (
                cursor < num_bru
                and parse_mit_id(brunetti_tokens[cursor].id_str) < range_end
            ):
                collected.append(brunetti_tokens[cursor])
                cursor += 1

        # Format output
        if collected:
            bru_text = "_".join(t.text for t in collected)
            bru_id = collected[0].id_str
        else:
            bru_text = "@"
            bru_id = row_tokens[0].id_str

        out_ids = [t.id_str for t in row_tokens] + [bru_id]
        out_texts = [t.text for t in row_tokens] + [bru_text]
        output_lines.append(" ".join(out_ids + out_texts))

    return output_lines


def main() -> None:
    """Load all 6 sources, align, and write aligned-sources.txt."""
    # The 5 text-file editions are just asset files — read them directly.
    txt_editions = [
        ("MIT", "mit.txt"),
        ("McMaster", "mcmaster.txt"),
        ("Heorot", "heorot.txt"),
        ("eBeowulf", "ebeowulf.txt"),
        ("Perseus", "perseus.txt"),
    ]

    print("Tokenizing text-file editions...")
    streams: List[List[Token]] = []
    for name, asset in txt_editions:
        lines = read_txt_edition(asset)
        stream = tokenize_simple_edition(lines)
        print(f"  {name}: {len(stream)} tokens")
        streams.append(stream)

    # Brunetti needs its source class (parses HTML, assigns half-lines).
    with tempfile.TemporaryDirectory() as tmp:
        db = BeoDB(Path(tmp) / "align.duckdb")
        brunetti = Brunetti(db=db)
        print("Loading Brunetti (fetches from URL if not cached)...")
        brunetti.load()

        bru_tokens = load_brunetti_tokens(brunetti)
        print(f"  Brunetti: {len(bru_tokens)} tokens")
        db.close()

    print("Aligning...")
    output = align_all(streams, bru_tokens)
    print(f"  {len(output)} output lines")

    out_path = Path("output") / "aligned-sources.txt"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        for line in output:
            f.write(line + "\n")
    print(f"Written to {out_path}")


if __name__ == "__main__":
    main()
