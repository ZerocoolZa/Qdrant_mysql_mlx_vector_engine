#!/usr/bin/env swift
//[@GHOST]
//[@VBSTYLE]
//[@FILEID] coreml_layout_update.swift
//[@SUMMARY] Runs MLUpdateTask to train CoreML layout policy on-device
//[@CLASS] none
//[@METHOD] main
//[@AUTHOR] Cascade
//[@DATE] 2026-06-28
//[@SESSION] coreml_layout_push

import Foundation
import CoreML
import ArgumentParser

struct LayoutUpdater: ParsableCommand {
    @Option(name: "--model", help: "Path to updatable .mlpackage")
    var modelPath: String

    @Option(name: "--data", help: "Path to training_data.json")
    var dataPath: String

    @Option(name: "--output", help: "Path to save trained .mlpackage")
    var outputPath: String

    @Option(name: "--epochs", help: "Number of training epochs")
    var epochs: Int = 50

    func run() throws {
        print("Loading model from: \(modelPath)")
        let modelURL = URL(fileURLWithPath: modelPath)
        let model = try MLModel(contentsOf: modelURL)

        print("Loading training data from: \(dataPath)")
        let dataURL = URL(fileURLWithPath: dataPath)
        let jsonData = try Data(contentsOf: dataURL)
        let json = try JSONSerialization.jsonObject(with: jsonData) as! [String: Any]
        let episodes = json["episodes"] as! [[String: Any]]

        print("Building training feature providers...")
        var featureProviders: [MLFeatureProvider] = []

        for episode in episodes {
            let steps = episode["steps"] as! [[String: Any]]
            for step in steps {
                let stateArray = step["state"] as! [Double]
                let actionArray = step["action"] as! [Double]

                let stateMLMultiArray = try MLMultiArray(
                    shape: [1, NSNumber(value: stateArray.count)],
                    dataType: .float32
                )
                let statePtr = stateMLMultiArray.dataPointer.bindMemory(to: Float.self, capacity: stateArray.count)
                for i in 0..<stateArray.count {
                    statePtr[i] = Float(stateArray[i])
                }

                let actionMLMultiArray = try MLMultiArray(
                    shape: [1, NSNumber(value: actionArray.count)],
                    dataType: .float32
                )
                let actionPtr = actionMLMultiArray.dataPointer.bindMemory(to: Float.self, capacity: actionArray.count)
                for i in 0..<actionArray.count {
                    actionPtr[i] = Float(actionArray[i])
                }

                let featureProvider = try MLDictionaryFeatureProvider(
                    dictionary: [
                        "state": MLFeatureValue(multiArray: stateMLMultiArray),
                        "action_target": MLFeatureValue(multiArray: actionMLMultiArray),
                    ]
                )
                featureProviders.append(featureProvider)
            }
        }

        print("Total training samples: \(featureProviders.count)")

        let batchProvider = MLArrayBatchProvider(array: featureProviders)

        let trainingTask = try MLUpdateTask(
            forModelAt: modelURL,
            trainingData: batchProvider,
            configuration: MLModelConfiguration(),
            handler: { context in
                let loss = context.metrics.lossValue
                let epoch = context.metrics.epochIndex
                print("  Epoch \(epoch + 1)/\(self.epochs) — Loss: \(loss)")
            }
        )

        print("Starting training: \(epochs) epochs...")
        trainingTask.resume()

        let updatedModel = trainingTask.model

        let outputURL = URL(fileURLWithPath: outputPath)
        try updatedModel.write(to: outputURL)
        print("Trained model saved to: \(outputPath)")
        print("DONE")
    }
}

LayoutUpdater.main()
