"""GitHub operations module for TARS programmer agent."""
import logging
import os
import subprocess
from typing import Dict, Any, Optional, List
from pathlib import Path
from config import Config

logger = logging.getLogger(__name__)


class GitHubOperations:
    """Handle GitHub operations with authentication and safety checks."""

    def __init__(self, token: Optional[str] = None, username: Optional[str] = None):
        """Initialize GitHub operations.
        
        Args:
            token: GitHub personal access token
            username: GitHub username
        """
        self.token = token or Config.GITHUB_TOKEN
        self.username = username or Config.GITHUB_USERNAME
        self.github_client = None
        
        # Initialize PyGithub client if token is available
        if self.token:
            try:
                from github import Github
                self.github_client = Github(self.token)
                # Test authentication
                user = self.github_client.get_user()
                logger.info(f"✓ GitHub authenticated as: {user.login}")
            except ImportError as ie:
                logger.warning(f"PyGithub not installed: {ie}. Install with: pip install PyGithub")
                self.github_client = None
            except Exception as e:
                logger.error(f"GitHub authentication failed: {e} (token length: {len(self.token) if self.token else 0})")
                self.github_client = None
        else:
            logger.info("No GitHub token in config. GitHub API operations will use git CLI only.")

    def is_authenticated(self) -> bool:
        """Check if GitHub client is authenticated."""
        return self.github_client is not None

    async def list_repositories(self) -> List[Dict[str, Any]]:
        """List user's GitHub repositories.
        
        Returns:
            List of repository information dicts
        """
        if not self.is_authenticated():
            return []
        
        try:
            user = self.github_client.get_user()
            repos = []
            for repo in user.get_repos():
                repos.append({
                    'name': repo.name,
                    'full_name': repo.full_name,
                    'url': repo.html_url,
                    'clone_url': repo.clone_url,
                    'private': repo.private,
                    'description': repo.description or '',
                    'updated_at': repo.updated_at.isoformat() if repo.updated_at else None
                })
            return repos
        except Exception as e:
            logger.error(f"Error listing repositories: {e}")
            return []

    async def create_repository(self, repo_name: str, description: str = "", private: bool = False) -> Dict[str, Any]:
        """Create a new GitHub repository.
        
        Args:
            repo_name: Name of the repository
            description: Repository description
            private: Whether to make the repository private
            
        Returns:
            Dictionary with repository info or error
        """
        if not self.is_authenticated():
            return {'success': False, 'error': 'Not authenticated with GitHub'}
        
        try:
            user = self.github_client.get_user()
            repo = user.create_repo(
                name=repo_name,
                description=description,
                private=private,
                auto_init=False  # Don't auto-initialize, we'll push from local
            )
            logger.info(f"Created GitHub repository: {repo.full_name}")
            return {
                'success': True,
                'name': repo.name,
                'full_name': repo.full_name,
                'url': repo.html_url,
                'clone_url': repo.clone_url
            }
        except Exception as e:
            logger.error(f"Error creating repository: {e}")
            return {'success': False, 'error': str(e)}

    async def clone_repository(self, repo_url: str, target_dir: str) -> Dict[str, Any]:
        """Clone a GitHub repository.
        
        Args:
            repo_url: URL of repository to clone
            target_dir: Directory to clone into
            
        Returns:
            Dictionary with success status and message
        """
        try:
            # Ensure target directory exists
            os.makedirs(os.path.dirname(target_dir), exist_ok=True)
            
            # Execute git clone
            result = subprocess.run(
                ['git', 'clone', repo_url, target_dir],
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout for cloning
            )
            
            if result.returncode == 0:
                logger.info(f"Successfully cloned {repo_url} to {target_dir}")
                return {
                    'success': True,
                    'message': f'Repository cloned to {target_dir}',
                    'output': result.stdout
                }
            else:
                logger.error(f"Failed to clone repository: {result.stderr}")
                return {
                    'success': False,
                    'error': result.stderr,
                    'output': result.stdout
                }
        except subprocess.TimeoutExpired:
            return {'success': False, 'error': 'Clone operation timed out'}
        except Exception as e:
            logger.error(f"Error cloning repository: {e}")
            return {'success': False, 'error': str(e)}

    async def git_init(self, directory: str) -> Dict[str, Any]:
        """Initialize a git repository.
        
        Args:
            directory: Directory to initialize git in
            
        Returns:
            Dictionary with success status and message
        """
        try:
            result = subprocess.run(
                ['git', 'init'],
                cwd=directory,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                logger.info(f"Initialized git repository in {directory}")
                return {
                    'success': True,
                    'message': 'Git repository initialized',
                    'output': result.stdout
                }
            else:
                return {'success': False, 'error': result.stderr}
        except Exception as e:
            logger.error(f"Error initializing git: {e}")
            return {'success': False, 'error': str(e)}

    async def git_status(self, directory: str) -> Dict[str, Any]:
        """Get git status for a directory.
        
        Args:
            directory: Directory to check git status
            
        Returns:
            Dictionary with git status info
        """
        try:
            result = subprocess.run(
                ['git', 'status', '--porcelain'],
                cwd=directory,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                return {
                    'success': True,
                    'clean': len(result.stdout.strip()) == 0,
                    'output': result.stdout,
                    'has_changes': len(result.stdout.strip()) > 0
                }
            else:
                return {'success': False, 'error': result.stderr}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    async def git_add_commit(self, directory: str, commit_message: str, files: str = ".") -> Dict[str, Any]:
        """Add files and commit changes.
        
        Args:
            directory: Directory to commit in
            commit_message: Commit message
            files: Files to add (default: all files ".")
            
        Returns:
            Dictionary with success status and message
        """
        try:
            # Add files
            add_result = subprocess.run(
                ['git', 'add', files],
                cwd=directory,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if add_result.returncode != 0:
                return {'success': False, 'error': f"Git add failed: {add_result.stderr}"}
            
            # Commit
            commit_result = subprocess.run(
                ['git', 'commit', '-m', commit_message],
                cwd=directory,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if commit_result.returncode == 0:
                logger.info(f"Committed changes in {directory}: {commit_message}")
                return {
                    'success': True,
                    'message': 'Changes committed',
                    'output': commit_result.stdout
                }
            else:
                # Check if it's because there's nothing to commit
                if "nothing to commit" in commit_result.stdout.lower():
                    return {
                        'success': True,
                        'message': 'Nothing to commit, working tree clean',
                        'output': commit_result.stdout
                    }
                return {'success': False, 'error': commit_result.stderr}
        except Exception as e:
            logger.error(f"Error committing changes: {e}")
            return {'success': False, 'error': str(e)}

    async def git_push(self, directory: str, branch: str = "main", force: bool = False) -> Dict[str, Any]:
        """Push commits to remote repository.
        
        Args:
            directory: Directory to push from
            branch: Branch to push
            force: Whether to force push
            
        Returns:
            Dictionary with success status and message
        """
        try:
            # Check if remote exists
            remote_result = subprocess.run(
                ['git', 'remote', '-v'],
                cwd=directory,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if not remote_result.stdout.strip():
                return {'success': False, 'error': 'No remote repository configured'}
            
            # Build push command
            push_cmd = ['git', 'push']
            if force:
                push_cmd.append('--force')
            push_cmd.extend(['origin', branch])
            
            # Execute push
            result = subprocess.run(
                push_cmd,
                cwd=directory,
                capture_output=True,
                text=True,
                timeout=120  # 2 minute timeout for push
            )
            
            if result.returncode == 0:
                logger.info(f"Pushed to {branch} in {directory}")
                return {
                    'success': True,
                    'message': f'Pushed to {branch}',
                    'output': result.stderr  # Git push outputs to stderr
                }
            else:
                return {'success': False, 'error': result.stderr}
        except subprocess.TimeoutExpired:
            return {'success': False, 'error': 'Push operation timed out'}
        except Exception as e:
            logger.error(f"Error pushing to remote: {e}")
            return {'success': False, 'error': str(e)}

    async def git_pull(self, directory: str, branch: str = "main") -> Dict[str, Any]:
        """Pull changes from remote repository.
        
        Args:
            directory: Directory to pull into
            branch: Branch to pull
            
        Returns:
            Dictionary with success status and message
        """
        try:
            result = subprocess.run(
                ['git', 'pull', 'origin', branch],
                cwd=directory,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode == 0:
                logger.info(f"Pulled from {branch} in {directory}")
                return {
                    'success': True,
                    'message': f'Pulled from {branch}',
                    'output': result.stdout
                }
            else:
                return {'success': False, 'error': result.stderr}
        except Exception as e:
            logger.error(f"Error pulling from remote: {e}")
            return {'success': False, 'error': str(e)}

    async def add_remote(self, directory: str, remote_url: str, remote_name: str = "origin") -> Dict[str, Any]:
        """Add a remote repository.
        
        Args:
            directory: Directory to add remote to
            remote_url: URL of remote repository
            remote_name: Name for the remote (default: origin)
            
        Returns:
            Dictionary with success status and message
        """
        try:
            result = subprocess.run(
                ['git', 'remote', 'add', remote_name, remote_url],
                cwd=directory,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                logger.info(f"Added remote {remote_name}: {remote_url}")
                return {
                    'success': True,
                    'message': f'Remote {remote_name} added',
                    'output': result.stdout
                }
            else:
                return {'success': False, 'error': result.stderr}
        except Exception as e:
            logger.error(f"Error adding remote: {e}")
            return {'success': False, 'error': str(e)}

    async def get_current_branch(self, directory: str) -> Optional[str]:
        """Get the current git branch.
        
        Args:
            directory: Directory to check
            
        Returns:
            Branch name or None if error
        """
        try:
            result = subprocess.run(
                ['git', 'branch', '--show-current'],
                cwd=directory,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                return result.stdout.strip()
            return None
        except Exception as e:
            logger.error(f"Error getting current branch: {e}")
            return None

    def is_git_repository(self, directory: str) -> bool:
        """Check if a directory is a git repository.
        
        Args:
            directory: Directory to check
            
        Returns:
            True if directory is a git repository
        """
        git_dir = Path(directory) / '.git'
        return git_dir.exists() and git_dir.is_dir()
