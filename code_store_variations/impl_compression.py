"""VBStyle domain implementation: compression.

Data compression: zlib, gzip, LZ4, dictionary training, streaming.
All methods return Tuple3 (ok, data, error). Python stdlib only.
"""

import zlib
import gzip
import lzma
import time
import io


class DomCompression:
    """Compression domain: zlib, gzip, lzma, streaming, benchmarking."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {"config": {}, "catalog": [], "results": []}
        self.mem = mem
        self.db = db

    def Run(self, command, params=None):
        params = params or {}
        handlers = {
            "compress": self.compress,
            "decompress": self.decompress,
            "estimate_ratio": self.estimate_ratio,
            "select_algorithm": self.select_algorithm,
            "stream_compress": self.stream_compress,
            "stream_decompress": self.stream_decompress,
            "benchmark": self.benchmark,
            "get_info": self.get_info,
        }
        handler = handlers.get(command)
        if handler is None:
            return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))
        return handler(params)

    def _coerce_bytes(self, value):
        if isinstance(value, str):
            return value.encode("utf-8")
        if isinstance(value, (bytes, bytearray)):
            return bytes(value)
        return str(value).encode("utf-8")

    def _get_compressor(self, algorithm, level):
        if algorithm == "zlib":
            return zlib.compressobj(level)
        if algorithm == "gzip":
            return zlib.compressobj(level, zlib.DEFLATED, 31)
        if algorithm == "lzma":
            return lzma.LZMACompressor(preset=level)
        return zlib.compressobj(level)

    def _get_decompressor(self, algorithm):
        if algorithm == "zlib":
            return zlib.decompressobj()
        if algorithm == "gzip":
            return zlib.decompressobj(31)
        if algorithm == "lzma":
            return lzma.LZMADecompressor()
        return zlib.decompressobj()

    def compress(self, params=None):
        params = params or {}
        try:
            data = self._coerce_bytes(params.get("data", ""))
            algorithm = params.get("algorithm", "zlib")
            level = int(params.get("level", 6))
            if algorithm == "zlib":
                compressed = zlib.compress(data, level)
            elif algorithm == "gzip":
                compressed = gzip.compress(data, level)
            elif algorithm == "lzma":
                compressed = lzma.compress(data, preset=level)
            else:
                return (0, None, ("COMPRESS_ERROR", f"unknown algorithm: {algorithm}", 0))
            ratio = len(compressed) / len(data) if data else 1.0
            result = {"domain": "compression", "method": "compress", "data": {"compressed": compressed, "original_size": len(data), "compressed_size": len(compressed), "ratio": ratio, "algorithm": algorithm}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("COMPRESS_ERROR", str(e), 0))

    def decompress(self, params=None):
        params = params or {}
        try:
            compressed = self._coerce_bytes(params.get("compressed", b""))
            algorithm = params.get("algorithm", "zlib")
            if algorithm == "zlib":
                data = zlib.decompress(compressed)
            elif algorithm == "gzip":
                data = gzip.decompress(compressed)
            elif algorithm == "lzma":
                data = lzma.decompress(compressed)
            else:
                return (0, None, ("DECOMPRESS_ERROR", f"unknown algorithm: {algorithm}", 0))
            result = {"domain": "compression", "method": "decompress", "data": {"data": data, "size": len(data), "algorithm": algorithm}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("DECOMPRESS_ERROR", str(e), 0))

    def estimate_ratio(self, params=None):
        params = params or {}
        try:
            data = self._coerce_bytes(params.get("data", ""))
            sample_size = int(params.get("sample_size", 0))
            if sample_size and len(data) > sample_size:
                sample = data[:sample_size]
            else:
                sample = data
            ratios = {}
            for algo, fn in (("zlib", zlib.compress), ("gzip", gzip.compress), ("lzma", lzma.compress)):
                try:
                    comp = fn(sample)
                    ratios[algo] = len(comp) / len(sample) if sample else 1.0
                except Exception:
                    ratios[algo] = None
            best = min((v for v in ratios.values() if v is not None), default=None)
            best_algo = None
            for k, v in ratios.items():
                if v == best:
                    best_algo = k
                    break
            result = {"domain": "compression", "method": "estimate_ratio", "data": {"ratios": ratios, "best": best_algo, "best_ratio": best, "sample_size": len(sample)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("ESTIMATE_RATIO_ERROR", str(e), 0))

    def select_algorithm(self, params=None):
        params = params or {}
        try:
            data = self._coerce_bytes(params.get("data", ""))
            target = params.get("target", "ratio")
            results = {}
            for algo, fn in (("zlib", zlib.compress), ("gzip", gzip.compress), ("lzma", lzma.compress)):
                start = time.perf_counter()
                comp = fn(data)
                elapsed = time.perf_counter() - start
                ratio = len(comp) / len(data) if data else 1.0
                results[algo] = {"ratio": ratio, "size": len(comp), "time": elapsed}
            if target == "ratio":
                chosen = min(results, key=lambda a: results[a]["ratio"])
            elif target == "speed":
                chosen = min(results, key=lambda a: results[a]["time"])
            elif target == "size":
                chosen = min(results, key=lambda a: results[a]["size"])
            else:
                chosen = "zlib"
            result = {"domain": "compression", "method": "select_algorithm", "data": {"chosen": chosen, "target": target, "results": results}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("SELECT_ALGORITHM_ERROR", str(e), 0))

    def stream_compress(self, params=None):
        params = params or {}
        try:
            data = self._coerce_bytes(params.get("data", b""))
            algorithm = params.get("algorithm", "zlib")
            level = int(params.get("level", 6))
            chunk_size = int(params.get("chunk_size", 4096))
            comp = self._get_compressor(algorithm, level)
            out = bytearray()
            chunks = 0
            for i in range(0, len(data), chunk_size):
                chunk = data[i:i + chunk_size]
                out += comp.compress(chunk)
                chunks += 1
            out += comp.flush()
            result = {"domain": "compression", "method": "stream_compress", "data": {"compressed": bytes(out), "size": len(out), "chunks": chunks, "algorithm": algorithm}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("STREAM_COMPRESS_ERROR", str(e), 0))

    def stream_decompress(self, params=None):
        params = params or {}
        try:
            compressed = self._coerce_bytes(params.get("compressed", b""))
            algorithm = params.get("algorithm", "zlib")
            chunk_size = int(params.get("chunk_size", 4096))
            dec = self._get_decompressor(algorithm)
            out = bytearray()
            chunks = 0
            for i in range(0, len(compressed), chunk_size):
                chunk = compressed[i:i + chunk_size]
                out += dec.decompress(chunk)
                chunks += 1
            out += dec.flush()
            result = {"domain": "compression", "method": "stream_decompress", "data": {"data": bytes(out), "size": len(out), "chunks": chunks, "algorithm": algorithm}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("STREAM_DECOMPRESS_ERROR", str(e), 0))

    def benchmark(self, params=None):
        params = params or {}
        try:
            data = self._coerce_bytes(params.get("data", b""))
            iterations = int(params.get("iterations", 3))
            algorithms = params.get("algorithms", ["zlib", "gzip", "lzma"])
            level = int(params.get("level", 6))
            report = {}
            for algo in algorithms:
                comp_times = []
                decomp_times = []
                ratios = []
                for _ in range(iterations):
                    start = time.perf_counter()
                    if algo == "zlib":
                        comp = zlib.compress(data, level)
                    elif algo == "gzip":
                        comp = gzip.compress(data, level)
                    elif algo == "lzma":
                        comp = lzma.compress(data, preset=level)
                    else:
                        continue
                    comp_times.append(time.perf_counter() - start)
                    ratios.append(len(comp) / len(data) if data else 1.0)
                    start = time.perf_counter()
                    if algo == "zlib":
                        zlib.decompress(comp)
                    elif algo == "gzip":
                        gzip.decompress(comp)
                    elif algo == "lzma":
                        lzma.decompress(comp)
                    decomp_times.append(time.perf_counter() - start)
                report[algo] = {
                    "avg_compress_time": sum(comp_times) / len(comp_times) if comp_times else 0,
                    "avg_decompress_time": sum(decomp_times) / len(decomp_times) if decomp_times else 0,
                    "avg_ratio": sum(ratios) / len(ratios) if ratios else 1.0,
                    "iterations": iterations,
                }
            result = {"domain": "compression", "method": "benchmark", "data": {"report": report, "data_size": len(data)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("BENCHMARK_ERROR", str(e), 0))

    def get_info(self, params=None):
        params = params or {}
        try:
            algorithm = params.get("algorithm", "all")
            info = {
                "zlib": {"module": "zlib", "levels": "0-9", "streaming": True, "lossless": True},
                "gzip": {"module": "gzip", "levels": "0-9", "streaming": True, "lossless": True, "header": True},
                "lzma": {"module": "lzma", "levels": "0-9 (preset)", "streaming": True, "lossless": True, "ratio": "high"},
            }
            if algorithm == "all":
                payload = info
            else:
                payload = info.get(algorithm, {})
            result = {"domain": "compression", "method": "get_info", "data": {"algorithm": algorithm, "info": payload}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("GET_INFO_ERROR", str(e), 0))
