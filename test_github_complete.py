#!/usr/bin/env python3
"""Comprehensive GitHub access test for TARS."""
import sys
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def print_section(title):
    """Print a formatted section header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)

def main():
    print("\n🔍 TARS GitHub Access Test")
    print("="*60)
    
    # Test 1: Check imports
    print_section("1. Testing Python Imports")
    try:
        from github import Github
        print("✅ PyGithub imported successfully")
    except ImportError as e:
        print(f"❌ PyGithub import failed: {e}")
        return False
    
    try:
        from config import Config
        print("✅ Config imported successfully")
    except ImportError as e:
        print(f"❌ Config import failed: {e}")
        return False
    
    # Test 2: Check token configuration
    print_section("2. Testing Token Configuration")
    token = Config.GITHUB_TOKEN
    username = Config.GITHUB_USERNAME
    
    if not token:
        print("❌ GITHUB_TOKEN is empty in config!")
        return False
    
    print(f"✅ Token configured (length: {len(token)} chars)")
    print(f"✅ Username configured: {username}")
    print(f"   Token preview: {token[:20]}...{token[-4:]}")
    
    # Test 3: Test PyGithub authentication
    print_section("3. Testing GitHub Authentication")
    try:
        g = Github(token)
        user = g.get_user()
        print(f"✅ Authenticated as: {user.login}")
        print(f"   Name: {user.name}")
        print(f"   Email: {user.email or 'Not public'}")
        print(f"   Public repos: {user.public_repos}")
        print(f"   Followers: {user.followers}")
    except Exception as e:
        print(f"❌ Authentication failed: {e}")
        return False
    
    # Test 4: Test GitHubOperations class
    print_section("4. Testing GitHubOperations Module")
    try:
        from github_operations import GitHubOperations
        gh_ops = GitHubOperations()
        print(f"✅ GitHubOperations initialized")
        print(f"   Is authenticated: {gh_ops.is_authenticated()}")
        print(f"   Token length: {len(gh_ops.token)}")
        
        if gh_ops.github_client:
            user = gh_ops.github_client.get_user()
            print(f"   Client user: {user.login}")
        else:
            print("❌ GitHub client is None!")
            return False
    except Exception as e:
        print(f"❌ GitHubOperations test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 5: List repositories
    print_section("5. Testing Repository Listing")
    try:
        repos = list(user.get_repos()[:5])  # Get first 5 repos
        print(f"✅ Found {user.public_repos} total repositories")
        print("   First 5 repos:")
        for repo in repos:
            print(f"     - {repo.name} ({repo.private and 'private' or 'public'})")
    except Exception as e:
        print(f"⚠️  Could not list repos: {e}")
    
    # Test 6: Test rate limit
    print_section("6. Testing API Rate Limit")
    try:
        rate_limit = g.get_rate_limit()
        core = rate_limit.core
        print(f"✅ Rate limit info:")
        print(f"   Remaining: {core.remaining}/{core.limit}")
        print(f"   Resets at: {core.reset}")
    except Exception as e:
        print(f"⚠️  Could not get rate limit: {e}")
    
    # Final summary
    print_section("✅ ALL TESTS PASSED!")
    print(f"""
GitHub Access Summary:
  • PyGithub: Working
  • Token: Configured ({len(token)} chars)
  • Authentication: Success
  • User: {user.login} ({user.name})
  • Repositories: {user.public_repos} public repos
  • GitHubOperations: Initialized and authenticated

🎉 TARS can now use GitHub API operations!
    """)
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
