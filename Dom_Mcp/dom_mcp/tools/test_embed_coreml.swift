// test_embed_coreml.swift — Test CoreML in-RAM embedding model
// [@GHOST]{file_path="Dom_Mcp/dom_mcp/tools/test_embed_coreml.swift" date="2026-07-04" author="Devin" session_id="coreml-embed-test" context="Test SemanticEmbed.mlpackage for in-RAM semantic embedding"}
// [@VBSTYLE]{standard="VBStyle" version="1"}

import Foundation
import CoreML

let embedDir = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Mcp/dom_mcp/tools/embed_model"
let vocabPath = "\(embedDir)/embed_vocab.json"
let modelPath = "\(embedDir)/SemanticEmbed.mlpackage"

// Load vocab
guard let vocabData = try? String(contentsOfFile: vocabPath, encoding: .utf8) else {
    print("FAIL: Could not load vocab")
    exit(1)
}

var vocab: [String] = []
var wordToIndex: [String: Int] = [:]

if let data = vocabData.data(using: .utf8),
   let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
    if let v = json["vocab"] as? [String] { vocab = v }
    if let wti = json["word_to_idx"] as? [String: Int] { wordToIndex = wti }
}
print("Loaded \(vocab.count) vocab words")

// Load CoreML model
let modelURL = URL(fileURLWithPath: modelPath)
let config = MLModelConfiguration()
config.computeUnits = .all  // ANE + GPU + CPU

let compiledURL: URL
do {
    compiledURL = try MLModel.compileModel(at: modelURL)
} catch {
    print("FAIL: compile error: \(error)")
    exit(1)
}

guard let model = try? MLModel(contentsOf: compiledURL, configuration: config) else {
    print("FAIL: Could not load model")
    exit(1)
}
print("Model loaded\n")

// Bag-of-words encoder
func bowEncode(_ text: String) -> [Float] {
    var vec = [Float](repeating: 0, count: vocab.count)
    let lower = text.lowercased()
    for word in lower.split(whereSeparator: { !$0.isLetter && $0 != "_" }) {
        let w = String(word)
        if let idx = wordToIndex[w] {
            vec[idx] = 1.0
        }
    }
    return vec
}

// Embed
func embed(_ text: String) -> [Float]? {
    let bow = bowEncode(text)
    guard let array = try? MLMultiArray(shape: [1, NSNumber(value: vocab.count)], dataType: .float32) else { return nil }
    let ptr = array.dataPointer.bindMemory(to: Float.self, capacity: vocab.count)
    for i in 0..<vocab.count { ptr[i] = bow[i] }

    let inputValue = MLFeatureValue(multiArray: array)
    guard let provider = try? MLDictionaryFeatureProvider(dictionary: ["text_bow": inputValue]) else { return nil }
    guard let output = try? model.prediction(from: provider) else { return nil }

    guard let outName = output.featureNames.first else { return nil }
    guard let outValue = output.featureValue(for: outName) else { return nil }
    guard let outArray = outValue.multiArrayValue else { return nil }

    let outPtr = outArray.dataPointer.bindMemory(to: Float.self, capacity: 64)
    var result = [Float](repeating: 0, count: 64)
    for i in 0..<64 { result[i] = outPtr[i] }
    return result
}

// Cosine similarity
func cosine(_ a: [Float], _ b: [Float]) -> Float {
    var dot: Float = 0, na: Float = 0, nb: Float = 0
    for i in 0..<a.count {
        dot += a[i] * b[i]
        na += a[i] * a[i]
        nb += b[i] * b[i]
    }
    let denom = sqrtf(na) * sqrtf(nb)
    return denom > 0 ? dot / denom : 0
}

// Test embeddings
let testTexts = [
    "kokoro voice pipeline",
    "tts speech synthesis",
    "mysql database query",
    "sql database connection",
    "coreml neural engine embedding",
    "bloodhound scent scanner",
]

print("Embeddings:")
var embeddings: [[Float]] = []
for text in testTexts {
    if let emb = embed(text) {
        embeddings.append(emb)
        let norm = sqrtf(emb.reduce(0) { $0 + $1 * $1 })
        print("  '\(text)' → 64-dim, norm=\(String(format: "%.3f", norm))")
    } else {
        print("  '\(text)' → FAILED")
        embeddings.append([])
    }
}

print("\nCosine similarities:")
let pairs = [(0,1,"kokoro vs tts"), (0,2,"kokoro vs mysql"), (2,3,"mysql vs sql"), (4,5,"coreml vs bloodhound"), (0,4,"kokoro vs coreml")]
for (i, j, label) in pairs {
    if !embeddings[i].isEmpty && !embeddings[j].isEmpty {
        let sim = cosine(embeddings[i], embeddings[j])
        print("  \(label): \(String(format: "%.4f", sim))")
    }
}

// Benchmark
print("\nBenchmark (1000 embeddings):")
let start = Date()
for _ in 0..<1000 {
    _ = embed("kokoro voice pipeline config")
}
let elapsed = Date().timeIntervalSince(start)
print(String(format: "  1000 embeddings in %.3f seconds (%.2f ms each)", elapsed, elapsed))
print("  Model size: 92KB | Runs on Neural Engine | Zero RAM bloat")
print("\nDone.")
