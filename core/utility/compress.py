# [@GHOST]{[@file<compress.py>][@domain<utility>][@role<compress>][@auth<cascade>][@date<2026-06-27>][@ver<1.0.0>]}
# [@VBSTYLE]{[@auth<system>][@role<compress_decompress>][@return<tuple3>][@no<decorators|print|hardcoded>]}
# [@SUMMARY]{Reusable zlib+base64 compress/decompress for any domain's docs}
# [@WCL]{[@format<[@document<name>]{(@compressed<base64_zlib_data>)}>][@reusable<true>]}

import zlib
import base64
import os


class Compress:
    """Compress/decompress text using zlib + base64.

    Reusable utility — any domain can compress its .md docs into
    BCL-tagged Python files and decompress on demand.

    Usage:
        from core.utility.compress import Compress
        c = Compress()
        encoded = c.encode(markdown_text)
        decoded = c.decode(encoded)
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {}

    def Run(self, command, params=None):
        if command == "encode":
            return self.encode(params.get("text", ""))
        elif command == "decode":
            return self.decode(params.get("encoded", ""))
        elif command == "encode_file":
            return self.encode_file(params.get("path"))
        elif command == "compress_dir":
            return self.compress_dir(
                params.get("dir_path"),
                params.get("output_path")
            )
        elif command == "read_state":
            return self.read_state()
        return (0, None, ("unknown_command", command, 0))

    def encode(self, text):
        if not text:
            return (0, None, ("empty_input", "no text to encode", 0))
        compressed = zlib.compress(text.encode("utf-8"), 9)
        encoded = base64.b64encode(compressed).decode("ascii")
        return (1, encoded, None)

    def decode(self, encoded):
        if not encoded:
            return (0, None, ("empty_input", "no data to decode", 0))
        try:
            raw = base64.b64decode(encoded)
            text = zlib.decompress(raw).decode("utf-8")
            return (1, text, None)
        except Exception as e:
            return (0, None, ("decode_failed", str(e), 0))

    def encode_file(self, path):
        if not path or not os.path.exists(path):
            return (0, None, ("file_not_found", path or "none", 0))
        with open(path, "r") as f:
            content = f.read()
        code, encoded, err = self.encode(content)
        if code != 1:
            return (code, None, err)
        orig_size = len(content)
        comp_size = len(zlib.compress(content.encode("utf-8"), 9))
        ratio = round((1 - comp_size / max(orig_size, 1)) * 100, 1)
        return (1, {
            "encoded": encoded,
            "orig_size": orig_size,
            "comp_size": comp_size,
            "ratio": ratio,
            "doc_name": os.path.splitext(os.path.basename(path))[0],
        }, None)

    def compress_dir(self, dir_path, output_path=None):
        if not dir_path or not os.path.isdir(dir_path):
            return (0, None, ("dir_not_found", dir_path or "none", 0))
        md_files = sorted([
            f for f in os.listdir(dir_path)
            if f.endswith(".md")
        ])
        if not md_files:
            return (0, None, ("no_md_files", dir_path, 0))
        results = {}
        for fname in md_files:
            fpath = os.path.join(dir_path, fname)
            code, data, err = self.encode_file(fpath)
            if code == 1:
                doc_name = data["doc_name"]
                results[doc_name] = data["encoded"]
        if not results:
            return (0, None, ("encode_failed", "no files encoded", 0))
        if output_path:
            code, content, err = self.build_py(results, dir_path)
            if code == 1:
                with open(output_path, "w") as f:
                    f.write(content)
        return (1, {"docs": list(results.keys()), "count": len(results)}, None)

    def build_py(self, results, dir_path):
        domain = os.path.basename(os.path.normpath(dir_path))
        lines = []
        lines.append('# [@GHOST]{[@file<graphs.py>][@domain<' + domain + '>][@role<docs>][@auth<cascade>][@date<2026-06-27>][@ver<1.0.0>]}')
        lines.append('# [@VBSTYLE]{[@auth<system>][@role<compressed_docs>][@return<str>][@no<decorators|print|hardcoded>]}')
        lines.append('# [@SUMMARY]{Compressed graph docs — decode via core.utility.compress}')
        lines.append('# [@WCL]{[@format<[@document<name>]{(@compressed<base64_zlib_data>)}>]}')
        lines.append('')
        lines.append('from core.utility.compress import Compress')
        lines.append('')
        lines.append('_compress = Compress()')
        lines.append('')
        lines.append('GRAPHS = {')
        for doc_name, encoded in results.items():
            lines.append('    # [@document<' + doc_name + ']{(@compressed<' + encoded + '>)}')
            lines.append('    "' + doc_name + '": "' + encoded + '",')
            lines.append('')
        lines.append('}')
        lines.append('')
        lines.append('def get_graph(name):')
        lines.append('    raw = GRAPHS.get(name)')
        lines.append('    if not raw:')
        lines.append('        return None')
        lines.append('    code, text, err = _compress.decode(raw)')
        lines.append('    return text if code == 1 else None')
        lines.append('')
        lines.append('def list_graphs():')
        lines.append('    return list(GRAPHS.keys())')
        return (1, '\n'.join(lines) + '\n', None)

    def read_state(self):
        return (1, {
            "domain": "utility",
            "role": "compress_decompress",
        }, None)
