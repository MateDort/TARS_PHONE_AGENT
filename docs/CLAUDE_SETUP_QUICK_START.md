# Claude Programming Integration - Quick Start Guide

Get TARS's Claude-powered programming agent up and running in 5 minutes!

---

## Step 1: Install Dependencies

```bash
cd /Users/matedort/TARS_PHONE_AGENT
pip install anthropic
```

Or install all dependencies:

```bash
pip install -r requirements.txt
```

---

## Step 2: Get Your Anthropic API Key

1. Visit [console.anthropic.com](https://console.anthropic.com)
2. Sign up or log in with your account
3. Navigate to **API Keys** in the sidebar
4. Click **Create Key**
5. Copy your new API key (starts with `sk-ant-`)

---

## Step 3: Add API Key to .env

Open your `.env` file and add:

```bash
# Claude AI for programming tasks
ANTHROPIC_API_KEY=sk-ant-api03-xxxxx  # Replace with your actual key
```

**Optional**: Customize models (defaults are already optimal):

```bash
CLAUDE_COMPLEX_MODEL=claude-sonnet-4-20250514  # Sonnet 4.5 for complex tasks
CLAUDE_FAST_MODEL=claude-3-5-haiku-20241022    # Haiku 3.5 for simple tasks
```

**Optional**: Customize documentation settings:

```bash
ENABLE_PROGRAMMING_DOCS=true       # Generate .md docs for all operations
PROGRAMMING_DOCS_DIR=.tars_docs    # Where to save documentation
```

---

## Step 4: Restart TARS

```bash
python3 main_tars.py
```

Look for the confirmation in the logs:

```
INFO: Claude client initialized with complex model: claude-sonnet-4-20250514, fast model: claude-3-5-haiku-20241022
```

---

## Step 5: Test It Out!

### Test 1: Create a Simple File (Should use Haiku)

Call TARS and say:

> "Create a Python file called hello.py that prints hello world"

**Expected**:
- Uses **Claude 3.5 Haiku** (fast model)
- File created instantly
- Documentation saved to `.tars_docs/`
- Discord notification sent

### Test 2: Complex Task (Should use Sonnet)

Call TARS and say:

> "Create a Python web scraper that extracts product information from e-commerce sites"

**Expected**:
- Uses **Claude Sonnet 4.5** (complex model)
- Full implementation generated
- Comprehensive documentation
- Discord notification sent

### Test 3: Edit Existing File

Call TARS and say:

> "Edit main.py to add error handling and logging"

**Expected**:
- File read and analyzed
- Appropriate model selected based on complexity
- Changes applied with backup
- Before/after diff in documentation
- Discord notification sent

---

## Verify It's Working

### 1. Check Logs

You should see entries like:

```
INFO: Task complexity analysis: 7/10 for 'create web scraper'
INFO: Selected Claude Sonnet 4.5 (complex) for complexity 7/10
INFO: Calling Claude Sonnet 4.5 for code generation/modification
INFO: Created file: /path/to/file.py using Claude Sonnet 4.5
INFO: Documentation saved to: /path/to/.tars_docs/create_file_20260127_143022.md
INFO: Successfully sent programming documentation for file.py to Discord
```

### 2. Check Documentation Folder

```bash
ls -la .tars_docs/
```

You should see `.md` files for each operation:

```
create_hello_20260127_143022.md
edit_main_20260127_144530.md
...
```

### 3. Check Discord

You should receive messages in Discord showing:
- File name
- Operation type
- Model used
- Complexity score
- Full documentation

---

## Troubleshooting

### "Claude client not initialized"

**Problem**: ANTHROPIC_API_KEY not found

**Solution**:
1. Check `.env` file has the key
2. Restart TARS
3. Verify key is valid at console.anthropic.com

### "Documentation generated but Discord notification skipped"

**Problem**: N8N webhook not configured

**Solution**:
1. Ensure `N8N_WEBHOOK_URL` is set in `.env`
2. Test N8N webhook separately
3. Documentation is still saved locally in `.tars_docs/`

### Model Selection Seems Wrong

**Check logs** for complexity analysis:

```
INFO: Task complexity analysis: 3/10 for 'add comment'
INFO: Selected Claude 3.5 Haiku (fast) for complexity 3/10
```

Threshold is 5/10:
- **≥ 5**: Sonnet 4.5 (complex)
- **< 5**: Haiku 3.5 (fast)

---

## What Changed?

### Files Modified

1. **`sub_agents_tars.py`**
   - Added Claude client initialization
   - Replaced Gemini with Claude for code operations
   - Added 6 new methods for complexity analysis, model selection, and documentation

2. **`core/config.py`**
   - Added `ANTHROPIC_API_KEY`
   - Added `CLAUDE_COMPLEX_MODEL` and `CLAUDE_FAST_MODEL`
   - Added `ENABLE_PROGRAMMING_DOCS` and `PROGRAMMING_DOCS_DIR`

3. **`requirements.txt`**
   - Added `anthropic>=0.40.0`

### Files Created

- `docs/CLAUDE_PROGRAMMING_INTEGRATION.md` - Full documentation
- `docs/CLAUDE_SETUP_QUICK_START.md` - This guide
- `env.example` - Configuration template

---

## Cost Estimates

### Per Operation

- **Simple edit** (Haiku): ~$0.001 (1/10th of a cent)
- **Medium task** (Haiku): ~$0.005 (half a cent)
- **Complex refactor** (Sonnet): ~$0.05-0.10 (5-10 cents)
- **New file creation** (varies): $0.005-0.05

### Monthly Estimates (Moderate Use)

- **10 simple edits/day**: ~$3/month
- **5 complex tasks/day**: ~$7.50/month
- **Total**: ~$10-15/month

The intelligent model selection saves ~90% compared to using Sonnet 4.5 for everything!

---

## Next Steps

### Explore Advanced Features

1. **Multi-file operations**: "Refactor all Python files in this project"
2. **Project management**: "Open project my-api" then "Create endpoints"
3. **GitHub integration**: "Create a new repo and push this project"

### Review Documentation

Check `.tars_docs/` regularly to see:
- What changes were made
- Which models were used
- Complexity trends over time

### Customize Complexity Thresholds

The default threshold (5/10) works well, but you can adjust by:
- Using more specific task descriptions
- Mentioning "simple" or "complex" explicitly
- Breaking large tasks into smaller ones

---

## Support

- **Full Documentation**: `docs/CLAUDE_PROGRAMMING_INTEGRATION.md`
- **Architecture Guide**: `docs/ARCHITECTURE.md`
- **Configuration Reference**: `env.example`

---

**Status**: ✅ Ready to Use  
**Version**: 1.0  
**Date**: 2026-01-27
