#!/usr/bin/env python3
#[@GHOST]{file_path="Cascade_toolStack/bcl_units/mysql_to_sqlite.py" date="2026-07-04" author="Devin" session_id="bnd-laws" context="Export MySQL laws DB to SQLite for bcl_sql_proxy.c"}
#[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
#[@FILEID]{id="mysql_to_sqlite.py" domain="bcl_c_engine" authority="MysqlToSqlite"}
#[@SUMMARY]{summary="Export MySQL database to SQLite file. Preserves schema, data types, and all rows. Used to feed bcl_sql_proxy.c."}
#[@CLASS]{class="MysqlToSqlite" domain="bcl_c_engine" authority="single"}
#[@METHOD]{methods="Run,cmd_export,cmd_list,_p"}

import sqlite3
import mysql.connector
import sys
import os
from datetime import datetime

MYSQL_HOST = "localhost"
MYSQL_USER = "root"
MYSQL_PASSWORD = ""
MAX_TEXT = 16777215

TYPE_MAP = {
    "int": "INTEGER",
    "bigint": "INTEGER",
    "tinyint": "INTEGER",
    "smallint": "INTEGER",
    "mediumint": "INTEGER",
    "float": "REAL",
    "double": "REAL",
    "decimal": "REAL",
    "numeric": "REAL",
    "varchar": "TEXT",
    "char": "TEXT",
    "text": "TEXT",
    "mediumtext": "TEXT",
    "longtext": "TEXT",
    "tinytext": "TEXT",
    "blob": "BLOB",
    "mediumblob": "BLOB",
    "longblob": "BLOB",
    "tinyblob": "BLOB",
    "date": "TEXT",
    "datetime": "TEXT",
    "timestamp": "TEXT",
    "time": "TEXT",
    "year": "INTEGER",
    "enum": "TEXT",
    "set": "TEXT",
    "json": "TEXT",
    "bit": "INTEGER",
    "binary": "BLOB",
    "varbinary": "BLOB",
    "geometry": "BLOB",
    "point": "BLOB",
    "linestring": "BLOB",
    "polygon": "BLOB",
}


class MysqlToSqlite:

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "mysql_host": MYSQL_HOST,
                "mysql_user": MYSQL_USER,
                "mysql_password": MYSQL_PASSWORD,
                "batch_size": 1000,
            },
            "stats": {},
        }

    def _p(self, params, key, default=None):
        if params is None:
            return default
        return params.get(key, default)

    def Run(self, command, params=None):
        dispatch = {
            "export": self.cmd_export,
            "list": self.cmd_list,
        }
        handler = dispatch.get(command)
        if handler is None:
            return (0, None, (3, "unknown command: %s" % command, 0))
        return handler(params or {})

    def cmd_list(self, params):
        host = self._p(params, "host", self.state["config"]["mysql_host"])
        user = self._p(params, "user", self.state["config"]["mysql_user"])
        password = self._p(params, "password", self.state["config"]["mysql_password"])
        try:
            conn = mysql.connector.connect(host=host, user=user, password=password)
            cur = conn.cursor()
            cur.execute("SHOW DATABASES")
            dbs = [row[0] for row in cur.fetchall() if row[0] not in ("information_schema", "mysql", "performance_schema", "sys")]
            cur.close()
            conn.close()
            return (1, {"databases": dbs}, None)
        except Exception as e:
            return (0, None, (2, str(e), 0))

    def cmd_export(self, params):
        dbName = self._p(params, "database")
        sqlitePath = self._p(params, "sqlite_path")
        if not dbName:
            return (0, None, (3, "missing 'database' parameter", 0))
        if not sqlitePath:
            sqlitePath = "%s.db" % dbName

        host = self._p(params, "host", self.state["config"]["mysql_host"])
        user = self._p(params, "user", self.state["config"]["mysql_user"])
        password = self._p(params, "password", self.state["config"]["mysql_password"])
        batchSize = self._p(params, "batch_size", self.state["config"]["batch_size"])
        tablesOnly = self._p(params, "tables")

        try:
            mConn = mysql.connector.connect(host=host, user=user, password=password, database=dbName)
            mCur = mConn.cursor()
        except Exception as e:
            return (0, None, (2, "MySQL connect: %s" % str(e), 0))

        if os.path.exists(sqlitePath):
            os.remove(sqlitePath)

        sConn = sqlite3.connect(sqlitePath)
        sCur = sConn.cursor()

        mCur.execute("SHOW TABLES")
        allTables = [row[0] for row in mCur.fetchall()]

        if tablesOnly:
            wanted = tablesOnly.split(",") if isinstance(tablesOnly, str) else tablesOnly
            allTables = [t for t in allTables if t in wanted]

        stats = {"tables": {}, "total_rows": 0, "total_tables": 0}

        for table in allTables:
            # Use SHOW COLUMNS instead of parsing CREATE TABLE
            mCur.execute("SHOW COLUMNS FROM `%s`" % table)
            columns = mCur.fetchall()
            sqliteCreate = self._build_create_from_columns(table, columns)
            try:
                sCur.execute(sqliteCreate)
            except Exception as e:
                sys.stderr.write("WARN: table %s create failed: %s\n  SQL: %s\n" % (table, str(e), sqliteCreate))
                continue

            mCur.execute("SELECT * FROM `%s`" % table)
            colCount = len(mCur.description)
            placeholders = ",".join(["?"] * colCount)
            insertSql = "INSERT OR REPLACE INTO `%s` VALUES (%s)" % (table, placeholders)

            rowCount = 0
            batch = []
            while True:
                rows = mCur.fetchmany(batchSize)
                if not rows:
                    break
                for row in rows:
                    converted = []
                    for val in row:
                        if isinstance(val, bytes):
                            converted.append(val)
                        elif isinstance(val, (dict, list)):
                            import json
                            converted.append(json.dumps(val))
                        elif hasattr(val, "__float__") and val.__class__.__name__ == "Decimal":
                            converted.append(float(val))
                        else:
                            converted.append(val)
                    batch.append(tuple(converted))
                    rowCount += 1
                sCur.executemany(insertSql, batch)
                sConn.commit()
                batch = []

            stats["tables"][table] = rowCount
            stats["total_rows"] += rowCount
            stats["total_tables"] += 1
            sys.stderr.write("  %s: %d rows\n" % (table, rowCount))

        sCur.execute("CREATE TABLE IF NOT EXISTS _meta (key TEXT, value TEXT)")
        sCur.execute("INSERT INTO _meta VALUES (?,?)", ("source_db", dbName))
        sCur.execute("INSERT INTO _meta VALUES (?,?)", ("exported_at", datetime.now().isoformat()))
        sCur.execute("INSERT INTO _meta VALUES (?,?)", ("total_tables", str(stats["total_tables"])))
        sCur.execute("INSERT INTO _meta VALUES (?,?)", ("total_rows", str(stats["total_rows"])))
        sConn.commit()
        sConn.close()
        mCur.close()
        mConn.close()

        stats["sqlite_path"] = sqlitePath
        self.state["stats"] = stats
        return (1, stats, None)

    def _build_create_from_columns(self, tableName, columns):
        # columns: [(Field, Type, Null, Key, Default, Extra), ...]
        colDefs = []
        primaryKeys = []
        for col in columns:
            fieldName, fieldType, nullable, keyType, defaultVal, extra = col[0], col[1], col[2], col[3], col[4], col[5]
            sqliteType = self._map_type(fieldType)
            isPrimaryKey = (keyType == "PRI")
            isAutoIncrement = "auto_increment" in (extra or "").lower()
            isNotNull = (nullable == "NO")

            if isPrimaryKey and isAutoIncrement and sqliteType == "INTEGER":
                colDefs.append("  `%s` INTEGER PRIMARY KEY AUTOINCREMENT" % fieldName)
            elif isPrimaryKey:
                colDefs.append("  `%s` %s PRIMARY KEY" % (fieldName, sqliteType))
            else:
                defn = "  `%s` %s" % (fieldName, sqliteType)
                colDefs.append(defn)
            if isPrimaryKey and not isAutoIncrement:
                primaryKeys.append(fieldName)

        # If no autoincrement PK, add PRIMARY KEY clause
        parts = ["CREATE TABLE IF NOT EXISTS `%s` (" % tableName]
        parts.append(",\n".join(colDefs))
        if primaryKeys and not any("PRIMARY KEY" in d for d in colDefs):
            parts.append(",\n  PRIMARY KEY (%s)" % ",".join(["`%s`" % pk for pk in primaryKeys]))
        parts.append(")")
        return "\n".join(parts)

    def _map_type(self, mysqlType):
        mt = mysqlType.lower().strip()
        if mt.startswith("int") or mt.startswith("bigint") or mt.startswith("tinyint") or mt.startswith("smallint") or mt.startswith("mediumint") or mt.startswith("year"):
            return "INTEGER"
        if mt.startswith("float") or mt.startswith("double") or mt.startswith("decimal") or mt.startswith("numeric") or mt.startswith("real"):
            return "REAL"
        if mt.startswith("blob") or mt.startswith("binary") or mt.startswith("varbinary") or mt.startswith("geometry") or mt.startswith("point") or mt.startswith("linestring") or mt.startswith("polygon"):
            return "BLOB"
        return "TEXT"

    def _convert_create(self, mysqlCreate):
        lines = mysqlCreate.split("\n")
        out = []
        for line in lines:
            stripped = line.strip()
            upper = stripped.upper()
            if upper.startswith("PRIMARY KEY"):
                out.append(stripped.rstrip(","))
            elif upper.startswith("UNIQUE KEY"):
                continue
            elif upper.startswith("KEY "):
                continue
            elif upper.startswith("INDEX "):
                continue
            elif upper.startswith("CONSTRAINT"):
                continue
            elif upper.startswith("FOREIGN KEY"):
                continue
            elif upper.startswith("FULLTEXT"):
                continue
            elif upper.startswith("SPATIAL"):
                continue
            elif upper.startswith("CHECK"):
                continue
            elif upper.startswith(")"):
                out.append(")")
            elif upper.startswith("CREATE"):
                out.append(stripped.replace("CREATE TABLE", "CREATE TABLE IF NOT EXISTS"))
            else:
                converted = self._convert_column(stripped)
                if converted:
                    out.append(converted)
        result = "\n".join(out)
        result = result.replace(",\n)", "\n)")
        result = result.replace("CHARACTER SET utf8mb4", "")
        result = result.replace("COLLATE utf8mb4_general_ci", "")
        result = result.replace("COLLATE utf8mb4_unicode_ci", "")
        result = result.replace("COLLATE utf8mb4_bin", "")
        result = result.replace("DEFAULT CHARSET=utf8mb4", "")
        result = result.replace("ENGINE=InnoDB", "")
        result = result.replace("AUTO_INCREMENT", "")
        result = result.replace("AUTOINCREMENT", "")
        result = result.replace("  ", " ")
        return result

    def _convert_column(self, line):
        if not line:
            return None
        if line.startswith("`"):
            parts = line.split("`")
            if len(parts) >= 3:
                colName = parts[1]
                rest = parts[2].strip()
                isPrimaryKey = "PRIMARY KEY" in line.upper()
                isNotNull = "NOT NULL" in line.upper()
                isUnique = "UNIQUE" in line.upper()
                isAutoIncrement = "AUTO_INCREMENT" in line.upper() or "AUTOINCREMENT" in line.upper()

                for mysqlType, sqliteType in TYPE_MAP.items():
                    if rest.upper().startswith(mysqlType.upper()):
                        # SQLite: AUTOINCREMENT only valid with INTEGER PRIMARY KEY
                        if isAutoIncrement and sqliteType == "INTEGER" and isPrimaryKey:
                            result = "  `%s` INTEGER PRIMARY KEY AUTOINCREMENT" % colName
                        elif isPrimaryKey:
                            result = "  `%s` %s PRIMARY KEY" % (colName, sqliteType)
                        else:
                            result = "  `%s` %s" % (colName, sqliteType)
                            if isNotNull:
                                result += " NOT NULL"
                            if isUnique:
                                result += " UNIQUE"
                        return result.rstrip(",")
        return line.rstrip(",")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Export MySQL database to SQLite")
    parser.add_argument("--database", required=True, help="MySQL database name")
    parser.add_argument("--sqlite-path", help="Output SQLite file path (default: <database>.db)")
    parser.add_argument("--tables", help="Comma-separated list of tables to export (default: all)")
    parser.add_argument("--list", action="store_true", help="List MySQL databases and exit")
    args = parser.parse_args()

    exporter = MysqlToSqlite()

    if args.list:
        ok, data, err = exporter.Run("list")
        if not ok:
            sys.stderr.write("ERROR: %s\n" % err[1])
            sys.exit(1)
        for db in data["databases"]:
            print(db)
        sys.exit(0)

    params = {
        "database": args.database,
        "sqlite_path": args.sqlite_path,
        "tables": args.tables,
    }
    ok, data, err = exporter.Run("export", params)
    if not ok:
        sys.stderr.write("ERROR: %s\n" % err[1])
        sys.exit(1)
    import json
    print(json.dumps(data, indent=2))
