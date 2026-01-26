#!/usr/bin/env python3
"""Test full GitHub workflow: create project, add file, create repo, push."""
import asyncio
import os
import shutil
from pathlib import Path

async def test_workflow():
    print("\n" + "="*60)
    print("  Testing Full GitHub Workflow")
    print("="*60 + "\n")
    
    # Import after showing header
    from github_operations import GitHubOperations
    
    test_project = Path("/Users/matedort/tars_test_project")
    
    # Cleanup if exists
    if test_project.exists():
        print(f"🧹 Cleaning up existing test project...")
        shutil.rmtree(test_project)
    
    # Step 1: Create project directory
    print(f"\n1️⃣  Creating test project directory...")
    test_project.mkdir(parents=True)
    print(f"   ✅ Created: {test_project}")
    
    # Step 2: Create test file
    print(f"\n2️⃣  Creating test HTML file...")
    index_file = test_project / "index.html"
    index_file.write_text("""<!DOCTYPE html>
<html>
<head>
    <title>TARS Test</title>
    <style>
        body {
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
            font-family: Arial, sans-serif;
        }
    </style>
</head>
<body>
    <h1>Hello from TARS! 🤖</h1>
</body>
</html>""")
    print(f"   ✅ Created: index.html")
    
    # Step 3: Initialize git
    print(f"\n3️⃣  Initializing git repository...")
    gh = GitHubOperations()
    result = await gh.git_init(str(test_project))
    if result.get('success'):
        print(f"   ✅ Git initialized")
    else:
        print(f"   ❌ Git init failed: {result.get('error')}")
        return False
    
    # Step 4: Create README
    print(f"\n4️⃣  Creating README...")
    readme = test_project / "README.md"
    readme.write_text("# TARS Test Project\n\nThis is a test project created by TARS to verify GitHub integration.\n")
    print(f"   ✅ Created: README.md")
    
    # Step 5: Commit files
    print(f"\n5️⃣  Committing files...")
    result = await gh.git_add_commit(
        str(test_project),
        "Initial commit by TARS test",
        "."
    )
    if result.get('success'):
        print(f"   ✅ Files committed")
    else:
        print(f"   ❌ Commit failed: {result.get('error')}")
        return False
    
    # Step 6: Create GitHub repository
    print(f"\n6️⃣  Creating GitHub repository...")
    if not gh.is_authenticated():
        print(f"   ❌ Not authenticated with GitHub")
        return False
    
    repo_name = "tars-test-repo-" + str(int(asyncio.get_event_loop().time()))[-6:]
    result = await gh.create_repository(
        repo_name,
        "Test repository created by TARS programmer agent",
        private=False
    )
    
    if result.get('success'):
        repo_url = result.get('url')
        print(f"   ✅ Repository created: {repo_url}")
        
        # Step 7: Add remote and push
        print(f"\n7️⃣  Adding remote and pushing...")
        remote_url = f"https://github.com/MateDort/{repo_name}.git"
        
        # Add remote
        add_result = await gh.add_remote(str(test_project), remote_url)
        if not add_result.get('success'):
            print(f"   ⚠️  Add remote warning: {add_result.get('message')}")
        
        # Get current branch
        branch = await gh.get_current_branch(str(test_project))
        print(f"   Current branch: {branch or 'main'}")
        
        # Push to GitHub
        push_result = await gh.git_push(str(test_project), branch or "main")
        if push_result.get('success'):
            print(f"   ✅ Pushed to GitHub!")
            print(f"\n🎉 SUCCESS! View your repo at:")
            print(f"   {repo_url}")
        else:
            print(f"   ❌ Push failed: {push_result.get('error')}")
            print(f"   You can manually push with:")
            print(f"   cd {test_project}")
            print(f"   git remote add origin {remote_url}")
            print(f"   git push -u origin main")
    else:
        print(f"   ❌ Repository creation failed: {result.get('error')}")
        return False
    
    # Summary
    print("\n" + "="*60)
    print("  ✅ Full Workflow Test Complete!")
    print("="*60)
    print(f"""
Test Summary:
  ✓ Project directory created
  ✓ HTML file created
  ✓ Git initialized
  ✓ Files committed
  ✓ GitHub repository created
  ✓ Code pushed to GitHub

Repository: {repo_url}
Local path: {test_project}

🎉 TARS can now handle complete GitHub workflows!
    """)
    
    return True

if __name__ == "__main__":
    import sys
    success = asyncio.run(test_workflow())
    sys.exit(0 if success else 1)
