"""Memory Manager for TARS - The Sovereign Agent.

Handles the "Soul" (MEMORY.md) and episodic memory (Daily Logs).
"""
import os
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

class MemoryManager:
    """Manages persistent memory and episodic logs."""
    
    def __init__(self, base_path: str = "memory"):
        self.base_path = Path(base_path)
        self.logs_path = self.base_path / "logs"
        self.memory_file = self.base_path / "MEMORY.md"
        
        self._ensure_paths()
        
    def _ensure_paths(self):
        """Ensure memory directories exist."""
        self.logs_path.mkdir(parents=True, exist_ok=True)
        
        if not self.memory_file.exists():
            self._init_memory_file()
            
    def _init_memory_file(self):
        """Initialize empty MEMORY.md."""
        header = """# TARS MEMORY CORE
This file contains your long-term memory and identity ("The Soul").
It is a curated collection of facts, preferences, and important context about your user (Máté).

## Identity
- Name: TARS
- Role: Personal Assistant
- User: Máté Dort

## Core Directives
1. Be helpful and proactive.
2. Maintain the established personality.

## User Preferences
- [Learned preferences will be stored here]

## Project Context
- [Active project details will be stored here]
"""
        with open(self.memory_file, 'w', encoding='utf-8') as f:
            f.write(header)
            
    def get_soul(self) -> str:
        """Retrieve the content of MEMORY.md (The Soul)."""
        try:
            with open(self.memory_file, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except Exception as e:
            logger.error(f"Failed to read MEMORY.md: {e}")
            return "Error reading memory core."

    def get_daily_log_path(self, date: Optional[datetime] = None) -> Path:
        """Get the path for a specific daily log."""
        if date is None:
            date = datetime.now()
        filename = date.strftime("%Y-%m-%d.md")
        return self.logs_path / filename

    def append_to_log(self, content: str, role: str = "system"):
        """Append an entry to the daily log."""
        try:
            log_path = self.get_daily_log_path()
            timestamp = datetime.now().strftime("%H:%M:%S")
            
            entry = f"\n\n### [{timestamp}] {role.upper()}\n{content}"
            
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(entry)
                
        except Exception as e:
            logger.error(f"Failed to write to daily log: {e}")

    def update_soul(self, content: str):
        """Overwrite MEMORY.md with new content (e.g., after manual consolidation)."""
        try:
            with open(self.memory_file, 'w', encoding='utf-8') as f:
                f.write(content)
            logger.info("Memory Core (Soul) updated.")
        except Exception as e:
            logger.error(f"Failed to update MEMORY.md: {e}")

    def add_memory_fragment(self, category: str, text: str):
        """Append a specific fact to the MEMORY.md file under a category (simple version)."""
        # This is a naive implementation; a smarter one would parse the markdown structure.
        # For now, we just append to the file.
        try:
            current_content = self.get_soul()
            new_entry = f"\n- [{category.upper()}] {text}"
            
            with open(self.memory_file, 'a', encoding='utf-8') as f:
                f.write(new_entry)
        except Exception as e:
            logger.error(f"Failed to add memory fragment: {e}")

# Global instance
memory_manager = MemoryManager()
