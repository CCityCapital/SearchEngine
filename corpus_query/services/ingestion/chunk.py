import argparse
from typing import Generator


def chunk_file_by_line(corpus_string: str) -> Generator[str, None, None]:
    """
    Chunk a corpus string into smaller strings.
    """
    prev_line = None
    for line in corpus_string.split("\n"):
        stripped_line = line.strip()
        if len(stripped_line) == 0:
            continue
        if prev_line is not None:
            yield " ".join([prev_line, stripped_line])

        prev_line = stripped_line


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("corpus_file", type=str, help="Path to corpus file.")
    args = parser.parse_args()

    with open(args.corpus_file, "r") as f:
        print(chunk_file_by_line(f.read()))
