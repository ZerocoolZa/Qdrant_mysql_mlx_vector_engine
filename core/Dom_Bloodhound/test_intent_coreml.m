// test_intent_coreml.m — Test the CoreML intent router
// [@GHOST]{file_path="core/Dom_Bloodhound/test_intent_coreml.m" date="2026-07-04" author="Devin" session_id="coreml-test" context="Test CoreML intent router from C/ObjC"}
// [@VBSTYLE]{standard="VBStyle" version="1"}

#import <Foundation/Foundation.h>
#import "intent_coreml.h"

int main(int argc, const char *argv[]) {
    @autoreleasepool {
        const char *model_path = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Mcp/dom_mcp/tools/intent_model/IntentRouter.mlpackage";
        const char *vocab_path = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Mcp/dom_mcp/tools/intent_model/intent_vocab.json";

        NSLog(@"=== CoreML Intent Router Test ===\n");

        IntentRouter router;
        if (intent_load(&router, model_path, vocab_path) != 0) {
            NSLog(@"FAIL: Could not load model or vocab");
            return 1;
        }
        NSLog(@"Loaded: %d vocab words, model ready\n", router.vocab.count);

        // Test queries
        const char *queries[] = {
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
        };
        int n_queries = sizeof(queries) / sizeof(queries[0]);

        NSLog(@"Predictions:\n");
        for (int i = 0; i < n_queries; i++) {
            IntentResult result;
            if (intent_predict(&router, queries[i], &result) == 0) {
                NSLog(@"  '%s' -> %s (conf=%.4f)",
                      queries[i], result.tool_name, result.confidence);
            } else {
                NSLog(@"  '%s' -> ERROR", queries[i]);
            }
        }

        // Benchmark: how fast?
        NSLog(@"\nBenchmark (100 predictions):");
        NSTimeInterval start = [NSDate timeIntervalSinceReferenceDate];
        for (int i = 0; i < 100; i++) {
            IntentResult result;
            intent_predict(&router, "search for kokoro", &result);
        }
        NSTimeInterval elapsed = [NSDate timeIntervalSinceReferenceDate] - start;
        NSLog(@"  100 predictions in %.3f seconds (%.1f ms each)\n",
              elapsed, elapsed * 10);

        intent_free(&router);
        NSLog(@"Done.");
    }
    return 0;
}
