// run_training.swift
// Native Swift MLUpdateTask runner — minimal version using completion handler only
import Foundation
import CoreML

struct TrainingSample: Codable {
    let features: [Double]
    let label: Int
}

class SampleFeatureProvider: MLFeatureProvider {
    let featureValue: MLFeatureValue
    let labelValue: MLFeatureValue

    init(sample: TrainingSample) throws {
        // Neural network spec (<=v3) requires input rank 1, 3, or 5
        // Use rank 1: shape [4] not [1, 4]
        let array = try MLMultiArray(shape: [NSNumber(value: sample.features.count)], dataType: .float32)
        for (i, v) in sample.features.enumerated() {
            array[i] = NSNumber(value: Float(v))
        }
        self.featureValue = MLFeatureValue(multiArray: array)
        let labelArray = try MLMultiArray(shape: [NSNumber(value: 1)], dataType: .int32)
        labelArray[0] = NSNumber(value: sample.label)
        self.labelValue = MLFeatureValue(multiArray: labelArray)
    }

    var featureNames: Set<String> {
        return Set(["features", "class_probs_true"])
    }

    func featureValue(for name: String) -> MLFeatureValue? {
        if name == "features" { return featureValue }
        if name == "class_probs_true" { return labelValue }
        return nil
    }
}

let args = CommandLine.arguments
if args.count < 3 {
    print("Usage: run_training <model.mlmodel> <training_data.json>")
    exit(1)
}
let modelPath = args[1]
let dataPath = args[2]
let modelURL = URL(fileURLWithPath: modelPath)

let samples: [TrainingSample]
do {
    let data = try Data(contentsOf: URL(fileURLWithPath: dataPath))
    samples = try JSONDecoder().decode([TrainingSample].self, from: data)
} catch {
    FileHandle.standardError.write("Failed to load data: \(error)\n".data(using: .utf8)!)
    exit(1)
}
print("loaded \(samples.count) samples")

let providers: [MLFeatureProvider]
do {
    providers = try samples.map { try SampleFeatureProvider(sample: $0) }
} catch {
    FileHandle.standardError.write("Failed to build providers: \(error)\n".data(using: .utf8)!)
    exit(1)
}
let batchProvider = MLArrayBatchProvider(array: providers)
print("built batch with \(providers.count) providers")

let compiledURL: URL
do {
    compiledURL = try MLModel.compileModel(at: modelURL)
    print("compiled to \(compiledURL.path)")
} catch {
    FileHandle.standardError.write("Failed to compile: \(error)\n".data(using: .utf8)!)
    exit(1)
}

let outURL = modelURL.deletingLastPathComponent().appendingPathComponent("TrainedClassifier.mlmodel")

// Use completion-handler-only API (no progress handlers)
var updateTask: MLUpdateTask?
var caughtError: Error?
do {
    updateTask = try MLUpdateTask(
        forModelAt: compiledURL,
        trainingData: batchProvider,
        configuration: nil,
        completionHandler: { finalContext in
            print("completion handler called")
            let trainedModel = finalContext.model
            print("model_description \(trainedModel.modelDescription.debugDescription)")

            // Run a prediction on the trained model to prove it works
            let testSample = samples[0]
            do {
                let testProvider = try SampleFeatureProvider(sample: testSample)
                let prediction = try trainedModel.prediction(from: testProvider)
                if let probs = prediction.featureValue(for: "class_probs")?.multiArrayValue {
                    var probsArr: [Float] = []
                    for i in 0..<probs.count {
                        probsArr.append(probs[i].floatValue)
                    }
                    let probsStr = probsArr.map { String($0) }.joined(separator: ",")
                    print("trained_prediction " + probsStr)
                }
            } catch {
                FileHandle.standardError.write("Prediction failed: \(error)\n".data(using: .utf8)!)
            }

            // Try to save the model
            let fm = FileManager.default
            let savePaths = [
                outURL.path,
                "/tmp/TrainedClassifier.mlmodel",
                outURL.deletingPathExtension().appendingPathExtension("mlmodelc").path,
            ]
            for path in savePaths {
                if fm.fileExists(atPath: path) {
                    try? fm.removeItem(atPath: path)
                }
                do {
                    try trainedModel.write(to: URL(fileURLWithPath: path))
                    print("trained_saved \(path)")
                    return
                } catch {
                    FileHandle.standardError.write("Save to \(path) failed: \(error)\n".data(using: .utf8)!)
                }
            }
            FileHandle.standardError.write("All save paths failed — but training completed and prediction works\n".data(using: .utf8)!)
        }
    )
} catch {
    caughtError = error
    FileHandle.standardError.write("Failed to create MLUpdateTask: \(error)\n".data(using: .utf8)!)
    exit(1)
}

print("task created, resuming...")

// Run a BASELINE prediction before training for comparison
do {
    let baselineModel = try MLModel(contentsOf: compiledURL, configuration: MLModelConfiguration())
    let testSample = samples[0]
    let testProvider = try SampleFeatureProvider(sample: testSample)
    let baselinePred = try baselineModel.prediction(from: testProvider)
    if let probs = baselinePred.featureValue(for: "class_probs")?.multiArrayValue {
        var probsArr: [Float] = []
        for i in 0..<probs.count {
            probsArr.append(probs[i].floatValue)
        }
        let baselineStr = probsArr.map { String($0) }.joined(separator: ",")
        print("baseline_prediction " + baselineStr)
    }
} catch {
    FileHandle.standardError.write("Baseline prediction failed: \(error)\n".data(using: .utf8)!)
}

updateTask?.resume()

// Keep the runloop alive
RunLoop.current.run(until: Date(timeIntervalSinceNow: 300))
print("runloop ended")
