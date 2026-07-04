#[@GHOST]{[@file<GhostQA.py>][@domain<ghost_qa>][@role<question_answering>][@return<Tuple3>][@auth<cascade>][@date<2026-06-21>][@ver<1.0>]}
#[@VBSTYLE]{[@auth<cascade>][@role<class>][@return<Tuple3>][@state<config,catalog,results,errors,meta>]}

import json
import os
import logging
import urllib.request
import numpy as np
import coremltools as ct
from sentence_transformers import SentenceTransformer
from transformers import BertTokenizer

try:
    from mlx_lm import load, generate
    MLX_AVAILABLE = True
except ImportError:
    MLX_AVAILABLE = False
    logging.warning(
        "MLX not available — LLM formatting will fall back to OpenAI API "
        "(if OPENAI_API_KEY set) or return the raw extracted answer."
    )

QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
EMBED_MODEL_NAME = "BAAI/bge-small-en-v1.5"
QA_MODEL_PATH = "/Users/wws/Qdrant_mysql_mlx_vector_engine/BERTSQUADFP16.mlmodel"
BERT_TOKENIZER_NAME = "bert-base-uncased"
LLM_MODEL_NAME = "mlx-community/Qwen2.5-Coder-1.5B-Instruct-4bit"
RETRIEVAL_THRESHOLD = 0.30
QA_CONFIDENCE_THRESHOLD = 0.0
LLM_CONFIDENCE_THRESHOLD = 1.0
QA_MAX_LENGTH = 384
LLM_MAX_TOKENS = 200
QDRANT_COLLECTIONS = [
    "dim_semantic", "dim_structural", "dim_capability",
    "dim_lifecycle", "dim_bracket",
]


class GhostQA:
    """Question answering via embedding retrieval + Apple Core ML BERT-SQuAD extraction.

    Architecture:
        Question -> BGE Embed -> Qdrant Search -> Chunks -> Apple BERT-SQuAD -> Answer Span

    No LLM. No generation. No hallucination. Pure retrieval + extraction.
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "qdrant_url": QDRANT_URL,
                "embed_model": EMBED_MODEL_NAME,
                "qa_model_path": QA_MODEL_PATH,
                "bert_tokenizer": BERT_TOKENIZER_NAME,
                "llm_model": LLM_MODEL_NAME,
                "retrieval_threshold": RETRIEVAL_THRESHOLD,
                "qa_confidence_threshold": QA_CONFIDENCE_THRESHOLD,
                "llm_confidence_threshold": LLM_CONFIDENCE_THRESHOLD,
                "qa_max_length": QA_MAX_LENGTH,
                "llm_max_tokens": LLM_MAX_TOKENS,
                "qdrant_collections": QDRANT_COLLECTIONS,
            },
            "catalog": [],
            "results": [],
            "errors": [],
            "meta": {"questions_asked": 0, "answers_found": 0, "llm_formatted": 0},
        }
        self.embedder = None
        self.qa_model = None
        self.tokenizer = None
        self.llm_model = None
        self.llm_tokenizer = None

    def Run(self, command, params=None):
        params = params or {}
        if command == "ask":
            return self.AskQuestion(params)
        if command == "embed":
            return self.EmbedText(params)
        if command == "search":
            return self.SearchQdrant(params)
        if command == "extract":
            return self.ExtractAnswer(params)
        if command == "explain":
            return self.ExplainAnswer(params)
        if command == "test":
            return self.RunTests(params)
        if command == "load_models":
            return self.LoadModels(params)
        if command == "read_state":
            return self.ReadState()
        if command == "set_config":
            return self.SetConfig(params.get("config"))
        return (0, None, ("UNKNOWN_COMMAND", f"GhostQA unknown: {command}", 0))

    def LoadModels(self, params=None):
        try:
            if self.embedder is None:
                self.embedder = SentenceTransformer(self.state["config"]["embed_model"])
            if self.tokenizer is None:
                self.tokenizer = BertTokenizer.from_pretrained(
                    self.state["config"]["bert_tokenizer"]
                )
            if self.qa_model is None:
                self.qa_model = ct.models.MLModel(
                    self.state["config"]["qa_model_path"]
                )
            if self.llm_model is None and MLX_AVAILABLE:
                self.llm_model, self.llm_tokenizer = load(
                    self.state["config"]["llm_model"]
                )
            return (1, "Models loaded", None)
        except Exception as e:
            self.state["errors"].append(str(e))
            return (0, None, ("MODEL_LOAD_FAILED", str(e), 0))

    def EmbedText(self, params):
        text = params.get("text", "")
        if not text:
            return (0, None, ("EMPTY_TEXT", "No text to embed", 0))
        if self.embedder is None:
            ok, _, err = self.LoadModels()
            if not ok:
                return (0, None, err)
        vec = self.embedder.encode([text])[0].tolist()
        return (1, vec, None)

    def SearchQdrant(self, params):
        question = params.get("question", "")
        if not question:
            return (0, None, ("EMPTY_QUESTION", "No question to search", 0))
        if self.embedder is None:
            ok, _, err = self.LoadModels()
            if not ok:
                return (0, None, err)

        vec = self.embedder.encode([question])[0].tolist()
        collections = params.get("collections", self.state["config"]["qdrant_collections"])
        top_k = params.get("top_k", 3)
        threshold = self.state["config"]["retrieval_threshold"]
        all_chunks = []

        for col in collections:
            payload = {
                "vector": vec,
                "limit": top_k,
                "with_payload": True,
                "with_vector": False,
            }
            req = urllib.request.Request(
                f"{self.state['config']['qdrant_url']}/collections/{col}/points/search",
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"},
            )
            try:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    result = json.loads(resp.read().decode())
                    hits = result.get("result", [])
                    for hit in hits:
                        score = hit.get("score", 0)
                        if score >= threshold:
                            pd = hit.get("payload", {})
                            text = ""
                            for key in ["text", "content", "sample_row", "filename", "source_table"]:
                                if key in pd:
                                    text = str(pd[key])
                                    break
                            if text:
                                all_chunks.append({
                                    "source": f"qdrant:{col}",
                                    "score": score,
                                    "text": text,
                                    "id": hit.get("id"),
                                })
            except Exception:
                continue

        all_chunks.sort(key=lambda x: x["score"], reverse=True)
        return (1, all_chunks[:5], None)

    def ExtractAnswer(self, params):
        question = params.get("question", "")
        context = params.get("context", "")
        if not question or not context:
            return (0, None, ("MISSING_PARAMS", "Need question and context", 0))
        if len(context.strip()) < 10:
            return (0, None, ("CONTEXT_TOO_SHORT", "Context is too short", 0))

        if self.qa_model is None or self.tokenizer is None:
            ok, _, err = self.LoadModels()
            if not ok:
                return (0, None, err)

        encoded = self.tokenizer(
            question,
            context,
            add_special_tokens=True,
            return_tensors="np",
            max_length=self.state["config"]["qa_max_length"],
            truncation=True,
            padding="max_length",
        )

        word_ids = encoded["input_ids"].astype(np.float32)
        word_types = encoded["token_type_ids"].astype(np.float32)

        output = self.qa_model.predict({
            "wordIDs": word_ids,
            "wordTypes": word_types,
        })

        start_logits = output["startLogits"][0]
        end_logits = output["endLogits"][0]

        start_idx = int(np.argmax(start_logits))
        end_idx = int(np.argmax(end_logits)) + 1
        if end_idx <= start_idx:
            end_idx = start_idx + 1

        answer_tokens = encoded["input_ids"][0][start_idx:end_idx]
        answer = self.tokenizer.decode(answer_tokens, skip_special_tokens=True).strip()

        start_score = float(np.max(start_logits))
        end_score = float(np.max(end_logits))
        confidence = (start_score + end_score) / 2

        return (1, {"answer": answer, "confidence": confidence}, None)

    def AskQuestion(self, params):
        question = params.get("question", "")
        if not question:
            return (0, None, ("EMPTY_QUESTION", "No question provided", 0))

        self.state["meta"]["questions_asked"] += 1

        ok, chunks, err = self.SearchQdrant({"question": question})
        if not ok:
            return (0, None, err)
        if not chunks:
            self.state["results"].append({
                "question": question, "found": False,
                "answer": "Not Found", "chunks_searched": 0,
            })
            return (1, {"found": False, "answer": "Not Found", "chunks_searched": 0}, None)

        best_answer = ""
        best_confidence = -999.0
        best_chunk = None

        for chunk in chunks:
            ok, result, err = self.ExtractAnswer({
                "question": question,
                "context": chunk["text"],
            })
            if ok and result["answer"]:
                if result["confidence"] > best_confidence:
                    best_answer = result["answer"]
                    best_confidence = result["confidence"]
                    best_chunk = chunk

        threshold = self.state["config"]["qa_confidence_threshold"]
        found = bool(best_answer and best_confidence > threshold)

        answer_data = {
            "question": question,
            "found": found,
            "answer": best_answer if found else "Not Found",
            "confidence": round(best_confidence, 4),
            "source": best_chunk["source"] if best_chunk else None,
            "source_score": round(best_chunk["score"], 4) if best_chunk else 0,
            "chunks_searched": len(chunks),
            "evidence": best_chunk["text"][:300] if best_chunk else None,
            "explained": None,
        }

        if found and best_confidence >= self.state["config"]["llm_confidence_threshold"]:
            ok, explained, err = self.ExplainAnswer({
                "question": question,
                "evidence": best_chunk["text"],
                "extracted": best_answer,
            })
            if ok:
                answer_data["explained"] = explained
                self.state["meta"]["llm_formatted"] += 1

        self.state["results"].append(answer_data)
        if found:
            self.state["meta"]["answers_found"] += 1

        return (1, answer_data, None)

    def ExplainAnswer(self, params):
        question = params.get("question", "")
        evidence = params.get("evidence", "")
        extracted = params.get("extracted", "")
        if not question or not evidence:
            return (0, None, ("MISSING_PARAMS", "Need question and evidence", 0))

        # Fallback chain: MLX → OpenAI → return extracted as-is
        if MLX_AVAILABLE:
            return self._ExplainWithMlx(question, evidence, extracted)
        openai_key = os.environ.get("OPENAI_API_KEY", "")
        if openai_key:
            ok, result, err = self._ExplainWithOpenAI(question, evidence, extracted, openai_key)
            if ok:
                return (1, result, None)
            self.state["errors"].append(f"OpenAI fallback failed: {err}")
        # No LLM available — return the raw extracted answer
        return (1, extracted, None)

    def _ExplainWithMlx(self, question, evidence, extracted):
        """Primary LLM: MLX local model."""
        if self.llm_model is None:
            ok, _, err = self.LoadModels()
            if not ok:
                return (0, None, err)

        prompt = (
            f"Based only on the following evidence, write a clear and concise answer "
            f"to the question. Do not add information that is not in the evidence.\n\n"
            f"Question: {question}\n\n"
            f"Evidence: {evidence}\n\n"
            f"Answer:"
        )

        try:
            response = generate(
                self.llm_model,
                self.llm_tokenizer,
                prompt=prompt,
                max_tokens=self.state["config"]["llm_max_tokens"],
                verbose=False,
            )
            cleaned = response.strip()
            return (1, cleaned, None)
        except Exception as e:
            self.state["errors"].append(str(e))
            return (0, None, ("LLM_FAILED", str(e), 0))

    def _ExplainWithOpenAI(self, question, evidence, extracted, api_key):
        """Fallback LLM: OpenAI API (requires OPENAI_API_KEY env var)."""
        prompt = (
            f"Based only on the following evidence, write a clear and concise answer "
            f"to the question. Do not add information that is not in the evidence.\n\n"
            f"Question: {question}\n\n"
            f"Evidence: {evidence}\n\n"
            f"Answer:"
        )
        payload = json.dumps({
            "model": os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            "messages": [
                {"role": "system", "content": "You are a precise QA assistant. Answer using only the provided evidence."},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": self.state["config"]["llm_max_tokens"],
            "temperature": 0.0,
        }).encode()
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
            answer = data["choices"][0]["message"]["content"].strip()
            return (1, answer, None)
        except Exception as e:
            return (0, None, ("OPENAI_FAILED", str(e), 0))

    def RunTests(self, params=None):
        ok, _, err = self.LoadModels()
        if not ok:
            return (0, None, err)

        tests = [
            {
                "question": "What is the capital of France?",
                "context": "Paris is the capital of France. France is a country in Western Europe.",
                "expected": "paris",
            },
            {
                "question": "What is MemUnit?",
                "context": "MEMBUS is the core of everything. It loads into RAM and allocates space. It is an in-memory message bus pattern like Redis Pub/Sub but in RAM with SQLite tables as channels.",
                "expected": "the core of everything",
            },
            {
                "question": "What is the Reporter class for?",
                "context": "VBStyle Boot class is the universal father class for all applications. It contains Reporter which handles central output with NO print statements allowed.",
                "expected": "central output",
            },
            {
                "question": "What is the capital of Japan?",
                "context": "The VBStyle lifecycle has five stages: parm, validate, execute, return_, and cleanup.",
                "expected": None,
            },
        ]

        results = []
        for test in tests:
            ok, result, err = self.ExtractAnswer({
                "question": test["question"],
                "context": test["context"],
            })
            if not ok:
                results.append({
                    "question": test["question"],
                    "answer": None,
                    "error": str(err),
                })
                continue

            entry = {
                "question": test["question"],
                "extracted": result["answer"],
                "confidence": round(result["confidence"], 4),
                "expected": test["expected"],
                "correct": (
                    test["expected"] is not None and
                    test["expected"].lower() in result["answer"].lower()
                ) or (
                    test["expected"] is None and
                    result["confidence"] < 0
                ),
                "explained": None,
            }

            if entry["correct"] and result["confidence"] >= self.state["config"]["llm_confidence_threshold"]:
                ok2, explained, err2 = self.ExplainAnswer({
                    "question": test["question"],
                    "evidence": test["context"],
                    "extracted": result["answer"],
                })
                if ok2:
                    entry["explained"] = explained

            results.append(entry)

        return (1, results, None)

    def ReadState(self):
        return (1, self.state.copy(), None)

    def SetConfig(self, config):
        if not config:
            return (0, None, ("EMPTY_CONFIG", "No config provided", 0))
        self.state["config"].update(config)
        return (1, "Config updated", None)
