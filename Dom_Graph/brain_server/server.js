// [@GHOST]{[@file<brain_server/server.js>][@domain<graph>][@role<storage_api>][@auth<devin>][@date<2026-06-27>][@ver<1.1>]}
// [@VBSTYLE]{[@auth<devin>][@role<storage_api>][@return<JSON>][@orch<express>][@no<console_log_in_prod>]}
// [@SUMMARY]{BrainStorageServer — Node.js Express + SQLite server for the GUI AI Brain. Stores trained models, layout templates, training history, and energy scores. REST API for Python brain to save and any frontend to query. Memory-optimized: cached prepared statements, WAL mode, bounded TTL cache, gc() hooks, graceful shutdown.}
// [@CLASS]{BrainStorageServer}
// [@METHOD]{start,saveModel,getModels,saveTemplate,getTemplates,saveHistory,getHistory,saveLayout,getLayouts,health,memStats,gc}

/**
 * BrainStorageServer
 *
 * REST API for the GUI AI Brain system.
 * Stores:
 *   - Trained PyTorch models (metadata + file path)
 *   - Layout templates (saved good layouts)
 *   - Training history (episodes, rewards, losses)
 *   - Layout snapshots (node positions + energy)
 *
 * Endpoints:
 *   GET  /health                    — server status
 *   GET  /mem-stats                 — process.memoryUsage() snapshot
 *   POST /gc                        — trigger gc() if --expose-gc is set
 *   POST /api/models                — save model metadata
 *   GET  /api/models                — list all models
 *   GET  /api/models/:id            — get specific model
 *   POST /api/templates             — save layout template
 *   GET  /api/templates             — list all templates
 *   GET  /api/templates/:name       — get specific template
 *   POST /api/history               — save training episode
 *   POST /api/history/batch         — batch insert history
 *   GET  /api/history               — get training history
 *   GET  /api/history/latest        — get latest training run
 *   POST /api/runs                  — save training run metadata
 *   GET  /api/runs                  — list training runs
 *   POST /api/layouts               — save layout snapshot
 *   GET  /api/layouts               — list layout snapshots
 *   GET  /api/layouts/:id           — get specific layout
 *   GET  /api/stats                 — overall system stats
 */

const express = require('express');
const Database = require('better-sqlite3');
const cors = require('cors');
const path = require('path');
const fs = require('fs');

const PORT = process.env.BRAIN_PORT || 7777;
const DB_PATH = path.join(__dirname, 'brain_storage.db');
const MODEL_DIR = path.join(__dirname, 'models');

// ════════════════════════════════════════════
// MEMORY TUNABLES
// ════════════════════════════════════════════
const STATS_CACHE_TTL_MS = parseInt(process.env.BRAIN_STATS_CACHE_TTL_MS || '5000', 10); // 5s default
const STATS_CACHE_MAX = 8;            // small bounded LRU for stats-style payloads
const GC_INTERVAL_MS = parseInt(process.env.BRAIN_GC_INTERVAL_MS || '60000', 10); // 60s, only if gc exposed
const SQLITE_CACHE_KB = parseInt(process.env.BRAIN_SQLITE_CACHE_KB || '20000', 10); // 20MB page cache cap
const JSON_BODY_LIMIT = process.env.BRAIN_JSON_LIMIT || '50mb';
const HAS_GC = typeof global.gc === 'function';

// Ensure model directory exists
if (!fs.existsSync(MODEL_DIR)) {
    fs.mkdirSync(MODEL_DIR, { recursive: true });
}

const app = express();
app.use(cors());
app.use(express.json({ limit: JSON_BODY_LIMIT }));

// Initialize database
const db = new Database(DB_PATH);

// ── SQLite memory pragmas ───────────────────
// WAL = better throughput + lower RSS footprint under concurrent reads.
// cache_size negative = KB budget (vs positive = pages). Cap to keep RSS bounded.
db.pragma('journal_mode = WAL');
db.pragma('synchronous = NORMAL');
db.pragma('cache_size = -' + SQLITE_CACHE_KB);
db.pragma('temp_store = MEMORY');
db.pragma('mmap_size = 268435456'); // 256MB mmap ceiling; avoids heap growth for large reads

// Create tables
db.exec(`
    CREATE TABLE IF NOT EXISTS models (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        version TEXT DEFAULT '1.0',
        file_path TEXT,
        episodes INTEGER DEFAULT 0,
        avg_reward REAL DEFAULT 0,
        best_reward REAL DEFAULT 0,
        best_episode INTEGER DEFAULT 0,
        loss_final REAL DEFAULT 0,
        device TEXT DEFAULT 'cpu',
        state_dim INTEGER DEFAULT 40,
        action_dim INTEGER DEFAULT 10,
        hidden_dim INTEGER DEFAULT 128,
        created_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS templates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        spec_json TEXT NOT NULL,
        node_count INTEGER DEFAULT 0,
        energy REAL DEFAULT 0,
        layout_state TEXT DEFAULT 'stable',
        created_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL,
        episode INTEGER NOT NULL,
        step INTEGER DEFAULT 0,
        reward REAL DEFAULT 0,
        energy REAL DEFAULT 0,
        loss REAL DEFAULT 0,
        overlap REAL DEFAULT 0,
        temperature REAL DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS layouts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        nodes_json TEXT NOT NULL,
        weights_json TEXT,
        energy REAL DEFAULT 0,
        temperature REAL DEFAULT 0,
        tick INTEGER DEFAULT 0,
        source TEXT DEFAULT 'physics',
        created_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT UNIQUE NOT NULL,
        algorithm TEXT DEFAULT 'REINFORCE',
        total_episodes INTEGER DEFAULT 0,
        avg_reward REAL DEFAULT 0,
        best_reward REAL DEFAULT 0,
        device TEXT DEFAULT 'cpu',
        status TEXT DEFAULT 'running',
        created_at TEXT DEFAULT (datetime('now')),
        completed_at TEXT
    );
`);

// ════════════════════════════════════════════
// PREPARED STATEMENT CACHE
// better-sqlite3 prepared statements are reusable; preparing once at module
// scope eliminates per-request allocation churn and lowers RSS growth under load.
// ════════════════════════════════════════════
const stmts = {
    // counts
    countModels:    db.prepare('SELECT COUNT(*) as c FROM models'),
    countTemplates: db.prepare('SELECT COUNT(*) as c FROM templates'),
    countHistory:   db.prepare('SELECT COUNT(*) as c FROM history'),
    countLayouts:   db.prepare('SELECT COUNT(*) as c FROM layouts'),
    countRuns:      db.prepare('SELECT COUNT(*) as c FROM runs'),

    // models
    insertModel: db.prepare(`
        INSERT INTO models (name, version, file_path, episodes, avg_reward,
            best_reward, best_episode, loss_final, device, state_dim, action_dim, hidden_dim)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `),
    listModels:   db.prepare('SELECT * FROM models ORDER BY created_at DESC LIMIT ?'),
    getModelById: db.prepare('SELECT * FROM models WHERE id = ?'),

    // templates
    upsertTemplate: db.prepare(`
        INSERT OR REPLACE INTO templates (name, spec_json, node_count, energy, layout_state)
        VALUES (?, ?, ?, ?, ?)
    `),
    listTemplates:    db.prepare('SELECT id, name, node_count, energy, layout_state, created_at FROM templates ORDER BY created_at DESC'),
    getTemplateByName: db.prepare('SELECT * FROM templates WHERE name = ?'),

    // history
    insertHistory: db.prepare(`
        INSERT INTO history (run_id, episode, step, reward, energy, loss, overlap, temperature)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    `),
    listHistoryByRun: db.prepare('SELECT * FROM history WHERE run_id = ? ORDER BY episode ASC, step ASC LIMIT ?'),
    listHistoryAll:   db.prepare('SELECT * FROM history ORDER BY created_at DESC LIMIT ?'),
    latestRun:        db.prepare('SELECT * FROM runs ORDER BY created_at DESC LIMIT 1'),
    historyForRun:    db.prepare('SELECT * FROM history WHERE run_id = ? ORDER BY episode ASC'),

    // runs
    upsertRun: db.prepare(`
        INSERT OR REPLACE INTO runs (run_id, algorithm, total_episodes, avg_reward, best_reward, device, status, completed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
    `),
    listRuns: db.prepare('SELECT * FROM runs ORDER BY created_at DESC'),

    // layouts
    insertLayout: db.prepare(`
        INSERT INTO layouts (name, nodes_json, weights_json, energy, temperature, tick, source)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    `),
    listLayouts:    db.prepare('SELECT id, name, energy, temperature, tick, source, created_at FROM layouts ORDER BY created_at DESC LIMIT ?'),
    getLayoutById:  db.prepare('SELECT * FROM layouts WHERE id = ?'),

    // stats
    bestModel:    db.prepare('SELECT * FROM models ORDER BY best_reward DESC LIMIT 1'),
    avgReward:    db.prepare('SELECT AVG(reward) as avg FROM history'),
    maxReward:    db.prepare('SELECT MAX(reward) as max FROM history'),
    minReward:    db.prepare('SELECT MIN(reward) as min FROM history'),
};

// Batch insert transaction factory (reused, not re-created per request)
const insertHistoryBatch = db.transaction((items, run_id) => {
    for (const item of items) {
        stmts.insertHistory.run(
            run_id, item.episode || 0, item.step || 0,
            item.reward || 0, item.energy || 0, item.loss || 0,
            item.overlap || 0, item.temperature || 0
        );
    }
});

// ════════════════════════════════════════════
// BOUNDED TTL CACHE (tiny LRU)
// Used for expensive aggregate endpoints so repeated polling does not
// re-run full-table scans. Entries self-expire; map is hard-capped.
// ════════════════════════════════════════════
class TtlLru {
    constructor(max, ttlMs) {
        this.max = max;
        this.ttlMs = ttlMs;
        this.map = new Map();
    }
    get(key) {
        const e = this.map.get(key);
        if (!e) return undefined;
        if (Date.now() - e.t > this.ttlMs) {
            this.map.delete(key);
            return undefined;
        }
        // move-to-end (LRU recency)
        this.map.delete(key);
        this.map.set(key, e);
        return e.v;
    }
    set(key, val) {
        if (this.map.size >= this.max && !this.map.has(key)) {
            // evict oldest (first key)
            const oldest = this.map.keys().next().value;
            this.map.delete(oldest);
        }
        this.map.set(key, { v: val, t: Date.now() });
    }
    clear() { this.map.clear(); }
    get size() { return this.map.size; }
}
const statsCache = new TtlLru(STATS_CACHE_MAX, STATS_CACHE_TTL_MS);

// Invalidate stats cache whenever underlying tables mutate.
function bustStatsCache() { statsCache.clear(); }

// ════════════════════════════════════════════
// PERIODIC GC (only if --expose-gc)
// ════════════════════════════════════════════
let gcTimer = null;
if (HAS_GC && GC_INTERVAL_MS > 0) {
    gcTimer = setInterval(() => {
        try { global.gc(); } catch (e) { /* ignore */ }
    }, GC_INTERVAL_MS);
    if (gcTimer.unref) gcTimer.unref(); // don't keep event loop alive
}

// ════════════════════════════════════════════
// HEALTH
// ════════════════════════════════════════════

app.get('/health', (req, res) => {
    const modelCount = stmts.countModels.get().c;
    const templateCount = stmts.countTemplates.get().c;
    const historyCount = stmts.countHistory.get().c;
    const layoutCount = stmts.countLayouts.get().c;
    res.json({
        status: 'online',
        server: 'BrainStorageServer',
        version: '1.1',
        port: PORT,
        database: DB_PATH,
        stats: {
            models: modelCount,
            templates: templateCount,
            history_records: historyCount,
            layouts: layoutCount
        }
    });
});

// ════════════════════════════════════════════
// MEMORY & GC ENDPOINTS
// ════════════════════════════════════════════

app.get('/mem-stats', (req, res) => {
    const m = process.memoryUsage();
    res.json({
        rss: m.rss,
        heapTotal: m.heapTotal,
        heapUsed: m.heapUsed,
        external: m.external,
        arrayBuffers: m.arrayBuffers,
        rss_mb: +(m.rss / 1048576).toFixed(2),
        heap_used_mb: +(m.heapUsed / 1048576).toFixed(2),
        heap_total_mb: +(m.heapTotal / 1048576).toFixed(2),
        gc_exposed: HAS_GC,
        stats_cache_size: statsCache.size,
        uptime_sec: +(process.uptime()).toFixed(1)
    });
});

app.post('/gc', (req, res) => {
    if (!HAS_GC) {
        return res.status(400).json({
            error: 'gc not exposed. start with: node --expose-gc server.js'
        });
    }
    const before = process.memoryUsage();
    try { global.gc(); } catch (e) {
        return res.status(500).json({ error: 'gc failed: ' + e.message });
    }
    const after = process.memoryUsage();
    res.json({
        status: 'gc_invoked',
        before: {
            heap_used_mb: +(before.heapUsed / 1048576).toFixed(2),
            rss_mb: +(before.rss / 1048576).toFixed(2)
        },
        after: {
            heap_used_mb: +(after.heapUsed / 1048576).toFixed(2),
            rss_mb: +(after.rss / 1048576).toFixed(2)
        },
        freed_heap_mb: +((before.heapUsed - after.heapUsed) / 1048576).toFixed(2)
    });
});

// ════════════════════════════════════════════
// MODELS — trained PyTorch model metadata
// ════════════════════════════════════════════

app.post('/api/models', (req, res) => {
    const {
        name, version, file_path, episodes, avg_reward,
        best_reward, best_episode, loss_final, device,
        state_dim, action_dim, hidden_dim
    } = req.body;

    if (!name) {
        return res.status(400).json({ error: 'name is required' });
    }

    const info = stmts.insertModel.run(
        name, version || '1.0', file_path || '',
        episodes || 0, avg_reward || 0,
        best_reward || 0, best_episode || 0, loss_final || 0,
        device || 'cpu', state_dim || 40, action_dim || 10, hidden_dim || 128
    );

    bustStatsCache();
    res.json({ id: info.lastInsertRowid, status: 'saved', name: name });
});

app.get('/api/models', (req, res) => {
    const limit = parseInt(req.query.limit) || 50;
    const rows = stmts.listModels.all(limit);
    res.json({ models: rows, count: rows.length });
});

app.get('/api/models/:id', (req, res) => {
    const row = stmts.getModelById.get(req.params.id);
    if (!row) {
        return res.status(404).json({ error: 'model not found' });
    }
    res.json({ model: row });
});

// ════════════════════════════════════════════
// TEMPLATES — saved good layouts
// ════════════════════════════════════════════

app.post('/api/templates', (req, res) => {
    const { name, spec_json, node_count, energy, layout_state } = req.body;

    if (!name || !spec_json) {
        return res.status(400).json({ error: 'name and spec_json are required' });
    }

    const specStr = typeof spec_json === 'string' ? spec_json : JSON.stringify(spec_json);

    const info = stmts.upsertTemplate.run(
        name, specStr,
        node_count || 0, energy || 0, layout_state || 'stable'
    );

    bustStatsCache();
    res.json({ id: info.lastInsertRowid, status: 'saved', name: name });
});

app.get('/api/templates', (req, res) => {
    const rows = stmts.listTemplates.all();
    res.json({ templates: rows, count: rows.length });
});

app.get('/api/templates/:name', (req, res) => {
    const row = stmts.getTemplateByName.get(req.params.name);
    if (!row) {
        return res.status(404).json({ error: 'template not found' });
    }
    row.spec_json = JSON.parse(row.spec_json);
    res.json({ template: row });
});

// ════════════════════════════════════════════
// HISTORY — training episode records
// ════════════════════════════════════════════

app.post('/api/history', (req, res) => {
    const {
        run_id, episode, step, reward, energy, loss, overlap, temperature
    } = req.body;

    if (!run_id) {
        return res.status(400).json({ error: 'run_id is required' });
    }

    const info = stmts.insertHistory.run(
        run_id, episode || 0, step || 0,
        reward || 0, energy || 0, loss || 0,
        overlap || 0, temperature || 0
    );

    bustStatsCache();
    res.json({ id: info.lastInsertRowid, status: 'recorded' });
});

// Batch insert history
app.post('/api/history/batch', (req, res) => {
    const { records, run_id } = req.body;

    if (!records || !Array.isArray(records) || !run_id) {
        return res.status(400).json({ error: 'records array and run_id are required' });
    }

    insertHistoryBatch(records, run_id);
    bustStatsCache();
    res.json({ status: 'batch_saved', count: records.length });
});

app.get('/api/history', (req, res) => {
    const runId = req.query.run_id;
    const limit = parseInt(req.query.limit) || 100;

    let rows;
    if (runId) {
        rows = stmts.listHistoryByRun.all(runId, limit);
    } else {
        rows = stmts.listHistoryAll.all(limit);
    }
    res.json({ history: rows, count: rows.length });
});

app.get('/api/history/latest', (req, res) => {
    const run = stmts.latestRun.get();
    if (!run) {
        return res.json({ run: null, history: [] });
    }
    const rows = stmts.historyForRun.all(run.run_id);
    res.json({ run: run, history: rows, count: rows.length });
});

// ════════════════════════════════════════════
// RUNS — training run metadata
// ════════════════════════════════════════════

app.post('/api/runs', (req, res) => {
    const { run_id, algorithm, total_episodes, avg_reward, best_reward, device, status } = req.body;

    if (!run_id) {
        return res.status(400).json({ error: 'run_id is required' });
    }

    const info = stmts.upsertRun.run(
        run_id, algorithm || 'REINFORCE',
        total_episodes || 0, avg_reward || 0,
        best_reward || 0, device || 'cpu',
        status || 'completed'
    );

    bustStatsCache();
    res.json({ id: info.lastInsertRowid, status: 'saved', run_id: run_id });
});

app.get('/api/runs', (req, res) => {
    const rows = stmts.listRuns.all();
    res.json({ runs: rows, count: rows.length });
});

// ════════════════════════════════════════════
// LAYOUTS — layout snapshots
// ════════════════════════════════════════════

app.post('/api/layouts', (req, res) => {
    const { name, nodes_json, weights_json, energy, temperature, tick, source } = req.body;

    if (!nodes_json) {
        return res.status(400).json({ error: 'nodes_json is required' });
    }

    const nodesStr = typeof nodes_json === 'string' ? nodes_json : JSON.stringify(nodes_json);
    const weightsStr = weights_json ? (typeof weights_json === 'string' ? weights_json : JSON.stringify(weights_json)) : null;

    const info = stmts.insertLayout.run(
        name || '', nodesStr, weightsStr,
        energy || 0, temperature || 0, tick || 0,
        source || 'physics'
    );

    bustStatsCache();
    res.json({ id: info.lastInsertRowid, status: 'saved' });
});

app.get('/api/layouts', (req, res) => {
    const limit = parseInt(req.query.limit) || 50;
    const rows = stmts.listLayouts.all(limit);
    res.json({ layouts: rows, count: rows.length });
});

app.get('/api/layouts/:id', (req, res) => {
    const row = stmts.getLayoutById.get(req.params.id);
    if (!row) {
        return res.status(404).json({ error: 'layout not found' });
    }
    if (row.nodes_json) {
        row.nodes_json = JSON.parse(row.nodes_json);
    }
    if (row.weights_json) {
        row.weights_json = JSON.parse(row.weights_json);
    }
    res.json({ layout: row });
});

// ════════════════════════════════════════════
// STATS — overall system statistics (TTL cached)
// ════════════════════════════════════════════

app.get('/api/stats', (req, res) => {
    const cached = statsCache.get('stats');
    if (cached) {
        return res.json(Object.assign({ _cached: true }, cached));
    }

    const modelCount = stmts.countModels.get().c;
    const templateCount = stmts.countTemplates.get().c;
    const historyCount = stmts.countHistory.get().c;
    const layoutCount = stmts.countLayouts.get().c;
    const runCount = stmts.countRuns.get().c;

    const bestModel = stmts.bestModel.get();
    const latestRun = stmts.latestRun.get();

    const avgReward = stmts.avgReward.get().avg || 0;
    const bestReward = stmts.maxReward.get().max || 0;
    const worstReward = stmts.minReward.get().min || 0;

    const payload = {
        models: modelCount,
        templates: templateCount,
        history_records: historyCount,
        layouts: layoutCount,
        runs: runCount,
        best_model: bestModel || null,
        latest_run: latestRun || null,
        reward_stats: {
            avg: avgReward,
            best: bestReward,
            worst: worstReward
        }
    };

    statsCache.set('stats', payload);
    res.json(payload);
});

// ════════════════════════════════════════════
// GRACEFUL SHUTDOWN — release DB handle + clear timers
// ════════════════════════════════════════════
let shuttingDown = false;
function shutdown(signal) {
    if (shuttingDown) return;
    shuttingDown = true;
    console.log('\n[shutdown] ' + signal + ' received, closing brain_server...');
    try {
        if (gcTimer) { clearInterval(gcTimer); gcTimer = null; }
        statsCache.clear();
        if (db && db.open) db.close();
    } catch (e) {
        console.error('[shutdown] error during cleanup:', e.message);
    }
    process.exit(0);
}
process.on('SIGINT', () => shutdown('SIGINT'));
process.on('SIGTERM', () => shutdown('SIGTERM'));

// ════════════════════════════════════════════
// START SERVER
// ════════════════════════════════════════════

const server = app.listen(PORT, () => {
    console.log('BrainStorageServer running on port ' + PORT);
    console.log('Database: ' + DB_PATH);
    console.log('Model dir: ' + MODEL_DIR);
    console.log('Health check: http://localhost:' + PORT + '/health');
    console.log('Mem stats:   http://localhost:' + PORT + '/mem-stats');
    console.log('GC exposed:  ' + (HAS_GC ? 'yes (POST /gc, interval ' + GC_INTERVAL_MS + 'ms)' : 'no (start with --expose-gc)'));
});

server.on('error', (err) => {
    console.error('Server error:', err.message);
    shutdown('SERVER_ERROR');
});
