/*
 * wcmd.c  —  Windows-Style Command VM for macOS
 * Version: 3.1
 * Author:  wws / Cascade
 * License: Private
 *
 * ============================================================================
 * PURPOSE
 * ============================================================================
 *   Single-binary command shell that replicates familiar Windows CMD commands
 *   (DIR, DEL, COPY, MOVE, etc.) on macOS, with a SQLite-backed configuration
 *   system and an embedded MySQL ingestion engine (INGEST).
 *
 *   The binary is fully self-contained — no external .db file, no .h files,
 *   no config files.  All settings live in an in-memory SQLite DB that is
 *   seeded at startup from a compiled-in SQL string.
 *
 * ============================================================================
 * ARCHITECTURE
 * ============================================================================
 *   1. Command Binding Table (g_bindings[])
 *      - Maps command names (DIR, GREP, INGEST, ...) to C functions
 *      - resolve_command() does case-insensitive lookup
 *      - Add a new command: write cmd_foo(), add to table, done
 *
 *   2. SQLite In-Memory DB
 *      - SEED_SQL creates tables: commands, command_flags, behaviors,
 *        help_sections, ui_modules, system_config
 *      - Stores command metadata, help text, and DIR display preferences
 *      - db_get() / db_help() read config and help from DB
 *      - load_config() pulls DIR settings at startup
 *
 *   3. INGEST Engine (cmd_ingest)
 *      - MySQL-backed file ingestion into CODEBASE database
 *      - Scanner writes jobs to ingestion_jobs table (prepared statements)
 *      - Workers pull jobs with SELECT ... FOR UPDATE SKIP LOCKED
 *      - Checkpoint table (file_checkpoint) deduplicates via SHA1 path hash
 *      - State machine: pending -> processing -> done | failed
 *      - Run multiple `wcmd INGEST run N` processes for parallelism
 *      - No threads, no WAL, no in-memory queue — MySQL IS the queue
 *
 *   4. Embedded PyQt6 GUI
 *      - GUI_LINES[] contains a full Python script as C string literals
 *      - `wcmd -cfg` writes it to a temp file and launches python3
 *      - GUI reads/writes config via ~/.wcmd_cfg.db (SQLite file)
 *
 * ============================================================================
 * COMMANDS
 * ============================================================================
 *   DIR     Display files and subdirectories  (/A /B /I /L /O /P /Q /R /S /W)
 *   DEL     Delete files                      (/S /Q)
 *   CD      Change directory
 *   MD      Create directory (mkdir -p)
 *   RD      Remove directory                  (/S)
 *   MOVE    Move or rename files
 *   COPY    Copy files                        (/Y)
 *   TYPE    Display file contents
 *   REN     Rename (alias for MOVE)
 *   WHERE   Find files by wildcard            (/S /R)
 *   GREP    Search inside files (regex)       (/S /R /I)
 *   FINDSTR Alias for GREP
 *   INGEST  MySQL ingestion engine            (init|scan|run|scanrun|stats|reset)
 *
 * ============================================================================
 * INGEST SUBCOMMANDS
 * ============================================================================
 *   wcmd INGEST init              Create MySQL schema (7 file tables + checkpoint + jobs)
 *   wcmd INGEST scan /path        Walk filesystem, insert file paths as pending jobs
 *   wcmd INGEST run [worker_id]   Pull pending jobs, read file, insert content, mark done
 *   wcmd INGEST scanrun /path     Scan + run in one pass
 *   wcmd INGEST stats             Show row counts per table + job status breakdown
 *   wcmd INGEST reset             TRUNCATE ingestion_jobs
 *
 *   Parallel: open N terminals, run `wcmd INGEST run 1`, `run 2`, `run 3` ...
 *   MySQL SKIP LOCKED ensures no two workers grab the same job.
 *
 * ============================================================================
 * BUILD
 * ============================================================================
 *   cc -O2 -o wcmd wcmd.c \
 *     -lsqlite3 \
 *     -I/opt/homebrew/Cellar/mysql@8.0/8.0.46_1/include \
 *     -I/opt/homebrew/Cellar/openssl@3/3.6.2/include \
 *     -L/opt/homebrew/Cellar/mysql@8.0/8.0.46_1/lib \
 *     -L/opt/homebrew/Cellar/openssl@3/3.6.2/lib \
 *     -lmysqlclient -lssl -lcrypto \
 *     -Wl,-rpath,/opt/homebrew/Cellar/mysql@8.0/8.0.46_1/lib \
 *     -Wl,-rpath,/opt/homebrew/Cellar/openssl@3/3.6.2/lib \
 *     -headerpad_max_install_names
 *
 * ============================================================================
 * USAGE
 * ============================================================================
 *   wcmd DIR /S /L class Brain       Recursive content search for "class Brain"
 *   wcmd DIR /R /L tokenizer.json    Search from home for "tokenizer.json"
 *   wcmd WHERE *.py /S               Find all .py files recursively
 *   wcmd GREP "def.*think" *.py /S   Regex search in Python files
 *   wcmd INGEST init                 Initialize MySQL schema
 *   wcmd INGEST scanrun /Users       Scan + ingest everything under /Users
 *   wcmd INGEST stats                Show database statistics
 *   wcmd -cfg                        Launch PyQt6 config GUI
 *
 * ============================================================================
 * FILE LAYOUT (single file, no headers)
 * ============================================================================
 *   Lines   Section
 *   ------  ------------------------------------------
 *     1-90   Header, includes, types, binding table, globals
 *    91-107  SEED_SQL (in-memory DB schema + seed data)
 *   108-215  DB helpers (db_open, db_bootstrap, db_get, load_config)
 *   216-253  Help system (db_help, db_command_enabled, resolve_command)
 *   254-270  VM dispatch (vm_execute)
 *   271-871  Command implementations (DIR, DEL, CD, MD, RD, MOVE, COPY, TYPE, WHERE, GREP)
 *   872-1101 INGEST engine (schema, scanner, worker, stats, cmd_ingest)
 *  1102-1336 Embedded PyQt6 GUI script (GUI_LINES[]) + launch_cfg + main()
 *
 * ============================================================================
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <dirent.h>
#include <sys/stat.h>
#include <sys/statvfs.h>
#include <fnmatch.h>
#include <time.h>
#include <unistd.h>
#include <pwd.h>
#include <ctype.h>
#include <libgen.h>
#include <errno.h>
#include <sqlite3.h>
#include <regex.h>
#include <mysql/mysql.h>
#include <openssl/sha.h>

typedef int (*cmd_fn)(int argc, char **argv);
typedef struct { const char *name; cmd_fn fn; } CommandBinding;

int cmd_dir(int argc, char **argv);
int cmd_del(int argc, char **argv);
int cmd_cd (int argc, char **argv);
int cmd_md (int argc, char **argv);
int cmd_rd (int argc, char **argv);
int cmd_move(int argc, char **argv);
int cmd_copy(int argc, char **argv);
int cmd_type(int argc, char **argv);
int cmd_where(int argc, char **argv);
int cmd_grep(int argc, char **argv);
int cmd_ingest(int argc, char **argv);

static CommandBinding g_bindings[] = {
    {"DIR",cmd_dir},{"DEL",cmd_del},{"CD",cmd_cd},{"MD",cmd_md},{"RD",cmd_rd},
    {"MOVE",cmd_move},{"COPY",cmd_copy},{"TYPE",cmd_type},
    {"WHERE",cmd_where},{"GREP",cmd_grep},{"FINDSTR",cmd_grep},
    {"INGEST",cmd_ingest},
    {NULL,NULL}
};

static char g_db_path[512]="";
static int cfg_show_date=1,cfg_show_time=1,cfg_show_hidden=0;
static int cfg_thousand=1,cfg_sort_rev=0;
static char cfg_sort='G',cfg_size_fmt[8]="auto";
static int opt_s=0,opt_b=0,opt_l=0,opt_w=0,opt_p=0,opt_q=0,opt_i=0;
static char g_search[1024]="";static int g_search_set=0;static int g_total_matches=0;static int g_matched_files=0;
static regex_t *g_re=NULL;
static int g_plain=0;static char g_plain_text[1024]="";
static char opt_a=0;
static long long grand_files=0,grand_bytes=0,grand_dirs=0;

static const char *SKIP_BUILTIN[] = {
    "__pycache__",".git",".svn",".hg","node_modules",
    ".Trash",".Spotlight-V100","Caches","Mail","Logs",
    "site-packages","dist-packages",
    "Python","python3.9","python3.10","python3.11",
    "python3.12","python3.13","python3.14",NULL
};
static char user_skip[48][256];
static int user_skip_count=0;

/* Schema only — seed data is inserted programmatically in db_open().
   No external .db file needed — the binary is fully self-contained. */
static const char SEED_SQL[] =
"CREATE TABLE IF NOT EXISTS commands (id INTEGER PRIMARY KEY,name TEXT UNIQUE,description TEXT,version TEXT,enabled INTEGER DEFAULT 1);"
"CREATE TABLE IF NOT EXISTS command_flags (id INTEGER PRIMARY KEY,command_id INTEGER,flag TEXT,description TEXT,flag_type TEXT DEFAULT 'bool',default_val TEXT DEFAULT '0');"
"CREATE TABLE IF NOT EXISTS behaviors (id INTEGER PRIMARY KEY,command_id INTEGER,key TEXT,value TEXT,description TEXT,UNIQUE(command_id,key));"
"CREATE TABLE IF NOT EXISTS help_sections (id INTEGER PRIMARY KEY,command_id INTEGER,section TEXT,content TEXT,sort_order INTEGER DEFAULT 0,UNIQUE(command_id,section));"
"CREATE TABLE IF NOT EXISTS ui_modules (id INTEGER PRIMARY KEY,name TEXT UNIQUE,description TEXT,script TEXT,version INTEGER DEFAULT 1);"
"CREATE TABLE IF NOT EXISTS system_config (key TEXT PRIMARY KEY,value TEXT,description TEXT);"
;

typedef struct { const char *name,*desc,*ver; } CmdSeed;
static const CmdSeed CMD_SEED[] = {
    {"DIR","Display files and subdirectories","1.2"},
    {"DEL","Delete files","1.0"},
    {"CD","Change current directory","1.0"},
    {"MD","Create directory","1.0"},
    {"RD","Remove directory","1.0"},
    {"MOVE","Move or rename files","1.0"},
    {"COPY","Copy files","1.0"},
    {"TYPE","Display file contents","1.0"},
    {"REN","Rename files (alias for MOVE)","1.0"},
    {"WHERE","Find files by pattern","1.0"},
    {"GREP","Search inside files (regex)","1.0"},
    {"FINDSTR","Alias for GREP","1.0"},
    {"INGEST","MySQL ingestion engine","1.0"},
    {NULL,NULL,NULL}
};

typedef struct { const char *cmd,*key,*val,*desc; } BehaveSeed;
static const BehaveSeed BEHAVE_SEED[] = {
    {"DIR","show_date","1","Show date"},
    {"DIR","show_time","1","Show time"},
    {"DIR","show_hidden","0","Show hidden"},
    {"DIR","thousand","1","Thousand sep"},
    {"DIR","sort","G","Default sort"},
    {"DIR","sort_rev","0","Reverse"},
    {"DIR","size_fmt","auto","Size format"},
    {"DIR","skip","__pycache__,.git,node_modules,site-packages","Skip dirs"},
    {NULL,NULL,NULL,NULL}
};

typedef struct { const char *cmd,*section,*content; } HelpSeed;
static const HelpSeed HELP_SEED[] = {
    {"DIR","DIR",
        "\n  DIR [path][pattern] [/A] [/B] [/I] [/L text] [/O:key] [/P] [/Q] [/R] [/S] [/W] [/?] [-cfg]\n"
        "  /A        All files incl hidden   /A:D dirs   /A:-D files only\n"
        "  /B        Bare paths\n"
        "  /I        Include all dirs (ignore skip list)\n"
        "  /L text   Look inside files for text (content search)\n"
        "  /O:N/S/E/D/G  Sort (prefix - reverses)\n"
        "  /P        Pause each screen\n"
        "  /Q        Show owner\n"
        "  /R        Start from home directory\n"
        "  /S        Recurse subdirectories\n"
        "  /W        Wide 5-column format\n"
        "  /X:name   Exclude named dir during /S\n"
        "  -cfg      Open configuration GUI\n"
        "  /?        Show this help\n"
        "  Examples:\n"
        "    DIR /L class Brain          Search current dir for \"class Brain\"\n"
        "    DIR /S /L def _think        Recursive search for \"def _think\"\n"
        "    DIR /R /L tokenizer          Search from home for \"tokenizer\"\n"},
    {"CD","CD","\n  CD [directory]\n  Changes the current working directory.\n  With no argument, shows the current directory.\n  /?        Show this help\n"},
    {"DEL","DEL","\n  DEL pattern [/S] [/Q] [/?]\n  pattern   Filename or wildcard (e.g. *.tmp)\n  /S        Recurse subdirectories\n  /Q        No confirmation prompt\n  /?        Show this help\n"},
    {"MD","MD","\n  MD dirname [dirname2 ...]\n  Creates directories recursively (like mkdir -p).\n"},
    {"RD","RD","\n  RD dirname [/S] [/?]\n  /S        Remove recursively with all contents (confirmation)\n  /?        Show this help\n"},
    {"MOVE","MOVE","\n  MOVE source destination\n  Moves source file/directory to destination path.\n  Cross-device moves handled automatically.\n"},
    {"COPY","COPY","\n  COPY source destination [/Y] [/?]\n  /Y        Overwrite without confirmation\n  /?        Show this help\n"},
    {"TYPE","TYPE","\n  TYPE filename [filename2 ...]\n  Prints each file to stdout.\n"},
    {"REN","REN","\n  REN oldname newname\n  Same as MOVE. Renames a single file or directory.\n"},
    {"WHERE","WHERE","\n  WHERE pattern [/S] [/R] [/?]\n  pattern   Filename wildcard (e.g. *.py, *.json)\n  /S        Recurse subdirectories\n  /R        Start from home directory\n  /?        Show this help\n  Example: WHERE *.py /S\n"},
    {"GREP","GREP",
        "\n  GREP pattern [filepattern] [/S] [/R] [/I] [/?]\n"
        "  pattern       Regex to search inside files\n"
        "  filepattern   Wildcard to filter files (e.g. *.py)\n"
        "  /S          Recurse subdirectories\n"
        "  /R          Start from home directory\n"
        "  /I          Case-insensitive\n"
        "  /?          Show this help\n"
        "  Examples:\n"
        "    GREP \"class.*Brain\" *.py /S\n"
        "    GREP \"def .*think\" *.py /S /I\n"
        "    FINDSTR \"import sqlite\" *.py /S\n"},
    {"FINDSTR","FINDSTR","\n  FINDSTR is an alias for GREP. See GREP /?\n"},
    {"INGEST","INGEST",
        "\n  INGEST init              Create MySQL schema\n"
        "  INGEST scan /path        Scan filesystem -> job queue\n"
        "  INGEST run [worker_id]   Process jobs from queue\n"
        "  INGEST scanrun /path     Scan + process in one pass\n"
        "  INGEST stats             Show table + job counts\n"
        "  INGEST reset             Clear job queue\n"
        "  INGEST config            Show current INGEST config\n"},
    {NULL,NULL,NULL}
};

typedef struct { const char *key,*val,*desc; } CfgSeed;
static const CfgSeed CFG_SEED[] = {
    {"ingest_mysql_host","localhost","MySQL host for INGEST"},
    {"ingest_mysql_user","root","MySQL user"},
    {"ingest_mysql_pass","","MySQL password"},
    {"ingest_mysql_db","CODEBASE","MySQL database name"},
    {"ingest_mysql_port","0","MySQL port (0=default)"},
    {"ingest_start_path","/Users/Shared","Default scan start path"},
    {"ingest_max_file_mb","50","Max file size in MB"},
    {"ingest_skip_dirs",".git,.svn,venv,env,__pycache__,site-packages,node_modules,Trash,build,DerivedData,Pods,Caches,Frameworks,dist,out,coverage,.next,.nuxt,.turbo,.gradle","Dirs to skip during scan"},
    {NULL,NULL,NULL}
};

static sqlite3 *db_open(void){
    sqlite3 *db=NULL;
    sqlite3_open(":memory:",&db);
    if(db){
        sqlite3_exec(db,SEED_SQL,NULL,NULL,NULL);
        sqlite3_stmt *st;
        /* Seed commands */
        sqlite3_prepare_v2(db,"INSERT OR IGNORE INTO commands (name,description,version) VALUES (?,?,?)",-1,&st,NULL);
        for(int i=0;CMD_SEED[i].name;i++){
            sqlite3_bind_text(st,1,CMD_SEED[i].name,-1,SQLITE_STATIC);
            sqlite3_bind_text(st,2,CMD_SEED[i].desc,-1,SQLITE_STATIC);
            sqlite3_bind_text(st,3,CMD_SEED[i].ver,-1,SQLITE_STATIC);
            sqlite3_step(st); sqlite3_reset(st);
        }
        sqlite3_finalize(st);
        /* Seed behaviors */
        sqlite3_prepare_v2(db,"INSERT OR IGNORE INTO behaviors (command_id,key,value,description) VALUES ((SELECT id FROM commands WHERE name=?),?,?,?)",-1,&st,NULL);
        for(int i=0;BEHAVE_SEED[i].cmd;i++){
            sqlite3_bind_text(st,1,BEHAVE_SEED[i].cmd,-1,SQLITE_STATIC);
            sqlite3_bind_text(st,2,BEHAVE_SEED[i].key,-1,SQLITE_STATIC);
            sqlite3_bind_text(st,3,BEHAVE_SEED[i].val,-1,SQLITE_STATIC);
            sqlite3_bind_text(st,4,BEHAVE_SEED[i].desc,-1,SQLITE_STATIC);
            sqlite3_step(st); sqlite3_reset(st);
        }
        sqlite3_finalize(st);
        /* Seed help_sections */
        sqlite3_prepare_v2(db,"INSERT OR IGNORE INTO help_sections (command_id,section,content,sort_order) VALUES ((SELECT id FROM commands WHERE name=?),?,?,1)",-1,&st,NULL);
        for(int i=0;HELP_SEED[i].cmd;i++){
            sqlite3_bind_text(st,1,HELP_SEED[i].cmd,-1,SQLITE_STATIC);
            sqlite3_bind_text(st,2,HELP_SEED[i].section,-1,SQLITE_STATIC);
            sqlite3_bind_text(st,3,HELP_SEED[i].content,-1,SQLITE_STATIC);
            sqlite3_step(st); sqlite3_reset(st);
        }
        sqlite3_finalize(st);
        /* Seed system_config */
        sqlite3_prepare_v2(db,"INSERT OR IGNORE INTO system_config (key,value,description) VALUES (?,?,?)",-1,&st,NULL);
        for(int i=0;CFG_SEED[i].key;i++){
            sqlite3_bind_text(st,1,CFG_SEED[i].key,-1,SQLITE_STATIC);
            sqlite3_bind_text(st,2,CFG_SEED[i].val,-1,SQLITE_STATIC);
            sqlite3_bind_text(st,3,CFG_SEED[i].desc,-1,SQLITE_STATIC);
            sqlite3_step(st); sqlite3_reset(st);
        }
        sqlite3_finalize(st);
    }
    return db;
}

static const char *db_get(sqlite3 *db,const char *cmd_name,const char *key,const char *def,char *buf,int bsz){
    strncpy(buf,def,bsz-1);buf[bsz-1]='\0';
    sqlite3_stmt *st;
    sqlite3_prepare_v2(db,"SELECT b.value FROM behaviors b JOIN commands c ON c.id=b.command_id WHERE c.name=? AND b.key=?",-1,&st,NULL);
    sqlite3_bind_text(st,1,cmd_name,-1,SQLITE_STATIC); sqlite3_bind_text(st,2,key,-1,SQLITE_STATIC);
    if(sqlite3_step(st)==SQLITE_ROW){ const char *v=(const char*)sqlite3_column_text(st,0); if(v)strncpy(buf,v,bsz-1); }
    sqlite3_finalize(st);
    return buf;
}

static void load_config(sqlite3 *db){
    char tmp[64];
    cfg_show_date  =atoi(db_get(db,"DIR","show_date",  "1",tmp,sizeof(tmp)));
    cfg_show_time  =atoi(db_get(db,"DIR","show_time",  "1",tmp,sizeof(tmp)));
    cfg_show_hidden=atoi(db_get(db,"DIR","show_hidden","0",tmp,sizeof(tmp)));
    cfg_thousand   =atoi(db_get(db,"DIR","thousand",   "1",tmp,sizeof(tmp)));
    cfg_sort       =toupper((unsigned char)db_get(db,"DIR","sort","G",tmp,sizeof(tmp))[0]);
    cfg_sort_rev   =atoi(db_get(db,"DIR","sort_rev",   "0",tmp,sizeof(tmp)));
    db_get(db,"DIR","size_fmt","auto",cfg_size_fmt,sizeof(cfg_size_fmt));
    char skip_buf[1024];
    db_get(db,"DIR","skip","",skip_buf,sizeof(skip_buf));
    if(skip_buf[0]){
        char t2[1024]; strncpy(t2,skip_buf,sizeof(t2)-1);
        char *tok=strtok(t2,",");
        while(tok&&user_skip_count<48){
            char *t=tok; while(*t==' ')t++;
            strncpy(user_skip[user_skip_count++],t,255);
            tok=strtok(NULL,",");
        }
    }
}

static void db_help(sqlite3 *db,const char *cmd_name){
    int self_open=0;
    if(!db){db=db_open();self_open=1;}
    if(!db){printf("\n  Help unavailable.\n\n");return;}
    sqlite3_stmt *st;
    int has=0;
    sqlite3_prepare_v2(db,"SELECT section,content FROM help_sections JOIN commands c ON c.id=help_sections.command_id WHERE c.name=? ORDER BY sort_order",-1,&st,NULL);
    sqlite3_bind_text(st,1,cmd_name,-1,SQLITE_STATIC);
    while(sqlite3_step(st)==SQLITE_ROW){
        has=1;
        const char *sec=(const char*)sqlite3_column_text(st,0);
        const char *txt=(const char*)sqlite3_column_text(st,1);
        if(sec&&sec[0])printf("\n%s\n",sec);
        if(txt&&txt[0])printf("%s",txt);
    }
    sqlite3_finalize(st);
    if(self_open)sqlite3_close(db);
    if(has)printf("\n");
    else printf("\n  No help found for %s.\n\n",cmd_name);
}

static int db_command_enabled(sqlite3 *db,const char *cmd){
    sqlite3_stmt *st;
    if(sqlite3_prepare_v2(db,"SELECT enabled FROM commands WHERE name=?",-1,&st,NULL)!=SQLITE_OK) return 1;
    sqlite3_bind_text(st,1,cmd,-1,SQLITE_STATIC);
    int en=1;
    if(sqlite3_step(st)==SQLITE_ROW) en=sqlite3_column_int(st,0);
    sqlite3_finalize(st);
    return en;
}

static cmd_fn resolve_command(const char *name){
    for(int i=0;g_bindings[i].name;i++){
        if(strcasecmp(g_bindings[i].name,name)==0) return g_bindings[i].fn;
    }
    return NULL;
}

static int vm_execute(sqlite3 *db,int argc,char **argv){
    if(argc<1) return 1;
    char cmd[64]="";
    if(argc>1&&argv[1]&&argv[1][0]&&argv[1][0]!='-'&&argv[1][0]!='/'){
        strncpy(cmd,argv[1],63);cmd[63]='\0';
        for(int i=0;cmd[i];i++)cmd[i]=toupper((unsigned char)cmd[i]);
        cmd_fn fn=resolve_command(cmd);
        if(fn){
            if(!db_command_enabled(db,cmd)){fprintf(stderr,"Command disabled in DB: %s\n",cmd);return 1;}
            return fn(argc-1,argv+1);
        }
    }
    char *base=basename(argv[0]);
    strncpy(cmd,base,63); cmd[63]='\0';
    for(int i=0;cmd[i];i++) cmd[i]=toupper((unsigned char)cmd[i]);
    if(!db_command_enabled(db,cmd)){
        fprintf(stderr,"Command disabled in DB: %s\n",cmd);
        return 1;
    }
    cmd_fn fn=resolve_command(cmd);
    if(!fn) fn=cmd_dir;
    return fn(argc,argv);
}

static int fnci(const char *pat,const char *name){
    size_t pl=strlen(pat),nl=strlen(name);
    char *p=malloc(pl+1),*n=malloc(nl+1);
    if(!p||!n){free(p);free(n);return FNM_NOMATCH;}
    for(size_t i=0;i<=pl;i++)p[i]=tolower((unsigned char)pat[i]);
    for(size_t i=0;i<=nl;i++)n[i]=tolower((unsigned char)name[i]);
    int r=fnmatch(p,n,0); free(p);free(n); return r;
}
static void lcase(char *s){while(*s){*s=tolower((unsigned char)*s);s++;}}
static int should_skip(const char *n){
    if(opt_i)return 0;
    for(int i=0;SKIP_BUILTIN[i];i++) if(strcasecmp(n,SKIP_BUILTIN[i])==0)return 1;
    for(int i=0;i<user_skip_count;i++) if(strcasecmp(n,user_skip[i])==0)return 1;
    return 0;
}
static char *fmt_count(long long n,char *buf,int bsz){
    char t[32];snprintf(t,sizeof(t),"%lld",n);
    if(!cfg_thousand){snprintf(buf,bsz,"%s",t);return buf;}
    int len=(int)strlen(t),out=0,c=len%3;
    for(int i=0;i<len;i++){if(i&&i%3==c)buf[out++]=',';buf[out++]=t[i];}
    buf[out]='\0';return buf;
}
static char *fmt_size(long long sz,char *buf,int bsz){
    char fmt[8];strncpy(fmt,cfg_size_fmt,7);lcase(fmt);
    if(!strcmp(fmt,"auto")){
        if(sz>=1073741824LL)snprintf(buf,bsz,"%.1f GB",sz/1073741824.0);
        else if(sz>=1048576LL)snprintf(buf,bsz,"%.1f MB",sz/1048576.0);
        else if(sz>=1024LL)snprintf(buf,bsz,"%.1f KB",sz/1024.0);
        else snprintf(buf,bsz,"%lld B",sz);
        return buf;
    }
    if(!strcmp(fmt,"kb")){snprintf(buf,bsz,"%.1f KB",sz/1024.0);return buf;}
    if(!strcmp(fmt,"mb")){snprintf(buf,bsz,"%.1f MB",sz/1048576.0);return buf;}
    if(!strcmp(fmt,"gb")){snprintf(buf,bsz,"%.2f GB",sz/1073741824.0);return buf;}
    char t[32];snprintf(t,sizeof(t),"%lld",sz);
    if(!cfg_thousand){snprintf(buf,bsz,"%s",t);return buf;}
    int len=(int)strlen(t),out=0,c=len%3;
    for(int i=0;i<len;i++){if(i&&i%3==c)buf[out++]=',';buf[out++]=t[i];}
    buf[out]='\0';return buf;
}

typedef struct { char name[512],fullpath[4096],ext[64]; int is_dir; long long size; time_t mtime,ctime,atime; } Entry;
static char g_sk; static int g_sr;
static int cmp_e(const void *a,const void *b){
    const Entry *ea=a,*eb=b; int r=0;
    if(g_sk=='G'){if(ea->is_dir&&!eb->is_dir)return -1;if(!ea->is_dir&&eb->is_dir)return 1;}
    switch(g_sk){
        case 'N':r=strcasecmp(ea->name,eb->name);break;
        case 'S':r=(ea->size<eb->size)?-1:(ea->size>eb->size)?1:0;break;
        case 'E':r=strcasecmp(ea->ext,eb->ext);break;
        case 'D':r=(ea->mtime<eb->mtime)?-1:(ea->mtime>eb->mtime)?1:0;break;
        default:r=strcasecmp(ea->name,eb->name);break;
    }
    return g_sr?-r:r;
}

static void list_dir(const char *path,const char *pattern,int level){
    DIR *dh=opendir(path);
    if(!dh){if(!opt_b)fprintf(stderr,"\n     Access is denied — %s\n",path);return;}
    Entry *entries=NULL; int count=0,cap=64; entries=malloc(cap*sizeof(Entry));
    char **subdirs=NULL; int scount=0,scap=16; subdirs=malloc(scap*sizeof(char*));
    struct dirent *de;
    while((de=readdir(dh))!=NULL){
        if(!strcmp(de->d_name,".")||!strcmp(de->d_name,".."))continue;
        int ih=(de->d_name[0]=='.');
        if(ih&&!opt_a&&!cfg_show_hidden)continue;
        int isd=(de->d_type==DT_DIR);
        int islink=(de->d_type==DT_LNK);
        if(de->d_type==DT_UNKNOWN){
            char fp2[4096];snprintf(fp2,sizeof(fp2),"%s/%s",path,de->d_name);
            struct stat s2;if(lstat(fp2,&s2)==0){isd=S_ISDIR(s2.st_mode);islink=S_ISLNK(s2.st_mode);}
        }
        if(islink&&opt_s)continue;
        if(isd&&opt_s&&!g_re&&should_skip(de->d_name))continue;
        if(opt_a=='D'&&!isd)continue;
        if(opt_a=='d'&&isd)continue;
        char fp[4096];snprintf(fp,sizeof(fp),"%s/%s",path,de->d_name);
        if(isd&&opt_s){
            if(scount>=scap){scap*=2;subdirs=realloc(subdirs,scap*sizeof(char*));}
            subdirs[scount++]=strdup(fp);
        }
        if(pattern&&fnci(pattern,de->d_name)!=0)continue;
        if(g_re){
            if(isd)continue;
            char *dot=strrchr(de->d_name,'.');
            if(!dot)continue;
            static const char *TX[]={"py","md","txt","js","ts","tsx","jsx","c","h","cpp","hpp",
                "json","yaml","yml","xml","html","htm","css","scss","sh","bash","zsh",
                "swift","sql","csv","toml","cfg","ini","conf","log","rst","rb","go",
                "rs","java","kt","scala","php","pl","lua","r","dart","vue","svelte",
                "gradle","makefile","dockerfile","env","tf","proto","graphql","gql",
                "bat","cmd","ps1","ahk","nix","lock","diff","patch",NULL};
            int is_text=0;
            for(int t=0;TX[t];t++){if(strcasecmp(dot+1,TX[t])==0){is_text=1;break;}}
            if(!is_text)continue;
            if(count>=cap){cap*=2;entries=realloc(entries,cap*sizeof(Entry));}
            Entry *e=&entries[count++];
            strncpy(e->name,de->d_name,511);e->name[511]='\0';
            strncpy(e->fullpath,fp,4095);e->fullpath[4095]='\0';
            e->is_dir=0;e->size=0;e->mtime=0;e->ctime=0;e->atime=0;
            strncpy(e->ext,dot+1,63);e->ext[63]='\0';
            continue;
        }
        struct stat st;if(stat(fp,&st)!=0)continue;
        if(count>=cap){cap*=2;entries=realloc(entries,cap*sizeof(Entry));}
        Entry *e=&entries[count++];
        strncpy(e->name,de->d_name,511);e->name[511]='\0';
        strncpy(e->fullpath,fp,4095);e->fullpath[4095]='\0';
        e->is_dir=isd;e->size=isd?0:(long long)st.st_size;
        e->mtime=st.st_mtime;e->ctime=st.st_birthtime;e->atime=st.st_atime;
        char *dot=strrchr(de->d_name,'.');
        strncpy(e->ext,dot?dot+1:"",63);e->ext[63]='\0';
        if(opt_l)lcase(e->name);
    }
    closedir(dh);
    if(!g_re){g_sk=cfg_sort;g_sr=cfg_sort_rev;qsort(entries,count,sizeof(Entry),cmp_e);}
    if(!opt_b&&count>0&&!g_re){
        char cwd[4096];const char *dp=path;
        if(!strcmp(path,".")){getcwd(cwd,sizeof(cwd));dp=cwd;}
        printf("\n Directory of %s\n\n",dp);
    }
    long long df=0,db=0,dd=0; int sl=3;
    if(g_re){
        for(int i=0;i<count;i++){
            Entry *e=&entries[i];
            df++;
            FILE *f=fopen(e->fullpath,"r");
            if(!f)continue;
            char line[8192];int lineno=0;int file_hit=0;
            while(fgets(line,sizeof(line),f)){
                lineno++;
                int hit=0;
                if(g_plain){hit=(strcasestr(line,g_plain_text)!=NULL);}
                else{hit=(regexec(g_re,line,0,NULL,0)==0);}
                if(hit){
                    char *nl=strchr(line,'\n');if(nl)*nl='\0';
                    printf("%s:%d:%s\n",e->fullpath,lineno,line);
                    g_total_matches++;file_hit=1;
                }
            }
            fclose(f);
            if(file_hit)g_matched_files++;
        }
    } else if(opt_w){
        int col=0;
        for(int i=0;i<count;i++){
            Entry *e=&entries[i];char tag[80];
            if(e->is_dir)snprintf(tag,sizeof(tag),"[%s]",e->name);
            else snprintf(tag,sizeof(tag),"%s",e->name);
            printf("%-18s ",tag);
            if(++col==5){printf("\n");col=0;sl++;}
            if(opt_p&&sl>=23){fprintf(stderr,"-- more --\n");getchar();sl=0;}
        }
        if(col)printf("\n");
    } else {
        for(int i=0;i<count;i++){
            Entry *e=&entries[i];
            if(opt_b){printf("%s\n",opt_s?e->fullpath:e->name);}
            else{
                char pfx[72]="";
                if(cfg_show_date||cfg_show_time){
                    char db2[20]="",tb[12]="";struct tm *tm=localtime(&e->mtime);
                    if(cfg_show_date)strftime(db2,sizeof(db2),"%m/%d/%Y",tm);
                    if(cfg_show_time)strftime(tb,sizeof(tb),"  %I:%M %p",tm);
                    snprintf(pfx,sizeof(pfx),"%s%s  ",db2,tb);
                }
                if(e->is_dir){printf("%s<DIR>          %s\n",pfx,e->name);}
                else{
                    char szb[32];fmt_size(e->size,szb,sizeof(szb));
                    if(opt_q){char own[64];struct passwd *pw;struct stat qs;
                        stat(e->fullpath,&qs);pw=getpwuid(qs.st_uid);
                        printf("%s%14s  %-14s  %s\n",pfx,szb,pw?pw->pw_name:"?",e->name);
                    }else printf("%s%14s  %s\n",pfx,szb,e->name);
                }
                sl++;if(opt_p&&sl>=23){fprintf(stderr,"-- more --\n");getchar();sl=0;}
            }
            if(e->is_dir)dd++;else{df++;db+=e->size;}
        }
    }
    grand_files+=df;grand_bytes+=db;grand_dirs+=dd;
    if(!opt_b&&!opt_s&&count>0&&!g_re){
        char fb[32],bb[32],d2[32];
        printf("%18s File(s)  %s\n",fmt_count(df,fb,sizeof(fb)),fmt_size(db,bb,sizeof(bb)));
        struct statvfs vfs;
        if(statvfs(path,&vfs)==0){
            long long fr=(long long)vfs.f_bavail*(long long)vfs.f_frsize;char frb[32];
            printf("%18s Dir(s)   %s free\n",fmt_count(dd,d2,sizeof(d2)),fmt_size(fr,frb,sizeof(frb)));
        }
    }
    for(int i=0;i<scount;i++){list_dir(subdirs[i],pattern,level+1);free(subdirs[i]);}
    free(subdirs);free(entries);
}

int cmd_dir(int argc,char *argv[]){
    opt_s=opt_b=opt_l=opt_w=opt_p=opt_q=opt_i=0;opt_a=0;
    grand_files=grand_bytes=grand_dirs=0;
    const char *path=".";const char *pattern=NULL;int from_home=0;
    for(int i=1;i<argc;i++){
        char *a=argv[i];
        if(a[0]=='-' || (a[0]=='/' && strchr(a+1,'/')==NULL && (isalpha((unsigned char)a[1]) || a[1]=='?') && (a[2]=='\0' || a[2]==':'))){
            char sw[64];strncpy(sw,a+1,63);sw[63]='\0';
            char swu[64];strncpy(swu,sw,63);
            for(int j=0;swu[j];j++)swu[j]=toupper((unsigned char)swu[j]);
            if(!strcmp(swu,"?")){db_help(NULL,"DIR");return 0;}
            else if(!strcmp(swu,"S"))opt_s=1;
            else if(!strcmp(swu,"B"))opt_b=1;
            else if(!strcmp(swu,"L")){
                opt_l=1;pattern=NULL;
                g_search[0]='\0';g_search_set=0;
                int si=0;
                while(i+1<argc&&argv[i+1][0]!='/'&&argv[i+1][0]!='-'){
                    if(si>0){g_search[si++]=' ';}
                    int len=strlen(argv[i+1]);
                    if(si+len<1023){strcpy(g_search+si,argv[i+1]);si+=len;}
                    i++;
                }
                if(si>0){g_search[si]='\0';g_search_set=1;}
            }
            else if(!strcmp(swu,"W"))opt_w=1;
            else if(!strcmp(swu,"P"))opt_p=1;
            else if(!strcmp(swu,"Q"))opt_q=1;
            else if(!strcmp(swu,"I"))opt_i=1;
            else if(!strcmp(swu,"R")){from_home=1;opt_s=1;}
            else if(!strcmp(swu,"C"))cfg_thousand=1;
            else if(!strcmp(swu,"-C"))cfg_thousand=0;
            else if(!strncmp(swu,"A",1)){
                char *col=strchr(sw,':');
                char attr=col?toupper((unsigned char)col[1]):'H';
                if(col&&col[1]=='-')attr='d';
                opt_a=attr;
            }
            else if(!strncmp(swu,"O",1)){
                char *col=strchr(sw,':');
                if(col){
                    if(col[1]=='-'){cfg_sort=toupper((unsigned char)col[2]);cfg_sort_rev=1;}
                    else           {cfg_sort=toupper((unsigned char)col[1]);cfg_sort_rev=0;}
                }else{cfg_sort='N';cfg_sort_rev=0;}
            }
            else if(!strncmp(swu,"X",1)){
                char *col=strchr(sw,':');
                if(col&&user_skip_count<48)strncpy(user_skip[user_skip_count++],col+1,255);
            }
            else{fprintf(stderr,"  Unknown switch: %s\n",a);return 1;}
        }
        else if(strchr(a,'*')||strchr(a,'?'))pattern=a;
        else path=a;
    }
    if(from_home){const char *h=getenv("HOME");path=h?h:"/Users";}
    if(!opt_b&&!g_re){
        char cwd[4096];
        const char *dp=(!strcmp(path,".")&&getcwd(cwd,sizeof(cwd)))?cwd:path;
        printf("\n Volume: macOS  |  Path: %s\n",dp);
    }
    if(opt_l&&g_search_set){
        int has_regex=0;
        for(int s=0;g_search[s];s++){if(strchr(".^$*+?()[]{}|\\",g_search[s])){has_regex=1;break;}}
        regex_t re;
        if(has_regex){
            char esc[2048];int ei=0;
            for(int s=0;g_search[s]&&ei<2040;s++){
                if(strchr(".^$*+?()[]{}|\\",g_search[s])){if(ei<2040)esc[ei++]='\\';}
                esc[ei++]=g_search[s];
            }
            esc[ei]='\0';
            if(regcomp(&re,esc,REG_EXTENDED|REG_NOSUB)!=0){
                fprintf(stderr,"  DIR /L: invalid pattern: %s\n",g_search);return 1;
            }
            g_re=&re;g_plain=0;
        } else {
            strncpy(g_plain_text,g_search,1023);g_plain_text[1023]='\0';
            g_plain=1;
            g_re=(regex_t*)1;
        }
        list_dir(path,NULL,0);
        if(has_regex)regfree(&re);
        g_re=NULL;g_plain=0;
        printf("\n     %d match(es) in %d file(s).\n\n",g_total_matches,g_matched_files);
    } else {
        list_dir(path,pattern,0);
        if(!opt_b&&opt_s){
            if(grand_files==0&&pattern){printf("\n     File Not Found\n\n");}
            else{
                char fb[32],bb[32],d2[32];
                printf("\n     Total Files Listed:\n");
                printf("%18s File(s)  %s\n",fmt_count(grand_files,fb,sizeof(fb)),fmt_size(grand_bytes,bb,sizeof(bb)));
                printf("%18s Dir(s)\n",fmt_count(grand_dirs,d2,sizeof(d2)));
                struct statvfs vfs;
                if(statvfs(path,&vfs)==0){
                    long long fr=(long long)vfs.f_bavail*(long long)vfs.f_frsize;char frb[32];
                    printf("                   %s free\n",fmt_size(fr,frb,sizeof(frb)));
                }
            }
        }
    }
    return 0;
}

static int del_one(const char *fp,int quiet,int *cnt){
    if(!quiet){
        printf("  Delete: %s ? [Y/N] ",fp);fflush(stdout);
        char ch=getchar();while(getchar()!='\n'){}
        if(ch!='y'&&ch!='Y')return 0;
    }
    if(remove(fp)==0){(*cnt)++;return 1;}
    fprintf(stderr,"  Cannot delete %s: %s\n",fp,strerror(errno));
    return 0;
}
static void del_scan(const char *path,const char *pattern,int recurse,int quiet,int *cnt){
    DIR *dh=opendir(path);if(!dh)return;
    struct dirent *de;
    while((de=readdir(dh))!=NULL){
        if(!strcmp(de->d_name,".")||!strcmp(de->d_name,".."))continue;
        char fp[4096];snprintf(fp,sizeof(fp),"%s/%s",path,de->d_name);
        int isd=(de->d_type==DT_DIR);
        if(de->d_type==DT_UNKNOWN){struct stat s;if(stat(fp,&s)==0)isd=S_ISDIR(s.st_mode);}
        if(isd){if(recurse)del_scan(fp,pattern,recurse,quiet,cnt);}
        else{if(!pattern||fnci(pattern,de->d_name)==0)del_one(fp,quiet,cnt);}
    }
    closedir(dh);
}

int cmd_del(int argc,char *argv[]){
    const char *path=".";const char *pattern=NULL;
    int recurse=0,quiet=0;
    for(int i=1;i<argc;i++){
        char *a=argv[i];
        if(a[0]=='-' || (a[0]=='/' && strchr(a+1,'/')==NULL && (isalpha((unsigned char)a[1]) || a[1]=='?') && (a[2]=='\0' || a[2]==':'))){
            char sw[16];strncpy(sw,a+1,15);sw[15]='\0';
            char swu[16];strncpy(swu,sw,15);
            for(int j=0;swu[j];j++)swu[j]=toupper((unsigned char)swu[j]);
            if(!strcmp(swu,"S"))recurse=1;
            else if(!strcmp(swu,"F")||!strcmp(swu,"Q"))quiet=1;
            else if(!strcmp(swu,"?")){db_help(NULL,"DEL");return 0;}
        }
        else if(strchr(a,'*')||strchr(a,'?'))pattern=a;
        else path=a;
    }
    if(!pattern&&!strcmp(path,".")){fprintf(stderr,"DEL: specify a pattern or filename.\n");return 1;}
    if(!pattern){
        int cnt=0;del_one(path,quiet,&cnt);
        printf("  %d file(s) deleted.\n",cnt);return 0;
    }
    if(!quiet){
        printf("  Delete all '%s' in %s%s? [Y/N] ",pattern,path,recurse?" (recursive)":"");
        fflush(stdout);char ch=getchar();while(getchar()!='\n'){}
        if(ch!='y'&&ch!='Y'){printf("  Cancelled.\n");return 0;}
        quiet=1;
    }
    int cnt=0;del_scan(path,pattern,recurse,quiet,&cnt);
    printf("  %d file(s) deleted.\n",cnt);
    return 0;
}

int cmd_cd(int argc,char *argv[]){
    for(int i=1;i<argc;i++){
        if(!strcmp(argv[i],"/?")||!strcmp(argv[i],"-?")){db_help(NULL,"CD");return 0;}
    }
    if(argc<2){
        char cwd[4096];
        if(getcwd(cwd,sizeof(cwd))) printf("%s\n",cwd);
        return 0;
    }
    if(chdir(argv[1])==0) return 0;
    fprintf(stderr,"  CD: %s\n",strerror(errno));
    return 1;
}

int cmd_md(int argc,char *argv[]){
    if(argc<2){fprintf(stderr,"MD: specify directory name.\n");return 1;}
    for(int i=1;i<argc;i++){
        if(!strcmp(argv[i],"/?")||!strcmp(argv[i],"-?")){db_help(NULL,"MD");return 0;}
    }
    int ok=0;
    for(int i=1;i<argc;i++){
        if(argv[i][0]=='/')continue;
        char c2[1024];snprintf(c2,sizeof(c2),"mkdir -p '%s'",argv[i]);
        if(system(c2)==0){printf("  Created: %s\n",argv[i]);ok++;}
        else fprintf(stderr,"  Failed: %s\n",argv[i]);
    }
    return ok>0?0:1;
}

int cmd_rd(int argc,char *argv[]){
    if(argc<2){fprintf(stderr,"RD: specify directory.\n");return 1;}
    int recurse=0;
    for(int i=1;i<argc;i++){
        char *a=argv[i];
        if(a[0]=='-' || (a[0]=='/' && strchr(a+1,'/')==NULL && (isalpha((unsigned char)a[1]) || a[1]=='?') && (a[2]=='\0' || a[2]==':'))){
            char sw[8];strncpy(sw,a+1,7);sw[7]='\0';
            for(int j=0;sw[j];j++)sw[j]=toupper((unsigned char)sw[j]);
            if(!strcmp(sw,"S"))recurse=1;
            else if(!strcmp(sw,"?")){db_help(NULL,"RD");return 0;}
        }
    }
    int ok=0;
    for(int i=1;i<argc;i++){
        if(argv[i][0]=='-' || (argv[i][0]=='/' && strchr(argv[i]+1,'/')==NULL && (isalpha((unsigned char)argv[i][1]) || argv[i][1]=='?') && (argv[i][2]=='\0' || argv[i][2]==':')))continue;
        if(recurse){
            printf("  Remove '%s' and ALL contents? [Y/N] ",argv[i]);fflush(stdout);
            char ch=getchar();while(getchar()!='\n'){}
            if(ch!='y'&&ch!='Y'){printf("  Skipped.\n");continue;}
            char c2[1024];snprintf(c2,sizeof(c2),"rm -rf '%s'",argv[i]);
            if(system(c2)==0){printf("  Removed: %s\n",argv[i]);ok++;}
            else fprintf(stderr,"  Failed: %s\n",argv[i]);
        } else {
            if(rmdir(argv[i])==0){printf("  Removed: %s\n",argv[i]);ok++;}
            else fprintf(stderr,"  Cannot remove %s: %s\n",argv[i],strerror(errno));
        }
    }
    return ok>0?0:1;
}

int cmd_move(int argc,char *argv[]){
    for(int i=1;i<argc;i++){
        if(!strcmp(argv[i],"/?")||!strcmp(argv[i],"-?")){db_help(NULL,"MOVE");return 0;}
    }
    const char *src=NULL,*dst=NULL;
    for(int i=1;i<argc;i++){
        if(argv[i][0]!='/'&&argv[i][0]!='-'){
            if(!src)src=argv[i]; else dst=argv[i];
        }
    }
    if(!src||!dst){fprintf(stderr,"MOVE: source destination\n");return 1;}
    if(rename(src,dst)==0){printf("  Moved: %s  ->  %s\n",src,dst);return 0;}
    char c2[2048];snprintf(c2,sizeof(c2),"cp -a '%s' '%s' && rm -rf '%s'",src,dst,src);
    if(system(c2)==0){printf("  Moved: %s  ->  %s\n",src,dst);return 0;}
    fprintf(stderr,"  Move failed: %s\n",strerror(errno));return 1;
}

int cmd_copy(int argc,char *argv[]){
    const char *src=NULL,*dst=NULL;int over=0;
    for(int i=1;i<argc;i++){
        if(argv[i][0]=='/'||argv[i][0]=='-'){
            char sw[8];strncpy(sw,argv[i]+1,7);
            for(int j=0;sw[j];j++)sw[j]=toupper((unsigned char)sw[j]);
            if(!strcmp(sw,"Y"))over=1;
            else if(!strcmp(sw,"?")){db_help(NULL,"COPY");return 0;}
        } else {
            if(!src)src=argv[i]; else dst=argv[i];
        }
    }
    if(!src||!dst){fprintf(stderr,"COPY source destination [/Y]\n");return 1;}
    struct stat st;
    if(!over&&stat(dst,&st)==0){
        printf("  Overwrite '%s'? [Y/N] ",dst);fflush(stdout);
        char ch=getchar();while(getchar()!='\n'){}
        if(ch!='y'&&ch!='Y'){printf("  Cancelled.\n");return 0;}
    }
    char c2[2048];snprintf(c2,sizeof(c2),"cp -a '%s' '%s'",src,dst);
    if(system(c2)==0){printf("  Copied: %s  ->  %s\n",src,dst);return 0;}
    fprintf(stderr,"  Copy failed.\n");return 1;
}

int cmd_type(int argc,char *argv[]){
    if(argc<2){fprintf(stderr,"TYPE: specify filename.\n");return 1;}
    for(int i=1;i<argc;i++){
        if(!strcmp(argv[i],"/?")||!strcmp(argv[i],"-?")){db_help(NULL,"TYPE");return 0;}
    }
    for(int i=1;i<argc;i++){
        if(argv[i][0]=='/')continue;
        FILE *f=fopen(argv[i],"r");
        if(!f){fprintf(stderr,"  Cannot open: %s\n",argv[i]);continue;}
        printf("\n--- %s ---\n",argv[i]);
        char buf[4096];size_t n;
        while((n=fread(buf,1,sizeof(buf),f))>0)fwrite(buf,1,n,stdout);
        fclose(f);
    }
    return 0;
}

/* ============== WHERE — find files by pattern (like where /R) ============== */
static void where_scan(const char *path,const char *pattern,int recurse,int *count){
    DIR *dh=opendir(path);
    if(!dh)return;
    struct dirent *de;
    while((de=readdir(dh))!=NULL){
        if(!strcmp(de->d_name,".")||!strcmp(de->d_name,".."))continue;
        int isd=(de->d_type==DT_DIR);
        int islink=(de->d_type==DT_LNK);
        if(de->d_type==DT_UNKNOWN){
            char fp2[4096];snprintf(fp2,sizeof(fp2),"%s/%s",path,de->d_name);
            struct stat s2;if(lstat(fp2,&s2)==0){isd=S_ISDIR(s2.st_mode);islink=S_ISLNK(s2.st_mode);}
        }
        if(islink&&recurse)continue;
        if(isd&&recurse&&should_skip(de->d_name))continue;
        char fp[4096];snprintf(fp,sizeof(fp),"%s/%s",path,de->d_name);
        if(isd&&recurse){where_scan(fp,pattern,recurse,count);continue;}
        if(!pattern||fnci(pattern,de->d_name)==0){
            printf("%s\n",fp);(*count)++;
        }
    }
    closedir(dh);
}

int cmd_where(int argc,char *argv[]){
    const char *pattern=NULL;const char *path=".";int recurse=0;int from_home=0;
    for(int i=1;i<argc;i++){
        char *a=argv[i];
        if(a[0]=='/'||a[0]=='-'){
            char sw[16];strncpy(sw,a+1,15);sw[15]='\0';
            for(int j=0;sw[j];j++)sw[j]=toupper((unsigned char)sw[j]);
            if(!strcmp(sw,"S"))recurse=1;
            else if(!strcmp(sw,"R"))from_home=1;
            else if(!strcmp(sw,"?")){db_help(NULL,"WHERE");return 0;}
        }else if(strchr(a,'*')||strchr(a,'?'))pattern=a;
        else path=a;
    }
    if(from_home){const char *h=getenv("HOME");path=h?h:"/Users";recurse=1;}
    if(!pattern){fprintf(stderr,"WHERE: specify a pattern (e.g. *.py)\n");return 1;}
    int count=0;
    where_scan(path,pattern,recurse,&count);
    fprintf(stderr,"\n  %d file(s) found.\n",count);
    return 0;
}

/* ============== GREP / FINDSTR — search inside files ============== */
static int grep_file(const char *filepath,const char *pattern,regex_t *re,int show_line,int show_name,int *matches){
    FILE *f=fopen(filepath,"r");
    if(!f)return 0;
    char line[8192];int lineno=0;int file_matched=0;
    while(fgets(line,sizeof(line),f)){
        lineno++;
        int r=regexec(re,line,0,NULL,0);
        if(r==0){
            (*matches)++;file_matched=1;
            char *nl=strchr(line,'\n');if(nl)*nl='\0';
            if(show_name&&show_line)printf("%s:%d:%s\n",filepath,lineno,line);
            else if(show_name)printf("%s:%s\n",filepath,line);
            else if(show_line)printf("%d:%s\n",lineno,line);
            else printf("%s\n",line);
        }
    }
    fclose(f);
    return file_matched;
}

static void grep_scan(const char *path,const char *filepattern,const char *searchpattern,regex_t *re,int recurse,int *matches,int *files_matched){
    DIR *dh=opendir(path);
    if(!dh)return;
    struct dirent *de;
    while((de=readdir(dh))!=NULL){
        if(!strcmp(de->d_name,".")||!strcmp(de->d_name,".."))continue;
        int isd=(de->d_type==DT_DIR);
        int islink=(de->d_type==DT_LNK);
        if(de->d_type==DT_UNKNOWN){
            char fp2[4096];snprintf(fp2,sizeof(fp2),"%s/%s",path,de->d_name);
            struct stat s2;if(lstat(fp2,&s2)==0){isd=S_ISDIR(s2.st_mode);islink=S_ISLNK(s2.st_mode);}
        }
        if(islink&&recurse)continue;
        if(isd&&recurse&&should_skip(de->d_name))continue;
        char fp[4096];snprintf(fp,sizeof(fp),"%s/%s",path,de->d_name);
        if(isd&&recurse){grep_scan(fp,filepattern,searchpattern,re,recurse,matches,files_matched);continue;}
        if(isd)continue;
        if(filepattern&&fnci(filepattern,de->d_name)!=0)continue;
        if(grep_file(fp,searchpattern,re,1,1,matches))(*files_matched)++;
    }
    closedir(dh);
}

int cmd_grep(int argc,char *argv[]){
    const char *searchpattern=NULL;const char *filepattern=NULL;
    const char *path=".";int recurse=0;int from_home=0;int case_insensitive=REG_EXTENDED;
    for(int i=1;i<argc;i++){
        char *a=argv[i];
        if(a[0]=='/'||a[0]=='-'){
            char sw[16];strncpy(sw,a+1,15);sw[15]='\0';
            for(int j=0;sw[j];j++)sw[j]=toupper((unsigned char)sw[j]);
            if(!strcmp(sw,"S"))recurse=1;
            else if(!strcmp(sw,"R"))from_home=1;
            else if(!strcmp(sw,"I"))case_insensitive|=REG_ICASE;
            else if(!strcmp(sw,"?")){db_help(NULL,"GREP");return 0;}
        }else{
            if(!searchpattern)searchpattern=a;
            else if(strchr(a,'*')||strchr(a,'?'))filepattern=a;
            else path=a;
        }
    }
    if(from_home){const char *h=getenv("HOME");path=h?h:"/Users";recurse=1;}
    if(!searchpattern){fprintf(stderr,"GREP: specify a search pattern.\n");return 1;}
    regex_t re;
    if(regcomp(&re,searchpattern,case_insensitive)!=0){
        fprintf(stderr,"GREP: invalid regex: %s\n",searchpattern);return 1;
    }
    int matches=0,files_matched=0;
    grep_scan(path,filepattern,searchpattern,&re,recurse,&matches,&files_matched);
    regfree(&re);
    fprintf(stderr,"\n  %d match(es) in %d file(s).\n",matches,files_matched);
    return 0;
}

/* ======================== INGEST ENGINE ======================== */

static const char *INGEST_TABLES[] = {
    "python_files","swift_files","c_files","csharp_files",
    "json_files","yaml_files","markdown_files"
};

static const char *INGEST_EXTS[] = {
    ".py",".swift",".c",".h",".cpp",".cs",".json",".yml",".yaml",".md"
};

static const char *INGEST_EXT_TABLE[] = {
    "python_files","swift_files","c_files","c_files","c_files",
    "csharp_files","json_files","yaml_files","yaml_files","markdown_files"
};

#define INGEST_NUM_EXTS 10
#define INGEST_NUM_TABLES 7
#define INGEST_MAX_FILE (50*1024*1024)

typedef struct {
    char mysql_host[64]; char mysql_user[32]; char mysql_pass[64];
    char mysql_db[32]; int mysql_port;
    char start_path[4096]; int max_file_mb;
    char skip_dirs[2048];
} IngestConfig;

static IngestConfig g_ingest_cfg;
static int g_ingest_cfg_loaded=0;

static void ingest_load_config(IngestConfig *cfg) {
    memset(cfg,0,sizeof(*cfg));
    sqlite3 *db=db_open();
    if(!db) {
        strcpy(cfg->mysql_host,"localhost");
        strcpy(cfg->mysql_user,"root");
        strcpy(cfg->mysql_db,"CODEBASE");
        strcpy(cfg->start_path,"/Users/Shared");
        cfg->max_file_mb=50;
        strcpy(cfg->skip_dirs,".git,.svn,venv,env,__pycache__,site-packages,node_modules,Trash,build,DerivedData,Pods,Caches,Frameworks,dist,out,coverage,.next,.nuxt,.turbo,.gradle");
        return;
    }
    /* Merge persisted config from ~/.wcmd_cfg.db */
    const char *h=getenv("HOME");
    if(h) {
        char cfg_path[512];
        snprintf(cfg_path,sizeof(cfg_path),"%s/.wcmd_cfg.db",h);
        sqlite3 *pdb=NULL;
        if(sqlite3_open(cfg_path,&pdb)==SQLITE_OK&&pdb) {
            sqlite3_stmt *pst;
            if(sqlite3_prepare_v2(pdb,"SELECT key,value FROM system_config",-1,&pst,NULL)==SQLITE_OK) {
                sqlite3_stmt *up;
                sqlite3_prepare_v2(db,"INSERT OR REPLACE INTO system_config (key,value,description) VALUES (?,?,?)",-1,&up,NULL);
                while(sqlite3_step(pst)==SQLITE_ROW) {
                    const char *k=(const char*)sqlite3_column_text(pst,0);
                    const char *v=(const char*)sqlite3_column_text(pst,1);
                    if(k&&v) {
                        sqlite3_bind_text(up,1,k,-1,SQLITE_STATIC);
                        sqlite3_bind_text(up,2,v,-1,SQLITE_STATIC);
                        sqlite3_bind_text(up,3,"from persisted",-1,SQLITE_STATIC);
                        sqlite3_step(up); sqlite3_reset(up);
                    }
                }
                sqlite3_finalize(up);
                sqlite3_finalize(pst);
            }
            sqlite3_close(pdb);
        }
    }
    sqlite3_stmt *st;
    const char *sql="SELECT value FROM system_config WHERE key=?";
#define SC(key,field,dflt) \
    if(sqlite3_prepare_v2(db,sql,-1,&st,NULL)==SQLITE_OK) { \
        sqlite3_bind_text(st,1,key,-1,SQLITE_STATIC); \
        if(sqlite3_step(st)==SQLITE_ROW){const char*v=(const char*)sqlite3_column_text(st,0);if(v)strncpy(field,v,sizeof(field)-1);} else strncpy(field,dflt,sizeof(field)-1); \
        field[sizeof(field)-1]=0; \
        sqlite3_finalize(st); \
    } else { strncpy(field,dflt,sizeof(field)-1); field[sizeof(field)-1]=0; }
    SC("ingest_mysql_host",cfg->mysql_host,"localhost");
    SC("ingest_mysql_user",cfg->mysql_user,"root");
    SC("ingest_mysql_pass",cfg->mysql_pass,"");
    SC("ingest_mysql_db",cfg->mysql_db,"CODEBASE");
    SC("ingest_start_path",cfg->start_path,"/Users");
    SC("ingest_skip_dirs",cfg->skip_dirs,".git,.svn,venv,env,__pycache__,site-packages,node_modules,Library,Trash,build,DerivedData,Pods,Caches,lib,Frameworks,dist,out,coverage,.next,.nuxt,.turbo,.gradle,opt,usr,bin,sbin");
#undef SC
    if(sqlite3_prepare_v2(db,sql,-1,&st,NULL)==SQLITE_OK) {
        sqlite3_bind_text(st,1,"ingest_mysql_port",-1,SQLITE_STATIC);
        if(sqlite3_step(st)==SQLITE_ROW){const char*v=(const char*)sqlite3_column_text(st,0);cfg->mysql_port=v?atoi(v):0;} else cfg->mysql_port=0;
        sqlite3_finalize(st);
    } else cfg->mysql_port=0;
    if(sqlite3_prepare_v2(db,sql,-1,&st,NULL)==SQLITE_OK) {
        sqlite3_bind_text(st,1,"ingest_max_file_mb",-1,SQLITE_STATIC);
        if(sqlite3_step(st)==SQLITE_ROW){const char*v=(const char*)sqlite3_column_text(st,0);cfg->max_file_mb=v?atoi(v):10;} else cfg->max_file_mb=10;
        sqlite3_finalize(st);
    } else cfg->max_file_mb=10;
    if(cfg->max_file_mb<1) cfg->max_file_mb=1;
    if(cfg->max_file_mb>1024) cfg->max_file_mb=1024;
    sqlite3_close(db);
}

static int ingest_skip_check(const char *name, const char *skip_csv) {
    if(!name||!name[0]) return 1;
    if(name[0]=='.') return 1;
    if(!skip_csv||!skip_csv[0]) return 0;
    char tmp[2048]; strncpy(tmp,skip_csv,sizeof(tmp)-1); tmp[sizeof(tmp)-1]=0;
    char *tok=strtok(tmp,",");
    while(tok) {
        while(*tok==' ')tok++;
        if(*tok&&strcmp(name,tok)==0) return 1;
        tok=strtok(NULL,",");
    }
    return 0;
}

static int ingest_excluded(const char *n) {
    if(!g_ingest_cfg_loaded) { ingest_load_config(&g_ingest_cfg); g_ingest_cfg_loaded=1; }
    return ingest_skip_check(n, g_ingest_cfg.skip_dirs);
}

static const char *ingest_table(const char *ext) {
    for(int i=0;i<INGEST_NUM_EXTS;i++) if(!strcmp(ext,INGEST_EXTS[i])) return INGEST_EXT_TABLE[i];
    return NULL;
}

static void ingest_sha1(const char *s,long len,char out[41]) {
    if(!s||len<=0) { strcpy(out,"0000000000000000000000000000000000000000"); return; }
    unsigned char h[20]; SHA1((unsigned char*)s,(size_t)len,h);
    for(int i=0;i<20;i++) sprintf(out+i*2,"%02x",h[i]);
    out[40]=0;
}

static int ingest_get_path_id(MYSQL *conn, const char *fpath) {
    if(!conn||!fpath||!fpath[0]) return 1;
    char dir[4096];
    strncpy(dir, fpath, sizeof(dir)-1);
    dir[sizeof(dir)-1] = 0;
    char *slash = strrchr(dir, '/');
    if(!slash) return 1;
    *slash = 0;
    if(!dir[0]) { dir[0]='/'; dir[1]=0; }
    char esc[8193];
    unsigned long el = mysql_real_escape_string(conn, esc, dir, (unsigned long)strlen(dir));
    char q[9000];
    snprintf(q, sizeof(q), "SELECT id FROM directories WHERE path='%s' LIMIT 1", esc);
    if(mysql_query(conn, q) == 0) {
        MYSQL_RES *r = mysql_store_result(conn);
        if(r) {
            MYSQL_ROW row = mysql_fetch_row(r);
            if(row && row[0]) { int id = atoi(row[0]); mysql_free_result(r); return id; }
            mysql_free_result(r);
        }
    }
    char dname[512];
    const char *base = strrchr(dir, '/');
    strncpy(dname, base ? base+1 : dir, sizeof(dname)-1);
    dname[sizeof(dname)-1] = 0;
    char esc_name[1025];
    unsigned long nl = mysql_real_escape_string(conn, esc_name, dname, (unsigned long)strlen(dname));
    snprintf(q, sizeof(q), "INSERT INTO directories (path,name) VALUES ('%s','%s')", esc, esc_name);
    if(mysql_query(conn, q) == 0) return (int)mysql_insert_id(conn);
    return 1;
}

static MYSQL *ingest_connect(void) {
    if(!g_ingest_cfg_loaded) { ingest_load_config(&g_ingest_cfg); g_ingest_cfg_loaded=1; }
    MYSQL *c=mysql_init(NULL);
    if(!c) return NULL;
    if(!mysql_real_connect(c,g_ingest_cfg.mysql_host,g_ingest_cfg.mysql_user,g_ingest_cfg.mysql_pass,g_ingest_cfg.mysql_db,g_ingest_cfg.mysql_port,NULL,0)) {
        fprintf(stderr,"INGEST DB ERROR: %s\n",mysql_error(c));
        mysql_close(c); return NULL;
    }
    return c;
}

static int ingest_schema(MYSQL *conn) {
    const char *sql[]={
        "CREATE TABLE IF NOT EXISTS directories (id INT AUTO_INCREMENT PRIMARY KEY,path TEXT,name VARCHAR(500),parent_id INT,INDEX idx_path(path(255)))",
        "CREATE TABLE IF NOT EXISTS python_files (id INT AUTO_INCREMENT PRIMARY KEY,path_id INT,filename VARCHAR(500),full_path TEXT,content LONGTEXT,file_size BIGINT,line_count INT,INDEX idx_fn(filename),INDEX idx_pid(path_id))",
        "CREATE TABLE IF NOT EXISTS swift_files LIKE python_files",
        "CREATE TABLE IF NOT EXISTS c_files LIKE python_files",
        "CREATE TABLE IF NOT EXISTS csharp_files LIKE python_files",
        "CREATE TABLE IF NOT EXISTS json_files LIKE python_files",
        "CREATE TABLE IF NOT EXISTS yaml_files LIKE python_files",
        "CREATE TABLE IF NOT EXISTS markdown_files LIKE python_files",
        "CREATE TABLE IF NOT EXISTS file_checkpoint (path_hash CHAR(40) PRIMARY KEY,full_path TEXT,status ENUM('done','failed') DEFAULT 'done',mtime BIGINT DEFAULT 0,content_hash CHAR(40),updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP)",
        "CREATE TABLE IF NOT EXISTS ingestion_jobs (id BIGINT AUTO_INCREMENT PRIMARY KEY,file_path TEXT,file_name VARCHAR(500),mtime BIGINT,status ENUM('pending','processing','done','failed') DEFAULT 'pending',worker_id INT,attempts INT DEFAULT 0,error_msg TEXT,updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,INDEX idx_status(status))",
        "CREATE TABLE IF NOT EXISTS ingest_solutions (id INT AUTO_INCREMENT PRIMARY KEY,problem_pattern VARCHAR(255) NOT NULL,solution_action VARCHAR(255) NOT NULL,solution_detail TEXT,applied_count INT DEFAULT 0,created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,UNIQUE KEY uniq_pattern (problem_pattern))",
        NULL
    };
    for(int i=0;sql[i];i++) if(mysql_query(conn,sql[i])) {fprintf(stderr,"SCHEMA: %s\n",mysql_error(conn));return 1;}
    return 0;
}

static void ingest_scan_jobs(MYSQL *conn,const char *dir,int *scanned,int *skipped) {
    if(!conn||!dir||!dir[0]) return;
    DIR *d=opendir(dir);
    if(!d) return;
    struct dirent *e;
    const char *stmt_sql="INSERT INTO ingestion_jobs (file_path,file_name,mtime,status) VALUES (?,?,?,'pending')";
    MYSQL_STMT *s=mysql_stmt_init(conn);
    if(!s) { closedir(d); return; }
    if(mysql_stmt_prepare(s,stmt_sql,strlen(stmt_sql))!=0) { mysql_stmt_close(s); closedir(d); return; }
    while((e=readdir(d))) {
        if(!e->d_name[0]) continue;
        if(!strcmp(e->d_name,".")||!strcmp(e->d_name,"..")) continue;
        if(ingest_excluded(e->d_name)) continue;
        char full[4096];
        int n=snprintf(full,sizeof(full),"%s/%s",dir,e->d_name);
        if(n<0||n>=(int)sizeof(full)) continue;
        struct stat st;
        if(stat(full,&st)==-1) continue;
        if(S_ISDIR(st.st_mode)) { ingest_scan_jobs(conn,full,scanned,skipped); continue; }
        if(!S_ISREG(st.st_mode)) continue;
        const char *ext=strrchr(e->d_name,'.');
        if(!ext||!ingest_table(ext)) {(*skipped)++;continue;}
        MYSQL_BIND b[3]; memset(b,0,sizeof(b));
        unsigned long pl=strlen(full),nl=strlen(e->d_name);
        long long mt=(long long)st.st_mtime;
        b[0].buffer_type=MYSQL_TYPE_STRING;b[0].buffer=full;b[0].buffer_length=pl;b[0].length=&pl;
        b[1].buffer_type=MYSQL_TYPE_STRING;b[1].buffer=e->d_name;b[1].buffer_length=nl;b[1].length=&nl;
        b[2].buffer_type=MYSQL_TYPE_LONGLONG;b[2].buffer=&mt;
        if(mysql_stmt_bind_param(s,b)!=0) continue;
        if(mysql_stmt_execute(s)!=0) continue;
        (*scanned)++;
    }
    closedir(d); mysql_stmt_close(s);
}

static int ingest_process(MYSQL *conn,int worker_id,int *ingested,int *skipped,int *errors) {
    if(!conn||!ingested||!skipped||!errors) return 1;
    if(!g_ingest_cfg_loaded) { ingest_load_config(&g_ingest_cfg); g_ingest_cfg_loaded=1; }
    long max_file=(long)g_ingest_cfg.max_file_mb*1024*1024;
    if(max_file<1) max_file=INGEST_MAX_FILE;
    const char *claim="SELECT id,file_path,file_name,mtime FROM ingestion_jobs WHERE status='pending' ORDER BY id LIMIT 1 FOR UPDATE SKIP LOCKED";
    char q[8192];
    while(1) {
        if(mysql_query(conn,"START TRANSACTION")) { break; }
        if(mysql_query(conn,claim)) { mysql_query(conn,"ROLLBACK"); break; }
        MYSQL_RES *res=mysql_store_result(conn);
        if(!res||mysql_num_rows(res)==0) { if(res)mysql_free_result(res); mysql_query(conn,"ROLLBACK"); break; }
        MYSQL_ROW row=mysql_fetch_row(res);
        if(!row||!row[0]||!row[1]||!row[2]||!row[3]) {
            if(res)mysql_free_result(res);
            mysql_query(conn,"ROLLBACK");
            break;
        }
        long long job_id=atoll(row[0]);
        const char *fpath=row[1];
        const char *fname=row[2];
        long long mtime=atoll(row[3]);
        unsigned long fpath_len=strlen(fpath);
        unsigned long fname_len=strlen(fname);
        mysql_free_result(res);
        snprintf(q,sizeof(q),"UPDATE ingestion_jobs SET status='processing',worker_id=%d WHERE id=%lld",worker_id,job_id);
        mysql_query(conn,q);
        mysql_query(conn,"COMMIT");

        const char *ext=strrchr(fname,'.');
        if(!ext) {
            char em[512]; snprintf(em,sizeof(em),"No file extension: %s",fname);
            char esc_em[1025]; mysql_real_escape_string(conn,esc_em,em,(unsigned long)strlen(em));
            snprintf(q,sizeof(q),"UPDATE ingestion_jobs SET status='failed',attempts=attempts+1,error_msg='%s' WHERE id=%lld",esc_em,job_id);
            mysql_query(conn,q); (*errors)++; continue;
        }
        const char *table=ingest_table(ext);
        if(!table) {
            char em[512]; snprintf(em,sizeof(em),"Unsupported extension: %s",ext);
            char esc_em[1025]; mysql_real_escape_string(conn,esc_em,em,(unsigned long)strlen(em));
            snprintf(q,sizeof(q),"UPDATE ingestion_jobs SET status='failed',attempts=attempts+1,error_msg='%s' WHERE id=%lld",esc_em,job_id);
            mysql_query(conn,q); (*errors)++; continue;
        }

        char path_hash[41];
        ingest_sha1(fpath,(long)fpath_len,path_hash);
        snprintf(q,sizeof(q),"SELECT 1 FROM file_checkpoint WHERE path_hash='%s' AND mtime=%lld LIMIT 1",path_hash,mtime);
        if(mysql_query(conn,q)) { (*errors)++; continue; }
        MYSQL_RES *cr=mysql_store_result(conn);
        int already=(cr&&mysql_num_rows(cr)>0);
        if(cr)mysql_free_result(cr);
        if(already) {
            snprintf(q,sizeof(q),"UPDATE ingestion_jobs SET status='done' WHERE id=%lld",job_id);
            mysql_query(conn,q); (*skipped)++; continue;
        }

        FILE *f=fopen(fpath,"rb");
        if(!f) {
            char em[512]; snprintf(em,sizeof(em),"Cannot open file (errno %d): %s",errno,fpath);
            char esc_em[1025]; mysql_real_escape_string(conn,esc_em,em,(unsigned long)strlen(em));
            snprintf(q,sizeof(q),"UPDATE ingestion_jobs SET status='failed',attempts=attempts+1,error_msg='%s' WHERE id=%lld",esc_em,job_id);
            mysql_query(conn,q); (*errors)++; continue;
        }
        fseek(f,0,SEEK_END);
        long sz=ftell(f);
        rewind(f);
        if(sz<0||sz>max_file) {
            /* Check if a solution exists for this problem */
            char sol_key[256]; snprintf(sol_key,sizeof(sol_key),"FILE_TOO_LARGE:%ld",(long)max_file);
            char esc_sk[513]; mysql_real_escape_string(conn,esc_sk,sol_key,(unsigned long)strlen(sol_key));
            snprintf(q,sizeof(q),"SELECT solution_action,solution_detail FROM ingest_solutions WHERE problem_pattern='%s'",esc_sk);
            int solved=0;
            if(mysql_query(conn,q)==0) {
                MYSQL_RES *sr=mysql_store_result(conn);
                if(sr&&mysql_num_rows(sr)>0) {
                    MYSQL_ROW srow=mysql_fetch_row(sr);
                    if(srow&&srow[0]&&strcmp(srow[0],"SKIP")==0) {
                        fclose(f);
                        char em[512]; snprintf(em,sizeof(em),"File too large: %ld bytes - skipped per learned solution: %s",sz,srow[1]?srow[1]:"");
                        char esc_em[1025]; mysql_real_escape_string(conn,esc_em,em,(unsigned long)strlen(em));
                        snprintf(q,sizeof(q),"UPDATE ingestion_jobs SET status='done',error_msg='%s' WHERE id=%lld",esc_em,job_id);
                        mysql_query(conn,q);
                        snprintf(q,sizeof(q),"UPDATE ingest_solutions SET applied_count=applied_count+1 WHERE problem_pattern='%s'",esc_sk);
                        mysql_query(conn,q);
                        (*skipped)++; if(sr)mysql_free_result(sr); continue;
                    }
                    if(srow&&srow[0]&&strcmp(srow[0],"RAISE_LIMIT")==0) {
                        long new_max=atol(srow[1]?srow[1]:"0");
                        if(new_max>max_file) max_file=new_max;
                        if(sz<=max_file) solved=1;
                    }
                }
                if(sr)mysql_free_result(sr);
            }
            if(!solved) {
                fclose(f);
                char em[512]; snprintf(em,sizeof(em),"File too large: %ld bytes (max %ld bytes)",sz,max_file);
                char esc_em[1025]; mysql_real_escape_string(conn,esc_em,em,(unsigned long)strlen(em));
                snprintf(q,sizeof(q),"UPDATE ingestion_jobs SET status='failed',attempts=attempts+1,error_msg='%s' WHERE id=%lld",esc_em,job_id);
                mysql_query(conn,q); (*skipped)++; continue;
            }
        }
        char *content=malloc(sz+1);
        if(!content) {
            fclose(f);
            char em[256]; snprintf(em,sizeof(em),"Malloc failed for %ld bytes",sz);
            char esc_em[513]; mysql_real_escape_string(conn,esc_em,em,(unsigned long)strlen(em));
            snprintf(q,sizeof(q),"UPDATE ingestion_jobs SET status='failed',attempts=attempts+1,error_msg='%s' WHERE id=%lld",esc_em,job_id);
            mysql_query(conn,q); (*errors)++; continue;
        }
        size_t rd=fread(content,1,sz,f);
        fclose(f);
        if(rd==0&&sz>0) {
            free(content);
            char em[256]; snprintf(em,sizeof(em),"Read 0 bytes from %ld byte file",sz);
            char esc_em[513]; mysql_real_escape_string(conn,esc_em,em,(unsigned long)strlen(em));
            snprintf(q,sizeof(q),"UPDATE ingestion_jobs SET status='failed',attempts=attempts+1,error_msg='%s' WHERE id=%lld",esc_em,job_id);
            mysql_query(conn,q); (*errors)++; continue;
        }
        content[rd]=0;

        int lines=1;
        for(size_t i=0;i<rd;i++) if(content[i]=='\n') lines++;
        char content_hash[41];
        ingest_sha1(content,(long)rd,content_hash);

        int path_id = ingest_get_path_id(conn, fpath);
        char isql[512];
        snprintf(isql,sizeof(isql),"INSERT INTO %s (path_id,filename,full_path,content,file_size,line_count) VALUES (%d,?,?,?,?,?)",table,path_id);
        MYSQL_STMT *ins=mysql_stmt_init(conn);
        if(!ins) {
            free(content);
            char em[256]; snprintf(em,sizeof(em),"stmt_init failed: %s",mysql_error(conn));
            char esc_em[513]; mysql_real_escape_string(conn,esc_em,em,(unsigned long)strlen(em));
            snprintf(q,sizeof(q),"UPDATE ingestion_jobs SET status='failed',attempts=attempts+1,error_msg='%s' WHERE id=%lld",esc_em,job_id);
            mysql_query(conn,q); (*errors)++; continue;
        }
        if(mysql_stmt_prepare(ins,isql,strlen(isql))!=0) {
            mysql_stmt_close(ins); free(content);
            char em[512]; snprintf(em,sizeof(em),"stmt_prepare failed: %s",mysql_stmt_error(ins));
            char esc_em[1025]; mysql_real_escape_string(conn,esc_em,em,(unsigned long)strlen(em));
            snprintf(q,sizeof(q),"UPDATE ingestion_jobs SET status='failed',attempts=attempts+1,error_msg='%s' WHERE id=%lld",esc_em,job_id);
            mysql_query(conn,q); (*errors)++; continue;
        }
        MYSQL_BIND ib[5]; memset(ib,0,sizeof(ib));
        unsigned long cl=(unsigned long)rd;
        long long fsz=(long long)sz;
        ib[0].buffer_type=MYSQL_TYPE_BLOB;ib[0].buffer=(char*)fname;ib[0].buffer_length=fname_len;ib[0].length=&fname_len;
        ib[1].buffer_type=MYSQL_TYPE_BLOB;ib[1].buffer=(char*)fpath;ib[1].buffer_length=fpath_len;ib[1].length=&fpath_len;
        ib[2].buffer_type=MYSQL_TYPE_BLOB;ib[2].buffer=content;ib[2].buffer_length=cl;ib[2].length=&cl;
        ib[3].buffer_type=MYSQL_TYPE_LONGLONG;ib[3].buffer=&fsz;
        ib[4].buffer_type=MYSQL_TYPE_LONG;ib[4].buffer=&lines;
        int ok=0;
        if(mysql_stmt_bind_param(ins,ib)==0 && mysql_stmt_execute(ins)==0)
            ok=1;
        mysql_stmt_close(ins);
        free(content);

        if(ok) {
            (*ingested)++;
            snprintf(q,sizeof(q),"UPDATE ingestion_jobs SET status='done' WHERE id=%lld",job_id);
            mysql_query(conn,q);
            char esc[8193];
            mysql_real_escape_string(conn,esc,fpath,fpath_len);
            snprintf(q,sizeof(q),"INSERT INTO file_checkpoint (path_hash,full_path,status,mtime,content_hash) VALUES ('%s','%s','done',%lld,'%s') ON DUPLICATE KEY UPDATE status='done',mtime=%lld",path_hash,esc,mtime,content_hash,mtime);
            mysql_query(conn,q);
        } else {
            (*errors)++;
            char em[512]; snprintf(em,sizeof(em),"MySQL insert failed: %s",mysql_error(conn));
            char esc_em[1025]; mysql_real_escape_string(conn,esc_em,em,(unsigned long)strlen(em));
            snprintf(q,sizeof(q),"UPDATE ingestion_jobs SET status='failed',attempts=attempts+1,error_msg='%s' WHERE id=%lld",esc_em,job_id);
            mysql_query(conn,q);
        }
    }
    return 0;
}

static void ingest_stats(MYSQL *conn) {
    if(!conn) { printf("No DB connection.\n"); return; }
    printf("=== CODEBASE Stats ===\n");
    for(int i=0;i<INGEST_NUM_TABLES;i++) {
        char q[128]; snprintf(q,sizeof(q),"SELECT COUNT(*) FROM %s",INGEST_TABLES[i]);
        if(mysql_query(conn,q)==0) {
            MYSQL_RES*r=mysql_store_result(conn);
            if(r) {
                MYSQL_ROW row=mysql_fetch_row(r);
                if(row&&row[0]) printf("  %-20s: %s\n",INGEST_TABLES[i],row[0]);
                else printf("  %-20s: 0\n",INGEST_TABLES[i]);
                mysql_free_result(r);
            }
        }
    }
    if(mysql_query(conn,"SELECT status,COUNT(*) FROM ingestion_jobs GROUP BY status")==0) {
        MYSQL_RES*r=mysql_store_result(conn);
        if(r) {
            printf("\n=== Jobs ===\n");
            MYSQL_ROW row;
            while((row=mysql_fetch_row(r)))
                printf("  %-12s: %s\n",row[0]?row[0]:"?",row[1]?row[1]:"0");
            mysql_free_result(r);
        }
    }
    if(mysql_query(conn,"SELECT status,COUNT(*) FROM file_checkpoint GROUP BY status")==0) {
        MYSQL_RES*r=mysql_store_result(conn);
        if(r) {
            printf("\n=== Checkpoint ===\n");
            MYSQL_ROW row;
            while((row=mysql_fetch_row(r)))
                printf("  %-12s: %s\n",row[0]?row[0]:"?",row[1]?row[1]:"0");
            mysql_free_result(r);
        }
    }
}

int cmd_ingest(int argc,char *argv[]) {
    if(argc<2){
        printf("INGEST - CODEBASE MySQL Ingestion Engine\n");
        printf("  INGEST init              Create schema\n");
        printf("  INGEST scan /path        Scan filesystem -> job queue\n");
        printf("  INGEST run [worker_id]   Process jobs from queue\n");
        printf("  INGEST scanrun /path     Scan + process in one pass\n");
        printf("  INGEST stats             Show table + job counts\n");
        printf("  INGEST config            Show current config\n");
        printf("  INGEST reset             Clear job queue\n");
        printf("  INGEST repair            Rename special-char files, reset failed, retry\n");
        printf("  INGEST solutions          Show learned solutions\n");
        printf("  INGEST teach <pat> <act>  Teach a solution for a problem pattern\n");
        return 0;
    }
    MYSQL *conn=ingest_connect();
    if(!conn) return 1;

    if(!strcmp(argv[1],"init")) {
        ingest_schema(conn); printf("Schema ready.\n");
    }
    else if(!strcmp(argv[1],"scan")&&argc>2) {
        ingest_schema(conn);
        int sc=0,sk=0; ingest_scan_jobs(conn,argv[2],&sc,&sk);
        printf("Scanned: %d | Skipped: %d\n",sc,sk);
    }
    else if(!strcmp(argv[1],"run")) {
        int wid=(argc>2)?atoi(argv[2]):1;
        int ing=0,sk=0,er=0; ingest_process(conn,wid,&ing,&sk,&er);
        printf("Worker %d: ingested=%d skipped=%d errors=%d\n",wid,ing,sk,er);
    }
    else if(!strcmp(argv[1],"scanrun")&&argc>2) {
        ingest_schema(conn);
        int sc=0,sk=0; ingest_scan_jobs(conn,argv[2],&sc,&sk);
        printf("Scanned: %d | Skipped: %d\n",sc,sk);
        int ing=0,er=0; ingest_process(conn,1,&ing,&sk,&er);
        printf("Ingested: %d | Skipped: %d | Errors: %d\n",ing,sk,er);
    }
    else if(!strcmp(argv[1],"stats")) {
        ingest_stats(conn);
    }
    else if(!strcmp(argv[1],"config")) {
        if(!g_ingest_cfg_loaded) { ingest_load_config(&g_ingest_cfg); g_ingest_cfg_loaded=1; }
        printf("=== INGEST Config ===\n");
        printf("  MySQL host:  %s\n", g_ingest_cfg.mysql_host);
        printf("  MySQL user:  %s\n", g_ingest_cfg.mysql_user);
        printf("  MySQL db:    %s\n", g_ingest_cfg.mysql_db);
        printf("  MySQL port:  %d\n", g_ingest_cfg.mysql_port);
        printf("  Start path:  %s\n", g_ingest_cfg.start_path);
        printf("  Max file MB: %d\n", g_ingest_cfg.max_file_mb);
        printf("  Skip dirs:   %s\n", g_ingest_cfg.skip_dirs);
    }
    else if(!strcmp(argv[1],"reset")) {
        mysql_query(conn,"TRUNCATE TABLE ingestion_jobs");
        printf("Job queue cleared.\n");
    }
    else if(!strcmp(argv[1],"solutions")) {
        printf("=== Learned Solutions ===\n");
        mysql_query(conn,"SELECT id,problem_pattern,solution_action,solution_detail,applied_count FROM ingest_solutions ORDER BY id");
        MYSQL_RES *sr=mysql_store_result(conn);
        if(sr) {
            MYSQL_ROW row;
            while((row=mysql_fetch_row(sr))) {
                printf("  [%s] %s -> %s (%s) [applied %s times]\n",
                    row[0]?row[0]:"",row[1]?row[1]:"",row[2]?row[2]:"",
                    row[3]?row[3]:"",row[4]?row[4]:"0");
            }
            mysql_free_result(sr);
        }
        if(mysql_num_rows(mysql_store_result(conn))==0) {}
        printf("  (use INGEST teach <pattern> <action> [detail] to add solutions)\n");
    }
    else if(!strcmp(argv[1],"teach")&&argc>3) {
        /* INGEST teach <problem_pattern> <action> [detail] */
        const char *pattern=argv[2];
        const char *action=argv[3];
        const char *detail=(argc>4)?argv[4]:"";
        char esc_p[513],esc_a[513],esc_d[1025];
        mysql_real_escape_string(conn,esc_p,pattern,(unsigned long)strlen(pattern));
        mysql_real_escape_string(conn,esc_a,action,(unsigned long)strlen(action));
        mysql_real_escape_string(conn,esc_d,detail,(unsigned long)strlen(detail));
        char q[2048];
        snprintf(q,sizeof(q),"INSERT INTO ingest_solutions (problem_pattern,solution_action,solution_detail) VALUES ('%s','%s','%s') ON DUPLICATE KEY UPDATE solution_action='%s',solution_detail='%s'",esc_p,esc_a,esc_d,esc_a,esc_d);
        if(mysql_query(conn,q)==0) printf("Solution learned: %s -> %s\n",pattern,action);
        else printf("Failed to learn: %s\n",mysql_error(conn));
    }
    else if(!strcmp(argv[1],"repair")) {
        /* 1. Find failed jobs with special chars in filename, rename on disk, update DB */
        int renamed=0;
        mysql_query(conn,"SELECT id,file_path,file_name FROM ingestion_jobs WHERE status='failed'");
        MYSQL_RES *fr=mysql_store_result(conn);
        if(fr) {
            MYSQL_ROW row;
            while((row=mysql_fetch_row(fr))) {
                if(!row[0]||!row[1]||!row[2]) continue;
                long long jid=atoll(row[0]);
                const char *fp=row[1];
                const char *fn=row[2];
                /* Check for special chars in filename */
                if(!strpbrk(fn,"#*")) continue;
                /* Build new path: strip # and * from filename */
                char dir[4096]; strncpy(dir,fp,sizeof(dir)-1); dir[sizeof(dir)-1]=0;
                char *slash=strrchr(dir,'/');
                if(!slash) continue;
                *slash=0;
                char newname[1024]; int ni=0;
                for(int i=0;fn[i]&&ni<(int)sizeof(newname)-1;i++) {
                    if(fn[i]!='#'&&fn[i]!='*') newname[ni++]=fn[i];
                }
                newname[ni]=0;
                char newpath[5120];
                snprintf(newpath,sizeof(newpath),"%s/%s",dir,newname);
                /* Rename on disk */
                if(rename(fp,newpath)==0) {
                    char esc_np[10240]; unsigned long epl=mysql_real_escape_string(conn,esc_np,newpath,(unsigned long)strlen(newpath));
                    char esc_nn[2048]; unsigned long enl=mysql_real_escape_string(conn,esc_nn,newname,(unsigned long)strlen(newname));
                    char uq[13000];
                    snprintf(uq,sizeof(uq),"UPDATE ingestion_jobs SET file_path='%s',file_name='%s',status='pending' WHERE id=%lld",esc_np,esc_nn,jid);
                    mysql_query(conn,uq);
                    renamed++;
                }
            }
            mysql_free_result(fr);
        }
        printf("Renamed %d files on disk.\n",renamed);
        /* 2. Reset remaining failed jobs to pending */
        mysql_query(conn,"UPDATE ingestion_jobs SET status='pending' WHERE status='failed'");
        /* 3. Run workers */
        int ing=0,sk=0,er=0; ingest_process(conn,1,&ing,&sk,&er);
        printf("Repair: ingested=%d skipped=%d errors=%d\n",ing,sk,er);
    }
    else {printf("Unknown: %s (try INGEST)\n",argv[1]);}

    mysql_close(conn);
    return 0;
}

static const char *GUI_LINES[] = {
"#!/usr/bin/env python3\n",
"import sys, os, sqlite3\n",
"try:\n",
"    from PyQt6.QtWidgets import (\n",
"        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,\n",
"        QGroupBox, QCheckBox, QRadioButton, QButtonGroup, QLabel,\n",
"        QPushButton, QListWidget, QLineEdit, QAbstractItemView,\n",
"        QMessageBox, QTabWidget, QTableWidget, QTableWidgetItem,\n",
"        QHeaderView, QTextEdit, QFormLayout)\n",
"    from PyQt6.QtGui import QFont, QColor\n",
"    from PyQt6.QtCore import Qt\n",
"except ImportError:\n",
"    print('PyQt6 not found. Install: pip install PyQt6')\n",
"    sys.exit(1)\n",
"\n",
"DB = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser('~/.wcmd.db')\n",
"BEHAVIOR_DEFAULTS = {\n",
"    'show_date':'1','show_time':'1','show_hidden':'0',\n",
"    'thousand':'1','sort':'G','sort_rev':'0',\n",
"    'size_fmt':'auto','skip':'__pycache__,.git,node_modules,site-packages',\n",
"}\n",
"def con():\n",
"    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row; return c\n",
"def load_dir_cfg():\n",
"    cfg = dict(BEHAVIOR_DEFAULTS)\n",
"    try:\n",
"        db = con()\n",
"        row = db.execute('SELECT id FROM commands WHERE name=?',('DIR',)).fetchone()\n",
"        if row:\n",
"            for r in db.execute('SELECT key,value FROM behaviors WHERE command_id=?',(row['id'],)):\n",
"                cfg[r['key']] = r['value']\n",
"        db.close()\n",
"    except Exception: pass\n",
"    return cfg\n",
"def save_dir_cfg(cfg):\n",
"    db = con()\n",
"    row = db.execute('SELECT id FROM commands WHERE name=?',('DIR',)).fetchone()\n",
"    if row:\n",
"        cid = row['id']\n",
"        for k,v in cfg.items():\n",
"            db.execute('INSERT OR REPLACE INTO behaviors (command_id,key,value) VALUES (?,?,?)',(cid,k,v))\n",
"    db.commit(); db.close()\n",
"class WCmdWindow(QMainWindow):\n",
"    def __init__(self):\n",
"        super().__init__()\n",
"        self.setWindowTitle('WCMD Config — ' + DB)\n",
"        self.setMinimumSize(640, 680)\n",
"        self.cfg = load_dir_cfg()\n",
"        self.ing_cfg = {}\n",
"        self._build(); self._load()\n",
"    def _build(self):\n",
"        c = QWidget(); self.setCentralWidget(c)\n",
"        root = QVBoxLayout(c); root.setSpacing(8); root.setContentsMargins(12,12,12,12)\n",
"        hdr = QLabel('WCMD Command System')\n",
"        hdr.setFont(QFont('Helvetica', 15, QFont.Weight.Bold))\n",
"        root.addWidget(hdr)\n",
"        sub = QLabel('Knowledge layer: ' + DB + ' (SQLite)')\n",
"        sub.setStyleSheet('color:gray;font-size:11px;')\n",
"        root.addWidget(sub)\n",
"        tabs = QTabWidget(); root.addWidget(tabs)\n",
"        tabs.addTab(self._tab_commands(), 'Commands')\n",
"        tabs.addTab(self._tab_display(), 'DIR Display')\n",
"        tabs.addTab(self._tab_size(), 'DIR Size')\n",
"        tabs.addTab(self._tab_sort(), 'DIR Sort')\n",
"        tabs.addTab(self._tab_skip(), 'Skip Dirs')\n",
"        tabs.addTab(self._tab_ingest(), 'INGEST')\n",
"        row = QHBoxLayout()\n",
"        b_save = QPushButton('Save DIR settings'); b_reset = QPushButton('Reset Defaults')\n",
"        b_close = QPushButton('Close'); b_save.setDefault(True)\n",
"        b_save.clicked.connect(self._save); b_reset.clicked.connect(self._reset)\n",
"        b_close.clicked.connect(self.close)\n",
"        row.addStretch(); row.addWidget(b_reset); row.addWidget(b_save); row.addWidget(b_close)\n",
"        root.addLayout(row)\n",
"    def _tab_commands(self):\n",
"        w = QWidget(); v = QVBoxLayout(w)\n",
"        lbl = QLabel('Registered commands in DB')\n",
"        lbl.setStyleSheet('color:gray;font-size:11px;')\n",
"        v.addWidget(lbl)\n",
"        self.cmd_table = QTableWidget()\n",
"        self.cmd_table.setColumnCount(4)\n",
"        self.cmd_table.setHorizontalHeaderLabels(['Command','Version','Description','Enabled'])\n",
"        self.cmd_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)\n",
"        self.cmd_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)\n",
"        v.addWidget(self.cmd_table); self._refresh_cmds(); return w\n",
"    def _refresh_cmds(self):\n",
"        try:\n",
"            db = con()\n",
"            rows = db.execute('SELECT name,version,description,enabled FROM commands ORDER BY name').fetchall()\n",
"            db.close()\n",
"            self.cmd_table.setRowCount(len(rows))\n",
"            for i,r in enumerate(rows):\n",
"                self.cmd_table.setItem(i,0,QTableWidgetItem(r['name']))\n",
"                self.cmd_table.setItem(i,1,QTableWidgetItem(r['version'] or ''))\n",
"                self.cmd_table.setItem(i,2,QTableWidgetItem(r['description'] or ''))\n",
"                en = QTableWidgetItem('Yes' if r['enabled'] else 'No')\n",
"                en.setForeground(QColor('#2a9d2a') if r['enabled'] else QColor('#cc3333'))\n",
"                self.cmd_table.setItem(i,3,en)\n",
"        except Exception: pass\n",
"    def _tab_display(self):\n",
"        w = QWidget(); v = QVBoxLayout(w); v.setSpacing(10)\n",
"        grp = QGroupBox('DIR Output Columns'); gl = QVBoxLayout(grp)\n",
"        self.chk_date = QCheckBox('Show date (mm/dd/yyyy)')\n",
"        self.chk_time = QCheckBox('Show time (hh:mm AM/PM)')\n",
"        self.chk_hidden = QCheckBox('Show hidden files')\n",
"        self.chk_thou = QCheckBox('Thousand separators')\n",
"        for c in [self.chk_date, self.chk_time, self.chk_hidden, self.chk_thou]: gl.addWidget(c)\n",
"        v.addWidget(grp); v.addStretch(); return w\n",
"    def _tab_size(self):\n",
"        w = QWidget(); v = QVBoxLayout(w); v.setSpacing(10)\n",
"        grp = QGroupBox('File Size Format'); gl = QVBoxLayout(grp)\n",
"        self.size_grp = QButtonGroup()\n",
"        opts = [('auto','Auto KB/MB/GB'),('bytes','Bytes'),('kb','KB'),('mb','MB'),('gb','GB')]\n",
"        self.size_rb = {}\n",
"        for val, lbl in opts:\n",
"            rb = QRadioButton(lbl); self.size_grp.addButton(rb)\n",
"            self.size_rb[val] = rb; gl.addWidget(rb)\n",
"        v.addWidget(grp); v.addStretch(); return w\n",
"    def _get_sz(self):\n",
"        for k,rb in self.size_rb.items():\n",
"            if rb.isChecked(): return k\n",
"        return 'auto'\n",
"    def _tab_sort(self):\n",
"        w = QWidget(); v = QVBoxLayout(w); v.setSpacing(10)\n",
"        grp = QGroupBox('Default Sort'); gl = QVBoxLayout(grp)\n",
"        self.sort_grp = QButtonGroup()\n",
"        sorts = [('G','Dirs first (default)'),('N','Name'),('S','Size'),('E','Extension'),('D','Date')]\n",
"        self.sort_rb = {}\n",
"        for val,lbl in sorts:\n",
"            rb = QRadioButton(lbl); self.sort_grp.addButton(rb)\n",
"            self.sort_rb[val] = rb; gl.addWidget(rb)\n",
"        self.chk_rev = QCheckBox('Reverse order'); gl.addWidget(self.chk_rev)\n",
"        v.addWidget(grp); v.addStretch(); return w\n",
"    def _tab_skip(self):\n",
"        w = QWidget(); v = QVBoxLayout(w); v.setSpacing(8)\n",
"        note = QLabel('Extra dirs skipped during /S')\n",
"        note.setWordWrap(True); note.setStyleSheet('color:gray;font-size:11px;')\n",
"        v.addWidget(note)\n",
"        grp = QGroupBox('Extra skip dirs'); gl = QVBoxLayout(grp)\n",
"        self.skip_list = QListWidget()\n",
"        self.skip_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)\n",
"        gl.addWidget(self.skip_list)\n",
"        row = QHBoxLayout()\n",
"        self.skip_in = QLineEdit(); self.skip_in.setPlaceholderText('dirname')\n",
"        b_add = QPushButton('Add'); b_del = QPushButton('Remove')\n",
"        b_add.clicked.connect(self._skip_add); b_del.clicked.connect(self._skip_del)\n",
"        self.skip_in.returnPressed.connect(self._skip_add)\n",
"        row.addWidget(self.skip_in); row.addWidget(b_add); row.addWidget(b_del)\n",
"        gl.addLayout(row); v.addWidget(grp); return w\n",
"    def _skip_add(self):\n",
"        t = self.skip_in.text().strip()\n",
"        if t: self.skip_list.addItem(t); self.skip_in.clear()\n",
"    def _skip_del(self):\n",
"        for item in self.skip_list.selectedItems():\n",
"            self.skip_list.takeItem(self.skip_list.row(item))\n",
"    def _load(self):\n",
"        self.chk_date.setChecked(self.cfg.get('show_date','1') == '1')\n",
"        self.chk_time.setChecked(self.cfg.get('show_time','1') == '1')\n",
"        self.chk_hidden.setChecked(self.cfg.get('show_hidden','0') == '1')\n",
"        self.chk_thou.setChecked(self.cfg.get('thousand','1') == '1')\n",
"        self.size_rb.get(self.cfg.get('size_fmt','auto'), self.size_rb['auto']).setChecked(True)\n",
"        self.sort_rb.get(self.cfg.get('sort','G').upper(), self.sort_rb['G']).setChecked(True)\n",
"        self.chk_rev.setChecked(self.cfg.get('sort_rev','0') == '1')\n",
"        self.skip_list.clear()\n",
"        for s in self.cfg.get('skip','').split(','):\n",
"            s = s.strip()\n",
"            if s: self.skip_list.addItem(s)\n",
"    def _save(self):\n",
"        self.cfg['show_date'] = '1' if self.chk_date.isChecked() else '0'\n",
"        self.cfg['show_time'] = '1' if self.chk_time.isChecked() else '0'\n",
"        self.cfg['show_hidden'] = '1' if self.chk_hidden.isChecked() else '0'\n",
"        self.cfg['thousand'] = '1' if self.chk_thou.isChecked() else '0'\n",
"        self.cfg['size_fmt'] = self._get_sz()\n",
"        for k, rb in self.sort_rb.items():\n",
"            if rb.isChecked(): self.cfg['sort'] = k\n",
"        self.cfg['sort_rev'] = '1' if self.chk_rev.isChecked() else '0'\n",
"        items = [self.skip_list.item(i).text() for i in range(self.skip_list.count())]\n",
"        self.cfg['skip'] = ','.join(items)\n",
"        save_dir_cfg(self.cfg)\n",
"        QMessageBox.information(self, 'Saved', 'DIR settings saved')\n",
"    def _reset(self):\n",
"        if QMessageBox.question(self,'Reset','Reset DIR defaults?') == QMessageBox.StandardButton.Yes:\n",
"            self.cfg = dict(BEHAVIOR_DEFAULTS); self._load()\n",
"    def _tab_ingest(self):\n",
"        w = QWidget(); v = QVBoxLayout(w); v.setSpacing(8)\n",
"        grp = QGroupBox('MySQL Connection'); gl = QGridLayout(grp)\n",
"        gl.setHorizontalSpacing(12); gl.setVerticalSpacing(6)\n",
"        gl.setContentsMargins(12, 16, 12, 12)\n",
"        self.ing_host = QLineEdit(); self.ing_user = QLineEdit()\n",
"        self.ing_pass = QLineEdit(); self.ing_pass.setEchoMode(QLineEdit.EchoMode.Password)\n",
"        self.ing_db = QLineEdit(); self.ing_port = QLineEdit()\n",
"        for f in [self.ing_host, self.ing_user, self.ing_pass, self.ing_db, self.ing_port]:\n",
"            f.setMinimumHeight(30)\n",
"        def _lbl(text):\n",
"            lab = QLabel(text); lab.setFixedWidth(100); lab.setStyleSheet('font-weight: bold;')\n",
"            return lab\n",
"        gl.addWidget(_lbl('Host:'), 0, 0); gl.addWidget(self.ing_host, 0, 1, 1, 3)\n",
"        gl.addWidget(_lbl('User:'), 1, 0); gl.addWidget(self.ing_user, 1, 1)\n",
"        gl.addWidget(_lbl('Password:'), 1, 3); gl.addWidget(self.ing_pass, 1, 4)\n",
"        gl.addWidget(_lbl('Database:'), 2, 0); gl.addWidget(self.ing_db, 2, 1)\n",
"        gl.addWidget(_lbl('Port:'), 2, 3); gl.addWidget(self.ing_port, 2, 4)\n",
"        gl.setColumnStretch(1, 1); gl.setColumnStretch(4, 1)\n",
"        gl.setColumnMinimumWidth(2, 20)\n",
"        v.addWidget(grp)\n",
"        grp2 = QGroupBox('Scan Settings'); gl2 = QGridLayout(grp2)\n",
"        gl2.setHorizontalSpacing(12); gl2.setVerticalSpacing(6)\n",
"        gl2.setContentsMargins(12, 16, 12, 12)\n",
"        self.ing_path = QLineEdit(); self.ing_maxmb = QLineEdit()\n",
"        self.ing_path.setMinimumHeight(30); self.ing_maxmb.setMinimumHeight(30)\n",
"        gl2.addWidget(_lbl('Start path:'), 0, 0); gl2.addWidget(self.ing_path, 0, 1)\n",
"        gl2.addWidget(_lbl('Max file MB:'), 1, 0); gl2.addWidget(self.ing_maxmb, 1, 1)\n",
"        gl2.setColumnStretch(1, 1); v.addWidget(grp2)\n",
"        grp3 = QGroupBox('Skip Dirs (comma-separated)'); gl3 = QVBoxLayout(grp3)\n",
"        self.ing_skip = QTextEdit(); self.ing_skip.setMinimumHeight(80)\n",
"        self.ing_skip.setPlaceholderText('.git,.svn,venv,env,__pycache__,site-packages,node_modules,...')\n",
"        gl3.addWidget(self.ing_skip); v.addWidget(grp3)\n",
"        btnRow = QHBoxLayout()\n",
"        b = QPushButton('Save INGEST Config'); b.clicked.connect(self._save_ingest)\n",
"        bTest = QPushButton('Test Connection'); bTest.clicked.connect(self._test_mysql)\n",
"        bDetect = QPushButton('Detect MySQL'); bDetect.clicked.connect(self._detect_mysql)\n",
"        btnRow.addWidget(b); btnRow.addWidget(bTest); btnRow.addWidget(bDetect)\n",
"        v.addLayout(btnRow)\n",
"        self.ing_status = QLabel('MySQL: not tested'); self.ing_status.setStyleSheet('color: gray;')\n",
"        v.addWidget(self.ing_status)\n",
"        self.ing_dblist = QListWidget(); self.ing_dblist.setMinimumHeight(100)\n",
"        grpDBList = QGroupBox('Available Databases (click to select)'); grpDBListL = QVBoxLayout(grpDBList)\n",
"        grpDBListL.addWidget(self.ing_dblist)\n",
"        self.ing_dblist.itemClicked.connect(lambda item: self.ing_db.setText(item.text()))\n",
"        v.addWidget(grpDBList)\n",
"        actRow = QHBoxLayout()\n",
"        bScan = QPushButton('Scan'); bScan.clicked.connect(self._ingest_scan)\n",
"        bRun = QPushButton('Run Worker'); bRun.clicked.connect(self._ingest_run)\n",
"        bStats = QPushButton('Stats'); bStats.clicked.connect(self._ingest_stats)\n",
"        bReset = QPushButton('Reset Jobs'); bReset.clicked.connect(self._ingest_reset)\n",
"        for b in [bScan, bRun, bStats, bReset]: b.setMinimumHeight(32)\n",
"        actRow.addWidget(bScan); actRow.addWidget(bRun); actRow.addWidget(bStats); actRow.addWidget(bReset)\n",
"        v.addLayout(actRow)\n",
"        self.ing_output = QTextEdit(); self.ing_output.setMinimumHeight(120)\n",
"        self.ing_output.setReadOnly(True)\n",
"        self.ing_output.setPlaceholderText('INGEST output will appear here...')\n",
"        outGrp = QGroupBox('Output'); outL = QVBoxLayout(outGrp)\n",
"        outL.addWidget(self.ing_output); v.addWidget(outGrp)\n",
"        v.addStretch(); self._load_ingest(); return w\n",
"    def _detect_mysql(self):\n",
"        import subprocess, shutil\n",
"        found = []\n",
"        # Check common mysql paths\n",
"        paths = ['/opt/homebrew/bin/mysql', '/usr/local/mysql/bin/mysql',\n",
"                 '/opt/homebrew/Cellar/mysql@8.0/8.0.46_1/bin/mysql', shutil.which('mysql')]\n",
"        for p in paths:\n",
"            if p and os.path.exists(p):\n",
"                found.append(p)\n",
"        # Check if mysqld is running\n",
"        try:\n",
"            r = subprocess.run(['pgrep', '-x', 'mysqld'], capture_output=True, text=True, timeout=5)\n",
"            running = r.returncode == 0\n",
"        except Exception:\n",
"            running = False\n",
"        # Check brew services\n",
"        try:\n",
"            r2 = subprocess.run(['brew', 'services', 'list'], capture_output=True, text=True, timeout=10)\n",
"            brew_info = r2.stdout if r2.returncode == 0 else ''\n",
"        except Exception:\n",
"            brew_info = ''\n",
"        msg = ''\n",
"        if running:\n",
"            msg += 'MySQL server: RUNNING\\n'\n",
"        else:\n",
"            msg += 'MySQL server: NOT RUNNING\\n'\n",
"            msg += 'Start with: brew services start mysql@8.0\\n'\n",
"        if found:\n",
"            msg += f'Binary: {found[0]}\\n'\n",
"        if brew_info and 'mysql' in brew_info.lower():\n",
"            for line in brew_info.split('\\n'):\n",
"                if 'mysql' in line.lower():\n",
"                    msg += f'Brew: {line.strip()}\\n'\n",
"        if not self.ing_host.text():\n",
"            self.ing_host.setText('localhost')\n",
"        if not self.ing_port.text():\n",
"            self.ing_port.setText('3306')\n",
"        self.ing_status.setText(msg.strip())\n",
"        self.ing_status.setStyleSheet('color: green;' if running else 'color: red;')\n",
"    def _test_mysql(self):\n",
"        import subprocess, shutil\n",
"        host = self.ing_host.text().strip() or 'localhost'\n",
"        user = self.ing_user.text().strip() or 'root'\n",
"        pw = self.ing_pass.text()\n",
"        port = self.ing_port.text().strip() or '3306'\n",
"        mysql_bin = shutil.which('mysql')\n",
"        if not mysql_bin:\n",
"            for p in ['/opt/homebrew/bin/mysql', '/usr/local/mysql/bin/mysql',\n",
"                      '/opt/homebrew/Cellar/mysql@8.0/8.0.46_1/bin/mysql']:\n",
"                if os.path.exists(p): mysql_bin = p; break\n",
"        if not mysql_bin:\n",
"            self.ing_status.setText('ERROR: mysql binary not found')\n",
"            self.ing_status.setStyleSheet('color: red;')\n",
"            return\n",
"        cmd = [mysql_bin, f'-h{host}', f'-P{port}', f'-u{user}']\n",
"        if pw: cmd.append(f'-p{pw}')\n",
"        cmd += ['-e', 'SELECT VERSION() AS version; SHOW DATABASES;']\n",
"        try:\n",
"            r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)\n",
"            if r.returncode == 0:\n",
"                lines = r.stdout.strip().split('\\n')\n",
"                ver_line = lines[0] if lines else ''\n",
"                self.ing_status.setText(f'CONNECTED — {ver_line}')\n",
"                self.ing_status.setStyleSheet('color: green; font-weight: bold;')\n",
"                self.ing_dblist.clear()\n",
"                for line in lines[2:]:\n",
"                    db = line.strip()\n",
"                    if db and db not in ('Database',):\n",
"                        self.ing_dblist.addItem(db)\n",
"            else:\n",
"                err = r.stderr.strip().split('\\n')[0] if r.stderr else 'Unknown error'\n",
"                self.ing_status.setText(f'FAILED: {err}')\n",
"                self.ing_status.setStyleSheet('color: red; font-weight: bold;')\n",
"        except subprocess.TimeoutExpired:\n",
"            self.ing_status.setText('TIMEOUT: MySQL not responding')\n",
"            self.ing_status.setStyleSheet('color: red;')\n",
"        except Exception as e:\n",
"            self.ing_status.setText(f'ERROR: {e}')\n",
"            self.ing_status.setStyleSheet('color: red;')\n",
"    def _ingest_scan(self):\n",
"        import subprocess\n",
"        path = self.ing_path.text().strip() or '/Users'\n",
"        wcmd = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'wcmd')\n",
"        if not os.path.exists(wcmd): wcmd = '/Users/wws/bin/wcmd'\n",
"        self.ing_output.append(f'>>> INGEST scan {path}')\n",
"        try:\n",
"            r = subprocess.run([wcmd, 'INGEST', 'scan', path], capture_output=True, text=True, timeout=300)\n",
"            self.ing_output.append(r.stdout + r.stderr)\n",
"        except Exception as e: self.ing_output.append(f'ERROR: {e}')\n",
"    def _ingest_run(self):\n",
"        import subprocess\n",
"        wcmd = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'wcmd')\n",
"        if not os.path.exists(wcmd): wcmd = '/Users/wws/bin/wcmd'\n",
"        self.ing_output.append('>>> INGEST run 1')\n",
"        try:\n",
"            r = subprocess.run([wcmd, 'INGEST', 'run', '1'], capture_output=True, text=True, timeout=600)\n",
"            self.ing_output.append(r.stdout + r.stderr)\n",
"        except Exception as e: self.ing_output.append(f'ERROR: {e}')\n",
"    def _ingest_stats(self):\n",
"        import subprocess\n",
"        wcmd = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'wcmd')\n",
"        if not os.path.exists(wcmd): wcmd = '/Users/wws/bin/wcmd'\n",
"        self.ing_output.append('>>> INGEST stats')\n",
"        try:\n",
"            r = subprocess.run([wcmd, 'INGEST', 'stats'], capture_output=True, text=True, timeout=30)\n",
"            self.ing_output.append(r.stdout + r.stderr)\n",
"        except Exception as e: self.ing_output.append(f'ERROR: {e}')\n",
"    def _ingest_reset(self):\n",
"        import subprocess\n",
"        wcmd = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'wcmd')\n",
"        if not os.path.exists(wcmd): wcmd = '/Users/wws/bin/wcmd'\n",
"        self.ing_output.append('>>> INGEST reset')\n",
"        try:\n",
"            r = subprocess.run([wcmd, 'INGEST', 'reset'], capture_output=True, text=True, timeout=30)\n",
"            self.ing_output.append(r.stdout + r.stderr)\n",
"        except Exception as e: self.ing_output.append(f'ERROR: {e}')\n",
"    def _load_ingest(self):\n",
"        try:\n",
"            db = con()\n",
"            for key, field in [('ingest_mysql_host',self.ing_host),('ingest_mysql_user',self.ing_user),('ingest_mysql_pass',self.ing_pass),('ingest_mysql_db',self.ing_db),('ingest_mysql_port',self.ing_port),('ingest_start_path',self.ing_path),('ingest_max_file_mb',self.ing_maxmb)]:\n",
"                row = db.execute('SELECT value FROM system_config WHERE key=?', (key,)).fetchone()\n",
"                field.setText(row['value'] if row else '')\n",
"            row = db.execute('SELECT value FROM system_config WHERE key=?', ('ingest_skip_dirs',)).fetchone()\n",
"            self.ing_skip.setPlainText(row['value'] if row else '')\n",
"            db.close()\n",
"        except Exception as e: print('INGEST LOAD:', e)\n",
"    def _save_ingest(self):\n",
"        try:\n",
"            db = con()\n",
"            for key, field in [('ingest_mysql_host',self.ing_host),('ingest_mysql_user',self.ing_user),('ingest_mysql_pass',self.ing_pass),('ingest_mysql_db',self.ing_db),('ingest_mysql_port',self.ing_port),('ingest_start_path',self.ing_path),('ingest_max_file_mb',self.ing_maxmb)]:\n",
"                db.execute('INSERT OR REPLACE INTO system_config (key,value) VALUES (?,?)', (key, field.text()))\n",
"            db.execute('INSERT OR REPLACE INTO system_config (key,value) VALUES (?,?)', ('ingest_skip_dirs', self.ing_skip.toPlainText()))\n",
"            db.commit(); db.close()\n",
"            QMessageBox.information(self, 'Saved', 'INGEST config saved')\n",
"        except Exception as e:\n",
"            QMessageBox.warning(self, 'Error', str(e))\n",
"def main():\n",
"    app = QApplication(sys.argv)\n",
"    app.setStyle('Fusion')\n",
"    win = WCmdWindow(); win.show()\n",
"    sys.exit(app.exec())\n",
"if __name__ == '__main__':\n",
"    main()\n",
NULL
};

static void launch_cfg(void){
    sqlite3 *db=db_open();
    if(db){
        size_t tot=0;
        for(int i=0;GUI_LINES[i];i++) tot+=strlen(GUI_LINES[i]);
        char *script=malloc(tot+1); script[0]='\0';
        for(int i=0;GUI_LINES[i];i++) strcat(script,GUI_LINES[i]);
        sqlite3_stmt *st;
        sqlite3_prepare_v2(db,
            "INSERT OR REPLACE INTO ui_modules (name,description,script) VALUES ('wcmd_config','WCMD Config GUI',?)",
            -1,&st,NULL);
        sqlite3_bind_text(st,1,script,-1,SQLITE_STATIC);
        sqlite3_step(st); sqlite3_finalize(st);
        sqlite3_close(db); free(script);
    }
    char tmp[64]; strcpy(tmp,"/tmp/wcmd_cfg_XXXXXX.py");
    int fd=mkstemps(tmp,3);
    if(fd<0){fprintf(stderr,"Cannot create temp file.\n");return;}
    for(int i=0;GUI_LINES[i];i++) write(fd,GUI_LINES[i],strlen(GUI_LINES[i]));
    close(fd);
    char cmd[768];
    const char *h=getenv("HOME");
    char cfg_path[512];
    snprintf(cfg_path,sizeof(cfg_path),"%s/.wcmd_cfg.db",h?h:"/tmp");
    snprintf(cmd,sizeof(cmd),"python3 '%s' '%s' &",tmp,cfg_path);
    system(cmd);
}

static void load_persisted_config(sqlite3 *db){
    const char *h=getenv("HOME");
    if(!h) return;
    char cfg_path[512];
    snprintf(cfg_path,sizeof(cfg_path),"%s/.wcmd_cfg.db",h);
    sqlite3 *pdb=NULL;
    if(sqlite3_open(cfg_path,&pdb)!=SQLITE_OK||!pdb) return;
    sqlite3_stmt *st;
    if(sqlite3_prepare_v2(pdb,"SELECT key,value FROM system_config",-1,&st,NULL)!=SQLITE_OK){
        sqlite3_close(pdb); return;
    }
    sqlite3_stmt *up;
    sqlite3_prepare_v2(db,"INSERT OR REPLACE INTO system_config (key,value,description) VALUES (?,?,?)",-1,&up,NULL);
    while(sqlite3_step(st)==SQLITE_ROW){
        const char *k=(const char*)sqlite3_column_text(st,0);
        const char *v=(const char*)sqlite3_column_text(st,1);
        if(k&&v){
            sqlite3_bind_text(up,1,k,-1,SQLITE_STATIC);
            sqlite3_bind_text(up,2,v,-1,SQLITE_STATIC);
            sqlite3_bind_text(up,3,"from persisted config",-1,SQLITE_STATIC);
            sqlite3_step(up); sqlite3_reset(up);
        }
    }
    sqlite3_finalize(up);
    sqlite3_finalize(st);
    sqlite3_close(pdb);
}

int main(int argc,char *argv[]){
    sqlite3 *db=db_open();
    if(db) load_persisted_config(db);
    for(int i=1;i<argc;i++){
        if(!strcmp(argv[i],"-cfg")||!strcmp(argv[i],"--config")){
            launch_cfg();
            if(db) sqlite3_close(db);
            return 0;
        }
    }
    int result=vm_execute(db,argc,argv);
    if(db) sqlite3_close(db);
    return result;
}
