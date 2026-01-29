"""Verification engine for autonomous programming tasks."""
import asyncio
import json
import logging
import subprocess
from pathlib import Path
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class VerificationEngine:
    """Auto-detects and runs project tests."""
    
    def __init__(self, project_path: str):
        """Initialize verification engine.
        
        Args:
            project_path: Root directory of the project
        """
        self.project_path = Path(project_path)
        self.test_commands = self.detect_test_framework()
        
        logger.info(f"VerificationEngine initialized with commands: {self.test_commands}")
    
    def detect_test_framework(self) -> List[str]:
        """Auto-detect test commands from project files.
        
        Returns:
            List of test commands to run
        """
        commands = []
        
        # Check for Node.js/JavaScript projects
        package_json = self.project_path / "package.json"
        if package_json.exists():
            try:
                package_data = json.loads(package_json.read_text())
                scripts = package_data.get("scripts", {})
                
                # Check for test script
                if "test" in scripts:
                    test_cmd = scripts["test"]
                    # Avoid infinite loops - don't run if test script just echoes error
                    if "no test specified" not in test_cmd.lower() and "exit 1" not in test_cmd:
                        commands.append("npm test")
                        logger.info("Detected npm test")
                
                # Check for specific test runners
                if "jest" in scripts.get("test", ""):
                    commands.append("npm run test")
                    logger.info("Detected Jest tests")
                elif "vitest" in scripts.get("test", ""):
                    commands.append("npm run test")
                    logger.info("Detected Vitest tests")
                
                # Check for type checking
                if "type-check" in scripts:
                    commands.append("npm run type-check")
                    logger.info("Detected TypeScript type checking")
                
                # Check for linting
                if "lint" in scripts:
                    commands.append("npm run lint")
                    logger.info("Detected linting")
                    
            except Exception as e:
                logger.warning(f"Could not parse package.json: {e}")
        
        # Check for Python projects
        if (self.project_path / "pytest.ini").exists() or \
           (self.project_path / "setup.py").exists() or \
           (self.project_path / "pyproject.toml").exists():
            
            # Check if pytest is likely installed
            if (self.project_path / "pytest.ini").exists():
                commands.append("pytest")
                logger.info("Detected pytest")
            elif any(self.project_path.glob("test_*.py")) or \
                 any(self.project_path.glob("tests/")):
                commands.append("python -m pytest")
                logger.info("Detected Python tests, using pytest")
            
            # Check for type checking with mypy
            if (self.project_path / "mypy.ini").exists() or \
               (self.project_path / ".mypy.ini").exists():
                commands.append("mypy .")
                logger.info("Detected mypy type checking")
        
        # Check for Rust projects
        if (self.project_path / "Cargo.toml").exists():
            commands.append("cargo test")
            commands.append("cargo clippy -- -D warnings")
            logger.info("Detected Rust project")
        
        # Check for Go projects
        if (self.project_path / "go.mod").exists():
            commands.append("go test ./...")
            logger.info("Detected Go project")
        
        # If no tests found, return a placeholder
        if not commands:
            logger.info("No test framework detected")
            commands.append("echo 'No tests configured'")
        
        return commands
    
    async def run_verification(self) -> Dict[str, Any]:
        """Run all detected test commands.
        
        Returns:
            Dictionary with verification results:
            {
                'all_passed': bool,
                'results': {
                    'command': {
                        'passed': bool,
                        'output': str,
                        'exit_code': int
                    }
                }
            }
        """
        results = {}
        
        for cmd in self.test_commands:
            logger.info(f"Running verification: {cmd}")
            
            try:
                result = subprocess.run(
                    cmd,
                    shell=True,
                    cwd=str(self.project_path),
                    capture_output=True,
                    text=True,
                    timeout=120  # 2 minute timeout per command
                )
                
                passed = result.returncode == 0
                output = result.stdout + result.stderr
                
                # Truncate very long output
                if len(output) > 5000:
                    output = output[:2500] + "\n\n... (truncated) ...\n\n" + output[-2500:]
                
                results[cmd] = {
                    'passed': passed,
                    'output': output,
                    'exit_code': result.returncode
                }
                
                logger.info(f"Command '{cmd}' {'passed' if passed else 'failed'} (exit code: {result.returncode})")
                
            except subprocess.TimeoutExpired:
                logger.warning(f"Command '{cmd}' timed out after 120s")
                results[cmd] = {
                    'passed': False,
                    'output': "Test command timed out after 120 seconds",
                    'exit_code': -1
                }
            except Exception as e:
                logger.error(f"Error running command '{cmd}': {e}")
                results[cmd] = {
                    'passed': False,
                    'output': f"Error running test: {str(e)}",
                    'exit_code': -1
                }
        
        # Determine overall status
        all_passed = all(r['passed'] for r in results.values())
        
        return {
            'all_passed': all_passed,
            'results': results,
            'summary': self._generate_summary(results)
        }
    
    def _generate_summary(self, results: Dict[str, Any]) -> str:
        """Generate human-readable summary of test results.
        
        Args:
            results: Test results dictionary
            
        Returns:
            Summary string
        """
        total = len(results)
        passed = sum(1 for r in results.values() if r['passed'])
        failed = total - passed
        
        summary_parts = [
            f"Tests: {passed}/{total} passed"
        ]
        
        if failed > 0:
            summary_parts.append(f"\nFailed commands:")
            for cmd, result in results.items():
                if not result['passed']:
                    # Extract key error info
                    output = result['output']
                    error_lines = [line for line in output.split('\n') if 'error' in line.lower() or 'failed' in line.lower()]
                    error_sample = '\n'.join(error_lines[:5]) if error_lines else output[:200]
                    
                    summary_parts.append(f"  - {cmd}")
                    summary_parts.append(f"    {error_sample}")
        
        return '\n'.join(summary_parts)
    
    async def quick_syntax_check(self) -> Dict[str, Any]:
        """Run quick syntax/type checks without full test execution.
        
        This is faster than running full tests and can catch obvious errors.
        
        Returns:
            Dictionary with syntax check results
        """
        results = {}
        
        # TypeScript/JavaScript type checking
        if (self.project_path / "tsconfig.json").exists():
            try:
                result = subprocess.run(
                    "npx tsc --noEmit",
                    shell=True,
                    cwd=str(self.project_path),
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                results['typescript'] = {
                    'passed': result.returncode == 0,
                    'output': result.stdout + result.stderr
                }
            except Exception as e:
                logger.warning(f"TypeScript check failed: {e}")
        
        # Python syntax check
        python_files = list(self.project_path.rglob("*.py"))
        if python_files:
            try:
                result = subprocess.run(
                    f"python -m py_compile {' '.join(str(f) for f in python_files[:10])}",
                    shell=True,
                    cwd=str(self.project_path),
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                results['python_syntax'] = {
                    'passed': result.returncode == 0,
                    'output': result.stderr if result.returncode != 0 else "OK"
                }
            except Exception as e:
                logger.warning(f"Python syntax check failed: {e}")
        
        return {
            'all_passed': all(r.get('passed', False) for r in results.values()),
            'results': results
        }
