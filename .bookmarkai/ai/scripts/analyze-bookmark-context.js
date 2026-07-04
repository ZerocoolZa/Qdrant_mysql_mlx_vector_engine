#!/usr/bin/env node

const fs = require("fs");
const path = require("path");
const crypto = require("crypto");
const { spawnSync } = require("child_process");

const args = parseArgs(process.argv.slice(2));
const projectRoot = path.resolve(args.root || process.cwd());
const mode = args.mode || "summary";
const workflowQuery = args.workflow || "";

const bookmarkSource = currentBookmarkSource(projectRoot);
const bookmarksPath = bookmarkSource.bookmarksPath;
const indexPath = path.join(projectRoot, ".bookmarkai", "cache", "bookmark-context-index.json");

if (!fs.existsSync(bookmarksPath) || !fs.statSync(bookmarksPath).isFile()) {
  fail(`BookmarkAI current branch data is missing: ${toPosix(path.relative(projectRoot, bookmarksPath))}. Run BookmarkAI Initialize Project, then retry.`);
}
const bookmarksRaw = readText(bookmarksPath);
const bookmarks = parseJson(bookmarksRaw, bookmarksPath);
if (bookmarks && bookmarks.__parseError) {
  fail(`Unable to parse BookmarkAI current branch data: ${bookmarks.__parseError}`);
}
const indexRaw = readText(indexPath);
const index = indexRaw ? parseJson(indexRaw, indexPath) : undefined;
const bookmarkRows = flattenBookmarks(bookmarks);
const currentGitCommitHash = git(["rev-parse", "HEAD"]) || "";
const changedFiles = mode === "changes" ? getChangedFiles(args.base) : [];

const currentOfficialBookmarksHash = officialBookmarksHash(bookmarkRows);
const rawBookmarksHash = bookmarksRaw ? sha256(bookmarksRaw) : "";
const indexStatus = buildIndexStatus(index, {
  currentOfficialBookmarksHash,
  rawBookmarksHash,
}, currentGitCommitHash);
const bookmarkStates = bookmarkRows.map((bookmark) => analyzeBookmark(projectRoot, bookmark));

const output = {
  schemaVersion: 2,
  generatedAt: new Date().toISOString(),
  mode,
  projectRoot,
  bookmarkSource: {
    branchId: bookmarkSource.branchId,
    branchName: bookmarkSource.branchName,
    workspaceFallback: bookmarkSource.workspaceFallback,
    bookmarksPath: toPosix(path.relative(projectRoot, bookmarksPath)),
  },
  indexStatus,
  bookmarks: {
    total: bookmarkRows.length,
    groups: groupCounts(bookmarkRows),
  },
  changedFiles,
  affectedBookmarks: mode === "changes"
    ? bookmarkStates.filter((state) => changedFiles.includes(state.filePath))
    : [],
  workflowMatches: mode === "workflow"
    ? workflowMatches(bookmarkStates, workflowQuery)
    : [],
  bookmarkStates,
};

process.stdout.write(JSON.stringify(output, null, 2));
process.stdout.write("\n");

function parseArgs(rawArgs) {
  const parsed = {};
  for (let index = 0; index < rawArgs.length; index++) {
    const arg = rawArgs[index];
    if (arg.startsWith("--mode=")) {
      parsed.mode = arg.slice("--mode=".length);
    } else if (arg === "--mode") {
      parsed.mode = rawArgs[++index];
    } else if (arg.startsWith("--workflow=")) {
      parsed.workflow = arg.slice("--workflow=".length);
      parsed.mode = parsed.mode || "workflow";
    } else if (arg === "--workflow") {
      parsed.workflow = rawArgs[++index];
      parsed.mode = parsed.mode || "workflow";
    } else if (arg.startsWith("--base=")) {
      parsed.base = arg.slice("--base=".length);
    } else if (arg === "--base") {
      parsed.base = rawArgs[++index];
    } else if (arg.startsWith("--root=")) {
      parsed.root = arg.slice("--root=".length);
    } else if (arg === "--root") {
      parsed.root = rawArgs[++index];
    }
  }
  return parsed;
}

function readText(filePath) {
  try {
    return fs.readFileSync(filePath, "utf8");
  } catch {
    return "";
  }
}

function parseJson(raw, filePath) {
  if (!raw) {
    return undefined;
  }
  try {
    return JSON.parse(raw);
  } catch (error) {
    return {
      __parseError: `${filePath}: ${error.message}`,
    };
  }
}

function sha256(value) {
  return crypto.createHash("sha256").update(value).digest("hex");
}

function git(gitArgs) {
  const result = spawnSync("git", gitArgs, {
    cwd: projectRoot,
    encoding: "utf8",
    windowsHide: true,
  });
  if (result.status !== 0) {
    return "";
  }
  return result.stdout.trim();
}

function currentBookmarkSource(root) {
  const branchName = git(["branch", "--show-current"]);
  const normalizedBranchName = branchName.trim();
  const workspaceFallback = !normalizedBranchName;
  const resolvedBranchName = workspaceFallback ? "workspace" : normalizedBranchName;
  const branchId = branchIdForName(resolvedBranchName);
  return {
    branchId,
    branchName: resolvedBranchName,
    workspaceFallback,
    bookmarksPath: path.join(root, ".bookmarkai", "branches", branchId, "bookmarks.json"),
  };
}

function branchIdForName(branchName) {
  const normalized = stringValue(branchName).trim();
  if (!normalized || normalized === "workspace") {
    return "workspace";
  }
  return `br_${crypto.createHash("sha256").update(normalized).digest("hex").slice(0, 16)}`;
}

function fail(message) {
  process.stderr.write(`ERROR: ${message}\n`);
  process.exit(1);
}

function gitLines(gitArgs) {
  const output = git(gitArgs);
  return output
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map(toPosix)
    .sort();
}

function getChangedFiles(base) {
  const changed = new Set();
  const diffArgs = base
    ? ["diff", "--name-only", `${base}...HEAD`]
    : ["diff", "--name-only"];
  for (const filePath of gitLines(diffArgs)) {
    changed.add(filePath);
  }
  for (const filePath of gitLines(["diff", "--cached", "--name-only"])) {
    changed.add(filePath);
  }
  for (const filePath of gitLines(["ls-files", "--others", "--exclude-standard"])) {
    changed.add(filePath);
  }
  return [...changed].sort();
}

function buildIndexStatus(indexFile, hashes, currentCommit) {
  if (!indexRaw) {
    return {
      exists: false,
      status: "missing",
      bookmarksHashMatches: false,
      rawBookmarksHashMatches: false,
      gitCommitHashMatches: false,
    };
  }
  if (indexFile && indexFile.__parseError) {
    return {
      exists: true,
      status: "invalid",
      error: indexFile.__parseError,
      bookmarksHashMatches: false,
      rawBookmarksHashMatches: false,
      gitCommitHashMatches: false,
    };
  }
  const bookmarksHash = stringValue(indexFile && indexFile.bookmarksHash);
  const gitCommitHash = stringValue(indexFile && indexFile.gitCommitHash);
  const schemaVersion = Number(indexFile && indexFile.schemaVersion);
  return {
    exists: true,
    schemaVersion,
    status: schemaVersion === 2 ? stringValue(indexFile.status) || "fresh" : "invalid",
    bookmarksHash,
    currentBookmarksHash: hashes.currentOfficialBookmarksHash,
    currentOfficialBookmarksHash: hashes.currentOfficialBookmarksHash,
    rawBookmarksHash: hashes.rawBookmarksHash,
    bookmarksHashMatches: Boolean(bookmarksHash && bookmarksHash === hashes.currentOfficialBookmarksHash),
    rawBookmarksHashMatches: Boolean(bookmarksHash && bookmarksHash === hashes.rawBookmarksHash),
    gitCommitHash,
    currentGitCommitHash: currentCommit,
    gitCommitHashMatches: Boolean(gitCommitHash && gitCommitHash === currentCommit),
  };
}

function flattenBookmarks(projectBookmarks) {
  if (!projectBookmarks || !Array.isArray(projectBookmarks.groups)) {
    return [];
  }
  const rows = [];
  for (const group of projectBookmarks.groups) {
    const bookmarksInGroup = Array.isArray(group.bookmarks) ? group.bookmarks : [];
    for (const bookmark of bookmarksInGroup) {
      rows.push({
        bookmarkId: stringValue(bookmark.bookmarkId) || stringValue(bookmark.id),
        itemId: stringValue(bookmark.id),
        title: stringValue(bookmark.title),
        groupId: stringValue(group.id),
        groupName: stringValue(group.name),
        filePath: toPosix(stringValue(bookmark.filePath)),
        line: positiveInt(bookmark.line, 1),
        column: nonNegativeInt(bookmark.column, 0),
        anchorText: stringValue(bookmark.anchor && bookmark.anchor.text),
        contextBefore: stringArray(bookmark.anchor && bookmark.anchor.before),
        contextAfter: stringArray(bookmark.anchor && bookmark.anchor.after),
        stageType: stringValue(bookmark.stage && bookmark.stage.type),
      });
    }
  }
  return rows;
}

function officialBookmarksHash(rows) {
  const byId = new Map();
  for (const row of rows) {
    if (!row.bookmarkId || row.stageType === "added" || byId.has(row.bookmarkId)) {
      continue;
    }
    byId.set(row.bookmarkId, {
      id: row.bookmarkId,
      filePath: row.filePath,
      line: row.line,
      column: row.column,
      lineTextAnchor: row.anchorText,
      contextBeforeAnchor: row.contextBefore.map((line) => stringValue(line).trim()),
      contextAfterAnchor: row.contextAfter.map((line) => stringValue(line).trim()),
    });
  }
  const projection = [...byId.values()]
    .sort((left, right) => left.id.localeCompare(right.id));
  return sha256(stableJson(projection));
}

function analyzeBookmark(root, bookmark) {
  const absolutePath = resolveSourcePath(root, bookmark.filePath);
  const base = {
    bookmarkId: bookmark.bookmarkId,
    title: bookmark.title,
    groupId: bookmark.groupId,
    groupName: bookmark.groupName,
    filePath: bookmark.filePath,
    line: bookmark.line,
  };
  if (!absolutePath) {
    return {
      ...base,
      status: "invalidPath",
      suggestedLine: 0,
      warning: "Bookmarked file path is not repository-relative.",
    };
  }
  let content;
  try {
    content = fs.readFileSync(absolutePath, "utf8");
  } catch {
    return {
      ...base,
      status: "missingFile",
      suggestedLine: 0,
      warning: "Bookmarked file is missing.",
    };
  }
  const lines = content.split(/\r?\n/);
  const currentLineText = lines[bookmark.line - 1] || "";
  const anchorText = bookmark.anchorText;
  if (!anchorText) {
    return {
      ...base,
      status: "unchecked",
      suggestedLine: bookmark.line,
      currentLineText,
      warning: "Bookmark has no line text anchor.",
    };
  }
  if (currentLineText.trim() === anchorText.trim()) {
    return {
      ...base,
      status: "stable",
      suggestedLine: bookmark.line,
      currentLineText,
    };
  }
  const matchingLines = [];
  for (let index = 0; index < lines.length; index++) {
    if (lines[index].trim() === anchorText.trim()) {
      matchingLines.push(index + 1);
    }
  }
  if (matchingLines.length === 1) {
    return {
      ...base,
      status: "moved",
      suggestedLine: matchingLines[0],
      currentLineText,
      warning: `Anchor moved from line ${bookmark.line} to ${matchingLines[0]}.`,
    };
  }
  if (matchingLines.length > 1) {
    return {
      ...base,
      status: "ambiguous",
      suggestedLine: 0,
      currentLineText,
      warning: "Anchor text appears multiple times.",
    };
  }
  return {
    ...base,
    status: "missingAnchor",
    suggestedLine: 0,
    currentLineText,
    warning: "Anchor text was not found in the current file.",
  };
}

function groupCounts(rows) {
  return rows.reduce((groups, row) => {
    const key = row.groupName || "(untitled)";
    groups[key] = (groups[key] || 0) + 1;
    return groups;
  }, {});
}

function workflowMatches(states, query) {
  const normalizedQuery = normalize(query);
  if (!normalizedQuery) {
    return [];
  }
  return states
    .map((state) => ({
      ...state,
      matchScore: scoreWorkflowMatch(state, normalizedQuery),
    }))
    .filter((state) => state.matchScore > 0)
    .sort((left, right) =>
      right.matchScore - left.matchScore
      || left.groupName.localeCompare(right.groupName)
      || left.title.localeCompare(right.title)
    );
}

function scoreWorkflowMatch(state, normalizedQuery) {
  let score = 0;
  if (normalize(state.groupName).includes(normalizedQuery)) score += 4;
  if (normalize(state.title).includes(normalizedQuery)) score += 3;
  if (normalize(state.filePath).includes(normalizedQuery)) score += 2;
  return score;
}

function normalize(value) {
  return stringValue(value).trim().toLowerCase();
}

function stringValue(value) {
  return typeof value === "string" ? value : "";
}

function stringArray(value) {
  return Array.isArray(value) ? value.map(stringValue) : [];
}

function positiveInt(value, fallback) {
  return Number.isInteger(value) && value >= 1 ? value : fallback;
}

function nonNegativeInt(value, fallback) {
  return Number.isInteger(value) && value >= 0 ? value : fallback;
}

function toPosix(value) {
  return stringValue(value).replace(/\\/g, "/");
}

function resolveSourcePath(root, filePath) {
  const normalizedPath = toPosix(filePath);
  if (!normalizedPath || path.isAbsolute(filePath) || normalizedPath.split("/").includes("..")) {
    return "";
  }
  const resolvedRoot = path.resolve(root);
  const resolvedPath = path.resolve(resolvedRoot, ...normalizedPath.split("/"));
  const comparableRoot = process.platform === "win32" ? resolvedRoot.toLowerCase() : resolvedRoot;
  const comparablePath = process.platform === "win32" ? resolvedPath.toLowerCase() : resolvedPath;
  if (comparablePath !== comparableRoot && !comparablePath.startsWith(comparableRoot + path.sep)) {
    return "";
  }
  return resolvedPath;
}

function stableJson(value) {
  return JSON.stringify(sortJson(value), null, 2);
}

function sortJson(value) {
  if (Array.isArray(value)) {
    return value.map(sortJson);
  }
  if (!value || typeof value !== "object") {
    return value;
  }
  return Object.keys(value)
    .sort()
    .reduce((result, key) => {
      result[key] = sortJson(value[key]);
      return result;
    }, {});
}
