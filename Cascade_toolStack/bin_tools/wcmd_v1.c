/*
 * wcmd.c  —  Database-Driven Command Kernel
 *
 * Single binary, dispatches by argv[0] basename:
 *   dir  del  md  rd  move  copy  type  ren
 *
 * Knowledge layer: ~/.wcmd.db  (SQLite)
 *   commands        — registered commands
 *   command_flags   — flags per command + descriptions
 *   behaviors       — per-command config defaults
 *   help_sections   — help text stored in DB
 *   ui_modules      — PyQt6 GUI scripts
 *   system_config   — global settings
 *
 * GUI: wcmd -cfg  (or dir -cfg  etc.)
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
#include <zlib.h>

/* ═══════════════════════════════════════════════════════════════════════
   I.  EMBEDDED DEFAULT DATABASE (gzipped SQLite, 2.3KB → 53KB)
   ═══════════════════════════════════════════════════════════════════════ */

#include "/tmp/db_embed.c"

/* extract embedded gzipped DB to disk */
static int db_extract(const char *out_path){
    FILE *f=fopen(out_path,"wb");if(!f)return 0;
    z_stream zs={0};
    if(inflateInit2(&zs,15+32)!=Z_OK){fclose(f);return 0;} /* auto gzip/zlib */
    zs.next_in=(Bytef*)WCMD_DB_GZ;
    zs.avail_in=WCMD_DB_GZ_LEN;
    unsigned char out[65536];
    int ret;
    do{
        zs.next_out=out; zs.avail_out=sizeof(out);
        ret=inflate(&zs,Z_NO_FLUSH);
        if(ret<0&&ret!=Z_BUF_ERROR){inflateEnd(&zs);fclose(f);return 0;}
        size_t written=sizeof(out)-zs.avail_out;
        if(written>0)fwrite(out,1,written,f);
    }while(ret!=Z_STREAM_END);
    inflateEnd(&zs);fclose(f);
    return 1;
}

/* schema fallback for upgrades */
static const char *SCHEMA_SQL =
"CREATE TABLE IF NOT EXISTS commands ("
"  id INTEGER PRIMARY KEY AUTOINCREMENT,"
"  name TEXT UNIQUE NOT NULL,"
"  description TEXT,"
"  version TEXT DEFAULT '1.0',"
"  enabled INTEGER DEFAULT 1"
");"
"CREATE TABLE IF NOT EXISTS command_flags ("
"  id INTEGER PRIMARY KEY AUTOINCREMENT,"
"  command_id INTEGER REFERENCES commands(id),"
"  flag TEXT NOT NULL,"
"  description TEXT,"
"  flag_type TEXT DEFAULT 'bool',"
"  default_val TEXT DEFAULT '0'"
");"
"CREATE TABLE IF NOT EXISTS behaviors ("
"  id INTEGER PRIMARY KEY AUTOINCREMENT,"
"  command_id INTEGER REFERENCES commands(id),"
"  key TEXT NOT NULL,"
"  value TEXT,"
"  description TEXT,"
"  UNIQUE(command_id, key)"
");"
"CREATE TABLE IF NOT EXISTS help_sections ("
"  id INTEGER PRIMARY KEY AUTOINCREMENT,"
"  command_id INTEGER REFERENCES commands(id),"
"  section TEXT,"
"  content TEXT,"
"  sort_order INTEGER DEFAULT 0,"
"  UNIQUE(command_id, section)"
");"
"CREATE TABLE IF NOT EXISTS ui_modules ("
"  id INTEGER PRIMARY KEY AUTOINCREMENT,"
"  name TEXT UNIQUE NOT NULL,"
"  description TEXT,"
"  script TEXT,"
"  version INTEGER DEFAULT 1"
");"
"CREATE TABLE IF NOT EXISTS system_config ("
"  key TEXT PRIMARY KEY,"
"  value TEXT,"
"  description TEXT"
");"

/* ═══════════════════════════════════════════════════════════════════════
   II.  EMBEDDED GUI SCRIPT  (Python, single-quoted, stored in DB)
   ═══════════════════════════════════════════════════════════════════════ */

static const char *GUI_LINES[] = {
"#!/usr/bin/env python3\n",
"import sys, os, sqlite3\n",
"try:\n",
"    from PyQt6.QtWidgets import (\n",
"        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,\n",
"        QGroupBox, QCheckBox, QRadioButton, QButtonGroup, QLabel,\n",
"        QPushButton, QListWidget, QListWidgetItem, QLineEdit,\n",
"        QAbstractItemView, QMessageBox, QTabWidget, QTableWidget,\n",
"        QTableWidgetItem, QHeaderView, QSplitter, QTextEdit)\n",
"    from PyQt6.QtGui import QFont, QColor\n",
"    from PyQt6.QtCore import Qt\n",
"except ImportError:\n",
"    print('PyQt6 not found.  Install:  pip install PyQt6')\n",
"    sys.exit(1)\n",
"\n",
"DB = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser('~/.wcmd.db')\n",
"\n",
"BEHAVIOR_DEFAULTS = {\n",
"    'show_date': '1', 'show_time': '1', 'show_hidden': '0',\n",
"    'thousand': '1', 'sort': 'G', 'sort_rev': '0',\n",
"    'size_fmt': 'auto', 'skip': '__pycache__,.git,node_modules,site-packages',\n",
"}\n",
"\n",
"def con():\n",
"    c = sqlite3.connect(DB)\n",
"    c.row_factory = sqlite3.Row\n",
"    return c\n",
"\n",
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
"\n",
"def save_dir_cfg(cfg):\n",
"    db = con()\n",
"    row = db.execute('SELECT id FROM commands WHERE name=?',('DIR',)).fetchone()\n",
"    if row:\n",
"        cid = row['id']\n",
"        for k,v in cfg.items():\n",
"            db.execute('INSERT OR REPLACE INTO behaviors (command_id,key,value) VALUES (?,?,?)',(cid,k,v))\n",
"    db.commit(); db.close()\n",
"\n",
"class WCmdWindow(QMainWindow):\n",
"    def __init__(self):\n",
"        super().__init__()\n",
"        self.setWindowTitle('WCMD  Command System  —  ' + DB)\n",
"        self.setMinimumSize(640, 560)\n",
"        self.cfg = load_dir_cfg()\n",
"        self._build()\n",
"        self._load()\n",
"\n",
"    def _build(self):\n",
"        c = QWidget(); self.setCentralWidget(c)\n",
"        root = QVBoxLayout(c); root.setSpacing(8); root.setContentsMargins(12,12,12,12)\n",
"        hdr = QLabel('WCMD  Database-Driven Command System')\n",
"        hdr.setFont(QFont('Helvetica',15,QFont.Weight.Bold))\n",
"        root.addWidget(hdr)\n",
"        sub = QLabel('Knowledge layer:  ' + DB + '  (SQLite)')\n",
"        sub.setStyleSheet('color:gray;font-size:11px;')\n",
"        root.addWidget(sub)\n",
"        tabs = QTabWidget(); root.addWidget(tabs)\n",
"        tabs.addTab(self._tab_commands(), 'Commands')\n",
"        tabs.addTab(self._tab_display(),  'DIR Display')\n",
"        tabs.addTab(self._tab_size(),     'DIR Size')\n",
"        tabs.addTab(self._tab_sort(),     'DIR Sort')\n",
"        tabs.addTab(self._tab_skip(),     'Skip Dirs')\n",
"        row = QHBoxLayout()\n",
"        b_save  = QPushButton('Save DIR settings')\n",
"        b_reset = QPushButton('Reset Defaults')\n",
"        b_close = QPushButton('Close')\n",
"        b_save.setDefault(True)\n",
"        b_save.clicked.connect(self._save)\n",
"        b_reset.clicked.connect(self._reset)\n",
"        b_close.clicked.connect(self.close)\n",
"        row.addStretch(); row.addWidget(b_reset); row.addWidget(b_save); row.addWidget(b_close)\n",
"        root.addLayout(row)\n",
"\n",
"    def _tab_commands(self):\n",
"        w = QWidget(); v = QVBoxLayout(w)\n",
"        lbl = QLabel('Registered commands in DB  (all powered by the same wcmd kernel)')\n",
"        lbl.setStyleSheet('color:gray;font-size:11px;')\n",
"        v.addWidget(lbl)\n",
"        self.cmd_table = QTableWidget()\n",
"        self.cmd_table.setColumnCount(4)\n",
"        self.cmd_table.setHorizontalHeaderLabels(['Command','Version','Description','Enabled'])\n",
"        self.cmd_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)\n",
"        self.cmd_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)\n",
"        self.cmd_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)\n",
"        v.addWidget(self.cmd_table)\n",
"        self._refresh_cmds()\n",
"        return w\n",
"\n",
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
"        except Exception as e:\n",
"            pass\n",
"\n",
"    def _tab_display(self):\n",
"        w = QWidget(); v = QVBoxLayout(w); v.setSpacing(10)\n",
"        grp = QGroupBox('DIR Output Columns'); gl = QVBoxLayout(grp)\n",
"        self.chk_date   = QCheckBox('Show date  (mm/dd/yyyy)')\n",
"        self.chk_time   = QCheckBox('Show time  (hh:mm AM/PM)')\n",
"        self.chk_hidden = QCheckBox('Show hidden files')\n",
"        self.chk_thou   = QCheckBox('Thousand separators  (1,234,567)')\n",
"        for c in [self.chk_date,self.chk_time,self.chk_hidden,self.chk_thou]: gl.addWidget(c)\n",
"        v.addWidget(grp); v.addStretch(); return w\n",
"\n",
"    def _tab_size(self):\n",
"        w = QWidget(); v = QVBoxLayout(w); v.setSpacing(10)\n",
"        grp = QGroupBox('File Size Format'); gl = QVBoxLayout(grp)\n",
"        self.size_grp = QButtonGroup()\n",
"        opts = [('auto','Auto  KB/MB/GB'),('bytes','Bytes'),('kb','KB'),('mb','MB'),('gb','GB')]\n",
"        self.size_rb = {}\n",
"        for val,lbl in opts:\n",
"            rb = QRadioButton(lbl); self.size_grp.addButton(rb)\n",
"            self.size_rb[val]=rb; gl.addWidget(rb)\n",
"        v.addWidget(grp); v.addStretch(); return w\n",
"\n",
"    def _get_sz(self):\n",
"        for k,rb in self.size_rb.items():\n",
"            if rb.isChecked(): return k\n",
"        return 'auto'\n",
"\n",
"    def _tab_sort(self):\n",
"        w = QWidget(); v = QVBoxLayout(w); v.setSpacing(10)\n",
"        grp = QGroupBox('Default Sort'); gl = QVBoxLayout(grp)\n",
"        self.sort_grp = QButtonGroup()\n",
"        sorts = [('G','Dirs first (default)'),('N','Name'),('S','Size'),('E','Extension'),('D','Date')]\n",
"        self.sort_rb = {}\n",
"        for val,lbl in sorts:\n",
"            rb = QRadioButton(lbl); self.sort_grp.addButton(rb)\n",
"            self.sort_rb[val]=rb; gl.addWidget(rb)\n",
"        self.chk_rev = QCheckBox('Reverse order'); gl.addWidget(self.chk_rev)\n",
"        v.addWidget(grp); v.addStretch(); return w\n",
"\n",
"    def _tab_skip(self):\n",
"        w = QWidget(); v = QVBoxLayout(w); v.setSpacing(8)\n",
"        note = QLabel('Extra dirs skipped during /S  (built-in: __pycache__ .git node_modules site-packages Caches)')\n",
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
"\n",
"    def _skip_add(self):\n",
"        t=self.skip_in.text().strip()\n",
"        if t: self.skip_list.addItem(t); self.skip_in.clear()\n",
"\n",
"    def _skip_del(self):\n",
"        for item in self.skip_list.selectedItems():\n",
"            self.skip_list.takeItem(self.skip_list.row(item))\n",
"\n",
"    def _load(self):\n",
"        self.chk_date.setChecked(self.cfg.get('show_date','1')=='1')\n",
"        self.chk_time.setChecked(self.cfg.get('show_time','1')=='1')\n",
"        self.chk_hidden.setChecked(self.cfg.get('show_hidden','0')=='1')\n",
"        self.chk_thou.setChecked(self.cfg.get('thousand','1')=='1')\n",
"        self.size_rb.get(self.cfg.get('size_fmt','auto'),self.size_rb['auto']).setChecked(True)\n",
"        self.sort_rb.get(self.cfg.get('sort','G').upper(),self.sort_rb['G']).setChecked(True)\n",
"        self.chk_rev.setChecked(self.cfg.get('sort_rev','0')=='1')\n",
"        self.skip_list.clear()\n",
"        for s in self.cfg.get('skip','').split(','):\n",
"            s=s.strip()\n",
"            if s: self.skip_list.addItem(s)\n",
"\n",
"    def _save(self):\n",
"        self.cfg['show_date']   = '1' if self.chk_date.isChecked()   else '0'\n",
"        self.cfg['show_time']   = '1' if self.chk_time.isChecked()   else '0'\n",
"        self.cfg['show_hidden'] = '1' if self.chk_hidden.isChecked() else '0'\n",
"        self.cfg['thousand']    = '1' if self.chk_thou.isChecked()   else '0'\n",
"        self.cfg['size_fmt']    = self._get_sz()\n",
"        for k,rb in self.sort_rb.items():\n",
"            if rb.isChecked(): self.cfg['sort']=k\n",
"        self.cfg['sort_rev'] = '1' if self.chk_rev.isChecked() else '0'\n",
"        items = [self.skip_list.item(i).text() for i in range(self.skip_list.count())]\n",
"        self.cfg['skip'] = ','.join(items)\n",
"        save_dir_cfg(self.cfg)\n",
"        QMessageBox.information(self,'Saved','DIR settings saved to ' + DB)\n",
"\n",
"    def _reset(self):\n",
"        if QMessageBox.question(self,'Reset','Reset DIR settings to defaults?') == QMessageBox.StandardButton.Yes:\n",
"            self.cfg = dict(BEHAVIOR_DEFAULTS); self._load()\n",
"\n",
"def main():\n",
"    app = QApplication(sys.argv)\n",
"    app.setStyle('Fusion')\n",
"    win = WCmdWindow(); win.show()\n",
"    sys.exit(app.exec())\n",
"\n",
"if __name__ == '__main__':\n",
"    main()\n",
NULL
};

/* ═══════════════════════════════════════════════════════════════════════
   III. GLOBAL CONFIG + SKIP LIST
   ═══════════════════════════════════════════════════════════════════════ */

static char g_db_path[512] = "";

static int  cfg_show_date=1, cfg_show_time=1, cfg_show_hidden=0;
static int  cfg_thousand=1;
static char cfg_sort='G';
static int  cfg_sort_rev=0;
static char cfg_size_fmt[8]="auto";

static int opt_s=0, opt_b=0, opt_l=0, opt_w=0;
static int opt_p=0, opt_q=0, opt_i=0;
static char opt_a=0;

static long long grand_files=0, grand_bytes=0, grand_dirs=0;

static const char *SKIP_BUILTIN[] = {
    "__pycache__",".git",".svn",".hg","node_modules",
    ".Trash",".Spotlight-V100","Caches","Mail","Logs",
    "site-packages","dist-packages",
    "Python","python3.9","python3.10","python3.11",
    "python3.12","python3.13","python3.14",
    NULL
};
static char user_skip[48][256];
static int  user_skip_count=0;

static int should_skip(const char *n){
    if(opt_i)return 0;
    for(int i=0;SKIP_BUILTIN[i];i++) if(strcasecmp(n,SKIP_BUILTIN[i])==0)return 1;
    for(int i=0;i<user_skip_count;i++) if(strcasecmp(n,user_skip[i])==0)return 1;
    return 0;
}

/* ═══════════════════════════════════════════════════════════════════════
   IV. SQLITE HELPERS + BOOTSTRAP
   ═══════════════════════════════════════════════════════════════════════ */

static sqlite3 *db_open(void){
    sqlite3 *db=NULL;
    sqlite3_open(g_db_path,&db);
    if(db) sqlite3_exec(db,SCHEMA_SQL,NULL,NULL,NULL);
    return db;
}

static const char *db_get(sqlite3 *db,const char *tbl,const char *cmd_name,
                           const char *key,const char *def,char *buf,int bsz){
    strncpy(buf,def,bsz-1);buf[bsz-1]='\0';
    char sql[256];
    snprintf(sql,sizeof(sql),
        "SELECT b.value FROM behaviors b "
        "JOIN commands c ON c.id=b.command_id "
        "WHERE c.name=? AND b.key=?");
    sqlite3_stmt *st;
    if(sqlite3_prepare_v2(db,sql,-1,&st,NULL)==SQLITE_OK){
        sqlite3_bind_text(st,1,cmd_name,-1,SQLITE_STATIC);
        sqlite3_bind_text(st,2,key,-1,SQLITE_STATIC);
        if(sqlite3_step(st)==SQLITE_ROW){
            const char *v=(const char*)sqlite3_column_text(st,0);
            if(v)strncpy(buf,v,bsz-1);
        }
        sqlite3_finalize(st);
    }
    return buf;
}

static void db_bootstrap(sqlite3 *db){
    /* commands */
    static const char *cmds[][3]={
        {"DIR",  "Display files and subdirectories","1.2"},
        {"DEL",  "Delete files",                   "1.0"},
        {"MD",   "Create directory",               "1.0"},
        {"RD",   "Remove directory",               "1.0"},
        {"MOVE", "Move or rename files",           "1.0"},
        {"COPY", "Copy files",                     "1.0"},
        {"TYPE", "Display file contents",          "1.0"},
        {"REN",  "Rename files (alias for MOVE)",  "1.0"},
        {NULL,NULL,NULL}
    };
    for(int i=0;cmds[i][0];i++){
        sqlite3_stmt *st;
        sqlite3_prepare_v2(db,
            "INSERT OR IGNORE INTO commands (name,description,version) VALUES (?,?,?)",
            -1,&st,NULL);
        sqlite3_bind_text(st,1,cmds[i][0],-1,SQLITE_STATIC);
        sqlite3_bind_text(st,2,cmds[i][1],-1,SQLITE_STATIC);
        sqlite3_bind_text(st,3,cmds[i][2],-1,SQLITE_STATIC);
        sqlite3_step(st); sqlite3_finalize(st);
    }

    /* DIR behaviors (only insert if missing) */
    static const char *dir_behaviors[][3]={
        {"show_date",  "1",    "Show date column"},
        {"show_time",  "1",    "Show time column"},
        {"show_hidden","0",    "Show hidden files by default"},
        {"thousand",   "1",    "Thousand separators"},
        {"sort",       "G",    "Default sort (G=dirs first)"},
        {"sort_rev",   "0",    "Reverse sort"},
        {"size_fmt",   "auto", "Size format: auto/bytes/kb/mb/gb"},
        {"skip",       "__pycache__,.git,node_modules,site-packages","Extra skip dirs"},
        {NULL,NULL,NULL}
    };
    sqlite3_stmt *cid_st;
    sqlite3_prepare_v2(db,"SELECT id FROM commands WHERE name='DIR'",-1,&cid_st,NULL);
    long long dir_id=0;
    if(sqlite3_step(cid_st)==SQLITE_ROW) dir_id=sqlite3_column_int64(cid_st,0);
    sqlite3_finalize(cid_st);
    if(dir_id>0){
        for(int i=0;dir_behaviors[i][0];i++){
            sqlite3_stmt *st;
            sqlite3_prepare_v2(db,
                "INSERT OR IGNORE INTO behaviors (command_id,key,value,description) VALUES (?,?,?,?)",
                -1,&st,NULL);
            sqlite3_bind_int64(st,1,dir_id);
            sqlite3_bind_text(st,2,dir_behaviors[i][0],-1,SQLITE_STATIC);
            sqlite3_bind_text(st,3,dir_behaviors[i][1],-1,SQLITE_STATIC);
            sqlite3_bind_text(st,4,dir_behaviors[i][2],-1,SQLITE_STATIC);
            sqlite3_step(st); sqlite3_finalize(st);
        }
    }

    /* help_sections for all commands */
    struct {const char *cmd; const char *section; const char *content; int order;} help[] = {
        {"DIR","DIR — Display files and subdirectories",
         "  DIR [path][pattern] [/A] [/B] [/I] [/L] [/O:key] [/P] [/Q] [/R] [/S] [/W] [/?] [-cfg]\n"
         "  /A        All files incl hidden   /A:D dirs   /A:-D files only\n"
         "  /B        Bare paths (no header/summary)\n"
         "  /I        Include all dirs (ignore skip list)\n"
         "  /L        Lowercase output\n"
         "  /O:N/S/E/D/G  Sort (prefix - reverses)\n"
         "  /P        Pause each screen\n"
         "  /Q        Show owner\n"
         "  /R        Start from home directory\n"
         "  /S        Recurse subdirectories\n"
         "  /W        Wide 5-column format\n"
         "  /X:name   Exclude named dir during /S\n"
         "  -cfg      Open configuration GUI\n"
         "  /?        Show this help\n",1},

        {"DEL","DEL — Delete files",
         "  DEL pattern [/S] [/Q] [/?]\n"
         "  pattern   Filename or wildcard (e.g. *.tmp)\n"
         "  /S        Recurse subdirectories\n"
         "  /Q        No confirmation prompt\n"
         "  /?        Show this help\n",1},

        {"MD","MD — Create directory",
         "  MD dirname [dirname2 ...]\n"
         "  Creates directories recursively (like mkdir -p).\n",1},

        {"RD","RD — Remove directory",
         "  RD dirname [/S] [/?]\n"
         "  /S        Remove recursively with all contents (confirmation)\n"
         "  /?        Show this help\n",1},

        {"MOVE","MOVE — Move or rename files",
         "  MOVE source destination\n"
         "  Moves source file/directory to destination path.\n"
         "  Cross-device moves handled automatically.\n",1},

        {"COPY","COPY — Copy files",
         "  COPY source destination [/Y] [/?]\n"
         "  /Y        Overwrite without confirmation\n"
         "  /?        Show this help\n",1},

        {"TYPE","TYPE — Display file contents",
         "  TYPE filename [filename2 ...]\n"
         "  Prints each file to stdout.\n",1},

        {"REN","REN — Rename file",
         "  REN oldname newname\n"
         "  Same as MOVE. Renames a single file or directory.\n",1},
        {NULL,NULL,NULL,0}
    };
    for(int i=0;help[i].cmd;i++){
        sqlite3_stmt *cid;
        sqlite3_prepare_v2(db,"SELECT id FROM commands WHERE name=?",-1,&cid,NULL);
        sqlite3_bind_text(cid,1,help[i].cmd,-1,SQLITE_STATIC);
        long long cid_val=0;
        if(sqlite3_step(cid)==SQLITE_ROW) cid_val=sqlite3_column_int64(cid,0);
        sqlite3_finalize(cid);
        if(cid_val>0){
            sqlite3_stmt *st;
            sqlite3_prepare_v2(db,
                "INSERT OR IGNORE INTO help_sections (command_id,section,content,sort_order) VALUES (?,?,?,?)",
                -1,&st,NULL);
            sqlite3_bind_int64(st,1,cid_val);
            sqlite3_bind_text(st,2,help[i].section,-1,SQLITE_STATIC);
            sqlite3_bind_text(st,3,help[i].content,-1,SQLITE_STATIC);
            sqlite3_bind_int(st,4,help[i].order);
            sqlite3_step(st); sqlite3_finalize(st);
        }
    }
}

/* print help for a command from DB (self-contained) */
static void db_help(const char *cmd_name){
    sqlite3 *db=db_open();
    if(!db){printf("  Help unavailable.\n");return;}
    char sql[256];
    snprintf(sql,sizeof(sql),
        "SELECT section,content FROM help_sections "
        "JOIN commands c ON c.id=help_sections.command_id "
        "WHERE c.name=? ORDER BY sort_order");
    sqlite3_stmt *st;
    int has_rows=0;
    if(sqlite3_prepare_v2(db,sql,-1,&st,NULL)==SQLITE_OK){
        sqlite3_bind_text(st,1,cmd_name,-1,SQLITE_STATIC);
        while(sqlite3_step(st)==SQLITE_ROW){
            has_rows=1;
            const char *section=(const char*)sqlite3_column_text(st,0);
            const char *content=(const char*)sqlite3_column_text(st,1);
            if(section&&section[0])printf("\n%s\n",section);
            if(content&&content[0])printf("%s",content);
        }
        sqlite3_finalize(st);
    }
    sqlite3_close(db);
    if(has_rows)printf("\n");
    else printf("\n  No help found for %s.  Use /? after running once to bootstrap.\n\n",cmd_name);
}

static void load_config(sqlite3 *db){
    char tmp[64];
    cfg_show_date  =atoi(db_get(db,NULL,"DIR","show_date",  "1",tmp,sizeof(tmp)));
    cfg_show_time  =atoi(db_get(db,NULL,"DIR","show_time",  "1",tmp,sizeof(tmp)));
    cfg_show_hidden=atoi(db_get(db,NULL,"DIR","show_hidden","0",tmp,sizeof(tmp)));
    cfg_thousand   =atoi(db_get(db,NULL,"DIR","thousand",   "1",tmp,sizeof(tmp)));
    cfg_sort       =toupper((unsigned char)db_get(db,NULL,"DIR","sort","G",tmp,sizeof(tmp))[0]);
    cfg_sort_rev   =atoi(db_get(db,NULL,"DIR","sort_rev",   "0",tmp,sizeof(tmp)));
    db_get(db,NULL,"DIR","size_fmt","auto",cfg_size_fmt,sizeof(cfg_size_fmt));

    char skip_buf[1024];
    db_get(db,NULL,"DIR","skip","",skip_buf,sizeof(skip_buf));
    if(skip_buf[0]){
        char tmp2[1024]; strncpy(tmp2,skip_buf,sizeof(tmp2)-1);
        char *tok=strtok(tmp2,",");
        while(tok&&user_skip_count<48){
            char *t=tok;while(*t==' ')t++;
            strncpy(user_skip[user_skip_count++],t,255);
            tok=strtok(NULL,",");
        }
    }
}

/* ═══════════════════════════════════════════════════════════════════════
   V.  COMMON UTILITIES
   ═══════════════════════════════════════════════════════════════════════ */

static int fnci(const char *pat,const char *name){
    size_t pl=strlen(pat),nl=strlen(name);
    char *p=malloc(pl+1),*n=malloc(nl+1);
    if(!p||!n){free(p);free(n);return FNM_NOMATCH;}
    for(size_t i=0;i<=pl;i++)p[i]=tolower((unsigned char)pat[i]);
    for(size_t i=0;i<=nl;i++)n[i]=tolower((unsigned char)name[i]);
    int r=fnmatch(p,n,0);free(p);free(n);return r;
}

static void lcase(char *s){while(*s){*s=tolower((unsigned char)*s);s++;}}

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

/* ═══════════════════════════════════════════════════════════════════════
   VI.  DIR COMMAND
   ═══════════════════════════════════════════════════════════════════════ */

typedef struct {
    char name[512],fullpath[4096],ext[64];
    int is_dir; long long size;
    time_t mtime,ctime,atime;
} Entry;

static char g_sk;static int g_sr;
static int cmp_e(const void *a,const void *b){
    const Entry *ea=a,*eb=b;int r=0;
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
    Entry *entries=NULL;int count=0,cap=64;
    entries=malloc(cap*sizeof(Entry));
    char **subdirs=NULL;int scount=0,scap=16;
    subdirs=malloc(scap*sizeof(char*));
    struct dirent *de;
    while((de=readdir(dh))!=NULL){
        if(!strcmp(de->d_name,".")||!strcmp(de->d_name,".."))continue;
        int ih=(de->d_name[0]=='.');
        if(ih&&!opt_a&&!cfg_show_hidden)continue;
        int isd=(de->d_type==DT_DIR);
        if(de->d_type==DT_UNKNOWN){
            char fp2[4096];snprintf(fp2,sizeof(fp2),"%s/%s",path,de->d_name);
            struct stat s2;if(stat(fp2,&s2)==0)isd=S_ISDIR(s2.st_mode);
        }
        if(isd&&opt_s&&should_skip(de->d_name))continue;
        if(opt_a=='D'&&!isd)continue;
        if(opt_a=='d'&&isd)continue;
        char fp[4096];snprintf(fp,sizeof(fp),"%s/%s",path,de->d_name);
        if(isd&&opt_s){
            if(scount>=scap){scap*=2;subdirs=realloc(subdirs,scap*sizeof(char*));}
            subdirs[scount++]=strdup(fp);
        }
        if(pattern&&fnci(pattern,de->d_name)!=0)continue;
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
    g_sk=cfg_sort;g_sr=cfg_sort_rev;
    qsort(entries,count,sizeof(Entry),cmp_e);
    if(!opt_b&&count>0){
        char cwd[4096];const char *dp=path;
        if(!strcmp(path,".")){getcwd(cwd,sizeof(cwd));dp=cwd;}
        printf("\n Directory of %s\n\n",dp);
    }
    long long df=0,db=0,dd=0;int sl=3;
    if(opt_w){
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
    if(!opt_b&&!opt_s&&count>0){
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

static int cmd_dir(int argc,char *argv[]){
    const char *path=".";const char *pattern=NULL;int from_home=0;
    for(int i=1;i<argc;i++){
        char *a=argv[i];
        if(a[0]=='/'||a[0]=='-'){
            char sw[64];strncpy(sw,a+1,63);sw[63]='\0';
            char swu[64];strncpy(swu,sw,63);
            for(int j=0;swu[j];j++)swu[j]=toupper((unsigned char)swu[j]);
            if(!strcmp(swu,"?")){db_help("DIR");return 0;}
            else if(!strcmp(swu,"S"))opt_s=1;
            else if(!strcmp(swu,"B"))opt_b=1;
            else if(!strcmp(swu,"L"))opt_l=1;
            else if(!strcmp(swu,"W"))opt_w=1;
            else if(!strcmp(swu,"P"))opt_p=1;
            else if(!strcmp(swu,"Q"))opt_q=1;
            else if(!strcmp(swu,"I"))opt_i=1;
            else if(!strcmp(swu,"R"))from_home=1;
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
    if(!opt_b){
        char cwd[4096];
        const char *dp=(!strcmp(path,".")&&getcwd(cwd,sizeof(cwd)))?cwd:path;
        printf("\n Volume: macOS  |  Path: %s\n",dp);
    }
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
    return 0;
}

/* ═══════════════════════════════════════════════════════════════════════
   VII.  DEL COMMAND
   ═══════════════════════════════════════════════════════════════════════ */

static int del_one(const char *fp,int opt_force,int opt_quiet,int *del_count){
    if(!opt_quiet){
        printf("  Delete: %s ? [Y/N] ",fp);fflush(stdout);
        char ch=getchar();while(getchar()!='\n'){}
        if(ch!='y'&&ch!='Y')return 0;
    }
    if(remove(fp)==0){(*del_count)++;return 1;}
    fprintf(stderr,"  Cannot delete %s: %s\n",fp,strerror(errno));
    return 0;
}

static void del_scan(const char *path,const char *pattern,
                     int recurse,int force,int quiet,int *cnt){
    DIR *dh=opendir(path);if(!dh)return;
    struct dirent *de;
    while((de=readdir(dh))!=NULL){
        if(!strcmp(de->d_name,".")||!strcmp(de->d_name,".."))continue;
        char fp[4096];snprintf(fp,sizeof(fp),"%s/%s",path,de->d_name);
        int isd=(de->d_type==DT_DIR);
        if(de->d_type==DT_UNKNOWN){struct stat s;if(stat(fp,&s)==0)isd=S_ISDIR(s.st_mode);}
        if(isd){if(recurse)del_scan(fp,pattern,recurse,force,quiet,cnt);}
        else{
            if(!pattern||fnci(pattern,de->d_name)==0)
                del_one(fp,force,quiet,cnt);
        }
    }
    closedir(dh);
}

static int cmd_del(int argc,char *argv[]){
    const char *path=".";const char *pattern=NULL;
    int recurse=0,force=0,quiet=0;
    for(int i=1;i<argc;i++){
        char *a=argv[i];
        if(a[0]=='/'||a[0]=='-'){
            char sw[16];strncpy(sw,a+1,15);sw[15]='\0';
            char swu[16];strncpy(swu,sw,15);
            for(int j=0;swu[j];j++)swu[j]=toupper((unsigned char)swu[j]);
            if(!strcmp(swu,"S"))recurse=1;
            else if(!strcmp(swu,"F")||!strcmp(swu,"Q"))quiet=1;
            else if(!strcmp(swu,"?")){db_help("DEL");return 0;}
        }
        else if(strchr(a,'*')||strchr(a,'?'))pattern=a;
        else path=a;
    }
    if(!pattern&&!strcmp(path,".")){fprintf(stderr,"DEL: specify a pattern or filename.\n");return 1;}

    /* single file (no wildcard) */
    if(!pattern){
        int cnt=0;del_one(path,force,quiet,&cnt);
        printf("  %d file(s) deleted.\n",cnt);return 0;
    }
    /* wildcard — safety confirm unless /Q */
    if(!quiet){
        printf("  Delete all '%s' in %s%s? [Y/N] ",
               pattern,path,recurse?" (recursive)":"");
        fflush(stdout);char ch=getchar();while(getchar()!='\n'){}
        if(ch!='y'&&ch!='Y'){printf("  Cancelled.\n");return 0;}
        quiet=1; /* already confirmed once */
    }
    int cnt=0;del_scan(path,pattern,recurse,force,quiet,&cnt);
    printf("  %d file(s) deleted.\n",cnt);
    return 0;
}

/* ═══════════════════════════════════════════════════════════════════════
   VIII.  MD / RD / MOVE / COPY / TYPE / REN
   ═══════════════════════════════════════════════════════════════════════ */

static int cmd_md(int argc,char *argv[]){
    if(argc<2){fprintf(stderr,"MD: specify directory name.\n");return 1;}
    for(int i=1;i<argc;i++){
        if(!strcmp(argv[i],"/?")||!strcmp(argv[i],"-?")){db_help("MD");return 0;}
    }
    int ok=0;
    for(int i=1;i<argc;i++){
        if(argv[i][0]=='/')continue;
        char cmd2[1024];snprintf(cmd2,sizeof(cmd2),"mkdir -p '%s'",argv[i]);
        if(system(cmd2)==0){printf("  Created: %s\n",argv[i]);ok++;}
        else fprintf(stderr,"  Failed: %s\n",argv[i]);
    }
    return ok>0?0:1;
}

static int cmd_rd(int argc,char *argv[]){
    if(argc<2){fprintf(stderr,"RD: specify directory.\n");return 1;}
    int recurse=0;
    for(int i=1;i<argc;i++){
        char *a=argv[i];
        if(a[0]=='/'||a[0]=='-'){
            char sw[8];strncpy(sw,a+1,7);sw[7]='\0';
            for(int j=0;sw[j];j++)sw[j]=toupper((unsigned char)sw[j]);
            if(!strcmp(sw,"S"))recurse=1;
            else if(!strcmp(sw,"?")){db_help("RD");return 0;}
        }
    }
    int ok=0;
    for(int i=1;i<argc;i++){
        if(argv[i][0]=='/')continue;
        if(recurse){
            printf("  Remove '%s' and ALL contents? [Y/N] ",argv[i]);fflush(stdout);
            char ch=getchar();while(getchar()!='\n'){}
            if(ch!='y'&&ch!='Y'){printf("  Skipped.\n");continue;}
            char cmd2[1024];snprintf(cmd2,sizeof(cmd2),"rm -rf '%s'",argv[i]);
            if(system(cmd2)==0){printf("  Removed: %s\n",argv[i]);ok++;}
            else fprintf(stderr,"  Failed: %s\n",argv[i]);
        } else {
            if(rmdir(argv[i])==0){printf("  Removed: %s\n",argv[i]);ok++;}
            else fprintf(stderr,"  Cannot remove %s: %s\n",argv[i],strerror(errno));
        }
    }
    return ok>0?0:1;
}

static int cmd_move(int argc,char *argv[]){
    for(int i=1;i<argc;i++){
        if(!strcmp(argv[i],"/?")||!strcmp(argv[i],"-?")){db_help("MOVE");return 0;}
    }
    const char *src=NULL,*dst=NULL;
    for(int i=1;i<argc;i++){
        if(argv[i][0]!='/'&&argv[i][0]!='-'){
            if(!src)src=argv[i];
            else dst=argv[i];
        }
    }
    if(!src||!dst){fprintf(stderr,"MOVE: source destination\n");return 1;}
    if(rename(src,dst)==0){printf("  Moved: %s  ->  %s\n",src,dst);return 0;}
    /* cross-device: copy + delete */
    char cmd2[2048];snprintf(cmd2,sizeof(cmd2),"cp -a '%s' '%s' && rm -rf '%s'",src,dst,src);
    if(system(cmd2)==0){printf("  Moved: %s  ->  %s\n",src,dst);return 0;}
    fprintf(stderr,"  Move failed: %s\n",strerror(errno));return 1;
}

static int cmd_copy(int argc,char *argv[]){
    const char *src=NULL,*dst=NULL;int over=0;
    for(int i=1;i<argc;i++){
        if(argv[i][0]=='/'||argv[i][0]=='-'){
            char sw[8];strncpy(sw,argv[i]+1,7);
            for(int j=0;sw[j];j++)sw[j]=toupper((unsigned char)sw[j]);
            if(!strcmp(sw,"Y"))over=1;
            else if(!strcmp(sw,"?")){db_help("COPY");return 0;}
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
    char cmd2[2048];snprintf(cmd2,sizeof(cmd2),"cp -a '%s' '%s'",src,dst);
    if(system(cmd2)==0){printf("  Copied: %s  ->  %s\n",src,dst);return 0;}
    fprintf(stderr,"  Copy failed.\n");return 1;
}

static int cmd_type(int argc,char *argv[]){
    if(argc<2){fprintf(stderr,"TYPE: specify filename.\n");return 1;}
    for(int i=1;i<argc;i++){
        if(!strcmp(argv[i],"/?")||!strcmp(argv[i],"-?")){db_help("TYPE");return 0;}
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

/* ═══════════════════════════════════════════════════════════════════════
   IX.  GUI LAUNCHER
   ═══════════════════════════════════════════════════════════════════════ */

static void launch_cfg(void){
    sqlite3 *db=db_open();
    if(db){
        size_t tot=0;
        for(int i=0;GUI_LINES[i];i++)tot+=strlen(GUI_LINES[i]);
        char *script=malloc(tot+1);script[0]='\0';
        for(int i=0;GUI_LINES[i];i++)strcat(script,GUI_LINES[i]);
        sqlite3_stmt *st;
        sqlite3_prepare_v2(db,
            "INSERT OR REPLACE INTO ui_modules (name,description,script) VALUES ('wcmd_config','WCMD Config GUI',?)",
            -1,&st,NULL);
        sqlite3_bind_text(st,1,script,-1,SQLITE_STATIC);
        sqlite3_step(st);sqlite3_finalize(st);
        sqlite3_close(db);free(script);
    }
    char tmp[64];strcpy(tmp,"/tmp/wcmd_cfg_XXXXXX.py");
    int fd=mkstemps(tmp,3);
    if(fd<0){fprintf(stderr,"Cannot create temp file.\n");return;}
    for(int i=0;GUI_LINES[i];i++)write(fd,GUI_LINES[i],strlen(GUI_LINES[i]));
    close(fd);
    char cmd[768];snprintf(cmd,sizeof(cmd),"python3 '%s' '%s' &",tmp,g_db_path);
    system(cmd);
}

/* ═══════════════════════════════════════════════════════════════════════
   X.  MAIN + DISPATCH
   ═══════════════════════════════════════════════════════════════════════ */

int main(int argc,char *argv[]){
    /* DB path */
    const char *home=getenv("HOME");
    snprintf(g_db_path,sizeof(g_db_path),"%s/.wcmd.db",home?home:"/tmp");

    /* bootstrap + load config */
    sqlite3 *db=db_open();
    if(db){db_bootstrap(db);load_config(db);sqlite3_close(db);}

    /* -cfg check (works for any invocation name) */
    for(int i=1;i<argc;i++){
        if(!strcmp(argv[i],"-cfg")||!strcmp(argv[i],"--config")){
            launch_cfg();return 0;
        }
    }

    /* dispatch by argv[0] basename */
    char *base=basename(argv[0]);
    char cmd_name[32];strncpy(cmd_name,base,31);cmd_name[31]='\0';
    for(int i=0;cmd_name[i];i++)cmd_name[i]=toupper((unsigned char)cmd_name[i]);

    if(!strcmp(cmd_name,"DIR"))  return cmd_dir(argc,argv);
    if(!strcmp(cmd_name,"DEL")
       ||!strcmp(cmd_name,"ERASE")) return cmd_del(argc,argv);
    if(!strcmp(cmd_name,"MD")
       ||!strcmp(cmd_name,"MKDIR")) return cmd_md(argc,argv);
    if(!strcmp(cmd_name,"RD")
       ||!strcmp(cmd_name,"RMDIR")) return cmd_rd(argc,argv);
    if(!strcmp(cmd_name,"MOVE"))    return cmd_move(argc,argv);
    if(!strcmp(cmd_name,"COPY"))    return cmd_copy(argc,argv);
    if(!strcmp(cmd_name,"TYPE"))    return cmd_type(argc,argv);
    if(!strcmp(cmd_name,"REN")
       ||!strcmp(cmd_name,"RENAME")) return cmd_move(argc,argv);

    /* default: treat as DIR */
    return cmd_dir(argc,argv);
}
