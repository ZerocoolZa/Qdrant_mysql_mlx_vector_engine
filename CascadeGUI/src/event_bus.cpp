#include "event_bus.h"
#include <string.h>
#include <time.h>
#include <stdio.h>

static uint64_t now_ns(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ULL + (uint64_t)ts.tv_nsec;
}

void event_bus_init(EventBus *bus) {
    memset(bus, 0, sizeof(*bus));
    pthread_mutex_init(&bus->lock, NULL);
    bus->next_id = 1;
}

void event_bus_publish(EventBus *bus, CascadeChannel ch, CascadeEventLevel lvl,
                       const char *source, const char *message) {
    pthread_mutex_lock(&bus->lock);
    if (bus->count >= CASCADE_EVENT_MAX) {
        bus->dropped_count++;
        uint32_t old = bus->tail;
        bus->tail = (bus->tail + 1) % CASCADE_EVENT_MAX;
        bus->count--;
    }
    uint32_t idx = bus->head;
    CascadeEvent *ev = &bus->events[idx];
    ev->id = bus->next_id++;
    ev->timestamp_ns = now_ns();
    ev->channel = ch;
    ev->level = lvl;
    ev->payload_int = 0;
    ev->payload_float = 0.0;
    strncpy(ev->source, source ? source : "", sizeof(ev->source) - 1);
    ev->source[sizeof(ev->source) - 1] = '\0';
    strncpy(ev->message, message ? message : "", sizeof(ev->message) - 1);
    ev->message[sizeof(ev->message) - 1] = '\0';
    bus->head = (bus->head + 1) % CASCADE_EVENT_MAX;
    bus->count++;
    for (uint32_t i = 0; i < bus->subscriber_count; i++) {
        if (bus->subscribers[i].active &&
            (bus->subscribers[i].channel_filter == ch ||
             bus->subscribers[i].channel_filter == CH_CHANNEL_COUNT)) {
            bus->subscribers[i].fn(ev, bus->subscribers[i].user_data);
        }
    }
    pthread_mutex_unlock(&bus->lock);
}

uint32_t event_bus_poll(EventBus *bus, CascadeEvent *out, uint32_t max_count) {
    pthread_mutex_lock(&bus->lock);
    uint32_t n = 0;
    uint32_t idx = bus->tail;
    while (n < max_count && n < bus->count) {
        out[n] = bus->events[idx];
        idx = (idx + 1) % CASCADE_EVENT_MAX;
        n++;
    }
    pthread_mutex_unlock(&bus->lock);
    return n;
}

int event_bus_subscribe(EventBus *bus, CascadeChannel filter, CascadeSubscriberFn fn, void *user_data) {
    pthread_mutex_lock(&bus->lock);
    if (bus->subscriber_count >= CASCADE_SUBSCRIBER_MAX) {
        pthread_mutex_unlock(&bus->lock);
        return -1;
    }
    int id = (int)bus->subscriber_count;
    bus->subscribers[id].fn = fn;
    bus->subscribers[id].user_data = user_data;
    bus->subscribers[id].channel_filter = filter;
    bus->subscribers[id].active = true;
    bus->subscriber_count++;
    pthread_mutex_unlock(&bus->lock);
    return id;
}

void event_bus_unsubscribe(EventBus *bus, int subscriber_id) {
    if (subscriber_id < 0 || subscriber_id >= (int)CASCADE_SUBSCRIBER_MAX) return;
    pthread_mutex_lock(&bus->lock);
    bus->subscribers[subscriber_id].active = false;
    pthread_mutex_unlock(&bus->lock);
}

void event_bus_clear(EventBus *bus) {
    pthread_mutex_lock(&bus->lock);
    bus->head = bus->tail = bus->count = 0;
    pthread_mutex_unlock(&bus->lock);
}

uint64_t event_bus_count(EventBus *bus) {
    pthread_mutex_lock(&bus->lock);
    uint64_t c = bus->count;
    pthread_mutex_unlock(&bus->lock);
    return c;
}

uint64_t event_bus_dropped(EventBus *bus) {
    pthread_mutex_lock(&bus->lock);
    uint64_t d = bus->dropped_count;
    pthread_mutex_unlock(&bus->lock);
    return d;
}

static const char *channel_names[CH_CHANNEL_COUNT] = {
    "SYSTEM", "AI", "GRAPH", "PROFILER", "MEMORY",
    "CONSOLE", "FILE", "NETWORK", "USER", "ERROR"
};

const char *channel_name(CascadeChannel ch) {
    if (ch < CH_CHANNEL_COUNT) return channel_names[ch];
    return "?";
}

static const char *level_names[5] = { "INFO", "WARN", "ERROR", "DEBUG", "TRACE" };

const char *level_name(CascadeEventLevel lvl) {
    if (lvl <= EV_TRACE) return level_names[lvl];
    return "?";
}

void level_color(CascadeEventLevel lvl, float *r, float *g, float *b, float *a) {
    *a = 1.0f;
    switch (lvl) {
        case EV_INFO:    *r = 0.4f; *g = 0.8f; *b = 0.4f; break;
        case EV_WARNING: *r = 0.9f; *g = 0.8f; *b = 0.2f; break;
        case EV_ERROR:   *r = 0.9f; *g = 0.3f; *b = 0.3f; break;
        case EV_DEBUG:   *r = 0.5f; *g = 0.6f; *b = 0.9f; break;
        case EV_TRACE:   *r = 0.5f; *g = 0.5f; *b = 0.5f; break;
        default:         *r = 0.8f; *g = 0.8f; *b = 0.8f; break;
    }
}
