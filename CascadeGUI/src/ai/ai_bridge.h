#ifndef CASCADE_AI_BRIDGE_H
#define CASCADE_AI_BRIDGE_H

typedef struct {
    char model[64];
    float confidence;
    int queries_made;
    int queries_cached;
    char last_query[1024];
} AiBridgeState;

const char *ai_bridge_query(const char *prompt, const char *model, float temperature);
float ai_bridge_last_confidence(void);
void ai_bridge_init(void);
void ai_bridge_shutdown(void);

#endif
