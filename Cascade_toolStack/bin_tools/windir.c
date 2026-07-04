/*
 * dir.c  —  Windows-style DIR for macOS
 * Config + GUI script stored in ~/.dir.db (SQLite)
 * GUI launched with:  dir -cfg
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
#include <sqlite3.h>

/* ────────────────── embedded PyQt6 GUI script ───────────────────────
   Stored in the DB on first -cfg call so the user never needs an
   external .py file.  Uses only single-quoted strings → no C escaping.
   ──────────────────────────────────────────────────────────────────── */
static const char *GUI_LINES[] = {
"#!/usr/bin/env python3\n",
"import sys, os, sqlite3\n",
"try:\n",
"    from PyQt6.QtWidgets import (\n",
"        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,\n",
"        QGroupBox, QCheckBox, QRadioButton, QButtonGroup, QLabel,\n",
"        QPushButton, QListWidget, QLineEdit, QAbstractItemView,\n",
"        QMessageBox, QTabWidget)\n",
"    from PyQt6.QtGui import QFont\n",
"except ImportError:\n",
"    print('PyQt6 not found.  Install:  pip install PyQt6')\n",
"    sys.exit(1)\n",
"\n",
"DB_PATH = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser('~/.dir.db')\n",
"\n",
"DEFAULTS = {\n",
"    'show_date': '1', 'show_time': '1', 'show_hidden': '0',\n",
"    'thousand': '1', 'sort': 'G', 'sort_rev': '0',\n",
"    'size_fmt': 'auto', 'skip': '__pycache__,.git,node_modules,site-packages',\n",
"}\n",
"\n",
"def get_db():\n",
"    con = sqlite3.connect(DB_PATH)\n",
"    con.execute('CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT)')\n",
"    con.execute('CREATE TABLE IF NOT EXISTS scripts (name TEXT PRIMARY KEY, content TEXT)')\n",
"    con.commit()\n",
"    return con\n",
"\n",
"def load_config():\n",
"    cfg = dict(DEFAULTS)\n",
"    try:\n",
"        con = get_db()\n",
"        for row in con.execute('SELECT key, value FROM config'):\n",
"            cfg[row[0]] = row[1]\n",
"        con.close()\n",
"    except Exception:\n",
"        pass\n",
"    return cfg\n",
"\n",
"def save_config(cfg):\n",
"    con = get_db()\n",
"    for k, v in cfg.items():\n",
"        con.execute('INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)', (k, v))\n",
"    con.commit()\n",
"    con.close()\n",
"\n",
"class DirConfigWindow(QMainWindow):\n",
"    def __init__(self):\n",
"        super().__init__()\n",
"        self.setWindowTitle('DIR Configuration  —  ' + DB_PATH)\n",
"        self.setMinimumWidth(520)\n",
"        self.setMinimumHeight(500)\n",
"        self.cfg = load_config()\n",
"        self._build_ui()\n",
"        self._load_to_ui()\n",
"\n",
"    def _build_ui(self):\n",
"        central = QWidget()\n",
"        self.setCentralWidget(central)\n",
"        root = QVBoxLayout(central)\n",
"        root.setSpacing(10)\n",
"        root.setContentsMargins(14, 14, 14, 14)\n",
"        title = QLabel('DIR  Command Settings')\n",
"        title.setFont(QFont('Helvetica', 15, QFont.Weight.Bold))\n",
"        root.addWidget(title)\n",
"        hint = QLabel('All settings stored in  ~/.dir.db  (SQLite  —  single source of truth)')\n",
"        hint.setStyleSheet('color: gray; font-size: 11px;')\n",
"        root.addWidget(hint)\n",
"        tabs = QTabWidget()\n",
"        root.addWidget(tabs)\n",
"        tabs.addTab(self._tab_display(), 'Display')\n",
"        tabs.addTab(self._tab_size(),    'File Size')\n",
"        tabs.addTab(self._tab_sort(),    'Sorting')\n",
"        tabs.addTab(self._tab_skip(),    'Skip Dirs')\n",
"        row = QHBoxLayout()\n",
"        b_save  = QPushButton('Save')\n",
"        b_reset = QPushButton('Reset Defaults')\n",
"        b_close = QPushButton('Close')\n",
"        b_save.setDefault(True)\n",
"        b_save.clicked.connect(self._on_save)\n",
"        b_reset.clicked.connect(self._on_reset)\n",
"        b_close.clicked.connect(self.close)\n",
"        row.addStretch()\n",
"        row.addWidget(b_reset)\n",
"        row.addWidget(b_save)\n",
"        row.addWidget(b_close)\n",
"        root.addLayout(row)\n",
"\n",
"    def _tab_display(self):\n",
"        w = QWidget(); v = QVBoxLayout(w); v.setSpacing(10)\n",
"        grp = QGroupBox('Output Columns'); gl = QVBoxLayout(grp)\n",
"        self.chk_date   = QCheckBox('Show date  (mm/dd/yyyy)')\n",
"        self.chk_time   = QCheckBox('Show time  (hh:mm AM/PM)')\n",
"        self.chk_hidden = QCheckBox('Show hidden files  (names starting with .)')\n",
"        self.chk_thou   = QCheckBox('Thousand separators in sizes  (1,234,567)')\n",
"        for c in [self.chk_date, self.chk_time, self.chk_hidden, self.chk_thou]: gl.addWidget(c)\n",
"        v.addWidget(grp); v.addStretch(); return w\n",
"\n",
"    def _tab_size(self):\n",
"        w = QWidget(); v = QVBoxLayout(w); v.setSpacing(10)\n",
"        grp = QGroupBox('File Size Format'); gl = QVBoxLayout(grp)\n",
"        self.size_grp = QButtonGroup()\n",
"        opts = [('auto','Auto — smart KB / MB / GB'),('bytes','Bytes — raw count'),\n",
"                ('kb','Kilobytes (KB)'),('mb','Megabytes (MB)'),('gb','Gigabytes (GB)')]\n",
"        self.size_radio = {}\n",
"        for val, lbl in opts:\n",
"            rb = QRadioButton(lbl)\n",
"            self.size_grp.addButton(rb)\n",
"            self.size_radio[val] = rb\n",
"            gl.addWidget(rb)\n",
"        v.addWidget(grp); v.addStretch(); return w\n",
"\n",
"    def _get_size_fmt(self):\n",
"        for k, rb in self.size_radio.items():\n",
"            if rb.isChecked(): return k\n",
"        return 'auto'\n",
"\n",
"    def _tab_sort(self):\n",
"        w = QWidget(); v = QVBoxLayout(w); v.setSpacing(10)\n",
"        grp = QGroupBox('Default Sort Order'); gl = QVBoxLayout(grp)\n",
"        self.sort_grp = QButtonGroup()\n",
"        sorts = [('G','Directories first, then name  (default)'),\n",
"                 ('N','Name  (A to Z)'),('S','Size  (smallest first)'),\n",
"                 ('E','Extension  (A to Z)'),('D','Date  (oldest first)')]\n",
"        self.sort_radio = {}\n",
"        for val, lbl in sorts:\n",
"            rb = QRadioButton(lbl)\n",
"            self.sort_grp.addButton(rb)\n",
"            self.sort_radio[val] = rb\n",
"            gl.addWidget(rb)\n",
"        self.chk_sort_rev = QCheckBox('Reverse order')\n",
"        gl.addWidget(self.chk_sort_rev)\n",
"        v.addWidget(grp); v.addStretch(); return w\n",
"\n",
"    def _tab_skip(self):\n",
"        w = QWidget(); v = QVBoxLayout(w); v.setSpacing(8)\n",
"        note = QLabel('Extra dirs to skip during /S (built-in: __pycache__ .git node_modules site-packages Caches)')\n",
"        note.setWordWrap(True)\n",
"        note.setStyleSheet('color: gray; font-size: 11px;')\n",
"        v.addWidget(note)\n",
"        grp = QGroupBox('Extra skip dirs'); gl = QVBoxLayout(grp)\n",
"        self.skip_list = QListWidget()\n",
"        self.skip_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)\n",
"        gl.addWidget(self.skip_list)\n",
"        row = QHBoxLayout()\n",
"        self.skip_input = QLineEdit()\n",
"        self.skip_input.setPlaceholderText('dirname')\n",
"        b_add = QPushButton('Add')\n",
"        b_del = QPushButton('Remove')\n",
"        b_add.clicked.connect(self._skip_add)\n",
"        b_del.clicked.connect(self._skip_del)\n",
"        self.skip_input.returnPressed.connect(self._skip_add)\n",
"        row.addWidget(self.skip_input); row.addWidget(b_add); row.addWidget(b_del)\n",
"        gl.addLayout(row)\n",
"        v.addWidget(grp); return w\n",
"\n",
"    def _skip_add(self):\n",
"        t = self.skip_input.text().strip()\n",
"        if t: self.skip_list.addItem(t); self.skip_input.clear()\n",
"\n",
"    def _skip_del(self):\n",
"        for item in self.skip_list.selectedItems():\n",
"            self.skip_list.takeItem(self.skip_list.row(item))\n",
"\n",
"    def _load_to_ui(self):\n",
"        self.chk_date.setChecked(self.cfg.get('show_date','1') == '1')\n",
"        self.chk_time.setChecked(self.cfg.get('show_time','1') == '1')\n",
"        self.chk_hidden.setChecked(self.cfg.get('show_hidden','0') == '1')\n",
"        self.chk_thou.setChecked(self.cfg.get('thousand','1') == '1')\n",
"        fmt = self.cfg.get('size_fmt','auto').lower()\n",
"        self.size_radio.get(fmt, self.size_radio['auto']).setChecked(True)\n",
"        sort = self.cfg.get('sort','G').upper()\n",
"        self.sort_radio.get(sort, self.sort_radio['G']).setChecked(True)\n",
"        self.chk_sort_rev.setChecked(self.cfg.get('sort_rev','0') == '1')\n",
"        self.skip_list.clear()\n",
"        for s in self.cfg.get('skip','').split(','):\n",
"            s = s.strip()\n",
"            if s: self.skip_list.addItem(s)\n",
"\n",
"    def _on_save(self):\n",
"        self.cfg['show_date']   = '1' if self.chk_date.isChecked()   else '0'\n",
"        self.cfg['show_time']   = '1' if self.chk_time.isChecked()   else '0'\n",
"        self.cfg['show_hidden'] = '1' if self.chk_hidden.isChecked() else '0'\n",
"        self.cfg['thousand']    = '1' if self.chk_thou.isChecked()   else '0'\n",
"        self.cfg['size_fmt']    = self._get_size_fmt()\n",
"        for k, rb in self.sort_radio.items():\n",
"            if rb.isChecked(): self.cfg['sort'] = k\n",
"        self.cfg['sort_rev'] = '1' if self.chk_sort_rev.isChecked() else '0'\n",
"        items = [self.skip_list.item(i).text() for i in range(self.skip_list.count())]\n",
"        self.cfg['skip'] = ','.join(items)\n",
"        save_config(self.cfg)\n",
"        QMessageBox.information(self, 'Saved', 'Settings saved to ' + DB_PATH)\n",
"\n",
"    def _on_reset(self):\n",
"        if QMessageBox.question(self,'Reset','Reset to defaults?') == QMessageBox.StandardButton.Yes:\n",
"            self.cfg = dict(DEFAULTS)\n",
"            self._load_to_ui()\n",
"\n",
"def main():\n",
"    app = QApplication(sys.argv)\n",
"    app.setStyle('Fusion')\n",
"    win = DirConfigWindow()\n",
"    win.show()\n",
"    sys.exit(app.exec())\n",
"\n",
"if __name__ == '__main__':\n",
"    main()\n",
NULL
};

/* ────────────────────────── config globals ──────────────────────────── */
static int  cfg_show_date   = 1;
static int  cfg_show_time   = 1;
static int  cfg_show_hidden = 0;
static int  cfg_thousand    = 1;
static char cfg_sort        = 'G';
static int  cfg_sort_rev    = 0;
static char cfg_size_fmt[8] = "auto";
static char cfg_skip_extra[1024] = "";

/* ────────────────────────── runtime flags ───────────────────────────── */
static int opt_s=0, opt_b=0, opt_l=0, opt_w=0, opt_p=0, opt_q=0, opt_i=0;
static char opt_a=0;

static long long grand_files=0, grand_bytes=0, grand_dirs=0;

/* ────────────────────────── skip list ──────────────────────────────── */
static const char *SKIP_BUILTIN[] = {
    "__pycache__", ".git", ".svn", ".hg",
    "node_modules", ".Trash", ".Spotlight-V100",
    "Caches", "Mail", "Logs",
    "site-packages", "dist-packages",
    "Python","python3.9","python3.10","python3.11",
    "python3.12","python3.13","python3.14",
    NULL
};
static char user_skip[48][256];
static int  user_skip_count = 0;

static int should_skip(const char *name) {
    if (opt_i) return 0;
    for (int i=0; SKIP_BUILTIN[i]; i++)
        if (strcasecmp(name, SKIP_BUILTIN[i])==0) return 1;
    for (int i=0; i<user_skip_count; i++)
        if (strcasecmp(name, user_skip[i])==0) return 1;
    return 0;
}

/* ────────────────────────── SQLite helpers ──────────────────────────── */
static char g_db_path[512] = "";

static void db_path_init(void) {
    const char *home = getenv("HOME");
    snprintf(g_db_path, sizeof(g_db_path), "%s/.dir.db", home ? home : "/tmp");
}

static sqlite3 *db_open(void) {
    sqlite3 *db = NULL;
    sqlite3_open(g_db_path, &db);
    if (db) {
        sqlite3_exec(db,
            "CREATE TABLE IF NOT EXISTS config "
            "(key TEXT PRIMARY KEY, value TEXT);"
            "CREATE TABLE IF NOT EXISTS scripts "
            "(name TEXT PRIMARY KEY, content TEXT);",
            NULL, NULL, NULL);
    }
    return db;
}

static const char *db_get(sqlite3 *db, const char *key, const char *def,
                           char *buf, int bufsz) {
    strncpy(buf, def, bufsz-1); buf[bufsz-1]='\0';
    sqlite3_stmt *st;
    if (sqlite3_prepare_v2(db,"SELECT value FROM config WHERE key=?",-1,&st,NULL)==SQLITE_OK){
        sqlite3_bind_text(st,1,key,-1,SQLITE_STATIC);
        if (sqlite3_step(st)==SQLITE_ROW){
            const char *v=(const char*)sqlite3_column_text(st,0);
            if(v) strncpy(buf,v,bufsz-1);
        }
        sqlite3_finalize(st);
    }
    return buf;
}

static void load_config(void) {
    sqlite3 *db = db_open();
    if (!db) return;
    char tmp[64];
    cfg_show_date   = atoi(db_get(db,"show_date","1",tmp,sizeof(tmp)));
    cfg_show_time   = atoi(db_get(db,"show_time","1",tmp,sizeof(tmp)));
    cfg_show_hidden = atoi(db_get(db,"show_hidden","0",tmp,sizeof(tmp)));
    cfg_thousand    = atoi(db_get(db,"thousand","1",tmp,sizeof(tmp)));
    cfg_sort        = toupper((unsigned char)db_get(db,"sort","G",tmp,sizeof(tmp))[0]);
    cfg_sort_rev    = atoi(db_get(db,"sort_rev","0",tmp,sizeof(tmp)));
    db_get(db,"size_fmt","auto",cfg_size_fmt,sizeof(cfg_size_fmt));

    char skip_buf[1024];
    db_get(db,"skip","",skip_buf,sizeof(skip_buf));
    if (skip_buf[0]) {
        strncpy(cfg_skip_extra, skip_buf, sizeof(cfg_skip_extra)-1);
        char tmp2[1024]; strncpy(tmp2,skip_buf,sizeof(tmp2)-1);
        char *tok=strtok(tmp2,",");
        while(tok && user_skip_count<48){
            char *t=tok; while(*t==' ')t++;
            strncpy(user_skip[user_skip_count++],t,255);
            tok=strtok(NULL,",");
        }
    }
    sqlite3_close(db);
}

/* ────────────────────────── helpers ────────────────────────────────── */
static int fnci(const char *pat, const char *name) {
    size_t pl=strlen(pat), nl=strlen(name);
    char *p=malloc(pl+1), *n=malloc(nl+1);
    if(!p||!n){free(p);free(n);return FNM_NOMATCH;}
    for(size_t i=0;i<=pl;i++) p[i]=tolower((unsigned char)pat[i]);
    for(size_t i=0;i<=nl;i++) n[i]=tolower((unsigned char)name[i]);
    int r=fnmatch(p,n,0); free(p);free(n); return r;
}

static void lcase(char *s){while(*s){*s=tolower((unsigned char)*s);s++;}}

static char *fmt_count(long long n, char *buf, int bufsz){
    char tmp[32]; snprintf(tmp,sizeof(tmp),"%lld",n);
    if(!cfg_thousand){snprintf(buf,bufsz,"%s",tmp);return buf;}
    int len=(int)strlen(tmp),out=0,comma=len%3;
    for(int i=0;i<len;i++){if(i&&i%3==comma)buf[out++]=',';buf[out++]=tmp[i];}
    buf[out]='\0'; return buf;
}

static char *fmt_size(long long sz, char *buf, int bufsz){
    char fmt[8]; strncpy(fmt,cfg_size_fmt,7); lcase(fmt);
    if(!strcmp(fmt,"auto")){
        if(sz>=1073741824LL)snprintf(buf,bufsz,"%.1f GB",sz/1073741824.0);
        else if(sz>=1048576LL)snprintf(buf,bufsz,"%.1f MB",sz/1048576.0);
        else if(sz>=1024LL)  snprintf(buf,bufsz,"%.1f KB",sz/1024.0);
        else                  snprintf(buf,bufsz,"%lld B",sz);
        return buf;
    }
    if(!strcmp(fmt,"kb")){snprintf(buf,bufsz,"%.1f KB",sz/1024.0);return buf;}
    if(!strcmp(fmt,"mb")){snprintf(buf,bufsz,"%.1f MB",sz/1048576.0);return buf;}
    if(!strcmp(fmt,"gb")){snprintf(buf,bufsz,"%.2f GB",sz/1073741824.0);return buf;}
    /* bytes */
    char tmp[32]; snprintf(tmp,sizeof(tmp),"%lld",sz);
    if(!cfg_thousand){snprintf(buf,bufsz,"%s",tmp);return buf;}
    int len=(int)strlen(tmp),out=0,comma=len%3;
    for(int i=0;i<len;i++){if(i&&i%3==comma)buf[out++]=',';buf[out++]=tmp[i];}
    buf[out]='\0'; return buf;
}

static void get_owner(const char *path,char *buf,int bufsz){
    struct stat st;
    if(stat(path,&st)!=0){snprintf(buf,bufsz,"?");return;}
    struct passwd *pw=getpwuid(st.st_uid);
    snprintf(buf,bufsz,"%s",pw?pw->pw_name:"?");
}

/* ────────────────────────── entry & sort ───────────────────────────── */
typedef struct {
    char  name[512], fullpath[4096], ext[64];
    int   is_dir;
    long long size;
    time_t mtime, ctime, atime;
} Entry;

static char g_skey; static int g_srev;

static int cmp_entries(const void *a,const void *b){
    const Entry *ea=a,*eb=b; int r=0;
    if(g_skey=='G'){if(ea->is_dir&&!eb->is_dir)return -1;if(!ea->is_dir&&eb->is_dir)return 1;}
    switch(g_skey){
        case 'N':r=strcasecmp(ea->name,eb->name);break;
        case 'S':r=(ea->size<eb->size)?-1:(ea->size>eb->size)?1:0;break;
        case 'E':r=strcasecmp(ea->ext,eb->ext);break;
        case 'D':r=(ea->mtime<eb->mtime)?-1:(ea->mtime>eb->mtime)?1:0;break;
        default: r=strcasecmp(ea->name,eb->name);break;
    }
    return g_srev?-r:r;
}

/* ────────────────────────── core listing ───────────────────────────── */
static void list_dir(const char *path, const char *pattern, int level){
    DIR *dh=opendir(path);
    if(!dh){if(!opt_b)fprintf(stderr,"\n     Access is denied — %s\n",path);return;}

    Entry *entries=NULL; int count=0,cap=64;
    entries=malloc(cap*sizeof(Entry));
    char **subdirs=NULL; int scount=0,scap=16;
    subdirs=malloc(scap*sizeof(char*));

    struct dirent *de;
    while((de=readdir(dh))!=NULL){
        if(!strcmp(de->d_name,".")||!strcmp(de->d_name,"..")) continue;
        int is_hidden=(de->d_name[0]=='.');
        if(is_hidden && !opt_a && !cfg_show_hidden) continue;

        int is_dir=(de->d_type==DT_DIR);
        if(de->d_type==DT_UNKNOWN){
            char fp2[4096];snprintf(fp2,sizeof(fp2),"%s/%s",path,de->d_name);
            struct stat s2;if(stat(fp2,&s2)==0)is_dir=S_ISDIR(s2.st_mode);
        }
        if(is_dir&&opt_s&&should_skip(de->d_name))continue;
        if(opt_a=='D'&&!is_dir)continue;
        if(opt_a=='d'&&is_dir)continue;

        char fp[4096]; snprintf(fp,sizeof(fp),"%s/%s",path,de->d_name);
        if(is_dir&&opt_s){
            if(scount>=scap){scap*=2;subdirs=realloc(subdirs,scap*sizeof(char*));}
            subdirs[scount++]=strdup(fp);
        }
        if(pattern&&fnci(pattern,de->d_name)!=0)continue;

        struct stat st; if(stat(fp,&st)!=0)continue;
        if(count>=cap){cap*=2;entries=realloc(entries,cap*sizeof(Entry));}
        Entry *e=&entries[count++];
        strncpy(e->name,de->d_name,511);  e->name[511]='\0';
        strncpy(e->fullpath,fp,4095);     e->fullpath[4095]='\0';
        e->is_dir=is_dir;
        e->size=is_dir?0:(long long)st.st_size;
        e->mtime=st.st_mtime; e->ctime=st.st_birthtime; e->atime=st.st_atime;
        char *dot=strrchr(de->d_name,'.');
        strncpy(e->ext,dot?dot+1:"",63); e->ext[63]='\0';
        if(opt_l)lcase(e->name);
    }
    closedir(dh);

    g_skey=cfg_sort; g_srev=cfg_sort_rev;
    qsort(entries,count,sizeof(Entry),cmp_entries);

    if(!opt_b&&count>0){
        char cwd[4096]; const char *disp=path;
        if(!strcmp(path,".")){getcwd(cwd,sizeof(cwd));disp=cwd;}
        printf("\n Directory of %s\n\n",disp);
    }

    long long dfiles=0,dbytes=0,ddirs=0; int slines=3;
    if(opt_w){
        int col=0;
        for(int i=0;i<count;i++){
            Entry *e=&entries[i]; char tag[80];
            if(e->is_dir)snprintf(tag,sizeof(tag),"[%s]",e->name);
            else snprintf(tag,sizeof(tag),"%s",e->name);
            printf("%-18s ",tag);
            if(++col==5){printf("\n");col=0;slines++;}
            if(opt_p&&slines>=23){fprintf(stderr,"-- more --\n");getchar();slines=0;}
        }
        if(col)printf("\n");
    } else {
        for(int i=0;i<count;i++){
            Entry *e=&entries[i];
            if(opt_b){
                printf("%s\n",opt_s?e->fullpath:e->name);
            } else {
                char prefix[72]="";
                if(cfg_show_date||cfg_show_time){
                    char db[20]="",tb[12]=""; struct tm *tm=localtime(&e->mtime);
                    if(cfg_show_date)strftime(db,sizeof(db),"%m/%d/%Y",tm);
                    if(cfg_show_time)strftime(tb,sizeof(tb),"  %I:%M %p",tm);
                    snprintf(prefix,sizeof(prefix),"%s%s  ",db,tb);
                }
                if(e->is_dir){
                    printf("%s<DIR>          %s\n",prefix,e->name);
                } else {
                    char szb[32]; fmt_size(e->size,szb,sizeof(szb));
                    if(opt_q){
                        char own[64];get_owner(e->fullpath,own,sizeof(own));
                        printf("%s%14s  %-14s  %s\n",prefix,szb,own,e->name);
                    } else {
                        printf("%s%14s  %s\n",prefix,szb,e->name);
                    }
                }
                slines++;
                if(opt_p&&slines>=23){fprintf(stderr,"-- more --\n");getchar();slines=0;}
            }
            if(e->is_dir)ddirs++; else{dfiles++;dbytes+=e->size;}
        }
    }
    grand_files+=dfiles; grand_bytes+=dbytes; grand_dirs+=ddirs;

    if(!opt_b&&!opt_s&&count>0){
        char fb[32],bb[32],db2[32];
        printf("%18s File(s)  %s\n",fmt_count(dfiles,fb,sizeof(fb)),fmt_size(dbytes,bb,sizeof(bb)));
        struct statvfs vfs;
        if(statvfs(path,&vfs)==0){
            long long fr=(long long)vfs.f_bavail*(long long)vfs.f_frsize;
            char frb[32];
            printf("%18s Dir(s)   %s free\n",fmt_count(ddirs,db2,sizeof(db2)),fmt_size(fr,frb,sizeof(frb)));
        }
    }
    for(int i=0;i<scount;i++){list_dir(subdirs[i],pattern,level+1);free(subdirs[i]);}
    free(subdirs); free(entries);
}

/* ────────────────────────── help ───────────────────────────────────── */
static void show_help(void){
    printf(
"\nWindows-style DIR for macOS\n"
"Config: ~/.dir.db (SQLite)  |  GUI: dir -cfg\n"
"\nDIR [path][pattern] [/A[:attr]] [/B] [/C] [/-C] [/I] [/L] [/O[:sort]]\n"
"    [/P] [/Q] [/R] [/S] [/W] [/?] [-cfg]\n"
"\n  /A        All including hidden   /A:D dirs only   /A:-D files only\n"
"  /B        Bare paths\n"
"  /C / /-C  Thousand separators on/off\n"
"  /I        Include skipped dirs\n"
"  /L        Lowercase\n"
"  /O:N/S/E/D/G  Sort (prefix - to reverse)\n"
"  /Q        Show owner\n"
"  /R        Start from home\n"
"  /S        Recurse\n"
"  /W        Wide 5-col\n"
"  -cfg      Config GUI (PyQt6, reads/writes ~/.dir.db)\n"
"  /?        Help\n\n");
}

/* ────────────────────────── -cfg launcher ──────────────────────────── */
static void launch_config_gui(void){
    /* upsert embedded script into DB */
    sqlite3 *db=db_open();
    if(db){
        /* build full script string */
        size_t total=0;
        for(int i=0;GUI_LINES[i];i++) total+=strlen(GUI_LINES[i]);
        char *script=malloc(total+1); script[0]='\0';
        for(int i=0;GUI_LINES[i];i++) strcat(script,GUI_LINES[i]);

        sqlite3_stmt *st;
        if(sqlite3_prepare_v2(db,
            "INSERT OR REPLACE INTO scripts (name,content) VALUES ('dir_config',?)",
            -1,&st,NULL)==SQLITE_OK){
            sqlite3_bind_text(st,1,script,-1,SQLITE_STATIC);
            sqlite3_step(st);
            sqlite3_finalize(st);
        }
        sqlite3_close(db);
        free(script);
    }

    /* extract script to temp file */
    char tmp_path[64]="/tmp/dir_cfg_XXXXXX.py";
    int fd=mkstemps(tmp_path,3);
    if(fd<0){fprintf(stderr,"Cannot create temp file\n");return;}
    for(int i=0;GUI_LINES[i];i++) write(fd,GUI_LINES[i],strlen(GUI_LINES[i]));
    close(fd);

    char cmd[768];
    snprintf(cmd,sizeof(cmd),"python3 '%s' '%s' &",tmp_path,g_db_path);
    system(cmd);
}

/* ────────────────────────── main ───────────────────────────────────── */
int main(int argc, char *argv[]){
    db_path_init();
    load_config();

    const char *path="."; const char *pattern=NULL; int from_home=0;

    for(int i=1;i<argc;i++){
        char *a=argv[i];
        if(!strcmp(a,"-cfg")||!strcmp(a,"--config")){launch_config_gui();return 0;}

        if(a[0]=='/'||a[0]=='-'){
            char sw[64]; strncpy(sw,a+1,63); sw[63]='\0';
            char swu[64]; strncpy(swu,sw,63);
            for(int j=0;swu[j];j++) swu[j]=toupper((unsigned char)swu[j]);

            if(!strcmp(swu,"?"))       {show_help();return 0;}
            else if(!strcmp(swu,"S"))  opt_s=1;
            else if(!strcmp(swu,"B"))  opt_b=1;
            else if(!strcmp(swu,"L"))  opt_l=1;
            else if(!strcmp(swu,"W"))  opt_w=1;
            else if(!strcmp(swu,"P"))  opt_p=1;
            else if(!strcmp(swu,"Q"))  opt_q=1;
            else if(!strcmp(swu,"I"))  opt_i=1;
            else if(!strcmp(swu,"R"))  from_home=1;
            else if(!strcmp(swu,"C"))  cfg_thousand=1;
            else if(!strcmp(swu,"-C")) cfg_thousand=0;
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
                } else {cfg_sort='N';cfg_sort_rev=0;}
            }
            else if(!strncmp(swu,"X",1)){
                char *col=strchr(sw,':');
                if(col&&user_skip_count<48)strncpy(user_skip[user_skip_count++],col+1,255);
            }
            else{fprintf(stderr,"\n  Invalid switch: \"%s\"  —  DIR /?\n\n",a);return 1;}
        }
        else if(strchr(a,'*')||strchr(a,'?')) pattern=a;
        else path=a;
    }

    if(from_home){const char *h=getenv("HOME");path=h?h:"/Users";}

    if(!opt_b){
        char cwd[4096];
        const char *dp=(!strcmp(path,".")&&getcwd(cwd,sizeof(cwd)))?cwd:path;
        printf("\n Volume: macOS  |  Path: %s\n",dp);
    }

    list_dir(path,pattern,0);

    if(!opt_b&&opt_s){
        if(grand_files==0&&pattern){
            printf("\n     File Not Found\n\n");
        } else {
            char fb[32],bb[32],db[32];
            printf("\n     Total Files Listed:\n");
            printf("%18s File(s)  %s\n",fmt_count(grand_files,fb,sizeof(fb)),fmt_size(grand_bytes,bb,sizeof(bb)));
            printf("%18s Dir(s)\n",fmt_count(grand_dirs,db,sizeof(db)));
            struct statvfs vfs;
            if(statvfs(path,&vfs)==0){
                long long fr=(long long)vfs.f_bavail*(long long)vfs.f_frsize;
                char frb[32];
                printf("                   %s free\n",fmt_size(fr,frb,sizeof(frb)));
            }
        }
    }
    return 0;
}
