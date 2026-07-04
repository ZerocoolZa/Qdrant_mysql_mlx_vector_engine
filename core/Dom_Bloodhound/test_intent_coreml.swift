// test_intent_coreml.swift — Test CoreML intent router
// [@GHOST]{file_path="core/Dom_Bloodhound/test_intent_coreml.swift" date="2026-07-04" author="Devin" session_id="coreml-test" context="Test CoreML intent router from Swift"}
// [@VBSTYLE]{standard="VBStyle" version="1"}

import Foundation
import CoreML

let toolNames = [
    "cascade_chat_search_sessions",
    "cascade_chat_session_detail",
    "cascade_chat_search_files",
    "cascade_chat_search",
    "cascade_chat_load_all",
    "cascade_chat_scan",
    "cascade_chat_stats",
    "cascade_chat_list",
    "cascade_chat_read",
    "cascade_chat_export",
    "cascade_chat_export_db",
    "cascade_chat_verify_db",
    "cascade_chat_clean",
    "bcl_chat_compress",
    "bcl_chat_dry_run",
    "read_file",
    "write_file",
    "list_directory",
    "tools_md",
]

let vocabPath = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Mcp/dom_mcp/tools/intent_model/intent_vocab.json"
let modelPath = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Mcp/dom_mcp/tools/intent_model/IntentRouter.mlpackage"

// Load vocab
guard let vocabData = try? String(contentsOfFile: vocabPath, encoding: .utf8) else {
    print("FAIL: Could not load vocab")
    exit(1)
}

// Simple vocab parsing — extract words from the "vocab" array
var vocab: [String] = []
if let vocabRange = vocabData.range(of: "\"vocab\""),
   let bracketStart = vocabData.range(of: "[", range: vocabRange.upperBound..<vocabData.endIndex) {
    let afterBracket = bracketStart.upperBound
    let bracketEnd = vocabData.range(of: "]", range: afterBracket..<vocabData.endIndex)!
    let arrayContent = vocabData[afterBracket..<bracketEnd.lowerBound]
    let pattern = "\"([^\"]+)\""
    if let regex = try? NSRegularExpression(pattern: pattern) {
        let nsContent = String(arrayContent) as NSString
        let matches = regex.matches(in: String(arrayContent), range: NSRange(location: 0, length: nsContent.length))
        for match in matches {
            vocab.append(nsContent.substring(with: match.range(at: 1)))
        }
    }
}
print("Loaded \(vocab.count) vocab words")

// Build word→index map
var wordToIndex: [String: Int] = [:]
for (i, word) in vocab.enumerated() {
    wordToIndex[word] = i
}

// Load CoreML model (must compile first)
let modelURL = URL(fileURLWithPath: modelPath)
let config = MLModelConfiguration()
config.computeUnits = .all  // ANE + GPU + CPU

// Compile the .mlpackage to .mlmodelc (cached in temp)
let compiledURL: URL
do {
    compiledURL = try MLModel.compileModel(at: modelURL)
    print("Model compiled to: \(compiledURL.path)")
} catch {
    print("FAIL: Could not compile model: \(error)")
    exit(1)
}

guard let model = try? MLModel(contentsOf: compiledURL, configuration: config) else {
    print("FAIL: Could not load compiled CoreML model")
    exit(1)
}
print("Model loaded\n")

// Bag-of-words encoder
func bowEncode(_ query: String) -> [Float] {
    var vec = [Float](repeating: 0, count: vocab.count)
    let lower = query.lowercased()
    for word in lower.split(whereSeparator: { !$0.isLetter }) {
        let w = String(word)
        if w.count >= 2, let idx = wordToIndex[w] {
            vec[idx] = 1.0
        }
    }
    return vec
}

// Predict
func predict(_ query: String) -> (tool: String, confidence: Float)? {
    let bow = bowEncode(query)
    let inputArray = try? MLMultiArray(shape: [1, NSNumber(value: vocab.count)], dataType: .float32)
    guard let array = inputArray else { return nil }
    let ptr = array.dataPointer.bindMemory(to: Float.self, capacity: vocab.count)
    for i in 0..<vocab.count { ptr[i] = bow[i] }

    let inputValue = MLFeatureValue(multiArray: array)
    let provider = try? MLDictionaryFeatureProvider(dictionary: ["query_bow": inputValue])
    guard let input = provider else { return nil }

    guard let output = try? model.prediction(from: input) else { return nil }

    // Get output array (auto-named)
    guard let outName = output.featureNames.first else { return nil }
    guard let outValue = output.featureValue(for: outName) else { return nil }
    guard let outArray = outValue.multiArrayValue else { return nil }

    let outPtr = outArray.dataPointer.bindMemory(to: Float.self, capacity: 19)

    // Softmax
    var logits = [Float](repeating: 0, count: 19)
    for i in 0..<19 { logits[i] = outPtr[i] }

    let maxLogit = logits.max() ?? 0
    var exps = [Float](repeating: 0, count: 19)
    var sum: Float = 0
    for i in 0..<19 {
        exps[i] = expf(logits[i] - maxLogit)
        sum += exps[i]
    }
    var probs = [Float](repeating: 0, count: 19)
    for i in 0..<19 { probs[i] = exps[i] / sum }

    // Find best
    var bestIdx = 0
    var bestProb: Float = probs[0]
    for i in 1..<19 {
        if probs[i] > bestProb {
            bestProb = probs[i]
            bestIdx = i
        }
    }

    return (tool: toolNames[bestIdx], confidence: bestProb)
}

// Test queries
let queries = [
    "search for kokoro voice pipeline",
    "which sessions touched model_gui.py",
    "load all chats",
    "export to mysql",
    "stats",
    "what tools are available",
    "show me session abc-123",
    "compress to bcl",
    "scan for pb files",
    "verify database",
]

print("Predictions:")
for q in queries {
    if let result = predict(q) {
        print("  '\(q)' → \(result.tool) (conf=\(String(format: "%.4f", result.confidence)))")
    } else {
        print("  '\(q)' → ERROR")
    }
}

// Benchmark
print("\nBenchmark (100 predictions):")
let start = Date()
for _ in 0..<100 {
    _ = predict("search for kokoro")
}
let elapsed = Date().timeIntervalSince(start)
print(String(format: "  100 predictions in %.3f seconds (%.1f ms each)", elapsed, elapsed * 10))
print("\nDone.")
