package tools

// [@GHOST]{file_path="Dom_Mcp/dom_mcp/tools/bclcompressor.go"
// date="2026-07-04" author="Devin" session_id="bnd-laws"
// context="MCP exposure for BclChatCompressor — bcl_chat_* tools via Python subprocess bridge"}
// [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase Tuple3 Run dispatch"}
// [@FILEID]{id="bclcompressor.go" domain="mcp_tools" authority="BclCompressorModule"}
// [@SUMMARY]{summary="MCP module that wraps bcl_chat_compressor.py as subprocess. Exposes BCL Stage 1 chat compression — extract tokens from chat markdown files as bcl_chat_* tools for MCP clients."}
// [@CLASS]{class="BclCompressorModule" domain="mcp_tools" authority="single"}
// [@METHOD]{method="Name" type="interface"}
// [@METHOD]{method="Tools" type="interface"}
// [@METHOD]{method="run" type="helper"}

import (
	"bytes"
	"context"
	"fmt"
	"os/exec"
	"strings"
	"time"
)

// BclCompressorModule wraps the bcl_chat_compressor.py Python script as a subprocess.
// It exposes BCL Stage 1 chat compression as MCP bcl_chat_* tools.
type BclCompressorModule struct {
	binary    string // path to python3
	script    string // path to bcl_chat_compressor.py
	timeoutMs int
}

// NewBclCompressorModule creates a BclCompressorModule from config.
func NewBclCompressorModule(pythonBinary, scriptPath string, timeoutMs int) *BclCompressorModule {
	if pythonBinary == "" {
		pythonBinary = "python3"
	}
	if timeoutMs <= 0 {
		timeoutMs = 60000
	}
	return &BclCompressorModule{binary: pythonBinary, script: scriptPath, timeoutMs: timeoutMs}
}

func (m *BclCompressorModule) Name() string { return "bcl_chat" }

func (m *BclCompressorModule) Tools() []Tool {
	return []Tool{
		&bclCompressTool{name: "bcl_chat_compress", desc: "Compress a chat markdown file to BCL tokens (Stage 1). Extracts [@USER_SAYS] [@AI_SAYS] [@ERROR] [@FILE] [@COMMAND_RAN] [@FRUSTRATION_SIGNAL] [@QUESTION] [@TOPIC] tokens. Writes compressed .md file.", m: m, required: []string{"input"}},
		&bclCompressTool{name: "bcl_chat_dry_run", desc: "Extract BCL tokens from a chat markdown file without writing output. Returns token count, line count, and compression ratio preview.", m: m, required: []string{"input"}},
	}
}

// run executes bcl_chat_compressor.py with given CLI args and returns stdout.
func (m *BclCompressorModule) run(ctx context.Context, args ...string) (string, error) {
	if m.script == "" {
		return "", fmt.Errorf("bcl_chat_compressor.py path not configured")
	}
	timeout := time.Duration(m.timeoutMs) * time.Millisecond
	cctx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()
	cmdArgs := append([]string{m.script}, args...)
	cmd := exec.CommandContext(cctx, m.binary, cmdArgs...)
	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr
	if err := cmd.Run(); err != nil {
		stderrStr := strings.TrimSpace(stderr.String())
		if cctx.Err() == context.DeadlineExceeded {
			return "", fmt.Errorf("bcl_chat timed out after %dms", m.timeoutMs)
		}
		if stderrStr != "" {
			return "", fmt.Errorf("bcl_chat: %s: %v", stderrStr, err)
		}
		return "", fmt.Errorf("bcl_chat: %v", err)
	}
	return stdout.String(), nil
}

// bclCompressTool is a tool that maps to a bcl_chat_compressor.py CLI command.
type bclCompressTool struct {
	name     string
	desc     string
	m        *BclCompressorModule
	required []string
}

func (t *bclCompressTool) Name() string        { return t.name }
func (t *bclCompressTool) Description() string { return t.desc }

func (t *bclCompressTool) InputSchema() map[string]any {
	props := map[string]map[string]any{
		"input":  Prop("string", "Path to source chat .md file to compress."),
		"output": Prop("string", "Output BCL .md file path (default: <input>_BCL_stage1.md). Only for compress, not dry_run."),
	}
	return Schema(props, t.required)
}

func (t *bclCompressTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	inputPath := ArgString(args, "input")
	if inputPath == "" {
		return NewErrorResult(t.name + " requires 'input' parameter")
	}

	var cmdArgs []string
	switch t.name {
	case "bcl_chat_compress":
		cmdArgs = []string{"--input", inputPath}
		if output := ArgString(args, "output"); output != "" {
			cmdArgs = append(cmdArgs, "--output", output)
		}
	case "bcl_chat_dry_run":
		cmdArgs = []string{"--input", inputPath, "--dry-run"}
	default:
		return NewErrorResult("unknown bcl_chat command: " + t.name)
	}

	out, err := t.m.run(ctx, cmdArgs...)
	if err != nil {
		return NewErrorResult(fmt.Sprintf("bcl_chat error: %v", err))
	}

	return NewTextResult(strings.TrimSpace(out))
}
