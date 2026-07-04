package tools

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"os/exec"
	"strings"
	"time"
)

// GmailModule wraps the gmail-go-mcp binary as a subprocess.
// The binary supports terminal mode via -tool <name> -args '<json>' flags,
// which allows each MCP tool call to be dispatched as a separate process.
// Account credentials are read from environment variables by the binary:
//
//	ACCOUNT_{name}_EMAIL    — email address for account {name}
//	ACCOUNT_{name}_PASSWORD — app password for account {name}
//	DEFAULT_ACCOUNT_ID      — the {name} used by default when none is specified
type GmailModule struct {
	binary    string
	timeoutMs int
}

// NewGmailModule creates a gmail module from config.
func NewGmailModule(binary string, timeoutMs int) (*GmailModule, error) {
	if binary == "" {
		return nil, fmt.Errorf("gmail binary path not configured (set [tools.gmail] binary)")
	}
	if timeoutMs <= 0 {
		timeoutMs = 120000 // email operations can be slow (IMAP fetch)
	}
	return &GmailModule{binary: binary, timeoutMs: timeoutMs}, nil
}

func (m *GmailModule) Name() string { return "gmail" }

func (m *GmailModule) Tools() []Tool {
	return []Tool{
		&gmailListAccountsTool{m: m},
		&gmailListFoldersTool{m: m},
		&gmailFetchHeadersTool{m: m},
		&gmailFetchEmailTool{m: m},
		&gmailReadEmailBodyTool{m: m},
		&gmailSendEmailTool{m: m},
		&gmailFetchAttachmentTool{m: m},
		&gmailCreateDraftTool{m: m},
		&gmailListDraftsTool{m: m},
		&gmailGetDraftTool{m: m},
		&gmailUpdateDraftTool{m: m},
		&gmailSendDraftTool{m: m},
		&gmailDeleteDraftTool{m: m},
		&gmailSendAllDraftsTool{m: m},
		&gmailMarkAsReadTool{m: m},
		&gmailDeleteEmailTool{m: m},
		&gmailCreateLabelTool{m: m},
		&gmailGetLabelTool{m: m},
	}
}

// run executes the gmail-go-mcp binary in terminal mode with -tool and -args.
func (m *GmailModule) run(ctx context.Context, toolName string, args map[string]any) (string, error) {
	argsJSON := "{}"
	if args != nil {
		data, err := json.Marshal(args)
		if err != nil {
			return "", fmt.Errorf("marshal args: %w", err)
		}
		argsJSON = string(data)
	}
	timeout := time.Duration(m.timeoutMs) * time.Millisecond
	cctx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()
	cmd := exec.CommandContext(cctx, m.binary, "-tool", toolName, "-args", argsJSON)
	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr
	if err := cmd.Run(); err != nil {
		stderrStr := strings.TrimSpace(stderr.String())
		if cctx.Err() == context.DeadlineExceeded {
			return "", fmt.Errorf("gmail %s timed out after %dms", toolName, m.timeoutMs)
		}
		if stderrStr != "" {
			return "", fmt.Errorf("gmail %s: %s: %v", toolName, stderrStr, err)
		}
		return "", fmt.Errorf("gmail %s: %v", toolName, err)
	}
	return stdout.String(), nil
}

// ---------------------------------------------------------------------------
// Tool definitions
// ---------------------------------------------------------------------------

// --- list_accounts ---

type gmailListAccountsTool struct{ m *GmailModule }

func (t *gmailListAccountsTool) Name() string { return "gmail_list_accounts" }
func (t *gmailListAccountsTool) Description() string {
	return "List all configured email accounts with their IDs, email addresses, and which is the default account. Use this to discover available accounts before using account_id parameter in other tools."
}
func (t *gmailListAccountsTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{}, nil)
}
func (t *gmailListAccountsTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	out, err := t.m.run(ctx, "list_accounts", args)
	if err != nil {
		return NewErrorResult(err.Error())
	}
	return NewTextResult(out)
}

// --- list_folders ---

type gmailListFoldersTool struct{ m *GmailModule }

func (t *gmailListFoldersTool) Name() string { return "gmail_list_folders" }
func (t *gmailListFoldersTool) Description() string {
	return "List all available email folders/labels with message counts. Use account_id parameter to specify which email account to query (call gmail_list_accounts first to see available accounts)."
}
func (t *gmailListFoldersTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"account_id": Prop("string", "Account ID to use. If not specified, uses the default account from DEFAULT_ACCOUNT_ID"),
	}, nil)
}
func (t *gmailListFoldersTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	out, err := t.m.run(ctx, "list_folders", args)
	if err != nil {
		return NewErrorResult(err.Error())
	}
	return NewTextResult(out)
}

// --- fetch_email_headers ---

type gmailFetchHeadersTool struct{ m *GmailModule }

func (t *gmailFetchHeadersTool) Name() string { return "gmail_fetch_email_headers" }
func (t *gmailFetchHeadersTool) Description() string {
	return "Fetch email headers (metadata) without bodies. Use this to list emails before fetching full content. Be mindful of the limit parameter as fetching many emails uses memory. Use account_id parameter to specify which email account to query."
}
func (t *gmailFetchHeadersTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"account_id":       Prop("string", "Account ID to use. If not specified, uses the default account."),
		"folder":           Prop("string", "Email folder to fetch from (e.g., 'INBOX', 'Sent'). Default: INBOX"),
		"since_date":       Prop("string", "Fetch emails since this date (ISO format: 2024-01-20)"),
		"until_date":       Prop("string", "Fetch emails until this date (ISO format: 2024-01-27)"),
		"from":             Prop("string", "Filter by sender email address"),
		"subject_contains": Prop("string", "Filter by subject containing this text"),
		"unread_only":      Prop("boolean", "Only fetch unread emails. Default: false"),
		"limit":            Prop("integer", "Maximum number of emails to fetch. Default: 50"),
	}, nil)
}
func (t *gmailFetchHeadersTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	out, err := t.m.run(ctx, "fetch_email_headers", args)
	if err != nil {
		return NewErrorResult(err.Error())
	}
	return NewTextResult(out)
}

// --- fetch_email ---

type gmailFetchEmailTool struct{ m *GmailModule }

func (t *gmailFetchEmailTool) Name() string { return "gmail_fetch_email" }
func (t *gmailFetchEmailTool) Description() string {
	return "Fetch an email and cache it locally. Returns email metadata (headers, subject, from, to, date, attachments) and a text preview. The full body content is cached and can be read in chunks using gmail_read_email_body."
}
func (t *gmailFetchEmailTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"account_id":     Prop("string", "Account ID to use. If not specified, uses the default account."),
		"message_id":     Prop("string", "The Message-ID header value (e.g., '<CADsK8=example@mail.gmail.com>')"),
		"preview_length": Prop("integer", "Number of characters to include in the text preview. Default: 1000"),
	}, []string{"message_id"})
}
func (t *gmailFetchEmailTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	if ArgString(args, "message_id") == "" {
		return NewErrorResult("message_id is required")
	}
	out, err := t.m.run(ctx, "fetch_email", args)
	if err != nil {
		return NewErrorResult(err.Error())
	}
	return NewTextResult(out)
}

// --- read_email_body ---

type gmailReadEmailBodyTool struct{ m *GmailModule }

func (t *gmailReadEmailBodyTool) Name() string { return "gmail_read_email_body" }
func (t *gmailReadEmailBodyTool) Description() string {
	return "Read email body content from cache with pagination. Call gmail_fetch_email first to cache the email. Default format is 'text' which returns plain text (or HTML converted to text if no plain text exists)."
}
func (t *gmailReadEmailBodyTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"account_id": Prop("string", "Account ID to use. If not specified, uses the default account."),
		"message_id": Prop("string", "The Message-ID of the email (must have been fetched first using gmail_fetch_email)"),
		"format":     PropEnum("Content format: 'text' (default) returns plain text or HTML converted to text; 'raw_html' returns raw HTML", "text", "raw_html"),
		"offset":     Prop("integer", "Character position to start reading from. Default: 0"),
		"limit":      Prop("integer", "Maximum characters to return. Default: 10000"),
	}, []string{"message_id"})
}
func (t *gmailReadEmailBodyTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	if ArgString(args, "message_id") == "" {
		return NewErrorResult("message_id is required")
	}
	out, err := t.m.run(ctx, "read_email_body", args)
	if err != nil {
		return NewErrorResult(err.Error())
	}
	return NewTextResult(out)
}

// --- send_email ---

type gmailSendEmailTool struct{ m *GmailModule }

func (t *gmailSendEmailTool) Name() string { return "gmail_send_email" }
func (t *gmailSendEmailTool) Description() string {
	return "Send an email. Properly sets threading headers for replies. Use account_id parameter to specify which email account to send from."
}
func (t *gmailSendEmailTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"account_id":          Prop("string", "Account ID to use. If not specified, uses the default account."),
		"to":                  PropArray("string", "Recipient email addresses"),
		"cc":                  PropArray("string", "CC recipient email addresses"),
		"bcc":                 PropArray("string", "BCC recipient email addresses (hidden from other recipients)"),
		"subject":             Prop("string", "Email subject line"),
		"body":                Prop("string", "Plain text email body"),
		"html_body":           Prop("string", "HTML email body (optional)"),
		"attachments":         PropArray("string", "Cache IDs of attachments to include (from gmail_fetch_email_attachment)"),
		"reply_to_message_id": Prop("string", "Message-ID of email being replied to (for threading)"),
		"references":          PropArray("string", "Message-IDs for threading chain"),
	}, []string{"to", "subject"})
}
func (t *gmailSendEmailTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	to := ArgArray(args, "to")
	if len(to) == 0 {
		return NewErrorResult("to is required")
	}
	if ArgString(args, "subject") == "" {
		return NewErrorResult("subject is required")
	}
	out, err := t.m.run(ctx, "send_email", args)
	if err != nil {
		return NewErrorResult(err.Error())
	}
	return NewTextResult(out)
}

// --- fetch_email_attachment ---

type gmailFetchAttachmentTool struct{ m *GmailModule }

func (t *gmailFetchAttachmentTool) Name() string { return "gmail_fetch_email_attachment" }
func (t *gmailFetchAttachmentTool) Description() string {
	return "Fetch attachments from an email. Files are saved to cache for use with gmail_send_email. Maximum attachment size: 25MB."
}
func (t *gmailFetchAttachmentTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"account_id":       Prop("string", "Account ID to use. If not specified, uses the default account."),
		"message_id":       Prop("string", "The Message-ID header value of the email"),
		"attachment_names": PropArray("string", "Specific attachment filenames to fetch (e.g., ['report.pdf', 'image.png'])"),
		"fetch_all":        Prop("boolean", "Fetch all attachments from the email. Default: false"),
	}, []string{"message_id"})
}
func (t *gmailFetchAttachmentTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	if ArgString(args, "message_id") == "" {
		return NewErrorResult("message_id is required")
	}
	out, err := t.m.run(ctx, "fetch_email_attachment", args)
	if err != nil {
		return NewErrorResult(err.Error())
	}
	return NewTextResult(out)
}

// --- create_draft ---

type gmailCreateDraftTool struct{ m *GmailModule }

func (t *gmailCreateDraftTool) Name() string { return "gmail_create_draft" }
func (t *gmailCreateDraftTool) Description() string {
	return "Create a new email draft. Save an email composition for later sending or editing."
}
func (t *gmailCreateDraftTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"account_id":          Prop("string", "Account ID to use. If not specified, uses the default account."),
		"to":                  PropArray("string", "Recipient email addresses"),
		"cc":                  PropArray("string", "CC recipient email addresses"),
		"bcc":                 PropArray("string", "BCC recipient email addresses (hidden from other recipients)"),
		"subject":             Prop("string", "Email subject line"),
		"body":                Prop("string", "Plain text email body"),
		"html_body":           Prop("string", "HTML email body (optional)"),
		"attachments":         PropArray("string", "Cache IDs of attachments to include"),
		"reply_to_message_id": Prop("string", "Message-ID of email being replied to (for threading)"),
		"references":          PropArray("string", "Message-IDs for threading chain"),
	}, nil)
}
func (t *gmailCreateDraftTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	out, err := t.m.run(ctx, "create_draft", args)
	if err != nil {
		return NewErrorResult(err.Error())
	}
	return NewTextResult(out)
}

// --- list_drafts ---

type gmailListDraftsTool struct{ m *GmailModule }

func (t *gmailListDraftsTool) Name() string { return "gmail_list_drafts" }
func (t *gmailListDraftsTool) Description() string {
	return "List all saved email drafts with their summaries."
}
func (t *gmailListDraftsTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"account_id": Prop("string", "Account ID to use. If not specified, uses the default account."),
	}, nil)
}
func (t *gmailListDraftsTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	out, err := t.m.run(ctx, "list_drafts", args)
	if err != nil {
		return NewErrorResult(err.Error())
	}
	return NewTextResult(out)
}

// --- get_draft ---

type gmailGetDraftTool struct{ m *GmailModule }

func (t *gmailGetDraftTool) Name() string { return "gmail_get_draft" }
func (t *gmailGetDraftTool) Description() string {
	return "Retrieve a specific draft by its ID to view or edit."
}
func (t *gmailGetDraftTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"account_id": Prop("string", "Account ID to use. If not specified, uses the default account."),
		"draft_id":   Prop("string", "The ID of the draft to retrieve"),
	}, []string{"draft_id"})
}
func (t *gmailGetDraftTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	if ArgString(args, "draft_id") == "" {
		return NewErrorResult("draft_id is required")
	}
	out, err := t.m.run(ctx, "get_draft", args)
	if err != nil {
		return NewErrorResult(err.Error())
	}
	return NewTextResult(out)
}

// --- update_draft ---

type gmailUpdateDraftTool struct{ m *GmailModule }

func (t *gmailUpdateDraftTool) Name() string { return "gmail_update_draft" }
func (t *gmailUpdateDraftTool) Description() string {
	return "Update an existing draft. Only provided fields will be updated."
}
func (t *gmailUpdateDraftTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"account_id":  Prop("string", "Account ID to use. If not specified, uses the default account."),
		"draft_id":    Prop("string", "The ID of the draft to update"),
		"to":          PropArray("string", "Updated recipient email addresses"),
		"cc":          PropArray("string", "Updated CC recipients"),
		"bcc":         PropArray("string", "Updated BCC recipients"),
		"subject":     Prop("string", "Updated subject line"),
		"body":        Prop("string", "Updated plain text body"),
		"html_body":   Prop("string", "Updated HTML body"),
		"attachments": PropArray("string", "Updated attachment cache IDs"),
	}, []string{"draft_id"})
}
func (t *gmailUpdateDraftTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	if ArgString(args, "draft_id") == "" {
		return NewErrorResult("draft_id is required")
	}
	out, err := t.m.run(ctx, "update_draft", args)
	if err != nil {
		return NewErrorResult(err.Error())
	}
	return NewTextResult(out)
}

// --- send_draft ---

type gmailSendDraftTool struct{ m *GmailModule }

func (t *gmailSendDraftTool) Name() string { return "gmail_send_draft" }
func (t *gmailSendDraftTool) Description() string {
	return "Send a draft email and remove it from drafts storage."
}
func (t *gmailSendDraftTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"account_id": Prop("string", "Account ID to use. If not specified, uses the default account."),
		"draft_id":   Prop("string", "The ID of the draft to send"),
	}, []string{"draft_id"})
}
func (t *gmailSendDraftTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	if ArgString(args, "draft_id") == "" {
		return NewErrorResult("draft_id is required")
	}
	out, err := t.m.run(ctx, "send_draft", args)
	if err != nil {
		return NewErrorResult(err.Error())
	}
	return NewTextResult(out)
}

// --- delete_draft ---

type gmailDeleteDraftTool struct{ m *GmailModule }

func (t *gmailDeleteDraftTool) Name() string { return "gmail_delete_draft" }
func (t *gmailDeleteDraftTool) Description() string {
	return "Delete a draft without sending it."
}
func (t *gmailDeleteDraftTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"account_id": Prop("string", "Account ID to use. If not specified, uses the default account."),
		"draft_id":   Prop("string", "The ID of the draft to delete"),
	}, []string{"draft_id"})
}
func (t *gmailDeleteDraftTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	if ArgString(args, "draft_id") == "" {
		return NewErrorResult("draft_id is required")
	}
	out, err := t.m.run(ctx, "delete_draft", args)
	if err != nil {
		return NewErrorResult(err.Error())
	}
	return NewTextResult(out)
}

// --- send_all_drafts ---

type gmailSendAllDraftsTool struct{ m *GmailModule }

func (t *gmailSendAllDraftsTool) Name() string { return "gmail_send_all_drafts" }
func (t *gmailSendAllDraftsTool) Description() string {
	return "Send all drafts with a configurable delay between each email to avoid rate limits."
}
func (t *gmailSendAllDraftsTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"account_id":    Prop("string", "Account ID to use. If not specified, uses the default account."),
		"delay_seconds": Prop("integer", "Seconds to wait between sending each email (2-60). Default: 5"),
		"dry_run":       Prop("boolean", "If true, simulate sending without actually sending. Default: false"),
		"stop_on_error": Prop("boolean", "If true, stop sending if any email fails. Default: false"),
	}, nil)
}
func (t *gmailSendAllDraftsTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	out, err := t.m.run(ctx, "send_all_drafts", args)
	if err != nil {
		return NewErrorResult(err.Error())
	}
	return NewTextResult(out)
}

// --- mark_as_read ---

type gmailMarkAsReadTool struct{ m *GmailModule }

func (t *gmailMarkAsReadTool) Name() string { return "gmail_mark_as_read" }
func (t *gmailMarkAsReadTool) Description() string {
	return "Mark an email as read by setting the Seen flag. Searches all folders for the message by Message-ID."
}
func (t *gmailMarkAsReadTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"account_id": Prop("string", "Account ID to use. If not specified, uses the default account."),
		"message_id": Prop("string", "The Message-ID header value of the email to mark as read"),
	}, []string{"message_id"})
}
func (t *gmailMarkAsReadTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	if ArgString(args, "message_id") == "" {
		return NewErrorResult("message_id is required")
	}
	out, err := t.m.run(ctx, "mark_as_read", args)
	if err != nil {
		return NewErrorResult(err.Error())
	}
	return NewTextResult(out)
}

// --- delete_email ---

type gmailDeleteEmailTool struct{ m *GmailModule }

func (t *gmailDeleteEmailTool) Name() string { return "gmail_delete_email" }
func (t *gmailDeleteEmailTool) Description() string {
	return "Delete an email by Message-ID. Sets the Deleted flag and expunges the message from the folder."
}
func (t *gmailDeleteEmailTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"account_id": Prop("string", "Account ID to use. If not specified, uses the default account."),
		"message_id": Prop("string", "The Message-ID header value of the email to delete"),
	}, []string{"message_id"})
}
func (t *gmailDeleteEmailTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	if ArgString(args, "message_id") == "" {
		return NewErrorResult("message_id is required")
	}
	out, err := t.m.run(ctx, "delete_email", args)
	if err != nil {
		return NewErrorResult(err.Error())
	}
	return NewTextResult(out)
}

// --- create_label ---

type gmailCreateLabelTool struct{ m *GmailModule }

func (t *gmailCreateLabelTool) Name() string { return "gmail_create_label" }
func (t *gmailCreateLabelTool) Description() string {
	return "Create a new email label (folder/mailbox). Useful for organizing emails in Gmail or other providers."
}
func (t *gmailCreateLabelTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"account_id": Prop("string", "Account ID to use. If not specified, uses the default account."),
		"name":       Prop("string", "Name of the label/folder to create (e.g., 'MyLabel' or 'INBOX/SubLabel')"),
	}, []string{"name"})
}
func (t *gmailCreateLabelTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	if ArgString(args, "name") == "" {
		return NewErrorResult("name is required")
	}
	out, err := t.m.run(ctx, "create_label", args)
	if err != nil {
		return NewErrorResult(err.Error())
	}
	return NewTextResult(out)
}

// --- get_label ---

type gmailGetLabelTool struct{ m *GmailModule }

func (t *gmailGetLabelTool) Name() string { return "gmail_get_label" }
func (t *gmailGetLabelTool) Description() string {
	return "Get information about a specific label/folder including message and unread counts."
}
func (t *gmailGetLabelTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"account_id": Prop("string", "Account ID to use. If not specified, uses the default account."),
		"name":       Prop("string", "Name of the label/folder to inspect (e.g., 'INBOX', 'Sent', '[Gmail]/All Mail')"),
	}, []string{"name"})
}
func (t *gmailGetLabelTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	if ArgString(args, "name") == "" {
		return NewErrorResult("name is required")
	}
	out, err := t.m.run(ctx, "get_label", args)
	if err != nil {
		return NewErrorResult(err.Error())
	}
	return NewTextResult(out)
}
