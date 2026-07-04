/*
 * MacControlPanel.m — Native macOS GUI (Objective-C + AppKit)
 * Gives the user real control over background daemons.
 * Compile: clang -framework Cocoa -o MacControlPanel MacControlPanel.m
 * Run:     ./MacControlPanel
 *
 * Architecture (4 classes):
 *   ServiceManager  — detection, registry, disable/enable/kill, status
 *   CleanerManager  — 0-byte file/folder cleaning
 *   GUIBuilder      — window, rows, bottom bar, toolbar construction
 *   AppDelegate     — thin orchestrator wiring it all together
 */

#import <Cocoa/Cocoa.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define MAX_SERVICES 200
#define MAX_LABEL 64
#define MAX_DESC 128
#define MAX_DOMAIN 128
#define MAX_KILL 64
#define MAX_CAT 32

/* Advisory levels */
#define ADV_UNKNOWN 0
#define ADV_SAFE 1
#define ADV_CAUTION 2
#define ADV_DANGEROUS 3

/* Service source */
#define SRC_BUILTIN 0
#define SRC_REGISTRY 1
#define SRC_DETECTED 2

typedef struct {
    char label[MAX_LABEL];
    char domain[MAX_DOMAIN];
    char desc[MAX_DESC];
    char killName[MAX_KILL];
    char category[MAX_CAT];
    int blocked;
    int running;
    int advisory;
    int source;
} Service;

/* Advisory database */
typedef struct {
    const char *keyword;
    int level;
    const char *desc;
    const char *category;
} AdvisoryEntry;

static AdvisoryEntry advisoryDB[] = {
    {"photolibraryd", ADV_SAFE, "Photo library indexing - RAM hog", "Photos"},
    {"photoanalysisd", ADV_SAFE, "Face/object analysis for Photos", "Photos"},
    {"PodcastsWidget", ADV_SAFE, "Podcasts widget", "Widgets"},
    {"StocksWidget", ADV_SAFE, "Stocks widget", "Widgets"},
    {"WeatherWidget", ADV_SAFE, "Weather widget", "Widgets"},
    {"CalendarWidget", ADV_SAFE, "Calendar widget", "Widgets"},
    {"widgetkit", ADV_SAFE, "Widget framework daemon", "Widgets"},
    {"amsengagementd", ADV_SAFE, "App Store engagement tracking", "App Store"},
    {"appstoreagent", ADV_SAFE, "App Store background agent", "App Store"},
    {"siriactionsd", ADV_SAFE, "Siri actions daemon", "Siri"},
    {"suggestionsd", ADV_SAFE, "Siri suggestions indexer", "Siri"},
    {"duetexpertd", ADV_SAFE, "Siri intelligence/suggestions", "Siri"},
    {"siriinferenced", ADV_SAFE, "Siri inference engine", "Siri"},
    {"sirittsd", ADV_SAFE, "Siri text-to-speech", "Siri"},
    {"corespeechd", ADV_SAFE, "Voice activation daemon", "Siri"},
    {"assistantd", ADV_SAFE, "Siri assistant daemon", "Siri"},
    {"routined", ADV_SAFE, "Location routines tracking", "Location"},
    {"ScreenTimeAgent", ADV_SAFE, "Screen Time monitoring", "System"},
    {"familycontrols", ADV_SAFE, "Parental controls daemon", "System"},
    {"AppleSpell", ADV_SAFE, "Spell checker daemon", "System"},
    {"chronod", ADV_SAFE, "Calendar/Reminders sync", "System"},
    {"sharingd", ADV_SAFE, "AirDrop/sharing services", "Sharing"},
    {"callservicesd", ADV_SAFE, "Continuity/phone call relay", "Continuity"},
    {"tipsd", ADV_SAFE, "Tips app daemon", "System"},
    {"NewsTag", ADV_SAFE, "News background fetcher", "News"},
    {"News", ADV_SAFE, "News app daemon", "News"},
    {"Stocks", ADV_SAFE, "Stocks app daemon", "Widgets"},
    {"Books", ADV_SAFE, "Books app daemon", "System"},
    {"Game", ADV_SAFE, "Game Center daemon", "System"},
    {"gamed", ADV_SAFE, "Game Center daemon", "System"},
    {"FolderActionsDispatcher", ADV_SAFE, "Folder actions daemon", "System"},
    {"ScriptMenuApp", ADV_SAFE, "Script menu daemon", "System"},
    {"SubmitDiagInfo", ADV_SAFE, "Diagnostic info submission", "System"},
    {"cloudtelemetry", ADV_SAFE, "Cloud telemetry tracking", "System"},
    {"AMPLibraryAgent", ADV_SAFE, "Apple Media library agent", "App Store"},
    {"AMPArtworkAgent", ADV_SAFE, "Apple Media artwork agent", "App Store"},
    {"SafariHistoryServiceAgent", ADV_SAFE, "Safari history sync agent", "Safari"},
    {"Safari.PasswordBreachAgent", ADV_SAFE, "Safari password breach agent", "Safari"},
    {"Safari.SafeBrowsing", ADV_SAFE, "Safari safe browsing daemon", "Safari"},
    {"spotlight", ADV_SAFE, "Spotlight indexer", "System"},
    {"corespotlightd", ADV_SAFE, "Core Spotlight daemon", "System"},
    {"nsattributedstringagent", ADV_SAFE, "Text rendering agent", "System"},
    {"helpd", ADV_SAFE, "Help viewer daemon", "System"},
    {"mediacontinuityd", ADV_SAFE, "Media continuity daemon", "Continuity"},
    {"mlhostd", ADV_SAFE, "Machine learning host daemon", "System"},
    {"peopled", ADV_SAFE, "Contacts background sync", "System"},
    {"facetimemessagestored", ADV_SAFE, "FaceTime message storage", "Continuity"},
    {"sidecar-display-agent", ADV_SAFE, "Sidecar display agent", "System"},
    {"AutoFillPanel", ADV_SAFE, "AutoFill panel daemon", "System"},
    {"unmountassistant", ADV_SAFE, "Unmount assistant agent", "System"},
    {"preference.displays.MirrorDisplays", ADV_SAFE, "Display mirror agent", "System"},
    {"contacts.donation-agent", ADV_SAFE, "Contacts donation agent", "System"},
    {"accessibility.heard", ADV_SAFE, "Accessibility hearing daemon", "System"},
    {"syncdefaultsd", ADV_SAFE, "iCloud default sync daemon", "iCloud"},
    {"DataDetectorsLocalSources", ADV_SAFE, "Data detectors daemon", "System"},
    {"identityservicesd", ADV_CAUTION, "iCloud identity/device trust", "iCloud"},
    {"fileproviderd", ADV_CAUTION, "iCloud Drive file provider", "iCloud"},
    {"networkserviceproxy", ADV_CAUTION, "Network service proxy", "System"},
    {"ManagedClientAgent", ADV_CAUTION, "MDM management agent", "System"},
    {"transparencyd", ADV_CAUTION, "App transparency tracking", "System"},
    {"suggestd", ADV_CAUTION, "Siri suggestion engine", "Siri"},
    {"loginwindow", ADV_DANGEROUS, "Login window - DO NOT DISABLE", "Critical"},
    {"WindowServer", ADV_DANGEROUS, "Display server - DO NOT DISABLE", "Critical"},
    {"Finder", ADV_DANGEROUS, "Finder - DO NOT DISABLE", "Critical"},
    {"Dock", ADV_DANGEROUS, "Dock - DO NOT DISABLE", "Critical"},
    {"SystemUIServer", ADV_DANGEROUS, "System UI server - DO NOT DISABLE", "Critical"},
    {"ControlCenter", ADV_DANGEROUS, "Control Center - DO NOT DISABLE", "Critical"},
    {"NotificationCenter", ADV_DANGEROUS, "Notification Center - DO NOT DISABLE", "Critical"},
    {"usernoted", ADV_DANGEROUS, "User notification daemon - DO NOT DISABLE", "Critical"},
    {"cfprefsd", ADV_DANGEROUS, "Preferences daemon - DO NOT DISABLE", "Critical"},
    {"pboard", ADV_DANGEROUS, "Pasteboard server - DO NOT DISABLE", "Critical"},
    {"lsd", ADV_DANGEROUS, "Launch services daemon - DO NOT DISABLE", "Critical"},
    {"securityd", ADV_DANGEROUS, "Security daemon - DO NOT DISABLE", "Critical"},
    {"trustd", ADV_DANGEROUS, "Trust evaluation daemon - DO NOT DISABLE", "Critical"},
    {"fontservicesd", ADV_DANGEROUS, "Font services daemon - DO NOT DISABLE", "Critical"},
    {"iconservicesd", ADV_DANGEROUS, "Icon services daemon - DO NOT DISABLE", "Critical"},
    {"coreaudio", ADV_DANGEROUS, "Core audio daemon - DO NOT DISABLE", "Critical"},
    {"bluetoothd", ADV_DANGEROUS, "Bluetooth daemon - DO NOT DISABLE", "Critical"},
    {NULL, 0, NULL, NULL}
};

static int findAdvisory(const char *domain, const char **outDesc, const char **outCat) {
    for (int i = 0; advisoryDB[i].keyword != NULL; i++) {
        if (strcasestr(domain, advisoryDB[i].keyword) != NULL) {
            if (outDesc) *outDesc = advisoryDB[i].desc;
            if (outCat) *outCat = advisoryDB[i].category;
            return advisoryDB[i].level;
        }
    }
    return ADV_UNKNOWN;
}

/* ============================================================
 * ServiceManager
 * Handles: service detection, persistent registry,
 *          disable/enable/kill, status refresh
 * ============================================================
 */
@interface ServiceManager : NSObject {
    Service services[MAX_SERVICES];
    int serviceCount;
    int uid;
    char disabledCache[8192];
    int disabledCacheValid;
    NSMutableDictionary *loadedRegistry;
}
- (id)init;
- (int)serviceCount;
- (Service *)services;
- (void)loadServices;
- (void)refreshStatusWithLabels:(NSMutableArray *)statusLabels
                       toggles:(NSMutableArray *)toggleButtons
                    advisories:(NSMutableArray *)advisoryLabels;
- (void)toggleServiceAtIndex:(int)idx;
- (void)disableAll;
- (void)enableAll;
- (NSString *)registryPath;
- (NSString *)osVersion;
- (int)builtinCount;
- (int)registryCount;
- (int)detectedCount;
@end

@implementation ServiceManager

- (id)init {
    self = [super init];
    if (self) {
        serviceCount = 0;
        uid = getuid();
        disabledCacheValid = 0;
        loadedRegistry = nil;
    }
    return self;
}

- (int)serviceCount { return serviceCount; }
- (Service *)services { return services; }

- (NSString *)registryPath {
    NSArray *dirs = NSSearchPathForDirectoriesInDomains(NSApplicationSupportDirectory, NSUserDomainMask, YES);
    NSString *baseDir = [dirs firstObject];
    NSString *appDir = [baseDir stringByAppendingPathComponent:@"MacControlPanel"];
    NSFileManager *fm = [NSFileManager defaultManager];
    [fm createDirectoryAtPath:appDir withIntermediateDirectories:YES attributes:nil error:nil];
    return [appDir stringByAppendingPathComponent:@"registry.plist"];
}

- (NSString *)osVersion {
    NSOperatingSystemVersion ver = [[NSProcessInfo processInfo] operatingSystemVersion];
    return [NSString stringWithFormat:@"%ld.%ld.%ld", (long)ver.majorVersion, (long)ver.minorVersion, (long)ver.patchVersion];
}

- (void)loadRegistry {
    loadedRegistry = [NSMutableDictionary dictionaryWithContentsOfFile:[self registryPath]];
    if (!loadedRegistry) {
        loadedRegistry = [[NSMutableDictionary alloc] init];
    }
}

- (void)saveRegistry {
    if (!loadedRegistry) return;
    [loadedRegistry writeToFile:[self registryPath] atomically:YES];
}

- (int)domainAlreadyAdded:(const char *)domain {
    for (int i = 0; i < serviceCount; i++) {
        if (strcmp(services[i].domain, domain) == 0) return 1;
    }
    return 0;
}

- (void)addService:(const char *)domain label:(const char *)label desc:(const char *)desc
               cat:(const char *)cat killName:(const char *)killName advisory:(int)advisory source:(int)source {
    if (serviceCount >= MAX_SERVICES) return;
    if ([self domainAlreadyAdded:domain]) return;

    strncpy(services[serviceCount].label, label, MAX_LABEL - 1);
    strncpy(services[serviceCount].domain, domain, MAX_DOMAIN - 1);
    strncpy(services[serviceCount].desc, desc, MAX_DESC - 1);
    strncpy(services[serviceCount].killName, killName, MAX_KILL - 1);
    strncpy(services[serviceCount].category, cat, MAX_CAT - 1);
    services[serviceCount].label[MAX_LABEL - 1] = '\0';
    services[serviceCount].domain[MAX_DOMAIN - 1] = '\0';
    services[serviceCount].desc[MAX_DESC - 1] = '\0';
    services[serviceCount].killName[MAX_KILL - 1] = '\0';
    services[serviceCount].category[MAX_CAT - 1] = '\0';
    services[serviceCount].blocked = 0;
    services[serviceCount].running = 0;
    services[serviceCount].advisory = advisory;
    services[serviceCount].source = source;
    serviceCount++;
}

- (void)loadServices {
    [self loadRegistry];
    NSString *osVer = [self osVersion];
    NSString *today = [NSDateFormatter localizedStringFromDate:[NSDate date]
                                                    dateStyle:NSDateFormatterShortStyle
                                                  timeStyle:NSDateFormatterNoStyle];

    char cmd[256];
    snprintf(cmd, sizeof(cmd), "launchctl print gui/%d 2>/dev/null", uid);
    FILE *fp = popen(cmd, "r");
    if (!fp) return;

    char liveDomains[MAX_SERVICES][MAX_DOMAIN];
    int liveCount = 0;
    char buf[1024];

    while (fgets(buf, sizeof(buf), fp) && liveCount < MAX_SERVICES) {
        char *p = buf;
        while (*p == ' ' || *p == '\t') p++;
        if (*p < '0' || *p > '9') {
            if (*p != '-') continue;
        }
        char *lineEnd = strchr(p, '\n');
        if (lineEnd) *lineEnd = '\0';
        while (*p && *p != ' ' && *p != '\t') p++;
        while (*p == ' ' || *p == '\t') p++;
        while (*p && *p != ' ' && *p != '\t') p++;
        while (*p == ' ' || *p == '\t') p++;
        if (!*p) continue;
        if (!strchr(p, '.')) continue;
        if (strstr(p, "xpc.")) continue;

        char *end = p + strlen(p) - 1;
        while (end > p && (*end == ' ' || *end == '\t')) *end-- = '\0';

        strncpy(liveDomains[liveCount], p, MAX_DOMAIN - 1);
        liveDomains[liveCount][MAX_DOMAIN - 1] = '\0';
        liveCount++;
    }
    pclose(fp);

    /* Phase 2: Match live domains against built-in advisory DB */
    for (int i = 0; i < liveCount && serviceCount < MAX_SERVICES; i++) {
        const char *domain = liveDomains[i];
        const char *advDesc = NULL;
        const char *advCat = NULL;
        int advLevel = findAdvisory(domain, &advDesc, &advCat);
        if (advLevel == ADV_UNKNOWN) continue;

        char *killName = strrchr(domain, '.');
        killName = killName ? killName + 1 : (char *)domain;
        [self addService:domain label:killName desc:(advDesc ?: "Known service")
                      cat:(advCat ?: "System") killName:killName advisory:advLevel source:SRC_BUILTIN];
    }

    /* Phase 3: Add registry entries not already added */
    for (NSString *regDomain in loadedRegistry) {
        if ([self domainAlreadyAdded:[regDomain UTF8String]]) continue;
        NSDictionary *entry = [loadedRegistry objectForKey:regDomain];
        const char *domain = [regDomain UTF8String];
        const char *desc = [[entry objectForKey:@"desc"] UTF8String] ?: "Previously detected service";
        const char *cat = [[entry objectForKey:@"category"] UTF8String] ?: "Detected";
        int advisory = [[entry objectForKey:@"advisory"] intValue];
        char *killName = strrchr(domain, '.');
        killName = killName ? killName + 1 : (char *)domain;
        [self addService:domain label:killName desc:desc cat:cat killName:killName advisory:advisory source:SRC_REGISTRY];
    }

    /* Phase 4: Add remaining live domains not in DB or registry */
    for (int i = 0; i < liveCount && serviceCount < MAX_SERVICES; i++) {
        const char *domain = liveDomains[i];
        if ([self domainAlreadyAdded:domain]) continue;
        if (strncmp(domain, "com.apple.", 10) == 0) continue;

        char *killName = strrchr(domain, '.');
        killName = killName ? killName + 1 : (char *)domain;
        [self addService:domain label:killName desc:"Newly detected launch agent"
                      cat:"Detected" killName:killName advisory:ADV_UNKNOWN source:SRC_DETECTED];

        [loadedRegistry setObject:[NSDictionary dictionaryWithObjectsAndKeys:
            [NSString stringWithUTF8String:"Newly detected launch agent"], @"desc",
            @"Detected", @"category",
            [NSNumber numberWithInt:ADV_UNKNOWN], @"advisory",
            today, @"firstSeen",
            today, @"lastSeen",
            osVer, @"osVersion",
            nil]
            forKey:[NSString stringWithUTF8String:domain]];
    }

    /* Phase 5: Update registry */
    for (int i = 0; i < liveCount; i++) {
        NSString *d = [NSString stringWithUTF8String:liveDomains[i]];
        NSMutableDictionary *entry = [[loadedRegistry objectForKey:d] mutableCopy];
        if (entry) {
            [entry setObject:today forKey:@"lastSeen"];
            [entry setObject:osVer forKey:@"osVersion"];
            [loadedRegistry setObject:entry forKey:d];
        } else {
            const char *advDesc = NULL;
            const char *advCat = NULL;
            int advLevel = findAdvisory(liveDomains[i], &advDesc, &advCat);
            if (advLevel != ADV_UNKNOWN) {
                [loadedRegistry setObject:[NSDictionary dictionaryWithObjectsAndKeys:
                    [NSString stringWithUTF8String:advDesc ?: "Known service"], @"desc",
                    [NSString stringWithUTF8String:advCat ?: "System"], @"category",
                    [NSNumber numberWithInt:advLevel], @"advisory",
                    today, @"firstSeen",
                    today, @"lastSeen",
                    osVer, @"osVersion",
                    nil]
                    forKey:d];
            }
        }
    }
    [self saveRegistry];
}

- (void)refreshDisabledCache {
    char cmd[256];
    snprintf(cmd, sizeof(cmd), "launchctl print-disabled gui/%d 2>/dev/null", uid);
    FILE *fp = popen(cmd, "r");
    if (!fp) {
        disabledCache[0] = '\0';
        disabledCacheValid = 0;
        return;
    }
    size_t total = fread(disabledCache, 1, sizeof(disabledCache) - 1, fp);
    disabledCache[total] = '\0';
    pclose(fp);
    disabledCacheValid = 1;
}

- (int)checkDisabled:(const char *)domain killName:(const char *)killName {
    if (!disabledCacheValid) [self refreshDisabledCache];
    const char *needles[2] = {domain, killName};
    for (int n = 0; n < 2; n++) {
        const char *cursor = disabledCache;
        while (cursor && *cursor) {
            const char *line = strstr(cursor, needles[n]);
            if (!line) break;
            const char *eol = strchr(line, '\n');
            size_t lineLen = eol ? (size_t)(eol - line) : strlen(line);
            if (memmem(line, lineLen, "=> disabled", 11) != NULL) return 1;
            cursor = eol ? eol + 1 : line + lineLen;
        }
    }
    return 0;
}

- (int)checkRunning:(const char *)killName {
    char cmd[128];
    snprintf(cmd, sizeof(cmd), "pgrep -x %s 2>/dev/null", killName);
    FILE *fp = popen(cmd, "r");
    if (!fp) return 0;
    char buf[32];
    int running = (fgets(buf, sizeof(buf), fp) != NULL);
    pclose(fp);
    return running;
}

- (void)disableService:(const char *)domain {
    char cmd[256];
    snprintf(cmd, sizeof(cmd), "launchctl disable gui/%d/%s 2>/dev/null", uid, domain);
    system(cmd);
    snprintf(cmd, sizeof(cmd), "launchctl bootout gui/%d/%s 2>/dev/null", uid, domain);
    system(cmd);
}

- (void)enableService:(const char *)domain {
    char cmd[256];
    snprintf(cmd, sizeof(cmd), "launchctl enable gui/%d/%s 2>/dev/null", uid, domain);
    system(cmd);
    snprintf(cmd, sizeof(cmd),
             "launchctl bootstrap gui/%d /System/Library/LaunchAgents/%s.plist 2>/dev/null",
             uid, domain);
    system(cmd);
}

- (void)killProcess:(const char *)name {
    char cmd[128];
    snprintf(cmd, sizeof(cmd), "killall -9 %s 2>/dev/null", name);
    system(cmd);
}

- (void)refreshStatusWithLabels:(NSMutableArray *)statusLabels
                       toggles:(NSMutableArray *)toggleButtons
                    advisories:(NSMutableArray *)advisoryLabels {
    disabledCacheValid = 0;
    [self refreshDisabledCache];
    for (int i = 0; i < serviceCount; i++) {
        services[i].blocked = [self checkDisabled:services[i].domain killName:services[i].killName];
        services[i].running = [self checkRunning:services[i].killName];

        NSTextField *statusLabel = [statusLabels objectAtIndex:i];
        NSButton *btn = [toggleButtons objectAtIndex:i];

        if (services[i].blocked) {
            [statusLabel setStringValue:@"BLOCKED"];
            [statusLabel setTextColor:[NSColor colorWithRed:1.0 green:0.27 blue:0.27 alpha:1.0]];
            [btn setTitle:@"Enable"];
        } else if (services[i].running) {
            [statusLabel setStringValue:@"RUNNING"];
            [statusLabel setTextColor:[NSColor colorWithRed:1.0 green:0.67 blue:0.0 alpha:1.0]];
            [btn setTitle:@"Disable"];
        } else {
            [statusLabel setStringValue:@"IDLE"];
            [statusLabel setTextColor:[NSColor colorWithRed:0.33 green:0.67 blue:0.33 alpha:1.0]];
            [btn setTitle:@"Disable"];
        }

        NSTextField *advLabel = [advisoryLabels objectAtIndex:i];
        switch (services[i].advisory) {
            case ADV_SAFE:
                [advLabel setStringValue:@"SAFE"];
                [advLabel setTextColor:[NSColor colorWithRed:0.33 green:0.67 blue:0.33 alpha:1.0]];
                break;
            case ADV_CAUTION:
                [advLabel setStringValue:@"CAUTION"];
                [advLabel setTextColor:[NSColor colorWithRed:1.0 green:0.67 blue:0.0 alpha:1.0]];
                break;
            case ADV_DANGEROUS:
                [advLabel setStringValue:@"DANGER"];
                [advLabel setTextColor:[NSColor colorWithRed:1.0 green:0.2 blue:0.2 alpha:1.0]];
                break;
            default:
                [advLabel setStringValue:@"?"];
                [advLabel setTextColor:[NSColor colorWithRed:0.5 green:0.5 blue:0.5 alpha:1.0]];
                break;
        }

        if (services[i].advisory == ADV_DANGEROUS) {
            [btn setEnabled:NO];
            [btn setTitle:@"LOCKED"];
        } else {
            [btn setEnabled:YES];
        }
    }
}

- (void)toggleServiceAtIndex:(int)idx {
    if (idx < 0 || idx >= serviceCount) return;
    Service *svc = &services[idx];
    if (svc->blocked) {
        [self enableService:svc->domain];
    } else {
        [self disableService:svc->domain];
        [self killProcess:svc->killName];
    }
}

- (void)disableAll {
    for (int i = 0; i < serviceCount; i++) {
        if (services[i].advisory == ADV_DANGEROUS) continue;
        [self disableService:services[i].domain];
        [self killProcess:services[i].killName];
    }
}

- (void)enableAll {
    for (int i = 0; i < serviceCount; i++) {
        [self enableService:services[i].domain];
    }
}

- (int)builtinCount {
    int c = 0;
    for (int i = 0; i < serviceCount; i++) if (services[i].source == SRC_BUILTIN) c++;
    return c;
}

- (int)registryCount {
    int c = 0;
    for (int i = 0; i < serviceCount; i++) if (services[i].source == SRC_REGISTRY) c++;
    return c;
}

- (int)detectedCount {
    int c = 0;
    for (int i = 0; i < serviceCount; i++) if (services[i].source == SRC_DETECTED) c++;
    return c;
}

@end

/* ============================================================
 * CleanerManager
 * Handles: 0-byte file and folder cleanup
 * ============================================================
 */
@interface CleanerManager : NSObject
- (void)runCleaner;
@end

@implementation CleanerManager

- (void)runCleaner {
    NSOpenPanel *panel = [NSOpenPanel openPanel];
    [panel setCanChooseFiles:NO];
    [panel setCanChooseDirectories:YES];
    [panel setAllowsMultipleSelection:NO];
    [panel setPrompt:@"Scan This Folder"];
    [panel setMessage:@"Select a folder to scan for 0-byte files and folders"];
    if ([panel runModal] != NSModalResponseOK) return;

    NSString *folderPath = [[panel URL] path];

    NSAlert *choice = [[NSAlert alloc] init];
    [choice setMessageText:@"What do you want to clean?"];
    [choice setInformativeText:[NSString stringWithFormat:@"Scanning: %@\n\nChoose what to find and delete:", folderPath]];
    [choice addButtonWithTitle:@"0-Byte Files Only"];
    [choice addButtonWithTitle:@"0-Byte Folders Only"];
    [choice addButtonWithTitle:@"Both Files + Folders"];
    [choice addButtonWithTitle:@"Cancel"];
    NSModalResponse resp = [choice runModal];
    if (resp == NSAlertThirdButtonReturn + 1) return;

    int doFiles = (resp == NSAlertFirstButtonReturn || resp == NSAlertThirdButtonReturn);
    int doFolders = (resp == NSAlertSecondButtonReturn || resp == NSAlertThirdButtonReturn);

    NSMutableArray *items = [[NSMutableArray alloc] init];
    char cmd[2048];
    char buf[4096];

    if (doFiles) {
        snprintf(cmd, sizeof(cmd), "find '%s' -type f -size 0 2>/dev/null", [folderPath UTF8String]);
        FILE *fp = popen(cmd, "r");
        if (fp) {
            while (fgets(buf, sizeof(buf), fp)) {
                size_t len = strlen(buf);
                if (len > 0 && buf[len - 1] == '\n') buf[len - 1] = '\0';
                if (len > 1) [items addObject:[NSString stringWithUTF8String:buf]];
            }
            pclose(fp);
        }
    }

    if (doFolders) {
        snprintf(cmd, sizeof(cmd), "find '%s' -type d -empty 2>/dev/null | sort -r", [folderPath UTF8String]);
        FILE *fp = popen(cmd, "r");
        if (fp) {
            while (fgets(buf, sizeof(buf), fp)) {
                size_t len = strlen(buf);
                if (len > 0 && buf[len - 1] == '\n') buf[len - 1] = '\0';
                if (len > 1 && strcmp(buf, [folderPath UTF8String]) != 0) {
                    [items addObject:[NSString stringWithUTF8String:buf]];
                }
            }
            pclose(fp);
        }
    }

    int count = (int)[items count];
    if (count == 0) {
        NSAlert *none = [[NSAlert alloc] init];
        [none setMessageText:@"Nothing to clean"];
        [none setInformativeText:[NSString stringWithFormat:@"Scanned: %@\nNo 0-byte files or empty folders found.", folderPath]];
        [none addButtonWithTitle:@"OK"];
        [none runModal];
        return;
    }

    NSMutableString *itemList = [NSMutableString string];
    int showCount = count > 50 ? 50 : count;
    for (int i = 0; i < showCount; i++) {
        [itemList appendFormat:@"%d. %@\n", i + 1, [items objectAtIndex:i]];
    }
    if (count > 50) {
        [itemList appendFormat:@"... and %d more\n", count - 50];
    }

    NSAlert *confirm = [[NSAlert alloc] init];
    [confirm setMessageText:[NSString stringWithFormat:@"Delete %d items?", count]];
    [confirm setInformativeText:[NSString stringWithFormat:@"Scanned: %@\n\nItems found:\n%@", folderPath, itemList]];
    [confirm addButtonWithTitle:@"Delete All"];
    [confirm addButtonWithTitle:@"Cancel"];
    if ([confirm runModal] != NSAlertFirstButtonReturn) return;

    int deleted = 0, failed = 0;
    NSFileManager *fm = [NSFileManager defaultManager];
    for (int i = 0; i < count; i++) {
        NSString *path = [items objectAtIndex:i];
        NSError *error = nil;
        if ([fm removeItemAtPath:path error:&error]) deleted++;
        else failed++;
    }

    NSAlert *result = [[NSAlert alloc] init];
    [result setMessageText:@"Cleanup Complete"];
    [result setInformativeText:[NSString stringWithFormat:@"Deleted: %d\nFailed: %d\nTotal found: %d\n\nScanned: %@", deleted, failed, count, folderPath]];
    [result addButtonWithTitle:@"OK"];
    [result runModal];
}

@end

/* ============================================================
 * GUIBuilder
 * Handles: window creation, row layout, bottom bar, toolbar
 * ============================================================
 */
@interface GUIBuilder : NSObject
+ (NSWindow *)buildWindowWithWidth:(CGFloat)w height:(CGFloat)h;
+ (NSScrollView *)buildScrollViewWithWidth:(CGFloat)w height:(CGFloat)h bottomHeight:(CGFloat)bh headerHeight:(CGFloat)hh;
+ (NSView *)buildHeaderBarWithWidth:(CGFloat)w height:(CGFloat)h;
+ (NSView *)buildBottomBarWithWidth:(CGFloat)w height:(CGFloat)h target:(id)target
                       disableSel:(SEL)ds enableSel:(SEL)es cleanSel:(SEL)cs refreshSel:(SEL)rs;
+ (NSToolbar *)buildToolbarWithDelegate:(id)delegate;
+ (NSMenu *)buildMenuBarWithRefreshTarget:(id)target refreshSel:(SEL)rs;
@end

@implementation GUIBuilder

+ (NSWindow *)buildWindowWithWidth:(CGFloat)w height:(CGFloat)h {
    NSRect screenRect = [[NSScreen mainScreen] frame];
    CGFloat cx = (screenRect.size.width - w) / 2;
    CGFloat cy = (screenRect.size.height - h) / 2;
    NSRect frame = NSMakeRect(cx, cy, w, h);
    NSUInteger style = NSWindowStyleMaskTitled | NSWindowStyleMaskClosable |
                       NSWindowStyleMaskMiniaturizable | NSWindowStyleMaskResizable;
    NSWindow *win = [[NSWindow alloc] initWithContentRect:frame
                                               styleMask:style
                                                 backing:NSBackingStoreBuffered
                                                   defer:NO];
    [win setTitle:@"Mac Control Panel - Take Back Your Machine"];
    [win setBackgroundColor:[NSColor colorWithRed:0.10 green:0.10 blue:0.18 alpha:1.0]];
    return win;
}

+ (NSScrollView *)buildScrollViewWithWidth:(CGFloat)w height:(CGFloat)h bottomHeight:(CGFloat)bh headerHeight:(CGFloat)hh {
    NSScrollView *sv = [[NSScrollView alloc] initWithFrame:NSMakeRect(0, bh, w, h - hh - bh)];
    [sv setHasVerticalScroller:YES];
    [sv setHasHorizontalScroller:NO];
    [sv setAutohidesScrollers:YES];
    [sv setDrawsBackground:NO];
    return sv;
}

+ (NSView *)buildHeaderBarWithWidth:(CGFloat)w height:(CGFloat)h {
    NSView *bar = [[NSView alloc] initWithFrame:NSMakeRect(0, 0, w, h)];
    [bar setWantsLayer:YES];
    [bar.layer setBackgroundColor:[[NSColor colorWithRed:0.08 green:0.08 blue:0.14 alpha:1.0] CGColor]];
    NSTextField *label = [[NSTextField alloc] initWithFrame:NSMakeRect(16, 8, w - 32, 24)];
    [label setStringValue:@"Mac Control Panel - Daemon Manager"];
    [label setFont:[NSFont boldSystemFontOfSize:16]];
    [label setTextColor:[NSColor colorWithRed:0.0 green:1.0 blue:0.53 alpha:1.0]];
    [label setBackgroundColor:[NSColor clearColor]];
    [label setBezeled:NO];
    [label setEditable:NO];
    [bar addSubview:label];
    return bar;
}

+ (NSView *)buildBottomBarWithWidth:(CGFloat)w height:(CGFloat)h target:(id)target
                       disableSel:(SEL)ds enableSel:(SEL)es cleanSel:(SEL)cs refreshSel:(SEL)rs {
    NSView *bar = [[NSView alloc] initWithFrame:NSMakeRect(0, 0, w, h)];
    [bar setWantsLayer:YES];
    [bar.layer setBackgroundColor:[[NSColor colorWithRed:0.08 green:0.08 blue:0.14 alpha:1.0] CGColor]];

    NSFont *boldFont = [NSFont boldSystemFontOfSize:12];

    NSButton *disableAllBtn = [[NSButton alloc] initWithFrame:NSMakeRect(16, 16, 140, 28)];
    [disableAllBtn setTitle:@"DISABLE ALL"];
    [disableAllBtn setFont:boldFont];
    [disableAllBtn setBezelStyle:NSBezelStyleRounded];
    [disableAllBtn setTarget:target];
    [disableAllBtn setAction:ds];
    [bar addSubview:disableAllBtn];

    NSButton *enableAllBtn = [[NSButton alloc] initWithFrame:NSMakeRect(166, 16, 140, 28)];
    [enableAllBtn setTitle:@"ENABLE ALL"];
    [enableAllBtn setFont:boldFont];
    [enableAllBtn setBezelStyle:NSBezelStyleRounded];
    [enableAllBtn setTarget:target];
    [enableAllBtn setAction:es];
    [bar addSubview:enableAllBtn];

    NSButton *cleanBtn = [[NSButton alloc] initWithFrame:NSMakeRect(316, 16, 160, 28)];
    [cleanBtn setTitle:@"File Cleaner"];
    [cleanBtn setFont:boldFont];
    [cleanBtn setBezelStyle:NSBezelStyleRounded];
    [cleanBtn setTarget:target];
    [cleanBtn setAction:cs];
    [bar addSubview:cleanBtn];

    NSButton *refreshBtn = [[NSButton alloc] initWithFrame:NSMakeRect(w - 160, 16, 140, 28)];
    [refreshBtn setTitle:@"REFRESH"];
    [refreshBtn setFont:boldFont];
    [refreshBtn setBezelStyle:NSBezelStyleRounded];
    [refreshBtn setTarget:target];
    [refreshBtn setAction:rs];
    [bar addSubview:refreshBtn];

    return bar;
}

+ (NSToolbar *)buildToolbarWithDelegate:(id)delegate {
    NSToolbar *tb = [[NSToolbar alloc] initWithIdentifier:@"MacControlToolbar"];
    [tb setDisplayMode:NSToolbarDisplayModeIconAndLabel];
    [tb setAllowsUserCustomization:NO];
    [tb setDelegate:delegate];
    return tb;
}

+ (NSMenu *)buildMenuBarWithRefreshTarget:(id)target refreshSel:(SEL)rs {
    NSMenuItem *fileItem = [[NSMenuItem alloc] initWithTitle:@"File" action:nil keyEquivalent:@""];
    NSMenu *fileMenu = [[NSMenu alloc] initWithTitle:@"File"];
    [fileItem setSubmenu:fileMenu];
    [fileMenu addItemWithTitle:@"Quit" action:@selector(terminate:) keyEquivalent:@"q"];

    NSMenuItem *editItem = [[NSMenuItem alloc] initWithTitle:@"Edit" action:nil keyEquivalent:@""];
    NSMenu *editMenu = [[NSMenu alloc] initWithTitle:@"Edit"];
    [editItem setSubmenu:editMenu];
    NSMenuItem *refreshItem = [editMenu addItemWithTitle:@"Refresh" action:rs keyEquivalent:@"r"];
    [refreshItem setTarget:target];

    NSMenu *mainMenu = [[NSMenu alloc] init];
    [mainMenu addItem:fileItem];
    [mainMenu addItem:editItem];
    return mainMenu;
}

@end

/* ============================================================
 * AppDelegate — thin orchestrator
 * Wires ServiceManager + CleanerManager + GUIBuilder together
 * ============================================================
 */
@interface AppDelegate : NSObject <NSApplicationDelegate, NSToolbarDelegate>
    @property (strong) NSWindow *window;
    @property (strong) ServiceManager *svcMgr;
    @property (strong) CleanerManager *cleanerMgr;
    @property (strong) NSMutableArray *rowViews;
    @property (strong) NSMutableArray *statusLabels;
    @property (strong) NSMutableArray *toggleButtons;
    @property (strong) NSMutableArray *advisoryLabels;
    @property (strong) NSTimer *refreshTimer;
@end

@implementation AppDelegate

- (void)toggleAction:(id)sender {
    NSInteger idx = [sender tag];
    [self.svcMgr toggleServiceAtIndex:(int)idx];
    [self refreshUI];
}

- (void)disableAllAction:(id)sender {
    NSAlert *alert = [[NSAlert alloc] init];
    [alert setMessageText:@"Disable ALL safe services?"];
    [alert setInformativeText:@"Dangerous services are protected. You can re-enable anytime."];
    [alert addButtonWithTitle:@"Yes, Disable All"];
    [alert addButtonWithTitle:@"Cancel"];
    if ([alert runModal] == NSAlertFirstButtonReturn) {
        [self.refreshTimer invalidate];
        [self.svcMgr disableAll];
        [self refreshUI];
        self.refreshTimer = [NSTimer scheduledTimerWithTimeInterval:5.0
                                                            target:self
                                                          selector:@selector(refreshAction:)
                                                          userInfo:nil
                                                           repeats:YES];
    }
}

- (void)enableAllAction:(id)sender {
    [self.svcMgr enableAll];
    [self refreshUI];
}

- (void)refreshAction:(id)sender {
    [self refreshUI];
}

- (void)cleanZeroByteAction:(id)sender {
    [self.cleanerMgr runCleaner];
}

- (void)settingsAction:(id)sender {
    NSAlert *settings = [[NSAlert alloc] init];
    [settings setMessageText:@"Mac Control Panel Settings"];
    [settings setInformativeText:[NSString stringWithFormat:
        @"OS Version: %@\nRegistry: %@\n\nServices: %d total\n  \u2713 Known (built-in DB): %d\n  \u21BB Remembered (registry): %d\n  \u26A0 Newly detected: %d\n\nAdvisory levels:\n  GREEN (SAFE) - safe to disable, frees RAM\n  ORANGE (CAUTION) - may break some features\n  RED (DANGER) - locked, will break core OS\n\nSource symbols:\n  \u2713 = matched built-in advisory database\n  \u21BB = saved from previous run (registry)\n  \u26A0 = newly detected this run\n\nThe registry persists at:\n%@\nIt grows each time you run the app - learning new services.",
        [self.svcMgr osVersion], [self.svcMgr registryPath],
        [self.svcMgr serviceCount], [self.svcMgr builtinCount],
        [self.svcMgr registryCount], [self.svcMgr detectedCount],
        [self.svcMgr registryPath]]];
    [settings addButtonWithTitle:@"OK"];
    [settings runModal];
}

- (void)refreshUI {
    [self.svcMgr refreshStatusWithLabels:self.statusLabels
                                  toggles:self.toggleButtons
                               advisories:self.advisoryLabels];
}

#pragma mark - NSToolbarDelegate

- (NSToolbarItem *)toolbar:(NSToolbar *)toolbar itemForItemIdentifier:(NSString *)itemIdentifier willBeInsertedIntoToolbar:(BOOL)flag {
    if ([itemIdentifier isEqualToString:@"settings"]) {
        NSToolbarItem *item = [[NSToolbarItem alloc] initWithItemIdentifier:@"settings"];
        [item setLabel:@"Settings"];
        [item setPaletteLabel:@"Settings"];
        [item setToolTip:@"Open settings panel"];
        [item setImage:[NSImage imageNamed:NSImageNamePreferencesGeneral]];
        [item setTarget:self];
        [item setAction:@selector(settingsAction:)];
        return item;
    }
    if ([itemIdentifier isEqualToString:@"refresh"]) {
        NSToolbarItem *item = [[NSToolbarItem alloc] initWithItemIdentifier:@"refresh"];
        [item setLabel:@"Refresh"];
        [item setPaletteLabel:@"Refresh"];
        [item setToolTip:@"Refresh all service statuses"];
        [item setImage:[NSImage imageNamed:NSImageNameRefreshTemplate]];
        [item setTarget:self];
        [item setAction:@selector(refreshAction:)];
        return item;
    }
    return nil;
}

- (NSArray *)toolbarAllowedItemIdentifiers:(NSToolbar *)toolbar {
    return @[@"settings", @"refresh"];
}

- (NSArray *)toolbarDefaultItemIdentifiers:(NSToolbar *)toolbar {
    return @[@"refresh", @"settings"];
}

- (void)applicationDidFinishLaunching:(NSNotification *)notification {
    /* Create managers */
    self.svcMgr = [[ServiceManager alloc] init];
    self.cleanerMgr = [[CleanerManager alloc] init];

    /* Load services from launchctl + registry */
    [self.svcMgr loadServices];

    /* Init UI arrays */
    self.rowViews = [[NSMutableArray alloc] init];
    self.statusLabels = [[NSMutableArray alloc] init];
    self.toggleButtons = [[NSMutableArray alloc] init];
    self.advisoryLabels = [[NSMutableArray alloc] init];

    /* Build window */
    CGFloat windowWidth = 880;
    CGFloat windowHeight = 720;
    CGFloat headerHeight = 40;
    CGFloat bottomHeight = 60;

    self.window = [GUIBuilder buildWindowWithWidth:windowWidth height:windowHeight];
    [self.window setToolbar:[GUIBuilder buildToolbarWithDelegate:self]];

    /* Header bar */
    NSView *headerBar = [GUIBuilder buildHeaderBarWithWidth:windowWidth height:headerHeight];
    [headerBar setFrameOrigin:NSMakePoint(0, windowHeight - headerHeight)];
    [[self.window contentView] addSubview:headerBar];

    /* Scroll view */
    NSScrollView *scrollView = [GUIBuilder buildScrollViewWithWidth:windowWidth
                                                              height:windowHeight
                                                         bottomHeight:bottomHeight
                                                         headerHeight:headerHeight];

    /* Build service rows */
    int svcCount = [self.svcMgr serviceCount];
    Service *svcs = [self.svcMgr services];
    NSView *contentView = [[NSView alloc] initWithFrame:NSMakeRect(0, 0, windowWidth - 20, svcCount * 44 + 40)];
    [scrollView setDocumentView:contentView];

    NSFont *nameFont = [NSFont fontWithName:@"Menlo" size:13];
    NSFont *regFont = [NSFont systemFontOfSize:12];
    NSFont *boldFont = [NSFont boldSystemFontOfSize:12];
    NSColor *textColor = [NSColor colorWithRed:0.88 green:0.88 blue:0.92 alpha:1.0];
    NSColor *dimColor = [NSColor colorWithRed:0.50 green:0.50 blue:0.58 alpha:1.0];

    for (int i = 0; i < svcCount; i++) {
        CGFloat y = contentView.frame.size.height - 44 - (i * 44);

        NSBox *rowBox = [[NSBox alloc] initWithFrame:NSMakeRect(8, y, windowWidth - 40, 38)];
        [rowBox setBoxType:NSBoxCustom];
        [rowBox setFillColor:[NSColor colorWithRed:0.09 green:0.09 blue:0.16 alpha:1.0]];
        [rowBox setBorderColor:[NSColor colorWithRed:0.18 green:0.18 blue:0.30 alpha:1.0]];
        [rowBox setWantsLayer:YES];
        rowBox.layer.cornerRadius = 6;
        [contentView addSubview:rowBox];
        [self.rowViews addObject:rowBox];

        NSTextField *nameLabel = [[NSTextField alloc] initWithFrame:NSMakeRect(12, 8, 160, 22)];
        [nameLabel setStringValue:[NSString stringWithUTF8String:svcs[i].label]];
        [nameLabel setFont:nameFont];
        [nameLabel setTextColor:textColor];
        [nameLabel setBackgroundColor:[NSColor clearColor]];
        [nameLabel setBezeled:NO];
        [nameLabel setEditable:NO];
        [nameLabel setSelectable:NO];
        [rowBox addSubview:nameLabel];

        NSTextField *catLabel = [[NSTextField alloc] initWithFrame:NSMakeRect(175, 8, 70, 22)];
        NSString *catStr = [NSString stringWithUTF8String:svcs[i].category];
        if (svcs[i].source == SRC_BUILTIN) {
            catStr = [NSString stringWithFormat:@"\u2713 %@", catStr];
        } else if (svcs[i].source == SRC_REGISTRY) {
            catStr = [NSString stringWithFormat:@"\u21BB %@", catStr];
        } else {
            catStr = [NSString stringWithFormat:@"\u26A0 %@", catStr];
        }
        [catLabel setStringValue:catStr];
        [catLabel setFont:regFont];
        [catLabel setTextColor:dimColor];
        [catLabel setBackgroundColor:[NSColor clearColor]];
        [catLabel setBezeled:NO];
        [catLabel setEditable:NO];
        [rowBox addSubview:catLabel];

        NSTextField *descLabel = [[NSTextField alloc] initWithFrame:NSMakeRect(250, 8, 280, 22)];
        [descLabel setStringValue:[NSString stringWithUTF8String:svcs[i].desc]];
        [descLabel setFont:regFont];
        [descLabel setTextColor:dimColor];
        [descLabel setBackgroundColor:[NSColor clearColor]];
        [descLabel setBezeled:NO];
        [descLabel setEditable:NO];
        [rowBox addSubview:descLabel];

        NSTextField *advLabel = [[NSTextField alloc] initWithFrame:NSMakeRect(535, 8, 70, 22)];
        [advLabel setStringValue:@"?"];
        [advLabel setFont:boldFont];
        [advLabel setTextColor:dimColor];
        [advLabel setBackgroundColor:[NSColor clearColor]];
        [advLabel setBezeled:NO];
        [advLabel setEditable:NO];
        [advLabel setAlignment:NSTextAlignmentCenter];
        [rowBox addSubview:advLabel];
        [self.advisoryLabels addObject:advLabel];

        NSTextField *statusLabel = [[NSTextField alloc] initWithFrame:NSMakeRect(610, 8, 80, 22)];
        [statusLabel setStringValue:@"..."];
        [statusLabel setFont:boldFont];
        [statusLabel setTextColor:textColor];
        [statusLabel setBackgroundColor:[NSColor clearColor]];
        [statusLabel setBezeled:NO];
        [statusLabel setEditable:NO];
        [statusLabel setAlignment:NSTextAlignmentCenter];
        [rowBox addSubview:statusLabel];
        [self.statusLabels addObject:statusLabel];

        NSButton *toggleBtn = [[NSButton alloc] initWithFrame:NSMakeRect(700, 6, 90, 26)];
        [toggleBtn setTitle:@"Toggle"];
        [toggleBtn setFont:regFont];
        [toggleBtn setBezelStyle:NSBezelStyleRounded];
        [toggleBtn setTag:i];
        [toggleBtn setTarget:self];
        [toggleBtn setAction:@selector(toggleAction:)];
        [rowBox addSubview:toggleBtn];
        [self.toggleButtons addObject:toggleBtn];
    }

    [[self.window contentView] addSubview:scrollView];

    /* Bottom bar */
    NSView *bottomBar = [GUIBuilder buildBottomBarWithWidth:windowWidth
                                                     height:bottomHeight
                                                     target:self
                                                disableSel:@selector(disableAllAction:)
                                                 enableSel:@selector(enableAllAction:)
                                                  cleanSel:@selector(cleanZeroByteAction:)
                                                refreshSel:@selector(refreshAction:)];
    [[self.window contentView] addSubview:bottomBar];

    [self.window makeKeyAndOrderFront:nil];
    [self.window center];

    /* Initial refresh + timer */
    [self refreshUI];
    self.refreshTimer = [NSTimer scheduledTimerWithTimeInterval:5.0
                                                        target:self
                                                      selector:@selector(refreshAction:)
                                                      userInfo:nil
                                                       repeats:YES];
}

- (BOOL)applicationShouldTerminateAfterLastWindowClosed:(NSApplication *)sender {
    return YES;
}

@end

/* ============================================================
 * main — entry point
 * ============================================================
 */
int main(int argc, const char *argv[]) {
    @autoreleasepool {
        NSApplication *app = [NSApplication sharedApplication];
        [app setActivationPolicy:NSApplicationActivationPolicyRegular];

        AppDelegate *delegate = [[AppDelegate alloc] init];
        [app setDelegate:delegate];

        NSMenu *mainMenu = [GUIBuilder buildMenuBarWithRefreshTarget:delegate
                                                          refreshSel:@selector(refreshAction:)];
        [app setMainMenu:mainMenu];

        [app activateIgnoringOtherApps:YES];
        [app run];
    }
    return 0;
}
