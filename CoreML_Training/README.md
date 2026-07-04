# CoreML On-Device Training — MLUpdateTask Proof-of-Concept

Real CoreML training via `MLUpdateTask`. This proves CoreML can actually train a model on-device — not just run inference on a PyTorch-converted model.

## What this proves

1. Builds a tiny FC classifier (4 -> 8 -> 3) from scratch in `coremltools`
2. Marks it **updatable** via `make_updatable()` + `set_categorical_cross_entropy_loss()` + `set_adam_optimizer()` + `set_epochs()`
3. Generates 200 synthetic labeled samples
4. Runs the actual CoreML training via `MLUpdateTask` (Python `coremltools` API)
5. Captures baseline weights, trains, captures trained weights, **verifies the weights actually changed**

If `weights_changed: True` at the end, CoreML training genuinely happened on-device.

## Files

| File | Role |
|---|---|
| `Config.py` | All paths, hyperparameters, constants (VBStyle) |
| `UpdatableBuilder.py` | Builds the updatable `.mlmodel` spec |
| `SyntheticDataGen.py` | Generates synthetic labeled data + `MLArrayBatchProvider` |
| `CoreMLTrainer.py` | Runs `MLUpdateTask`, captures weights, verifies change |
| `main.py` | Entry point — dispatch: `build`, `gendata`, `train`, `verify`, `all` |
| `run_training.swift` | Native Swift `MLUpdateTask` runner (requires Xcode to compile) |
| `output/` | Generated models + weight snapshots (created on first run) |

## Run it (Python path — works now)

```bash
cd /Users/wws/Qdrant_mysql_mlx_vector_engine/CoreML_Training
/usr/local/bin/python3 main.py all
```

Or step-by-step:
```bash
/usr/local/bin/python3 main.py build     # build updatable .mlmodel
/usr/local/bin/python3 main.py gendata   # generate synthetic data
/usr/local/bin/python3 main.py train     # run MLUpdateTask training
/usr/local/bin/python3 main.py verify    # verify weights changed
```

## Run it (Swift path — requires Xcode)

The Swift runner uses the native `MLUpdateTask` + `MLUpdateProgressHandlers` API. It needs the full Xcode SDK (not just Command Line Tools):

```bash
# Once Xcode is installed:
swiftc -framework CoreML -framework Foundation run_training.swift -o run_training
./run_training output/UpdatableClassifier.mlmodel training_data.json
```

## Phase 2 — Real model

Phase 1 uses synthetic data on a tiny FC network. Phase 2 adapts this to your real `BestMapper(384, 40)` PyTorch model:

1. Convert `BestMapper(384, 40)` to a `neuralNetwork` spec (not `mlProgram`) — `make_updatable` requires the neural-network spec type
2. Mark the FC layers updatable
3. Pull training data from `token_registry.db`
4. Run `MLUpdateTask` to finetune on real data

## Verification checklist

- [ ] `py_compile` passes on all `.py` files
- [ ] No `print(` outside `__main__` (uses `logging`)
- [ ] No `@staticmethod` / `@property` / `@classmethod`
- [ ] No `self._` variables (uses `self.state` dict)
- [ ] All methods return Tuple3 `(ok, data, error)`
- [ ] All classes have `Run()` dispatch
- [ ] End-to-end run produces `weights_changed: True`
- [ ] Trained model has `isUpdatable: True`
