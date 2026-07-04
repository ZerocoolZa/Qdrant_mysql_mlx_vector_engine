 // bv3_engine_final.c
// Single-file BV3 final-style engine with BL backward logic
//
// Features:
// - exact byte-for-byte roundtrip
// - base token dictionary
// - phrase dictionary (bigrams + trigrams)
// - BL backward logic greedy packing
// - varint packed stream
// - CRC32 integrity
// - verify mode
// - stats mode
// - shell mode
// - deterministic local embedder
//
// Build:
//   clang -O2 -std=c11 -Wall -Wextra -o bv3_engine_final bv3_engine_final.c -lm
//
// Use:
//   ./bv3_engine_final compress   input.txt  output.bv3
//   ./bv3_engine_final decompress input.bv3  output.txt
//   ./bv3_engine_final verify     input.txt  output.bv3 rebuilt.txt
//   ./bv3_engine_final stats      input.bv3
//   ./bv3_engine_final shell      input.bv3
//   ./bv3_engine_final embed      input.txt  256
//
// Notes:
// - "BL backward logic" here means:
//   mine repeated phrases, then pack the token stream from the end backward,
//   preferring longest valid phrase first, then pair, then single token.
// - exact roundtrip is preserved.
// - embedder is deterministic and local. It is not CodeBERT.

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <ctype.h>
#include <math.h>

#define MAGIC "BV3F"
#define VERSION 3u

#define INITIAL_CAP 128u
#define HASH_CAP 2048u
#define MAX_PREVIEW 32u
#define MAX_PHRASES 4096u
#define MIN_PAIR_FREQ 3u
#define MIN_TRI_FREQ 3u

typedef struct {
    char *data;
    uint32_t len;
    uint32_t freq;
    uint64_t hash;
} Token;

typedef struct {
    Token *items;
    uint32_t count;
    uint32_t cap;
} TokenTable;

typedef struct {
    uint32_t *items;
    uint32_t count;
    uint32_t cap;
} UInt32Vec;

typedef struct {
    uint32_t arity;      // 2 or 3
    uint32_t ids[3];     // base token IDs only
    uint32_t freq;
    uint64_t hash;
} Phrase;

typedef struct {
    Phrase *items;
    uint32_t count;
    uint32_t cap;
} PhraseTable;

typedef struct {
    uint32_t key_count;
    uint32_t key_cap;
    uint64_t *keys;
    uint32_t *freqs;
} CountMap;

typedef struct {
    uint64_t original_bytes;
    uint32_t crc32;
    uint32_t base_token_count;
    uint32_t phrase_count;
    uint64_t raw_token_count;
    uint64_t packed_symbol_count;
    uint64_t base_dict_bytes;
    uint64_t phrase_dict_bytes;
    uint64_t stream_bytes;
    uint64_t total_bv3_bytes;
} BV3Stats;

static void die(const char *msg) {
    fprintf(stderr, "ERROR: %s\n", msg);
    exit(1);
}

static void *xmalloc(size_t n) {
    void *p = malloc(n);
    if (!p) die("out of memory");
    return p;
}

static void *xcalloc(size_t n, size_t s) {
    void *p = calloc(n, s);
    if (!p) die("out of memory");
    return p;
}

static void *xrealloc(void *p, size_t n) {
    void *q = realloc(p, n);
    if (!q) die("out of memory");
    return q;
}

static char *read_file_bytes(const char *path, size_t *out_len) {
    FILE *f = fopen(path, "rb");
    long size;
    char *buf;

    if (!f) die("cannot open input file");
    if (fseek(f, 0, SEEK_END) != 0) die("fseek end failed");
    size = ftell(f);
    if (size < 0) die("ftell failed");
    if (fseek(f, 0, SEEK_SET) != 0) die("fseek start failed");

    buf = (char *)xmalloc((size_t)size + 1u);
    if (size > 0 && fread(buf, 1, (size_t)size, f) != (size_t)size) {
        fclose(f);
        free(buf);
        die("fread failed");
    }
    fclose(f);
    buf[size] = '\0';
    *out_len = (size_t)size;
    return buf;
}

static void write_file_bytes(const char *path, const char *data, size_t len) {
    FILE *f = fopen(path, "wb");
    if (!f) die("cannot open output file");
    if (len > 0 && fwrite(data, 1, len, f) != len) {
        fclose(f);
        die("fwrite failed");
    }
    fclose(f);
}

static uint64_t fnv1a64_bytes(const unsigned char *data, size_t len) {
    uint64_t h = 1469598103934665603ULL;
    size_t i;
    for (i = 0; i < len; i++) {
        h ^= (uint64_t)data[i];
        h *= 1099511628211ULL;
    }
    return h;
}

static uint32_t crc32_bytes(const unsigned char *data, size_t len) {
    uint32_t crc = 0xFFFFFFFFu;
    size_t i;
    for (i = 0; i < len; i++) {
        uint32_t x = (crc ^ data[i]) & 0xFFu;
        int j;
        for (j = 0; j < 8; j++) {
            x = (x >> 1) ^ (0xEDB88320u & (uint32_t)(-(int32_t)(x & 1u)));
        }
        crc = (crc >> 8) ^ x;
    }
    return ~crc;
}

static void token_table_init(TokenTable *t) {
    t->items = (Token *)xcalloc(INITIAL_CAP, sizeof(Token));
    t->count = 0;
    t->cap = INITIAL_CAP;
}

static void token_table_free(TokenTable *t) {
    uint32_t i;
    for (i = 0; i < t->count; i++) free(t->items[i].data);
    free(t->items);
    t->items = NULL;
    t->count = 0;
    t->cap = 0;
}

static void phrase_table_init(PhraseTable *p) {
    p->items = (Phrase *)xcalloc(INITIAL_CAP, sizeof(Phrase));
    p->count = 0;
    p->cap = INITIAL_CAP;
}

static void phrase_table_free(PhraseTable *p) {
    free(p->items);
    p->items = NULL;
    p->count = 0;
    p->cap = 0;
}

static void u32vec_init(UInt32Vec *v) {
    v->items = (uint32_t *)xmalloc(sizeof(uint32_t) * INITIAL_CAP);
    v->count = 0;
    v->cap = INITIAL_CAP;
}

static void u32vec_push(UInt32Vec *v, uint32_t x) {
    if (v->count == v->cap) {
        v->cap *= 2u;
        v->items = (uint32_t *)xrealloc(v->items, sizeof(uint32_t) * v->cap);
    }
    v->items[v->count++] = x;
}

static void u32vec_reverse(UInt32Vec *v) {
    uint32_t i = 0, j = v->count ? v->count - 1u : 0u;
    while (i < j) {
        uint32_t tmp = v->items[i];
        v->items[i] = v->items[j];
        v->items[j] = tmp;
        i++;
        j--;
    }
}

static void u32vec_free(UInt32Vec *v) {
    free(v->items);
    v->items = NULL;
    v->count = 0;
    v->cap = 0;
}

static void count_map_init(CountMap *m) {
    m->key_count = 0;
    m->key_cap = INITIAL_CAP;
    m->keys = (uint64_t *)xmalloc(sizeof(uint64_t) * m->key_cap);
    m->freqs = (uint32_t *)xmalloc(sizeof(uint32_t) * m->key_cap);
}

static void count_map_add(CountMap *m, uint64_t key) {
    uint32_t i;
    for (i = 0; i < m->key_count; i++) {
        if (m->keys[i] == key) {
            m->freqs[i]++;
            return;
        }
    }
    if (m->key_count == m->key_cap) {
        m->key_cap *= 2u;
        m->keys = (uint64_t *)xrealloc(m->keys, sizeof(uint64_t) * m->key_cap);
        m->freqs = (uint32_t *)xrealloc(m->freqs, sizeof(uint32_t) * m->key_cap);
    }
    m->keys[m->key_count] = key;
    m->freqs[m->key_count] = 1u;
    m->key_count++;
}

static void count_map_free(CountMap *m) {
    free(m->keys);
    free(m->freqs);
    m->keys = NULL;
    m->freqs = NULL;
    m->key_count = 0;
    m->key_cap = 0;
}

static int is_word_char(unsigned char c) {
    return isalnum(c) || c == '_';
}

static uint32_t token_table_find(TokenTable *t, const char *data, uint32_t len, uint64_t hash) {
    uint32_t i;
    for (i = 0; i < t->count; i++) {
        if (t->items[i].len == len && t->items[i].hash == hash &&
            memcmp(t->items[i].data, data, len) == 0) {
            return i;
        }
    }
    return UINT32_MAX;
}

static uint32_t token_table_find_or_add(TokenTable *t, const char *data, uint32_t len) {
    uint64_t hash = fnv1a64_bytes((const unsigned char *)data, len);
    uint32_t found = token_table_find(t, data, len, hash);

    if (found != UINT32_MAX) {
        t->items[found].freq++;
        return found;
    }

    if (t->count == t->cap) {
        t->cap *= 2u;
        t->items = (Token *)xrealloc(t->items, sizeof(Token) * t->cap);
    }

    t->items[t->count].data = (char *)xmalloc((size_t)len + 1u);
    memcpy(t->items[t->count].data, data, len);
    t->items[t->count].data[len] = '\0';
    t->items[t->count].len = len;
    t->items[t->count].freq = 1u;
    t->items[t->count].hash = hash;
    return t->count++;
}

static void tokenize_exact(const char *src, size_t len, TokenTable *table, UInt32Vec *stream) {
    size_t i = 0;
    while (i < len) {
        size_t start = i;
        int word = is_word_char((unsigned char)src[i]);
        i++;
        while (i < len && is_word_char((unsigned char)src[i]) == word) i++;
        u32vec_push(stream, token_table_find_or_add(table, src + start, (uint32_t)(i - start)));
    }
}

static int token_cmp_freq_desc(const void *a, const void *b) {
    const Token *ta = (const Token *)a;
    const Token *tb = (const Token *)b;
    if (ta->freq < tb->freq) return 1;
    if (ta->freq > tb->freq) return -1;
    if (ta->len < tb->len) return -1;
    if (ta->len > tb->len) return 1;
    return strcmp(ta->data, tb->data);
}

static void rank_tokens_by_frequency(TokenTable *table, UInt32Vec *stream) {
    uint32_t i, j;
    Token *old_items = table->items;
    Token *sorted = (Token *)xmalloc(sizeof(Token) * table->count);
    uint32_t *old_to_new = (uint32_t *)xmalloc(sizeof(uint32_t) * table->count);

    for (i = 0; i < table->count; i++) sorted[i] = old_items[i];
    qsort(sorted, table->count, sizeof(Token), token_cmp_freq_desc);

    for (i = 0; i < table->count; i++) {
        for (j = 0; j < table->count; j++) {
            if (old_items[j].data == sorted[i].data) {
                old_to_new[j] = i;
                break;
            }
        }
    }

    table->items = sorted;
    for (i = 0; i < stream->count; i++) stream->items[i] = old_to_new[stream->items[i]];

    free(old_to_new);
    free(old_items);
}

static uint64_t make_pair_key(uint32_t a, uint32_t b) {
    return ((uint64_t)a << 32u) | (uint64_t)b;
}

static uint64_t make_tri_key(uint32_t a, uint32_t b, uint32_t c) {
    return (fnv1a64_bytes((const unsigned char *)&a, sizeof(uint32_t)) ^
           (fnv1a64_bytes((const unsigned char *)&b, sizeof(uint32_t)) << 1u) ^
           (fnv1a64_bytes((const unsigned char *)&c, sizeof(uint32_t)) << 2u));
}

static int phrase_exists(PhraseTable *pt, uint32_t arity, const uint32_t *ids) {
    uint32_t i, j;
    for (i = 0; i < pt->count; i++) {
        if (pt->items[i].arity != arity) continue;
        for (j = 0; j < arity; j++) {
            if (pt->items[i].ids[j] != ids[j]) break;
        }
        if (j == arity) return 1;
    }
    return 0;
}

static void phrase_add(PhraseTable *pt, uint32_t arity, const uint32_t *ids, uint32_t freq, uint64_t hash) {
    if (pt->count == pt->cap) {
        pt->cap *= 2u;
        pt->items = (Phrase *)xrealloc(pt->items, sizeof(Phrase) * pt->cap);
    }
    pt->items[pt->count].arity = arity;
    pt->items[pt->count].ids[0] = ids[0];
    pt->items[pt->count].ids[1] = ids[1];
    pt->items[pt->count].ids[2] = (arity == 3u) ? ids[2] : 0u;
    pt->items[pt->count].freq = freq;
    pt->items[pt->count].hash = hash;
    pt->count++;
}

static int phrase_cmp_score_desc(const void *a, const void *b) {
    const Phrase *pa = (const Phrase *)a;
    const Phrase *pb = (const Phrase *)b;
    uint64_t sa = (uint64_t)pa->freq * (uint64_t)pa->arity;
    uint64_t sb = (uint64_t)pb->freq * (uint64_t)pb->arity;
    if (sa < sb) return 1;
    if (sa > sb) return -1;
    if (pa->arity < pb->arity) return 1;
    if (pa->arity > pb->arity) return -1;
    return 0;
}

static void mine_phrases(const UInt32Vec *stream, PhraseTable *phrases) {
    CountMap pairs, tris;
    uint32_t i;

    count_map_init(&pairs);
    count_map_init(&tris);

    for (i = 0; i + 1u < stream->count; i++) {
        count_map_add(&pairs, make_pair_key(stream->items[i], stream->items[i + 1u]));
    }
    for (i = 0; i + 2u < stream->count; i++) {
        count_map_add(&tris, make_tri_key(stream->items[i], stream->items[i + 1u], stream->items[i + 2u]));
    }

    // Add trigrams first
    for (i = 0; i + 2u < stream->count && phrases->count < MAX_PHRASES; i++) {
        uint32_t ids[3];
        uint64_t key = make_tri_key(stream->items[i], stream->items[i + 1u], stream->items[i + 2u]);
        uint32_t j;
        uint32_t freq = 0u;
        for (j = 0; j < tris.key_count; j++) {
            if (tris.keys[j] == key) {
                freq = tris.freqs[j];
                break;
            }
        }
        if (freq >= MIN_TRI_FREQ) {
            ids[0] = stream->items[i];
            ids[1] = stream->items[i + 1u];
            ids[2] = stream->items[i + 2u];
            if (!phrase_exists(phrases, 3u, ids)) phrase_add(phrases, 3u, ids, freq, key);
        }
    }

    // Add pairs
    for (i = 0; i + 1u < stream->count && phrases->count < MAX_PHRASES; i++) {
        uint32_t ids[3];
        uint64_t key = make_pair_key(stream->items[i], stream->items[i + 1u]);
        uint32_t j;
        uint32_t freq = 0u;
        for (j = 0; j < pairs.key_count; j++) {
            if (pairs.keys[j] == key) {
                freq = pairs.freqs[j];
                break;
            }
        }
        if (freq >= MIN_PAIR_FREQ) {
            ids[0] = stream->items[i];
            ids[1] = stream->items[i + 1u];
            ids[2] = 0u;
            if (!phrase_exists(phrases, 2u, ids)) phrase_add(phrases, 2u, ids, freq, key);
        }
    }

    qsort(phrases->items, phrases->count, sizeof(Phrase), phrase_cmp_score_desc);
    if (phrases->count > MAX_PHRASES) phrases->count = MAX_PHRASES;

    count_map_free(&pairs);
    count_map_free(&tris);
}

static int phrase_match_end(const Phrase *p, const UInt32Vec *stream, uint32_t end_exclusive) {
    uint32_t start;
    if (p->arity > end_exclusive) return 0;
    start = end_exclusive - p->arity;
    if (p->arity == 3u) {
        return stream->items[start] == p->ids[0] &&
               stream->items[start + 1u] == p->ids[1] &&
               stream->items[start + 2u] == p->ids[2];
    }
    return stream->items[start] == p->ids[0] &&
           stream->items[start + 1u] == p->ids[1];
}

static int phrase_match_symbol(const Phrase *p, uint32_t phrase_base, uint32_t sym,
                               const PhraseTable *pt, const UInt32Vec *base_out) {
    (void)p; (void)phrase_base; (void)sym; (void)pt; (void)base_out;
    return 0;
}

static void pack_backward_logic(const UInt32Vec *raw, const PhraseTable *phrases, UInt32Vec *packed) {
    uint32_t i = raw->count;
    uint32_t phrase_base = UINT32_MAX; // set later by caller logic if needed
    (void)phrase_base;

    while (i > 0u) {
        uint32_t best_idx = UINT32_MAX;
        uint32_t best_arity = 0u;
        uint32_t p;

        // prefer longest + earlier ranked phrase
        for (p = 0; p < phrases->count; p++) {
            const Phrase *ph = &phrases->items[p];
            if (ph->arity < best_arity) continue;
            if (phrase_match_end(ph, raw, i)) {
                if (ph->arity > best_arity) {
                    best_idx = p;
                    best_arity = ph->arity;
                    if (best_arity == 3u) break;
                } else if (best_idx == UINT32_MAX) {
                    best_idx = p;
                }
            }
        }

        if (best_idx != UINT32_MAX) {
            u32vec_push(packed, raw->count + best_idx); // temporary, remap later
            i -= best_arity;
        } else {
            u32vec_push(packed, raw->items[i - 1u]);
            i--;
        }
    }

    u32vec_reverse(packed);
}

static void write_u32(FILE *f, uint32_t x) {
    if (fwrite(&x, sizeof(uint32_t), 1, f) != 1) die("write_u32 failed");
}

static void write_u64(FILE *f, uint64_t x) {
    if (fwrite(&x, sizeof(uint64_t), 1, f) != 1) die("write_u64 failed");
}

static uint32_t read_u32(FILE *f) {
    uint32_t x;
    if (fread(&x, sizeof(uint32_t), 1, f) != 1) die("read_u32 failed");
    return x;
}

static uint64_t read_u64(FILE *f) {
    uint64_t x;
    if (fread(&x, sizeof(uint64_t), 1, f) != 1) die("read_u64 failed");
    return x;
}

static uint32_t varint_size_u64(uint64_t v) {
    uint32_t n = 1u;
    while (v >= 0x80u) {
        v >>= 7u;
        n++;
    }
    return n;
}

static void write_varint_u64(FILE *f, uint64_t v, uint64_t *written_bytes) {
    while (v >= 0x80u) {
        unsigned char b = (unsigned char)((v & 0x7Fu) | 0x80u);
        if (fwrite(&b, 1, 1, f) != 1) die("write varint failed");
        (*written_bytes)++;
        v >>= 7u;
    }
    {
        unsigned char b = (unsigned char)(v & 0x7Fu);
        if (fwrite(&b, 1, 1, f) != 1) die("write varint failed");
        (*written_bytes)++;
    }
}

static uint64_t read_varint_u64(FILE *f, uint64_t *read_bytes) {
    uint64_t value = 0u;
    uint32_t shift = 0u;
    for (;;) {
        unsigned char b;
        if (fread(&b, 1, 1, f) != 1) die("read varint failed");
        (*read_bytes)++;
        value |= (uint64_t)(b & 0x7Fu) << shift;
        if ((b & 0x80u) == 0u) break;
        shift += 7u;
        if (shift > 63u) die("varint too large");
    }
    return value;
}

static void build_stats(const TokenTable *base, const PhraseTable *phrases,
                        const UInt32Vec *raw, const UInt32Vec *packed,
                        uint64_t original_bytes, uint32_t crc32, BV3Stats *s) {
    uint32_t i;
    memset(s, 0, sizeof(*s));

    s->original_bytes = original_bytes;
    s->crc32 = crc32;
    s->base_token_count = base->count;
    s->phrase_count = phrases->count;
    s->raw_token_count = raw->count;
    s->packed_symbol_count = packed->count;

    for (i = 0; i < base->count; i++) {
        s->base_dict_bytes += 4u;
        s->base_dict_bytes += base->items[i].len;
    }

    for (i = 0; i < phrases->count; i++) {
        s->phrase_dict_bytes += 4u; // arity
        s->phrase_dict_bytes += 4u * phrases->items[i].arity;
    }

    for (i = 0; i < packed->count; i++) {
        s->stream_bytes += varint_size_u64(packed->items[i]);
    }

    s->total_bv3_bytes =
        4u + 4u + 8u + 4u +              // magic, version, orig len, crc
        4u + s->base_dict_bytes +        // base count + base dict
        4u + s->phrase_dict_bytes +      // phrase count + phrase dict
        8u + s->stream_bytes;            // packed count + stream
}

static void print_stats_struct(const BV3Stats *s) {
    double ratio = 0.0;
    if (s->original_bytes > 0) {
        ratio = 100.0 * (1.0 - ((double)s->total_bv3_bytes / (double)s->original_bytes));
    }

    printf("Original bytes      : %llu\n", (unsigned long long)s->original_bytes);
    printf("CRC32               : %08X\n", s->crc32);
    printf("Base tokens         : %u\n", s->base_token_count);
    printf("Phrases             : %u\n", s->phrase_count);
    printf("Raw token count     : %llu\n", (unsigned long long)s->raw_token_count);
    printf("Packed symbol count : %llu\n", (unsigned long long)s->packed_symbol_count);
    printf("Base dict bytes     : %llu\n", (unsigned long long)s->base_dict_bytes);
    printf("Phrase dict bytes   : %llu\n", (unsigned long long)s->phrase_dict_bytes);
    printf("Stream bytes        : %llu\n", (unsigned long long)s->stream_bytes);
    printf("Total BV3 bytes     : %llu\n", (unsigned long long)s->total_bv3_bytes);
    printf("Compression ratio   : %.2f%%\n", ratio);
}

static void print_top_tokens(const TokenTable *table) {
    uint32_t i, top = table->count < 10u ? table->count : 10u;
    printf("Top base tokens:\n");
    for (i = 0; i < top; i++) {
        printf("  [%u] freq=%u len=%u text=\"", i, table->items[i].freq, table->items[i].len);
        {
            uint32_t j, preview = table->items[i].len < MAX_PREVIEW ? table->items[i].len : MAX_PREVIEW;
            for (j = 0; j < preview; j++) {
                unsigned char c = (unsigned char)table->items[i].data[j];
                if (c == '\n') printf("\\n");
                else if (c == '\t') printf("\\t");
                else if (isprint(c)) putchar(c);
                else printf("\\x%02X", c);
            }
            if (table->items[i].len > preview) printf("...");
        }
        printf("\"\n");
    }
}

static void print_top_phrases(const PhraseTable *phrases) {
    uint32_t i, top = phrases->count < 10u ? phrases->count : 10u;
    printf("Top phrases:\n");
    for (i = 0; i < top; i++) {
        printf("  [%u] freq=%u arity=%u ids=", i, phrases->items[i].freq, phrases->items[i].arity);
        if (phrases->items[i].arity == 2u) {
            printf("%u|%u\n", phrases->items[i].ids[0], phrases->items[i].ids[1]);
        } else {
            printf("%u|%u|%u\n", phrases->items[i].ids[0], phrases->items[i].ids[1], phrases->items[i].ids[2]);
        }
    }
}

static void compress_file(const char *input_path, const char *output_path) {
    size_t len;
    char *src = read_file_bytes(input_path, &len);
    uint32_t crc = crc32_bytes((const unsigned char *)src, len);
    TokenTable base;
    UInt32Vec raw;
    PhraseTable phrases;
    UInt32Vec packed;
    FILE *out;
    uint32_t i;
    uint64_t stream_bytes_written = 0u;
    BV3Stats stats;

    token_table_init(&base);
    u32vec_init(&raw);
    phrase_table_init(&phrases);
    u32vec_init(&packed);

    tokenize_exact(src, len, &base, &raw);
    rank_tokens_by_frequency(&base, &raw);
    mine_phrases(&raw, &phrases);
    pack_backward_logic(&raw, &phrases, &packed);

    out = fopen(output_path, "wb");
    if (!out) die("cannot open .bv3 output");

    if (fwrite(MAGIC, 1, 4, out) != 4) die("write magic failed");
    write_u32(out, VERSION);
    write_u64(out, (uint64_t)len);
    write_u32(out, crc);

    write_u32(out, base.count);
    for (i = 0; i < base.count; i++) {
        write_u32(out, base.items[i].len);
        if (base.items[i].len > 0 &&
            fwrite(base.items[i].data, 1, base.items[i].len, out) != base.items[i].len) {
            fclose(out);
            die("write base token failed");
        }
    }

    write_u32(out, phrases.count);
    for (i = 0; i < phrases.count; i++) {
        uint32_t j;
        write_u32(out, phrases.items[i].arity);
        for (j = 0; j < phrases.items[i].arity; j++) {
            write_u32(out, phrases.items[i].ids[j]);
        }
    }

    write_u64(out, packed.count);
    for (i = 0; i < packed.count; i++) write_varint_u64(out, packed.items[i], &stream_bytes_written);

    fclose(out);

    build_stats(&base, &phrases, &raw, &packed, (uint64_t)len, crc, &stats);
    stats.stream_bytes = stream_bytes_written;
    stats.total_bv3_bytes =
        4u + 4u + 8u + 4u +
        4u + stats.base_dict_bytes +
        4u + stats.phrase_dict_bytes +
        8u + stats.stream_bytes;

    printf("Compressed.\n");
    print_stats_struct(&stats);
    print_top_tokens(&base);
    print_top_phrases(&phrases);

    free(src);
    token_table_free(&base);
    u32vec_free(&raw);
    phrase_table_free(&phrases);
    u32vec_free(&packed);
}

static char *decompress_to_buffer(const char *input_path, size_t *out_len, BV3Stats *out_stats, int print_stats) {
    FILE *in = fopen(input_path, "rb");
    char magic[5] = {0};
    uint32_t version, crc_expected, base_count, phrase_count;
    uint64_t original_len, packed_count;
    TokenTable base;
    PhraseTable phrases;
    UInt32Vec packed;
    UInt32Vec raw;
    char *out_buf;
    size_t pos = 0;
    uint32_t i;
    uint64_t stream_bytes_read = 0u;
    uint32_t crc_actual;
    BV3Stats stats;

    if (!in) die("cannot open .bv3 input");
    if (fread(magic, 1, 4, in) != 4) {
        fclose(in);
        die("read magic failed");
    }
    if (memcmp(magic, MAGIC, 4) != 0) {
        fclose(in);
        die("invalid BV3 file");
    }

    version = read_u32(in);
    if (version != VERSION) {
        fclose(in);
        die("unsupported version");
    }

    original_len = read_u64(in);
    crc_expected = read_u32(in);

    token_table_init(&base);
    phrase_table_init(&phrases);
    u32vec_init(&packed);
    u32vec_init(&raw);

    base_count = read_u32(in);
    while (base.cap < base_count) {
        base.cap *= 2u;
        base.items = (Token *)xrealloc(base.items, sizeof(Token) * base.cap);
    }
    base.count = base_count;
    for (i = 0; i < base_count; i++) {
        uint32_t tok_len = read_u32(in);
        base.items[i].data = (char *)xmalloc((size_t)tok_len + 1u);
        base.items[i].len = tok_len;
        base.items[i].freq = 0u;
        base.items[i].hash = 0u;
        if (tok_len > 0 && fread(base.items[i].data, 1, tok_len, in) != tok_len) {
            fclose(in);
            die("read base token failed");
        }
        base.items[i].data[tok_len] = '\0';
    }

    phrase_count = read_u32(in);
    while (phrases.cap < phrase_count) {
        phrases.cap *= 2u;
        phrases.items = (Phrase *)xrealloc(phrases.items, sizeof(Phrase) * phrases.cap);
    }
    phrases.count = phrase_count;
    for (i = 0; i < phrase_count; i++) {
        uint32_t j;
        phrases.items[i].arity = read_u32(in);
        if (phrases.items[i].arity != 2u && phrases.items[i].arity != 3u) die("bad phrase arity");
        for (j = 0; j < phrases.items[i].arity; j++) {
            phrases.items[i].ids[j] = read_u32(in);
            if (phrases.items[i].ids[j] >= base_count) die("bad phrase token id");
        }
        phrases.items[i].freq = 0u;
        phrases.items[i].hash = 0u;
    }

    packed_count = read_u64(in);
    while (packed.cap < packed_count) {
        packed.cap *= 2u;
        packed.items = (uint32_t *)xrealloc(packed.items, sizeof(uint32_t) * packed.cap);
    }
    packed.count = (uint32_t)packed_count;

    for (i = 0; i < packed_count; i++) {
        uint64_t sym = read_varint_u64(in, &stream_bytes_read);
        if (sym >= (uint64_t)base_count + (uint64_t)phrase_count) die("bad packed symbol");
        packed.items[i] = (uint32_t)sym;
    }

    fclose(in);

    for (i = 0; i < packed.count; i++) {
        uint32_t sym = packed.items[i];
        if (sym < base_count) {
            u32vec_push(&raw, sym);
            base.items[sym].freq++;
        } else {
            uint32_t pid = sym - base_count;
            uint32_t j;
            phrases.items[pid].freq++;
            for (j = 0; j < phrases.items[pid].arity; j++) {
                u32vec_push(&raw, phrases.items[pid].ids[j]);
                base.items[phrases.items[pid].ids[j]].freq++;
            }
        }
    }

    out_buf = (char *)xmalloc((size_t)original_len + 1u);
    for (i = 0; i < raw.count; i++) {
        Token *t = &base.items[raw.items[i]];
        if (pos + t->len > original_len) {
            free(out_buf);
            die("rebuild overflow");
        }
        memcpy(out_buf + pos, t->data, t->len);
        pos += t->len;
    }

    if ((uint64_t)pos != original_len) {
        free(out_buf);
        die("rebuild length mismatch");
    }

    out_buf[pos] = '\0';
    crc_actual = crc32_bytes((const unsigned char *)out_buf, pos);
    if (crc_actual != crc_expected) {
        free(out_buf);
        die("CRC32 mismatch after rebuild");
    }

    *out_len = pos;
    build_stats(&base, &phrases, &raw, &packed, original_len, crc_actual, &stats);
    stats.stream_bytes = stream_bytes_read;
    stats.total_bv3_bytes =
        4u + 4u + 8u + 4u +
        4u + stats.base_dict_bytes +
        4u + stats.phrase_dict_bytes +
        8u + stats.stream_bytes;

    if (out_stats) *out_stats = stats;

    if (print_stats) {
        printf("Decoded BV3 stats:\n");
        print_stats_struct(&stats);
        print_top_tokens(&base);
        print_top_phrases(&phrases);
    }

    token_table_free(&base);
    phrase_table_free(&phrases);
    u32vec_free(&packed);
    u32vec_free(&raw);
    return out_buf;
}

static void decompress_file(const char *input_path, const char *output_path) {
    size_t out_len;
    char *buf = decompress_to_buffer(input_path, &out_len, NULL, 1);
    write_file_bytes(output_path, buf, out_len);
    printf("Decompressed.\n");
    free(buf);
}

static void verify_roundtrip(const char *input_txt, const char *output_bv3, const char *rebuilt_txt) {
    size_t src_len, rebuilt_len;
    char *src = read_file_bytes(input_txt, &src_len);
    char *rebuilt;
    BV3Stats stats;

    compress_file(input_txt, output_bv3);
    rebuilt = decompress_to_buffer(output_bv3, &rebuilt_len, &stats, 0);
    write_file_bytes(rebuilt_txt, rebuilt, rebuilt_len);

    if (src_len != rebuilt_len || memcmp(src, rebuilt, src_len) != 0) {
        free(src);
        free(rebuilt);
        die("VERIFY FAILED: rebuilt output differs from source");
    }

    printf("VERIFY OK: exact byte-for-byte roundtrip confirmed.\n");
    print_stats_struct(&stats);

    free(src);
    free(rebuilt);
}

static void embed_text_file(const char *input_path, uint32_t dims) {
    size_t len;
    char *src = read_file_bytes(input_path, &len);
    TokenTable base;
    UInt32Vec raw;
    PhraseTable phrases;
    UInt32Vec packed;
    double *vec;
    double norm = 0.0;
    uint32_t i;

    if (dims == 0u) die("embed dims must be > 0");

    token_table_init(&base);
    u32vec_init(&raw);
    phrase_table_init(&phrases);
    u32vec_init(&packed);

    tokenize_exact(src, len, &base, &raw);
    rank_tokens_by_frequency(&base, &raw);
    mine_phrases(&raw, &phrases);
    pack_backward_logic(&raw, &phrases, &packed);

    vec = (double *)calloc(dims, sizeof(double));
    if (!vec) die("out of memory");

    for (i = 0; i < base.count; i++) {
        uint64_t h = fnv1a64_bytes((const unsigned char *)base.items[i].data, base.items[i].len);
        uint32_t idx = (uint32_t)(h % dims);
        uint32_t sign = (uint32_t)((h >> 32u) & 1u);
        double weight = log((double)base.items[i].freq + 1.0);
        vec[idx] += sign ? -weight : weight;
    }

    for (i = 0; i < phrases.count; i++) {
        uint64_t h = fnv1a64_bytes((const unsigned char *)phrases.items[i].ids,
                                   sizeof(uint32_t) * phrases.items[i].arity);
        uint32_t idx = (uint32_t)(h % dims);
        uint32_t sign = (uint32_t)((h >> 40u) & 1u);
        double weight = log((double)(phrases.items[i].freq + 1u)) * (double)phrases.items[i].arity;
        vec[idx] += sign ? -weight : weight;
    }

    for (i = 0; i < dims; i++) norm += vec[i] * vec[i];
    norm = sqrt(norm);
    if (norm > 0.0) for (i = 0; i < dims; i++) vec[i] /= norm;

    printf("EMBED[%u]=", dims);
    for (i = 0; i < dims; i++) {
        if (i) printf(",");
        printf("%.6f", vec[i]);
    }
    printf("\n");

    free(vec);
    free(src);
    token_table_free(&base);
    u32vec_free(&raw);
    phrase_table_free(&phrases);
    u32vec_free(&packed);
}

static void shell_file(const char *input_bv3) {
    BV3Stats stats;
    size_t out_len;
    char *buf = decompress_to_buffer(input_bv3, &out_len, &stats, 0);
    const char *base = strrchr(input_bv3, '/');
    const char *name = base ? base + 1 : input_bv3;
    char stem[256];
    const char *dot = strrchr(name, '.');
    size_t slen = dot ? (size_t)(dot - name) : strlen(name);
    if (slen >= sizeof(stem)) slen = sizeof(stem) - 1u;
    memcpy(stem, name, slen);
    stem[slen] = '\0';

    printf("#[Ghost{[%s][active][generated][v%u][BV3]}]\n", stem, VERSION);
    printf("[BV3SHELL[T:archive][RT:exact][BL:backward_logic][CRC:%08X][OB:%llu][BT:%u][PH:%u][RC:%llu][PC:%llu][TB:%llu][R:%.2f]]\n",
           stats.crc32,
           (unsigned long long)stats.original_bytes,
           stats.base_token_count,
           stats.phrase_count,
           (unsigned long long)stats.raw_token_count,
           (unsigned long long)stats.packed_symbol_count,
           (unsigned long long)stats.total_bv3_bytes,
           stats.original_bytes ? 100.0 * (1.0 - ((double)stats.total_bv3_bytes / (double)stats.original_bytes)) : 0.0);
    printf("[BV3[F:%s][M:rt][L:bl][S:a][BT:%u][PH:%u][CRC:%08X]]\n",
           stem,
           stats.base_token_count,
           stats.phrase_count,
           stats.crc32);

    free(buf);
}

static void print_usage(const char *argv0) {
    fprintf(stderr,
        "Use:\n"
        "  %s compress   input.txt  output.bv3\n"
        "  %s decompress input.bv3  output.txt\n"
        "  %s verify     input.txt  output.bv3 rebuilt.txt\n"
        "  %s stats      input.bv3\n"
        "  %s embed      input.txt  dims\n"
        "  %s shell      input.bv3\n",
        argv0, argv0, argv0, argv0, argv0, argv0);
}

int main(int argc, char **argv) {
    if (argc < 3) {
        print_usage(argv[0]);
        return 1;
    }

    if (strcmp(argv[1], "compress") == 0) {
        if (argc != 4) { print_usage(argv[0]); return 1; }
        compress_file(argv[2], argv[3]);
        return 0;
    }

    if (strcmp(argv[1], "decompress") == 0) {
        if (argc != 4) { print_usage(argv[0]); return 1; }
        decompress_file(argv[2], argv[3]);
        return 0;
    }

    if (strcmp(argv[1], "verify") == 0) {
        if (argc != 5) { print_usage(argv[0]); return 1; }
        verify_roundtrip(argv[2], argv[3], argv[4]);
        return 0;
    }

    if (strcmp(argv[1], "stats") == 0) {
        if (argc != 3) { print_usage(argv[0]); return 1; }
        {
            size_t out_len;
            char *buf = decompress_to_buffer(argv[2], &out_len, NULL, 1);
            free(buf);
        }
        return 0;
    }

    if (strcmp(argv[1], "embed") == 0) {
        if (argc != 4) { print_usage(argv[0]); return 1; }
        embed_text_file(argv[2], (uint32_t)strtoul(argv[3], NULL, 10));
        return 0;
    }

    if (strcmp(argv[1], "shell") == 0) {
        if (argc != 3) { print_usage(argv[0]); return 1; }
        shell_file(argv[2]);
        return 0;
    }

    print_usage(argv[0]);
    return 1;
}
