#!/usr/bin/env python3
"""
PLFCompressor v1
Domain-aware dictionary compressor.

This is NOT general compression.
It replaces common Python/SQL/BCL tokens with compact binary tokens.
"""

from typing import Dict


class PlfCompressor:

    ESC = b'\xFF'

    DICTIONARY: Dict[bytes, bytes] = {

        b"CREATE TABLE": b"\x01",
        b"INSERT INTO": b"\x02",
        b"UPDATE": b"\x03",
        b"DELETE FROM": b"\x04",
        b"SELECT": b"\x05",
        b"WHERE": b"\x06",
        b"PRIMARY KEY": b"\x07",

        b"class ": b"\x10",
        b"def ": b"\x11",
        b"return ": b"\x12",
        b"self": b"\x13",
        b"import ": b"\x14",
        b"from ": b"\x15",

        b"GRAPH": b"\x20",
        b"BCL": b"\x21",
        b"BCLIR": b"\x22",
        b"LAW": b"\x23",
        b"METHOD": b"\x24",
        b"CLASS": b"\x25",

        b"True": b"\x30",
        b"False": b"\x31",
        b"None": b"\x32"
    }

    def __init__(self):

        self.reverse = {
            v: k
            for k, v in self.DICTIONARY.items()
        }

        self.encode_order = sorted(
            self.DICTIONARY.items(),
            key=lambda x: len(x[0]),
            reverse=True
        )

    def compress(self, text: str) -> bytes:

        data = text.encode("utf8")

        for word, token in self.encode_order:
            data = data.replace(word, self.ESC + token)

        return data

    def decompress(self, blob: bytes) -> str:

        out = bytearray()

        i = 0

        while i < len(blob):

            if blob[i] == 0xFF:

                token = bytes([blob[i + 1]])

                out.extend(
                    self.reverse[token]
                )

                i += 2

            else:

                out.append(blob[i])

                i += 1

        return out.decode("utf8")


if __name__ == "__main__":

    c = PlfCompressor()

    original = """
CREATE TABLE Person (
    id INT PRIMARY KEY,
    name TEXT
)

class Person:

    def save(self):
        return True
"""

    packed = c.compress(original)

    restored = c.decompress(packed)

    print("Original :", len(original.encode()))
    print("Compressed :", len(packed))
    print()
    print(restored)
