import argparse
from typing import Generator


def chunk_corpus_file(corpus_file: str) -> Generator[str, None, None]:
    """
    Chunk a corpus file into smaller strings.
    """
    with open(corpus_file, 'r') as f:


        prev_line = None
        while line := f.readline():

            stripped_line = line.strip()
            if len(stripped_line) == 0:
                continue

            if prev_line is not None:
                yield " ".join([prev_line, stripped_line])

            prev_line = stripped_line


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('corpus_file', type=str,
                        help='Path to corpus file.')
    args = parser.parse_args()

    for l in chunk_corpus_file(args.corpus_file):
        print(len(l))
        print("_" * 20)