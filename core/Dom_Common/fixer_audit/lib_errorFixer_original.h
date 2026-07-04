/*
 * CASCADE Error Fixer - In-Memory Error Detection & Correction
 * Self-modifying error recovery system
 */

#ifndef LIB_ERROR_FIXER_H
#define LIB_ERROR_FIXER_H

#include <stdint.h>
#include <stddef.h>

#define MAX_ERROR_RECORDS 5000
#define ERROR_CONTEXT_SIZE 256

typedef enum {
    ERROR_TYPE_MEMORY = 1,
    ERROR_TYPE_LOGIC = 2,
    ERROR_TYPE_BOUNDARY = 3,
    ERROR_TYPE_RACE = 4,
    ERROR_TYPE_DEADLOCK = 5
} ErrorType;

typedef struct {
    uint32_t id;
    ErrorType type;
    uint64_t address;
    uint32_t severity;
    char context[ERROR_CONTEXT_SIZE];
    uint64_t timestamp;
    uint32_t fix_attempts;
    uint32_t fixed;
} ErrorRecord;

typedef struct {
    ErrorRecord records[MAX_ERROR_RECORDS];
    uint32_t count;
    uint32_t total_fixed;
    uint32_t total_failed;
} ErrorFixer;

// Core API
ErrorFixer* error_fixer_init(void);
void error_fixer_free(ErrorFixer *fixer);
uint32_t error_fixer_detect(ErrorFixer *fixer, ErrorType type, uint64_t addr, const char *context);
int error_fixer_attempt_fix(ErrorFixer *fixer, uint32_t error_id);
int error_fixer_auto_fix(ErrorFixer *fixer);
uint32_t error_fixer_get_fixed_count(ErrorFixer *fixer);
uint32_t error_fixer_get_failed_count(ErrorFixer *fixer);

#endif

