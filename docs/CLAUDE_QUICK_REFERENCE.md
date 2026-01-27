# Claude Programming Integration - Quick Reference

One-page reference for TARS's Claude programming features.

---

## 🚀 Quick Start (3 Steps)

```bash
# 1. Install dependency
pip install anthropic

# 2. Add to .env
ANTHROPIC_API_KEY=sk-ant-api03-xxxxx

# 3. Restart TARS
python3 main_tars.py
```

---

## 🤖 Model Selection

| Complexity | Model | Speed | Use Case |
|-----------|-------|-------|----------|
| **0-4** | Claude 3.5 Haiku | ⚡ Fast (1-2s) | Simple edits, comments, formatting |
| **5-10** | Claude Sonnet 4.5 | 🧠 Smart (5-10s) | Refactoring, complex logic, architecture |

**Threshold**: 5/10

---

## 📊 Complexity Factors

| Factor | Impact |
|--------|--------|
| Keywords: "refactor", "debug", "optimize" | +2 each |
| Keywords: "comment", "format", "typo" | -2 each |
| File > 500 lines | +3 |
| File > 200 lines | +2 |
| Multi-file operation | +3 |

---

## 💬 Example Commands

### Simple Tasks (→ Haiku 3.5)

```
"Add a comment to the main function"
"Fix the typo in config.py"
"Rename variable user_id to userId"
"Format the code in utils.py"
```

### Complex Tasks (→ Sonnet 4.5)

```
"Create a web scraper for e-commerce products"
"Refactor the authentication system"
"Debug the memory leak in process_data"
"Optimize the database query performance"
```

---

## 📝 Documentation

Every operation creates `.tars_docs/filename_timestamp.md` with:

- ✅ Timestamp & file path
- ✅ Model used (Sonnet 4.5 / Haiku 3.5)
- ✅ Complexity score (0-10)
- ✅ Logic explanation
- ✅ Changes/diff (for edits)
- ✅ Sent to Discord automatically

---

## 💰 Cost Estimates

| Task Type | Model | Cost |
|-----------|-------|------|
| Simple edit | Haiku | $0.001 |
| Medium task | Haiku | $0.005 |
| Complex | Sonnet | $0.05-0.10 |

**Monthly** (10 tasks/day): ~$2.50

---

## ⚙️ Configuration

### Required
```bash
ANTHROPIC_API_KEY=sk-ant-xxxxx
```

### Optional
```bash
CLAUDE_COMPLEX_MODEL=claude-sonnet-4-20250514
CLAUDE_FAST_MODEL=claude-3-5-haiku-20241022
ENABLE_PROGRAMMING_DOCS=true
PROGRAMMING_DOCS_DIR=.tars_docs
```

---

## 🔍 Verify It's Working

### Check Logs
```
INFO: Claude client initialized...
INFO: Task complexity analysis: 7/10
INFO: Selected Claude Sonnet 4.5 (complex)
INFO: Documentation saved to: .tars_docs/...
INFO: Successfully sent to Discord
```

### Check Files
```bash
ls -la .tars_docs/
# Should show .md files for each operation
```

### Check Discord
Should receive notifications with full documentation

---

## ⚠️ Troubleshooting

| Issue | Solution |
|-------|----------|
| "Claude client not initialized" | Add ANTHROPIC_API_KEY to .env and restart |
| "Discord notification skipped" | Set N8N_WEBHOOK_URL in .env |
| Model selection seems wrong | Check logs for complexity analysis |

---

## 📚 Full Documentation

- **Quick Start**: `docs/CLAUDE_SETUP_QUICK_START.md`
- **Complete Guide**: `docs/CLAUDE_PROGRAMMING_INTEGRATION.md`
- **Summary**: `docs/CLAUDE_INTEGRATION_SUMMARY.md`
- **Config Template**: `env.example`

---

## 🎯 What Changed

| File | Change |
|------|--------|
| `sub_agents_tars.py` | +989 lines (6 new methods, 2 enhanced) |
| `core/config.py` | +5 lines (Claude config) |
| `requirements.txt` | +3 lines (anthropic package) |
| `docs/*` | +1,400 lines (documentation) |

---

**Version**: 1.0  
**Status**: ✅ Ready  
**Date**: 2026-01-27
