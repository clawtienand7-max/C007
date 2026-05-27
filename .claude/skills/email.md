# Email Skill

Use this skill whenever the user wants to **send, read, list, search, reply to, or delete emails**.

## Tool location
All email operations go through:
```
python3 /home/user/C007/email_tool.py <command> [options]
```

## First-time setup check
Before any email operation, verify config exists:
```bash
test -f /home/user/C007/email_config.json && echo "configured" || echo "not configured"
```
If not configured, run `python3 /home/user/C007/email_tool.py setup` interactively
OR ask the user for credentials to write `email_config.json` directly.

---

## Commands

### Send an email
```bash
python3 /home/user/C007/email_tool.py send \
  --to "recipient@example.com" \
  --subject "Subject here" \
  --body "Email body text"
```
Optional flags: `--cc`, `--bcc`, `--attach file.pdf`, `--html` (for HTML body)

Write body to a temp file for long content:
```bash
cat > /tmp/email_body.txt << 'EOF'
Multi-line body here
EOF
python3 /home/user/C007/email_tool.py send \
  --to "recipient@example.com" \
  --subject "Subject" \
  --body-file /tmp/email_body.txt
```

### List inbox (most recent first)
```bash
python3 /home/user/C007/email_tool.py list --limit 20
```
Add `--search "UNSEEN"` for unread only.
Add `--folder "Sent"` for sent mail.

### Read a specific email
```bash
python3 /home/user/C007/email_tool.py read <ID>
```
The ID comes from the `list` command output.

### Reply to an email
```bash
python3 /home/user/C007/email_tool.py reply <ID> --body "Your reply text"
```

### Search emails
```bash
python3 /home/user/C007/email_tool.py search --from-addr "boss@company.com"
python3 /home/user/C007/email_tool.py search --subject "Invoice" --since "01-Jan-2026"
python3 /home/user/C007/email_tool.py search --unread
python3 /home/user/C007/email_tool.py search --body "NINJA 400"
```

### Delete an email
```bash
python3 /home/user/C007/email_tool.py delete <ID>
```

### List folders / labels
```bash
python3 /home/user/C007/email_tool.py folders
```

---

## Workflow patterns

### "Check my email"
1. Run `list --limit 20`
2. Summarise subjects, senders, dates in a readable table
3. Ask if user wants to read any specific one

### "Send the complaint letter"
1. Write the full body to `/tmp/email_body.txt`
2. Run `send --to ... --subject ... --body-file /tmp/email_body.txt`
3. Confirm success

### "Reply to the latest email from X"
1. `search --from-addr "X"` → get ID
2. `read <ID>` → show user the original
3. Compose reply, confirm with user
4. `reply <ID> --body "..."`

### "Find emails about topic Y"
1. `search --subject "Y"` and/or `search --body "Y"`
2. Present results, let user pick one to read

---

## Security notes
- `email_config.json` is chmod 600 (owner-read only)
- Never print or log passwords
- For Gmail: always use a 16-char **App Password**, not the account password
  Setup: myaccount.google.com → Security → 2-Step Verification → App passwords
- Credentials can also be set via env vars:
  `EMAIL_USER`, `EMAIL_PASS`, `EMAIL_SMTP`, `EMAIL_IMAP`

## Error handling
| Error | Likely cause | Fix |
|-------|-------------|-----|
| `[AUTHENTICATIONFAILED]` | Wrong password | Use App Password for Gmail |
| `SMTPAuthenticationError` | 2FA not set up | Enable 2FA first, then create App Password |
| `Connection refused` | Wrong host/port | Check provider preset in config |
| `No credentials found` | Missing config | Run `setup` or create `email_config.json` |
