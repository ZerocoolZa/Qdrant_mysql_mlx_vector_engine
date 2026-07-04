#!/usr/bin/env python3
"""Test CoreML models to find which one works for embeddings."""
import coremltools as ct
import numpy as np

paths = [
    ("/Users/wws/Documents/Models/coreml_models/TokenEmbedder.mlmodel", "TokenEmbedder"),
    ("/Users/wws/Documents/Models/coreml_models/TokenEmbedder_V2.mlpackage", "TokenEmbedder_V2"),
    ("/Users/wws/Documents/Models/MiniLM-L12-v2/all-MiniLM-L12-v2-converted/all-MiniLM-L6-v2_6136536182.mlpackage", "MiniLM-L6"),
    ("/Users/wws/Documents/Models/coreml_models/BERTSQUADFP16.mlmodel", "BERTSQUAD"),
    ("/Users/wws/Documents/Models/CustomReverseEmbedder/CustomReverseEmbedder.mlmodel", "CustomReverse"),
]

for path, name in paths:
    print(f"\n--- {name} ---")
    try:
        m = ct.models.MLModel(path)
        spec = m.get_spec()
        for i in spec.description.input:
            if i.type.HasField('multiArrayType'):
                shape = list(i.type.multiArrayType.shape)
                dtype = i.type.multiArrayType.dataType
                print(f"  Input: {i.name} shape={shape} dtype={dtype}")
            elif i.type.HasField('stringType'):
                print(f"  Input: {i.name} type=string")
            else:
                print(f"  Input: {i.name} type=other")
        for o in spec.description.output:
            if o.type.HasField('multiArrayType'):
                shape = list(o.type.multiArrayType.shape)
                print(f"  Output: {o.name} shape={shape}")
            elif o.type.HasField('stringType'):
                print(f"  Output: {o.name} type=string")
            else:
                print(f"  Output: {o.name} type=other")
        # Try a test prediction
        inp_name = spec.description.input[0].name
        out_name = spec.description.output[0].name
        if spec.description.input[0].type.HasField('multiArrayType'):
            shape = list(spec.description.input[0].type.multiArrayType.shape)
            if not shape or shape[0] == 0:
                shape = [1]
            test_vec = np.ones(shape, dtype=np.float32)
            try:
                out = m.predict({inp_name: test_vec})
                result = np.asarray(out[out_name], dtype=np.float32)
                print(f"  Test predict OK: {result.shape}")
            except Exception as pe:
                print(f"  Test predict FAIL: {str(pe)[:150]}")
    except Exception as e:
        print(f"  LOAD FAIL: {str(e)[:150]}")
