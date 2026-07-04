#ifndef CASCADE_EVENT_BUS_H
#define CASCADE_EVENT_BUS_H

#include <stdint.h>
#include <stdbool.h>
#include <pthread.h>

#define CASCADE_EVENT_MAX 4096
#define CASCADE_CHANNEL_MAX 32
#define CASCADE_SUBSCRIBER_MAX 64

typedef enum {
    CH_SYSTEM = 0,
    CH_AI,
    CH_GRAPH,
    CH_PROFILER,
    CH_MEMORY,
    CH_CONSOLE,
    CH_FILE,
    CH_NETWORK,
    CH_USER,
    CH_ERROR,
    CH_CHANNEL_COUNT
} CascadeChannel;

typedef enum {
    EV_INFO = 0,
    EV_WARNING,
    EV_ERROR,
    EV_DEBUG,
    EV_TRACE
} CascadeEventLevel;

typedef struct {
    uint64_t id;
    uint64_t timestamp_ns;
    CascadeChannel channel;
    CascadeEventLevel level;
    char source[64];
    char message[1024];
    int32_t payload_int;
    double payload_float;
} CascadeEvent;

typedef void (*CascadeSubscriberFn)(const CascadeEvent *ev, void *user_data);

typedef struct {
    CascadeSubscriberFn fn;
    void *user_data;
    CascadeChannel channel_filter;
    bool active;
} CascadeSubscriber;

typedef struct {
    CascadeEvent events[CASCADE_EVENT_MAX];
    uint32_t head;
    uint32_t tail;
    uint32_t count;
    pthread_mutex_t lock;
    CascadeSubscriber subscribers[CASCADE_SUBSCRIBER_MAX];
    uint32_t subscriber_count;
    uint64_t next_id;
    uint64_t dropped_count;
} EventBus;

void event_bus_init(EventBus *bus);
void event_bus_publish(EventBus *bus, CascadeChannel ch, CascadeEventLevel lvl,
                       const char *source, const char *message);
uint32_t event_bus_poll(EventBus *bus, CascadeEvent *out, uint32_t max_count);
int event_bus_subscribe(EventBus *bus, CascadeChannel filter, CascadeSubscriberFn fn, void *user_data);
void event_bus_unsubscribe(EventBus *bus, int subscriber_id);
void event_bus_clear(EventBus *bus);
uint64_t event_bus_count(EventBus *bus);
uint64_t event_bus_dropped(EventBus *bus);

const char *channel_name(CascadeChannel ch);
const char *level_name(CascadeEventLevel lvl);
void level_color(CascadeEventLevel lvl, float *r, float *g, float *b, float *a);

#endif
