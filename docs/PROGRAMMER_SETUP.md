# Programmer Agent Setup Guide

The Programmer Agent has been successfully added to TARS! This guide will help you configure and use it.

## Configuration

Add these environment variables to your `.env` file:

```bash
# GitHub Integration
GITHUB_TOKEN=your_github_personal_access_token_here
GITHUB_USERNAME=matedort

# Programmer Agent Settings
PROJECTS_ROOT=/Users/matedort/
MAX_COMMAND_TIMEOUT=60
ENABLE_CODE_BACKUPS=true
```

### Getting a GitHub Token

1. Go to GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Click "Generate new token (classic)"
3. Give it a name (e.g., "TARS Programmer Agent")
4. Select scopes:
   - `repo` (Full control of private repositories)
   - `workflow` (Update GitHub Action workflows)
5. Click "Generate token"
6. Copy the token and add it to your `.env` file as `GITHUB_TOKEN`

**Important**: Keep your token secure. Never commit it to version control.

## Features

The Programmer Agent provides four main functions:

### 1. Project Management (`manage_project`)

List, create, open, and get info about projects:

**Examples**:
- "List all my projects"
- "Create a new Python project called spending-tracker"
- "Open my simple-portfolio project"
- "Tell me about the simple-portfolio project"

### 2. Terminal Execution (`execute_terminal`)

Execute terminal commands with safety checks:

**Safe commands** (no confirmation needed):
- `ls`, `pwd`, `cd`, `cat`, `echo`
- `git status`, `git log`, `git diff`
- `npm install`, `pip install`
- `node --version`, `python --version`

**Destructive commands** (requires confirmation):
- `rm`, `rmdir`, `git push`
- `sudo`, `chmod`, `chown`

**Examples**:
- "Run npm install in my project"
- "Execute git status in simple-portfolio"
- "Run python main.py in spending-tracker"

### 3. Code Editing (`edit_code`)

AI-powered code editing:

**Actions**:
- `read`: View file contents
- `create`: Create new file
- `edit`: Modify file using AI (shows diff before applying)
- `delete`: Remove file (requires confirmation)

**Examples**:
- "Read the style.css file in simple-portfolio"
- "Change the background color to blue in simple-portfolio/style.css"
- "Fix the bug in the login function in app.py"
- "Add error handling to the API call in main.js"

### 4. GitHub Operations (`github_operation`)

Full GitHub integration:

**Actions**:
- `init`: Initialize git repository
- `list_repos`: Show your GitHub repositories
- `clone`: Clone a repository
- `push`: Push changes (requires confirmation)
- `pull`: Pull latest changes
- `create_repo`: Create new repository (requires confirmation)

**Examples**:
- "Initialize git in this project"
- "List my GitHub repositories"
- "Clone https://github.com/user/repo.git"
- "Push changes to GitHub with message 'Update background color'"
- "Create a new GitHub repository for spending-tracker"

## Safety Features

### Confirmation System

Destructive operations require user confirmation:
- Git push operations
- Repository creation
- File deletion
- Commands with `rm`, `sudo`, etc.

When TARS asks for confirmation, respond with:
- "yes" / "confirm" / "proceed" → Execute the operation
- "no" / "cancel" / "stop" → Cancel the operation

### Backups

When `ENABLE_CODE_BACKUPS=true`, TARS creates backups before editing files:
- Backups are stored in `.tars_backups/` folder
- Named with timestamp: `filename.backup.20260126_143025`
- Only created for edit operations, not creates

### Timeouts

Terminal commands have timeouts to prevent hanging:
- Default: 60 seconds
- Maximum: 600 seconds (10 minutes)
- Configurable via `MAX_COMMAND_TIMEOUT`

### Permission Restrictions

All programmer functions require **FULL** access:
- Only Máté (authenticated via phone number) can use them
- Unknown callers cannot access programming features
- Logged in security audit log

## Usage Examples

### Example 1: Change Portfolio Background

```
You: "Change the background color of my simple portfolio website to blue"

TARS:
1. Lists projects → finds "simple-portfolio"
2. Opens project → shows structure
3. Edits style.css → shows diff
4. Asks: "Ready to apply these changes?"
5. You: "yes"
6. Applies changes
7. Asks: "Ready to push to GitHub?"
8. You: "yes"
9. Commits and pushes
```

### Example 2: Create Spending Tracker App

```
You: "Make an app that uses Gemini to track my spending"

TARS:
1. Creates project folder: /Users/matedort/spending-tracker/
2. Creates main.py with Gemini integration code
3. Creates requirements.txt
4. Creates README.md
5. Initializes git
6. Asks: "Create GitHub repo 'spending-tracker'?"
7. You: "yes"
8. Creates repository via GitHub API
9. Asks: "Push to GitHub?"
10. You: "yes"
11. Commits and pushes
```

### Example 3: Debug a File

```
You: "There's a bug in my spending tracker app, can you debug the main.py file?"

TARS:
1. Reads main.py
2. Analyzes code with Gemini
3. Identifies bug
4. Generates fix
5. Shows diff
6. Asks: "Apply these changes?"
7. You: "yes"
8. Applies fix
9. Creates backup in .tars_backups/
10. Asks: "Push to GitHub?"
```

## Database Logging

All programming operations are logged to the database:

**Tables**:
- `programming_operations`: Command history with output/errors
- `project_cache`: Project metadata and git status

**Query examples**:
```sql
-- View recent operations
SELECT * FROM programming_operations ORDER BY created_at DESC LIMIT 10;

-- View cached projects
SELECT * FROM project_cache ORDER BY last_accessed DESC;
```

## Troubleshooting

### GitHub Authentication Failed

**Error**: "GitHub authentication not configured"

**Solution**:
1. Verify `GITHUB_TOKEN` is set in `.env`
2. Check token has correct permissions (repo, workflow)
3. Test token: `gh auth status` or visit https://github.com/settings/tokens

### Command Timeout

**Error**: "Command timed out after 60 seconds"

**Solution**:
1. Increase `MAX_COMMAND_TIMEOUT` in `.env`
2. For very long operations, use background processes
3. Split large operations into smaller steps

### File Too Large

**Error**: "File is too large to read (>100KB)"

**Solution**:
- TARS limits file reads to 100KB for performance
- For large files, use terminal commands: `head`, `tail`, `grep`
- Or split file editing into sections

### Permission Denied

**Error**: "Permission Denied"

**Solution**:
1. Check file/directory permissions
2. Ensure TARS user has access
3. For system directories, use `sudo` (will require confirmation)

## Technical Details

### Architecture

```
ProgrammerAgent
├── Project Management
│   ├── List projects in /Users/matedort/
│   ├── Create new projects (Python, Node, React, Next)
│   ├── Open and analyze project structure
│   └── Cache project metadata
├── Terminal Execution
│   ├── Execute shell commands via subprocess
│   ├── Safety classification (safe vs destructive)
│   ├── Timeout protection
│   └── Operation logging
├── Code Editing
│   ├── Read/create/edit/delete files
│   ├── AI-powered analysis with Gemini
│   ├── Diff generation before applying
│   └── Automatic backups
└── GitHub Operations
    ├── git init, status, add, commit
    ├── Push/pull with GitHub API
    ├── Repository creation/cloning
    └── Authentication via token
```

### Files Modified

1. `sub_agents_tars.py` - ProgrammerAgent class (~700 lines)
2. `github_operations.py` - GitHub integration module (new file)
3. `database.py` - Added programming tables and methods
4. `config.py` - Added GitHub and programmer settings
5. `main_tars.py` - Registered programmer functions
6. `task_planner.py` - Added programming category
7. `requirements.txt` - Added PyGithub and gitpython

## Next Steps

1. **Add GitHub token to `.env`**:
   ```bash
   GITHUB_TOKEN=ghp_your_token_here
   GITHUB_USERNAME=matedort
   ```

2. **Restart TARS**:
   ```bash
   python main_tars.py
   ```

3. **Test the features**:
   - "List all my projects"
   - "Create a test project"
   - "Show my GitHub repositories"

4. **Try a complete workflow**:
   - Create a project
   - Edit some files
   - Push to GitHub

## Support

If you encounter issues:
1. Check logs in console output
2. Review database: `SELECT * FROM programming_operations`
3. Verify environment variables in `.env`
4. Check GitHub token permissions

Happy coding with TARS! 🚀
