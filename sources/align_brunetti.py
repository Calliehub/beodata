"""Align Brunetti tokens with the existing 5-way token alignment."""

from pathlib import Path
from typing import List, NamedTuple, Optional, Tuple

from assets import get_asset_path


class BrunettiToken(NamedTuple):
    """A parsed Brunetti token with its ID and text."""

    id_tuple: Tuple[int, str, int]  # (line_num, half_line, token_offset)
    id_str: str  # e.g. "0001a1"
    text: str  # pre_punc + with_length + post_punc, spaces → _


class AlignRow(NamedTuple):
    """A row from the 5-way aligned.txt."""

    ids: List[str]  # 5 edition IDs
    texts: List[str]  # 5 edition texts


def parse_mit_id(id_str: str) -> Tuple[int, str, int]:
    """Parse '0001a1' → (1, 'a', 1) for tuple comparison."""
    return (int(id_str[:4]), id_str[4], int(id_str[5:]))


def parse_brunetti_tokens(path: Optional[Path] = None) -> List[BrunettiToken]:
    """Parse brunetti-length.txt into an ordered list of BrunettiToken."""
    if path is None:
        path = get_asset_path("brunetti-length.txt")
    tokens: List[BrunettiToken] = []
    with open(path) as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            fields = line.split("|")
            if len(fields) < 18:
                continue

            line_id = fields[4]
            half_line = fields[5]
            token_offset = fields[6]
            pre_punc = fields[8]
            with_length = fields[17]
            post_punc = fields[10]

            id_tuple = (int(line_id), half_line, int(token_offset))
            id_str = f"{line_id}{half_line}{token_offset}"
            text = (pre_punc + with_length + post_punc).replace(" ", "_")

            tokens.append(BrunettiToken(id_tuple, id_str, text))
    return tokens


def parse_aligned(path: Optional[Path] = None) -> List[AlignRow]:
    """Parse aligned.txt into rows of 5 IDs + 5 texts."""
    if path is None:
        path = get_asset_path("aligned.txt")
    rows: List[AlignRow] = []
    with open(path) as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            parts = line.split(" ")
            if len(parts) != 10:
                continue
            rows.append(AlignRow(ids=parts[:5], texts=parts[5:]))
    return rows


def align_brunetti(
    aligned_rows: List[AlignRow],
    brunetti_tokens: List[BrunettiToken],
) -> List[str]:
    """Walk aligned rows and Brunetti tokens in parallel, producing 12-col output."""
    cursor = 0
    output_lines: List[str] = []
    num_rows = len(aligned_rows)
    num_bru = len(brunetti_tokens)
    sentinel: Tuple[int, str, int] = (99999, "z", 99999)

    for i, row in enumerate(aligned_rows):
        mit_id = parse_mit_id(row.ids[0])

        # Is this a join row? (any non-@ text contains _)
        is_join = any("_" in t for t in row.texts if t != "@")

        # Compute range_end: mit_id of the first later row that differs
        if i + 1 < num_rows:
            next_mit = parse_mit_id(aligned_rows[i + 1].ids[0])
            if next_mit != mit_id:
                range_end = next_mit
            else:
                # mit stuck on same ID (@ gap) — scan forward
                range_end = sentinel
                for j in range(i + 2, num_rows):
                    candidate = parse_mit_id(aligned_rows[j].ids[0])
                    if candidate != mit_id:
                        range_end = candidate
                        break
        else:
            range_end = sentinel

        # Skip Brunetti tokens that fall before this row's mit_id
        while cursor < num_bru and brunetti_tokens[cursor].id_tuple < mit_id:
            cursor += 1

        # Collect matching Brunetti tokens
        collected: List[BrunettiToken] = []
        if is_join:
            # Grab all tokens in [mit_id, range_end)
            while cursor < num_bru and brunetti_tokens[cursor].id_tuple < range_end:
                collected.append(brunetti_tokens[cursor])
                cursor += 1
        else:
            # Grab at most one token in [mit_id, range_end)
            if cursor < num_bru and brunetti_tokens[cursor].id_tuple < range_end:
                collected.append(brunetti_tokens[cursor])
                cursor += 1

        # Format output
        if collected:
            bru_text = "_".join(t.text for t in collected)
            bru_id = collected[0].id_str
        else:
            bru_text = "@"
            bru_id = row.ids[0]

        out_ids = row.ids + [bru_id]
        out_texts = row.texts + [bru_text]
        output_lines.append(" ".join(out_ids + out_texts))

    return output_lines


def main() -> None:
    """Run alignment and write output."""
    print("Parsing Brunetti tokens...")
    brunetti_tokens = parse_brunetti_tokens()
    print(f"  {len(brunetti_tokens)} tokens")

    print("Parsing aligned.txt...")
    aligned_rows = parse_aligned()
    print(f"  {len(aligned_rows)} rows")

    print("Aligning...")
    output = align_brunetti(aligned_rows, brunetti_tokens)
    print(f"  {len(output)} output lines")

    out_path = get_asset_path("aligned_with_brunetti.txt")
    with open(out_path, "w") as f:
        for line in output:
            f.write(line + "\n")
    print(f"Written to {out_path}")


if __name__ == "__main__":
    main()
