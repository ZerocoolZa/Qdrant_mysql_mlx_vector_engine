/*
 * mac_server.c — Remote Desktop Server Engine for macOS
 * 
 * Single-file VBStyle-like architecture:
 *   Capture   — screen capture via CoreGraphics
 *   VidCodec  — video encoder (H264 / VP8 / Raw / JPEG)
 *   Network   — TCP server, sends frames, receives input
 *   Input     — mouse/keyboard injection via CGEventPost
 *   Main      — wires everything together, runs the loop
 *
 * Build: cc -o mac_server mac_server.c -framework CoreGraphics -framework CoreFoundation -framework ApplicationServices -framework ImageIO
 *        (add -lx264 -lvpx for those codecs)
 * Run:   ./mac_server [port] [codec]
 *        port default 29000, codec default raw (h264/vp8/raw/jpeg)
 *
 * No GUI. Just runs.
 */
//[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<warn>][@notes<Remote Desktop Server Engine for macOS. Screen capture via CoreGraphics, video encoding, TCP server, input injection. C file with no #[@...] identity headers. Uses printf-style logging. Multiple structs/functions in single file.>][@todos<Add #[@GHOST]/[@VBSTYLE] identity headers. Consider splitting into multiple files.>]}

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <pthread.h>
#include <signal.h>
#include <stdint.h>
#include <fcntl.h>
#include <time.h>
#include <ImageIO/ImageIO.h>
#include <mach/mach_time.h>

#include <ApplicationServices/ApplicationServices.h>
#include <CoreFoundation/CoreFoundation.h>
#include <dlfcn.h>

/* macOS 15 removed CGDisplayCreateImage from headers, but the symbol still exists in the dylib.
 * Load it dynamically via dlsym to bypass the availability check. */
typedef CGImageRef (*CGDisplayCreateImageFunc)(CGDirectDisplayID);
static CGDisplayCreateImageFunc _CGDisplayCreateImage = NULL;

static void LoadDeprecatedSymbols(void) {
    void *handle = dlopen("/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices", RTLD_LAZY);
    if (!handle) {
        handle = dlopen("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics", RTLD_LAZY);
    }
    if (handle) {
        _CGDisplayCreateImage = (CGDisplayCreateImageFunc)dlsym(handle, "CGDisplayCreateImage");
    }
    if (!_CGDisplayCreateImage) {
        _CGDisplayCreateImage = (CGDisplayCreateImageFunc)dlsym(RTLD_DEFAULT, "CGDisplayCreateImage");
    }
    if (!_CGDisplayCreateImage) {
        fprintf(stderr, "FATAL: CGDisplayCreateImage not found in any framework\n");
    }
}

/* ================================================================
 * CONSTANTS
 * ================================================================ */

#define DEFAULT_PORT        29000
#define RECV_BUF_SIZE       256
#define FPS_TARGET          30
#define FRAME_INTERVAL_US   (1000000 / FPS_TARGET)

#define CODEC_RAW           0
#define CODEC_JPEG          1
#define CODEC_H264          2
#define CODEC_VP8           3

#define MSG_VIDEO_FRAME     1
#define MSG_MOUSE_EVENT     2
#define MSG_KEYBOARD_EVENT  3
#define MSG_DISPLAY_INFO    4
#define MSG_SET_RESOLUTION  5
#define MSG_SET_QUALITY     6
#define MSG_SET_FPS         7
#define MSG_HEARTBEAT       8

#define HEARTBEAT_TIMEOUT_SEC  10
#define SEND_TIMEOUT_SEC       5

#define MOUSE_MOVE          0
#define MOUSE_LEFT_DOWN     1
#define MOUSE_LEFT_UP       2
#define MOUSE_RIGHT_DOWN    3
#define MOUSE_RIGHT_UP      4
#define MOUSE_SCROLL        5

#define KEY_DOWN            0
#define KEY_UP              1

static volatile int RUNNING = 1;

static void SignalHandler(int sig) {
    (void)sig;
    RUNNING = 0;
}

/* Write a 32-bit value in network byte order (big-endian) */
static void WriteBE32(uint8_t *buf, uint32_t val) {
    buf[0] = (val >> 24) & 0xFF;
    buf[1] = (val >> 16) & 0xFF;
    buf[2] = (val >> 8) & 0xFF;
    buf[3] = val & 0xFF;
}

/* Read a 32-bit value in network byte order */
static uint32_t ReadBE32(const uint8_t *buf) {
    return ((uint32_t)buf[0] << 24) | ((uint32_t)buf[1] << 16) |
           ((uint32_t)buf[2] << 8) | (uint32_t)buf[3];
}

/* ================================================================
 * CAPTURE CLASS — Screen capture via CoreGraphics
 * ================================================================ */

typedef struct Capture {
    int        width;
    int        height;
    int        scale;
    size_t     bufferSize;
    uint8_t   *frameBuffer;
    int        frameSize;
    int        hasNewFrame;
    int        framesDropped;
    pthread_mutex_t frameLock;
} Capture;

static int Capture_Init(Capture *self) {
    memset(self, 0, sizeof(Capture));
    pthread_mutex_init(&self->frameLock, NULL);
    
    CGDirectDisplayID displayID = CGMainDisplayID();
    
    /* CGDisplayPixelsWide/High return pixel dimensions (not logical).
     * No additional Retina multiplication needed. */
    self->width = (int)CGDisplayPixelsWide(displayID);
    self->height = (int)CGDisplayPixelsHigh(displayID);
    
    /* Detect Retina scale using the mode's pixel vs logical dimensions.
     * CGDisplayBounds can return pixel dimensions on some configurations,
     * so we use CGDisplayCopyDisplayMode for a reliable comparison. */
    CGDisplayModeRef mode = CGDisplayCopyDisplayMode(displayID);
    if (mode) {
        int pixelWidth = (int)CGDisplayModeGetPixelWidth(mode);
        int logicalWidth = (int)CGDisplayModeGetWidth(mode);
        if (logicalWidth > 0 && pixelWidth > logicalWidth) {
            self->scale = pixelWidth / logicalWidth;
        } else {
            self->scale = 1;
        }
        CGDisplayModeRelease(mode);
    } else {
        self->scale = 1;
    }
    if (self->scale < 1) self->scale = 1;
    
    /* Allocate buffer based on actual display size (handles 4K/5K/8K).
     * Use size_t to avoid integer overflow on large displays. */
    self->bufferSize = (size_t)self->width * (size_t)self->height * 4;
    self->frameBuffer = (uint8_t *)malloc(self->bufferSize);
    if (!self->frameBuffer) {
        fprintf(stderr, "[Capture] Failed to allocate %zu bytes for frame buffer\n", self->bufferSize);
        return -1;
    }
    
    fprintf(stderr, "[Capture] Display: %dx%d scale=%d bufferSize=%zu\n",
            self->width, self->height, self->scale, self->bufferSize);
    return 0;
}

static int Capture_GrabFrame(Capture *self) {
    CGDirectDisplayID displayID = CGMainDisplayID();
    
    CGImageRef image = _CGDisplayCreateImage(displayID);
    
    if (!image) {
        return -1;
    }
    
    CGDataProviderRef provider = CGImageGetDataProvider(image);
    CFDataRef dataRef = CGDataProviderCopyData(provider);
    
    if (!dataRef) {
        CGImageRelease(image);
        return -1;
    }
    
    const uint8_t *data = CFDataGetBytePtr(dataRef);
    size_t dataLength = CFDataGetLength(dataRef);
    
    pthread_mutex_lock(&self->frameLock);
    
    /* Frame dropping: if previous frame wasn't consumed, drop it */
    if (self->hasNewFrame) {
        self->framesDropped++;
        pthread_mutex_unlock(&self->frameLock);
        CFRelease(dataRef);
        CGImageRelease(image);
        return 0;
    }
    
    /* Copy BGRA data into our dynamically-sized buffer */
    int copySize = (int)dataLength;
    if ((size_t)copySize > self->bufferSize) copySize = (int)self->bufferSize;
    memcpy(self->frameBuffer, data, copySize);
    self->frameSize = copySize;
    self->hasNewFrame = 1;
    
    pthread_mutex_unlock(&self->frameLock);
    
    CFRelease(dataRef);
    CGImageRelease(image);
    
    return 0;
}

static int Capture_GetFrame(Capture *self, uint8_t *outBuf, int maxBuf) {
    pthread_mutex_lock(&self->frameLock);
    
    if (!self->hasNewFrame || self->frameSize <= 0) {
        pthread_mutex_unlock(&self->frameLock);
        return -1;
    }
    
    int copySize = self->frameSize;
    if (copySize > maxBuf) copySize = maxBuf;
    memcpy(outBuf, self->frameBuffer, copySize);
    self->hasNewFrame = 0;
    
    pthread_mutex_unlock(&self->frameLock);
    return copySize;
}

static void Capture_Cleanup(Capture *self) {
    pthread_mutex_destroy(&self->frameLock);
    if (self->frameBuffer) {
        free(self->frameBuffer);
        self->frameBuffer = NULL;
    }
}

/* ================================================================
 * VIDCODEC CLASS — Video encoder with 4 codec variants
 * ================================================================ */

typedef struct VidCodec {
    int    codecType;
    int    width;
    int    height;
    int    quality;
    int    fps;
    
    /* JPEG state — cached objects reused across frames */
    int             jpegInitialized;
    CGColorSpaceRef jpegColorSpace;
    CFDictionaryRef     jpegProps;
    CFMutableDataRef jpegData;
    
    /* H264 state (placeholder — link -lx264 to enable) */
    void  *h264Encoder;
    
    /* VP8 state (placeholder — link -lvpx to enable) */
    void  *vp8Encoder;
    
    pthread_mutex_t codecLock;
} VidCodec;

static int VidCodec_Init(VidCodec *self, int codecType, int width, int height) {
    memset(self, 0, sizeof(VidCodec));
    self->codecType = codecType;
    self->width = width;
    self->height = height;
    self->quality = 80;
    
    switch (codecType) {
        case CODEC_RAW:
            fprintf(stderr, "[VidCodec] Raw frames (no compression)\n");
            break;
        case CODEC_JPEG:
            fprintf(stderr, "[VidCodec] JPEG compression, quality=%d\n", self->quality);
            self->jpegInitialized = 1;
            /* Cache reusable objects */
            self->jpegColorSpace = CGColorSpaceCreateDeviceRGB();
            self->jpegData = CFDataCreateMutable(NULL, 0);
            float quality = self->quality / 100.0f;
            CFNumberRef qualityVal = CFNumberCreate(NULL, kCFNumberFloat32Type, &quality);
            self->jpegProps = CFDictionaryCreateMutable(NULL, 0,
                                                        &kCFTypeDictionaryKeyCallBacks, &kCFTypeDictionaryValueCallBacks);
            CFDictionarySetValue((CFMutableDictionaryRef)self->jpegProps,
                                 kCGImageDestinationLossyCompressionQuality, qualityVal);
            CFRelease(qualityVal);
            pthread_mutex_init(&self->codecLock, NULL);
            break;
        case CODEC_H264:
            fprintf(stderr, "[VidCodec] H264 (requires libx264 — not yet linked)\n");
            /* TODO: x264_encoder_open */
            return -1;
        case CODEC_VP8:
            fprintf(stderr, "[VidCodec] VP8 (requires libvpx — not yet linked)\n");
            /* TODO: vpx_codec_enc_init */
            return -1;
        default:
            fprintf(stderr, "[VidCodec] Unknown codec type %d\n", codecType);
            return -1;
    }
    
    return 0;
}

/* RAW codec: just copy the data */
static int VidCodec_EncodeRaw(VidCodec *self, const uint8_t *raw, int rawSize, uint8_t *out, int outMax) {
    (void)self;
    if (rawSize > outMax) return -1;
    memcpy(out, raw, rawSize);
    return rawSize;
}

/* JPEG codec: compress using ImageIO with cached objects */
static int VidCodec_EncodeJPEG(VidCodec *self, const uint8_t *raw, int rawSize, uint8_t *out, int outMax) {
    size_t expectedSize = (size_t)self->width * (size_t)self->height * 4;
    if ((size_t)rawSize < expectedSize) {
        fprintf(stderr, "[VidCodec] JPEG: rawSize %d < expected %zu\n", rawSize, expectedSize);
        return -1;
    }
    
    pthread_mutex_lock(&self->codecLock);
    
    /* Create CGImage from raw BGRA data (provider must be created per-frame,
     * but colorSpace and props are cached) */
    CGDataProviderRef provider = CGDataProviderCreateWithData(NULL, raw, (size_t)expectedSize, NULL);
    if (!provider) { pthread_mutex_unlock(&self->codecLock); return -1; }
    
    CGImageRef image = CGImageCreate(
        self->width, self->height,
        8, 32, self->width * 4,
        self->jpegColorSpace,
        kCGImageAlphaPremultipliedFirst | kCGBitmapByteOrder32Little,
        provider, NULL, 0, kCGRenderingIntentDefault
    );
    
    CGDataProviderRelease(provider);
    
    if (!image) { pthread_mutex_unlock(&self->codecLock); return -1; }
    
    /* Reuse cached mutable data — reset it for this frame */
    CFDataSetLength(self->jpegData, 0);
    CGImageDestinationRef dst = CGImageDestinationCreateWithData(self->jpegData, CFSTR("public.jpeg"), 1, NULL);
    
    if (!dst) {
        CGImageRelease(image);
        pthread_mutex_unlock(&self->codecLock);
        return -1;
    }
    
    CGImageDestinationAddImage(dst, image, self->jpegProps);
    if (!CGImageDestinationFinalize(dst)) {
        fprintf(stderr, "[VidCodec] JPEG: CGImageDestinationFinalize failed\n");
        CFRelease(dst);
        CGImageRelease(image);
        pthread_mutex_unlock(&self->codecLock);
        return -1;
    }
    
    int encodedSize = (int)CFDataGetLength(self->jpegData);
    if (encodedSize > outMax) encodedSize = outMax;
    memcpy(out, CFDataGetBytePtr(self->jpegData), encodedSize);
    
    CFRelease(dst);
    CGImageRelease(image);
    
    pthread_mutex_unlock(&self->codecLock);
    return encodedSize;
}

static int VidCodec_Encode(VidCodec *self, const uint8_t *raw, int rawSize, uint8_t *out, int outMax) {
    switch (self->codecType) {
        case CODEC_RAW:
            return VidCodec_EncodeRaw(self, raw, rawSize, out, outMax);
        case CODEC_JPEG:
            return VidCodec_EncodeJPEG(self, raw, rawSize, out, outMax);
        case CODEC_H264:
            /* TODO: x264_encoder_encode(self->h264Encoder, ...) */
            fprintf(stderr, "[VidCodec] H264 not yet implemented, falling back to raw\n");
            return VidCodec_EncodeRaw(self, raw, rawSize, out, outMax);
        case CODEC_VP8:
            /* TODO: vpx_codec_encode(self->vp8Encoder, ...) */
            fprintf(stderr, "[VidCodec] VP8 not yet implemented, falling back to raw\n");
            return VidCodec_EncodeRaw(self, raw, rawSize, out, outMax);
        default:
            return -1;
    }
}

static void VidCodec_Cleanup(VidCodec *self) {
    if (self->jpegColorSpace) CGColorSpaceRelease(self->jpegColorSpace);
    if (self->jpegProps) CFRelease(self->jpegProps);
    if (self->jpegData) CFRelease(self->jpegData);
    if (self->jpegInitialized) pthread_mutex_destroy(&self->codecLock);
    /* TODO: free h264/vp8 encoders */
}

/* ================================================================
 * NETWORK HELPERS — Robust TCP send/recv (handles partial reads)
 * ================================================================ */

static int SendAll(int fd, const uint8_t *buf, int len, int flags) {
    int sent = 0;
    while (sent < len) {
        int n = send(fd, buf + sent, len - sent, flags);
        if (n < 0) {
            if (errno == EAGAIN || errno == EWOULDBLOCK) {
                usleep(1000);
                continue;
            }
            return -1;
        }
        if (n == 0) return -1;
        sent += n;
    }
    return sent;
}

static int RecvAll(int fd, uint8_t *buf, int len, int flags) {
    int received = 0;
    while (received < len) {
        int n = recv(fd, buf + received, len - received, flags);
        if (n < 0) {
            if (errno == EAGAIN || errno == EWOULDBLOCK) {
                if (received > 0) continue;
                return -1;
            }
            return -1;
        }
        if (n == 0) return -1;
        received += n;
    }
    return received;
}

/* ================================================================
 * NETWORK CLASS — TCP server, frame send, input recv
 * ================================================================ */

typedef struct Network {
    int    serverFd;
    int    clientFd;
    int    port;
    struct sockaddr_in addr;
} Network;

static int Network_Init(Network *self, int port) {
    memset(self, 0, sizeof(Network));
    self->port = port;
    self->clientFd = -1;
    
    self->serverFd = socket(AF_INET, SOCK_STREAM, 0);
    if (self->serverFd < 0) {
        perror("[Network] socket");
        return -1;
    }
    
    int opt = 1;
    setsockopt(self->serverFd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));
    
    /* Prevent SIGPIPE when sending to a disconnected client */
    setsockopt(self->serverFd, SOL_SOCKET, SO_NOSIGPIPE, &opt, sizeof(opt));
    
    self->addr.sin_family = AF_INET;
    self->addr.sin_addr.s_addr = INADDR_ANY;
    self->addr.sin_port = htons(port);
    
    if (bind(self->serverFd, (struct sockaddr *)&self->addr, sizeof(self->addr)) < 0) {
        perror("[Network] bind");
        return -1;
    }
    
    if (listen(self->serverFd, 1) < 0) {
        perror("[Network] listen");
        return -1;
    }
    
    fprintf(stderr, "[Network] Listening on port %d\n", port);
    return 0;
}

static int Network_WaitClient(Network *self) {
    fprintf(stderr, "[Network] Waiting for client...\n");
    
    struct sockaddr_in clientAddr;
    socklen_t addrLen = sizeof(clientAddr);
    self->clientFd = accept(self->serverFd, (struct sockaddr *)&clientAddr, &addrLen);
    
    if (self->clientFd < 0) {
        perror("[Network] accept");
        return -1;
    }
    
    /* Set non-blocking for input recv */
    int flags = fcntl(self->clientFd, F_GETFL, 0);
    fcntl(self->clientFd, F_SETFL, flags | O_NONBLOCK);
    
    /* Prevent SIGPIPE on client socket too */
    int opt = 1;
    setsockopt(self->clientFd, SOL_SOCKET, SO_NOSIGPIPE, &opt, sizeof(opt));
    
    /* Set send timeout so SendAll doesn't block forever on stalled client */
    struct timeval tv;
    tv.tv_sec = SEND_TIMEOUT_SEC;
    tv.tv_usec = 0;
    setsockopt(self->clientFd, SOL_SOCKET, SO_SNDTIMEO, &tv, sizeof(tv));
    setsockopt(self->clientFd, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
    
    char ip[INET_ADDRSTRLEN];
    inet_ntop(AF_INET, &clientAddr.sin_addr, ip, sizeof(ip));
    fprintf(stderr, "[Network] Client connected: %s\n", ip);
    
    return 0;
}

/* Send a complete message: [4B type][4B len][payload] */
static int Network_SendMsg(Network *self, int msgType, const uint8_t *payload, int payloadLen) {
    if (self->clientFd < 0) return -1;
    
    uint8_t header[8];
    WriteBE32(header, (uint32_t)msgType);
    WriteBE32(header + 4, (uint32_t)payloadLen);
    
    if (SendAll(self->clientFd, header, 8, 0) < 0) return -1;
    if (payloadLen > 0) {
        if (SendAll(self->clientFd, payload, payloadLen, 0) < 0) return -1;
    }
    return 0;
}

/* Try to receive input (non-blocking). Returns msg type or -1 if no data. */
static int Network_RecvMsg(Network *self, uint8_t *outBuf, int maxBuf, int *outLen) {
    if (self->clientFd < 0) return -1;
    
    uint8_t header[8];
    int n = recv(self->clientFd, header, 8, MSG_DONTWAIT);
    if (n < 0) {
        if (errno == EAGAIN || errno == EWOULDBLOCK) return -1;  /* no data yet */
        fprintf(stderr, "[Network] recv header error: %s\n", strerror(errno));
        return -2;  /* real error or disconnect */
    }
    if (n == 0) return -2;  /* peer closed */
    if (n < 8) {
        /* Partial header — read remaining bytes (blocking) */
        int remaining = 8 - n;
        int r = RecvAll(self->clientFd, header + n, remaining, 0);
        if (r < 0) return -2;
    }
    
    uint32_t msgType = ReadBE32(header);
    uint32_t payloadLen = ReadBE32(header + 4);
    
    /* Sanity check: reject absurd payload sizes from client */
    if (payloadLen > 65536) {
        fprintf(stderr, "[Network] Rejecting oversized payload: %u\n", payloadLen);
        /* Drain the payload from the socket to avoid protocol desync */
        uint8_t drainBuf[4096];
        while (payloadLen > 0) {
            int toRead = (payloadLen > sizeof(drainBuf)) ? (int)sizeof(drainBuf) : (int)payloadLen;
            int r = RecvAll(self->clientFd, drainBuf, toRead, 0);
            if (r < 0) break;
            payloadLen -= (uint32_t)r;
        }
        return -2;
    }
    if (payloadLen > (uint32_t)maxBuf) {
        /* Truncate but drain the excess to keep protocol aligned */
        uint32_t excess = payloadLen - (uint32_t)maxBuf;
        uint8_t drainBuf[4096];
        while (excess > 0) {
            int toRead = (excess > sizeof(drainBuf)) ? (int)sizeof(drainBuf) : (int)excess;
            int r = RecvAll(self->clientFd, drainBuf, toRead, 0);
            if (r < 0) return -2;
            excess -= (uint32_t)r;
        }
        payloadLen = (uint32_t)maxBuf;
    }
    
    if (payloadLen > 0) {
        int r = RecvAll(self->clientFd, outBuf, (int)payloadLen, 0);
        if (r < 0) return -2;
        *outLen = r;
    } else {
        *outLen = 0;
    }
    
    return (int)msgType;
}

static void Network_Close(Network *self) {
    if (self->clientFd >= 0) close(self->clientFd);
    if (self->serverFd >= 0) close(self->serverFd);
}

/* ================================================================
 * INPUT CLASS — Mouse/keyboard injection via CGEventPost
 * ================================================================ */

typedef struct Input {
    int    screenWidth;
    int    screenHeight;
} Input;

static int Input_Init(Input *self, int screenWidth, int screenHeight) {
    memset(self, 0, sizeof(Input));
    self->screenWidth = screenWidth;
    self->screenHeight = screenHeight;
    fprintf(stderr, "[Input] Ready (screen %dx%d)\n", screenWidth, screenHeight);
    return 0;
}

static int Input_HandleMouseEvent(Input *self, const uint8_t *data, int len) {
    if (len < 6) return -1;
    
    int eventType = data[0];
    int x = (data[1] << 8) | data[2];
    int y = (data[3] << 8) | data[4];
    int buttonMask = data[5];
    
    /* Clamp client coordinates to valid server pixel range */
    if (self->screenWidth > 0 && self->screenHeight > 0) {
        if (x < 0) x = 0;
        if (y < 0) y = 0;
        if (x > self->screenWidth) x = self->screenWidth;
        if (y > self->screenHeight) y = self->screenHeight;
    }
    
    CGPoint point = CGPointMake(x, y);
    
    switch (eventType) {
        case MOUSE_MOVE: {
            CGEventRef event = CGEventCreateMouseEvent(NULL, kCGEventMouseMoved, point, kCGMouseButtonLeft);
            if (event) {
                CGEventPost(kCGHIDEventTap, event);
                CFRelease(event);
            }
            break;
        }
        case MOUSE_LEFT_DOWN: {
            CGEventRef event = CGEventCreateMouseEvent(NULL, kCGEventLeftMouseDown, point, kCGMouseButtonLeft);
            if (event) {
                CGEventPost(kCGHIDEventTap, event);
                CFRelease(event);
            }
            break;
        }
        case MOUSE_LEFT_UP: {
            CGEventRef event = CGEventCreateMouseEvent(NULL, kCGEventLeftMouseUp, point, kCGMouseButtonLeft);
            if (event) {
                CGEventPost(kCGHIDEventTap, event);
                CFRelease(event);
            }
            break;
        }
        case MOUSE_RIGHT_DOWN: {
            CGEventRef event = CGEventCreateMouseEvent(NULL, kCGEventRightMouseDown, point, kCGMouseButtonRight);
            if (event) {
                CGEventPost(kCGHIDEventTap, event);
                CFRelease(event);
            }
            break;
        }
        case MOUSE_RIGHT_UP: {
            CGEventRef event = CGEventCreateMouseEvent(NULL, kCGEventRightMouseUp, point, kCGMouseButtonRight);
            if (event) {
                CGEventPost(kCGHIDEventTap, event);
                CFRelease(event);
            }
            break;
        }
        case MOUSE_SCROLL: {
            if (len < 8) return -1;
            int16_t scrollY = (int16_t)((data[6] << 8) | data[7]);
            int32_t delta = (scrollY > 0) ? -1 : (scrollY < 0) ? 1 : 0;
            CGEventRef event = CGEventCreateScrollWheelEvent(NULL, kCGScrollEventUnitLine, 1, delta);
            if (event) {
                CGEventPost(kCGHIDEventTap, event);
                CFRelease(event);
            }
            break;
        }
        default:
            return -1;
    }
    
    (void)buttonMask;
    return 0;
}

static int Input_HandleKeyboardEvent(Input *self, const uint8_t *data, int len) {
    if (len < 4) return -1;
    (void)self;
    
    int eventType = data[0];
    int keycode = (data[1] << 8) | data[2];
    int modifiers = data[3];
    
    CGEventRef event = CGEventCreateKeyboardEvent(NULL, (CGKeyCode)keycode, eventType == KEY_DOWN);
    if (event) {
        CGEventFlags flags = 0;
        if (modifiers & 0x01) flags |= kCGEventFlagMaskShift;
        if (modifiers & 0x02) flags |= kCGEventFlagMaskControl;
        if (modifiers & 0x04) flags |= kCGEventFlagMaskAlternate;
        if (modifiers & 0x08) flags |= kCGEventFlagMaskCommand;
        CGEventSetFlags(event, flags);
        CGEventPost(kCGHIDEventTap, event);
        CFRelease(event);
    }
    
    return 0;
}

static void Input_Cleanup(Input *self) {
    (void)self;
}

/* ================================================================
 * PERMISSIONS — Check Accessibility and Screen Recording
 * ================================================================ */

static int CheckPermissions(void) {
    int ok = 1;
    
    /* Check Accessibility (needed for CGEventPost input injection) */
    if (!AXIsProcessTrusted()) {
        fprintf(stderr, "[Permissions] Accessibility NOT granted — input will fail\n");
        ok = 0;
    } else {
        fprintf(stderr, "[Permissions] Accessibility: OK\n");
    }
    
    /* Check Screen Recording by attempting a capture */
    CGDirectDisplayID displayID = CGMainDisplayID();
    CGImageRef testImage = _CGDisplayCreateImage ? _CGDisplayCreateImage(displayID) : NULL;
    if (!testImage) {
        fprintf(stderr, "[Permissions] Screen Recording NOT granted — capture will fail\n");
        ok = 0;
    } else {
        fprintf(stderr, "[Permissions] Screen Recording: OK\n");
        CGImageRelease(testImage);
    }
    
    return ok;
}

/* ================================================================
 * MAIN — Wire everything together and run the loop
 * ================================================================ */

int main(int argc, char *argv[]) {
    int port = DEFAULT_PORT;
    int codecType = CODEC_RAW;
    
    if (argc >= 2) port = atoi(argv[1]);
    if (argc >= 3) {
        if (strcmp(argv[2], "raw") == 0) codecType = CODEC_RAW;
        else if (strcmp(argv[2], "jpeg") == 0) codecType = CODEC_JPEG;
        else if (strcmp(argv[2], "h264") == 0) codecType = CODEC_H264;
        else if (strcmp(argv[2], "vp8") == 0) codecType = CODEC_VP8;
        else {
            fprintf(stderr, "Unknown codec: %s (use: raw, jpeg, h264, vp8)\n", argv[2]);
            return 1;
        }
    }
    
    signal(SIGINT, SignalHandler);
    signal(SIGTERM, SignalHandler);
    signal(SIGPIPE, SIG_IGN);  /* Don't crash on send to closed socket */
    
    LoadDeprecatedSymbols();
    if (!_CGDisplayCreateImage) return 1;
    
    if (!CheckPermissions()) {
        fprintf(stderr, "WARNING: Missing permissions. Open System Settings > Privacy & Security\n");
        fprintf(stderr, "         Grant Accessibility and Screen Recording to this process\n");
    }
    
    fprintf(stderr, "=== Mac Remote Desktop Server ===\n");
    fprintf(stderr, "Port: %d, Codec: %s\n", port, 
            codecType == CODEC_RAW ? "raw" : 
            codecType == CODEC_JPEG ? "jpeg" : 
            codecType == CODEC_H264 ? "h264" : "vp8");
    
    /* Init classes with unified cleanup path */
    Capture cap;
    memset(&cap, 0, sizeof(cap));
    VidCodec codec;
    memset(&codec, 0, sizeof(codec));
    Network net;
    memset(&net, 0, sizeof(net));
    Input inp;
    memset(&inp, 0, sizeof(inp));
    
    if (Capture_Init(&cap) != 0) {
        fprintf(stderr, "Failed to init Capture\n");
        goto cleanup;
    }
    
    if (VidCodec_Init(&codec, codecType, cap.width, cap.height) != 0) {
        fprintf(stderr, "Falling back to raw codec\n");
        if (VidCodec_Init(&codec, CODEC_RAW, cap.width, cap.height) != 0) {
            fprintf(stderr, "Failed to init codec\n");
            goto cleanup_capture;
        }
    }
    
    if (Network_Init(&net, port) != 0) {
        fprintf(stderr, "Failed to init Network\n");
        goto cleanup_codec;
    }
    
    if (Network_WaitClient(&net) != 0) {
        fprintf(stderr, "Failed to accept client\n");
        goto cleanup_net;
    }
    
    Input_Init(&inp, cap.width, cap.height);
    goto streaming;

cleanup:
    goto done;
cleanup_capture:
    Capture_Cleanup(&cap);
    goto done;
cleanup_codec:
    VidCodec_Cleanup(&codec);
    goto cleanup_capture;
cleanup_net:
    Network_Close(&net);
    goto cleanup_codec;

streaming:
    ; /* empty statement — labels can't be followed by declarations in C11 */
    
    /* Send display info to client */
    uint8_t displayInfo[12];
    WriteBE32(displayInfo, (uint32_t)cap.width);
    WriteBE32(displayInfo + 4, (uint32_t)cap.height);
    WriteBE32(displayInfo + 8, (uint32_t)cap.scale);
    Network_SendMsg(&net, MSG_DISPLAY_INFO, displayInfo, 12);
    
    fprintf(stderr, "Sent display info: %dx%d scale=%d\n", cap.width, cap.height, cap.scale);
    fprintf(stderr, "Streaming started...\n");
    
    /* Allocate buffers based on actual capture size (handles 4K/5K/8K) */
    size_t rawBufSize = cap.bufferSize;
    size_t encodedBufSize = rawBufSize + 1024;
    uint8_t *rawFrame = (uint8_t *)malloc(rawBufSize);
    uint8_t *encodedFrame = (uint8_t *)malloc(encodedBufSize);
    uint8_t *framePayload = (uint8_t *)malloc(encodedBufSize + 12);
    uint8_t recvBuf[RECV_BUF_SIZE];
    
    if (!rawFrame || !encodedFrame || !framePayload) {
        fprintf(stderr, "Failed to allocate buffers (raw=%zu, enc=%zu)\n", rawBufSize, encodedBufSize);
        goto cleanup_net;
    }
    
    int frameCount = 0;
    time_t startTime = time(NULL);
    time_t lastHeartbeat = startTime;
    
    /* Send initial display info includes FPS and quality */
    uint8_t settingsInfo[8];
    WriteBE32(settingsInfo, (uint32_t)codec.quality);
    WriteBE32(settingsInfo + 4, (uint32_t)FPS_TARGET);
    Network_SendMsg(&net, MSG_SET_QUALITY, settingsInfo, 8);
    
    /* Main loop */
    while (RUNNING) {
        uint64_t frameStart = mach_absolute_time();
        
        /* 1. Capture frame */
        if (Capture_GrabFrame(&cap) != 0) {
            usleep(1000);
            continue;
        }
        
        int rawSize = Capture_GetFrame(&cap, rawFrame, (int)rawBufSize);
        if (rawSize <= 0) {
            usleep(1000);
            continue;
        }
        
        /* 2. Encode frame */
        int encodedSize = VidCodec_Encode(&codec, rawFrame, rawSize, encodedFrame, (int)encodedBufSize);
        if (encodedSize <= 0) {
            usleep(1000);
            continue;
        }
        
        /* 3. Send video frame with dimensions header */
        /* Payload: [4B width][4B height][4B encoded_len][encoded_data] */
        int totalPayload = 12 + encodedSize;
        WriteBE32(framePayload, (uint32_t)cap.width);
        WriteBE32(framePayload + 4, (uint32_t)cap.height);
        WriteBE32(framePayload + 8, (uint32_t)encodedSize);
        memcpy(framePayload + 12, encodedFrame, encodedSize);
        
        if (Network_SendMsg(&net, MSG_VIDEO_FRAME, framePayload, totalPayload) < 0) {
            fprintf(stderr, "[Main] Client disconnected\n");
            break;
        }
        
        /* 4. Check for input (non-blocking) */
        int recvLen = 0;
        int msgType = Network_RecvMsg(&net, recvBuf, RECV_BUF_SIZE, &recvLen);
        if (msgType == -2) {
            fprintf(stderr, "[Main] Client disconnected (recv error)\n");
            break;
        }
        if (msgType == MSG_MOUSE_EVENT) {
            Input_HandleMouseEvent(&inp, recvBuf, recvLen);
        } else if (msgType == MSG_KEYBOARD_EVENT) {
            Input_HandleKeyboardEvent(&inp, recvBuf, recvLen);
        } else if (msgType == MSG_SET_QUALITY) {
            if (recvLen >= 4) {
                int newQuality = (int)ReadBE32(recvBuf);
                if (newQuality >= 10 && newQuality <= 100) {
                    codec.quality = newQuality;
                    float q = newQuality / 100.0f;
                    CFNumberRef qv = CFNumberCreate(NULL, kCFNumberFloat32Type, &q);
                    CFDictionarySetValue((CFMutableDictionaryRef)codec.jpegProps,
                                         kCGImageDestinationLossyCompressionQuality, qv);
                    CFRelease(qv);
                    fprintf(stderr, "[Main] Quality set to %d\n", newQuality);
                }
            }
        } else if (msgType == MSG_SET_FPS) {
            if (recvLen >= 4) {
                int newFps = (int)ReadBE32(recvBuf);
                if (newFps >= 1 && newFps <= 60) {
                    codec.fps = newFps;
                    fprintf(stderr, "[Main] FPS set to %d\n", newFps);
                }
            }
        } else if (msgType == MSG_HEARTBEAT) {
            /* Client is alive — reset timeout */
            lastHeartbeat = time(NULL);
        }
        
        /* Check heartbeat timeout */
        if (time(NULL) - lastHeartbeat > HEARTBEAT_TIMEOUT_SEC) {
            fprintf(stderr, "[Main] Client timeout (no heartbeat for %d sec)\n", HEARTBEAT_TIMEOUT_SEC);
            break;
        }
        
        /* 5. Frame rate control — account for processing time */
        frameCount++;
        if (frameCount % 30 == 0) {
            time_t now = time(NULL);
            if (now > startTime) {
                int fps = frameCount / (int)(now - startTime);
                fprintf(stderr, "[Main] FPS: ~%d, frame size: %d bytes\n", fps, encodedSize);
            }
        }
        
        /* Calculate elapsed time since frame start, sleep only the remainder */
        uint64_t elapsed = mach_absolute_time() - frameStart;
        static double timebaseRatio = 0.0;
        if (timebaseRatio == 0.0) {
            mach_timebase_info_data_t tb;
            mach_timebase_info(&tb);
            timebaseRatio = (double)tb.numer / (double)tb.denom / 1000.0;  /* to microseconds */
        }
        int elapsedUs = (int)(elapsed * timebaseRatio);
        int sleepUs = FRAME_INTERVAL_US - elapsedUs;
        if (sleepUs > 0) usleep(sleepUs);
    }
    
    /* Cleanup */
    fprintf(stderr, "\nShutting down...\n");
    if (rawFrame) free(rawFrame);
    if (encodedFrame) free(encodedFrame);
    if (framePayload) free(framePayload);
    Input_Cleanup(&inp);
    Network_Close(&net);
    VidCodec_Cleanup(&codec);
    Capture_Cleanup(&cap);
    
done:
    fprintf(stderr, "Done.\n");
    return 0;
}
