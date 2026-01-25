"""Task planning layer for ordering function calls before execution."""
import logging
from typing import List, Dict, Any, Set
from collections import defaultdict, deque

logger = logging.getLogger(__name__)


class TaskPlanner:
    """Analyzes and orders function calls for optimal execution."""

    def __init__(self):
        """Initialize task planner."""
        # Define function dependencies and categories
        self.function_categories = {
            "database_query": ["lookup_contact", "search_conversations", "manage_reminder"],
            "lookup": ["lookup_contact"],
            "action": ["make_goal_call", "adjust_config", "manage_reminder"],
            "communication": ["send_to_n8n", "send_message_to_session"],
            "notification": ["send_notification", "request_user_confirmation"],
        }
        
        # Define execution order priority (lower number = higher priority)
        self.priority_order = {
            "database_query": 1,
            "lookup": 2,
            "action": 3,
            "notification": 4,
            "communication": 5,
        }
        
        # Define explicit dependencies (function_name -> list of required functions)
        self.dependencies = {
            "send_to_n8n": ["lookup_contact"],  # May need contact info before sending
            "make_goal_call": ["lookup_contact"],  # Need contact info before calling
        }

    def plan_tasks(self, function_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Plan and order function calls for optimal execution.

        Args:
            function_calls: List of function call dictionaries with 'name' and 'args'

        Returns:
            Ordered list of function calls
        """
        if not function_calls or len(function_calls) == 1:
            return function_calls

        logger.info(f"Planning {len(function_calls)} function calls")

        # Build dependency graph
        function_names = [call.get("name") for call in function_calls]
        ordered_calls = self._topological_sort(function_calls, function_names)

        logger.info(f"Planned execution order: {[call.get('name') for call in ordered_calls]}")
        return ordered_calls

    def _topological_sort(
        self, function_calls: List[Dict[str, Any]], function_names: List[str]
    ) -> List[Dict[str, Any]]:
        """Sort function calls using topological sort based on dependencies.

        Args:
            function_calls: List of function call dictionaries
            function_names: List of function names

        Returns:
            Topologically sorted list of function calls
        """
        # Create a mapping of function name to call
        call_map = {call.get("name"): call for call in function_calls}

        # Build dependency graph
        graph = defaultdict(list)
        in_degree = defaultdict(int)

        for func_name in function_names:
            in_degree[func_name] = 0

        # Add edges based on dependencies
        for func_name in function_names:
            if func_name in self.dependencies:
                for dep in self.dependencies[func_name]:
                    if dep in function_names:
                        graph[dep].append(func_name)
                        in_degree[func_name] += 1

        # Also consider category-based ordering
        for i, func_name in enumerate(function_names):
            func_category = self._get_category(func_name)
            for j, other_func in enumerate(function_names):
                if i != j:
                    other_category = self._get_category(other_func)
                    if self.priority_order.get(func_category, 99) < self.priority_order.get(
                        other_category, 99
                    ):
                        # func_name should come before other_func
                        if other_func not in graph[func_name]:
                            graph[func_name].append(other_func)
                            in_degree[other_func] += 1

        # Topological sort using Kahn's algorithm
        queue = deque([func for func in function_names if in_degree[func] == 0])
        result = []

        while queue:
            # Sort queue by priority for deterministic ordering
            queue = deque(
                sorted(
                    queue,
                    key=lambda x: self.priority_order.get(self._get_category(x), 99),
                )
            )
            current = queue.popleft()
            result.append(call_map[current])

            for neighbor in graph[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # Add any remaining functions (shouldn't happen in a DAG, but handle cycles)
        remaining = [call for call in function_calls if call not in result]
        if remaining:
            logger.warning(f"Found {len(remaining)} functions not in dependency graph, appending")
            result.extend(remaining)

        return result

    def _get_category(self, function_name: str) -> str:
        """Get category for a function name.

        Args:
            function_name: Name of the function

        Returns:
            Category name
        """
        for category, functions in self.function_categories.items():
            if function_name in functions:
                return category

        # Default categories based on function name patterns
        if "lookup" in function_name or "search" in function_name:
            return "lookup"
        elif "send" in function_name or "message" in function_name:
            return "communication"
        elif "call" in function_name:
            return "action"
        else:
            return "action"  # Default
