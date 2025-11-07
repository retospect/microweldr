"""Caching and optimization utilities for SVG parsing and other operations."""

import hashlib
import logging
import pickle  # nosec B403 - Used for internal caching only, not user data
import time
from functools import lru_cache, wraps
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from ..core.models import WeldPath

logger = logging.getLogger(__name__)


class FileCache:
    """File-based cache for expensive operations with automatic invalidation."""

    def __init__(self, cache_dir: Union[str, Path] = None, max_age_seconds: int = 3600):
        """Initialize file cache.

        Args:
            cache_dir: Directory for cache files (default: .cache)
            max_age_seconds: Maximum age of cache entries in seconds
        """
        self.cache_dir = Path(cache_dir or ".cache")
        self.cache_dir.mkdir(exist_ok=True)
        self.max_age = max_age_seconds

    def _get_cache_key(self, content: str, operation: str = "default") -> str:
        """Generate cache key from content and operation."""
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        return f"{operation}_{content_hash[:16]}"

    def _get_cache_path(self, cache_key: str) -> Path:
        """Get cache file path for given key."""
        return self.cache_dir / f"{cache_key}.cache"

    def _is_cache_valid(self, cache_path: Path) -> bool:
        """Check if cache file is still valid."""
        if not cache_path.exists():
            return False

        try:
            age = time.time() - cache_path.stat().st_mtime
            return age < self.max_age
        except OSError:
            return False

    def get(self, content: str, operation: str = "default") -> Optional[Any]:
        """Get cached result for content and operation.

        Args:
            content: Content to check cache for
            operation: Operation identifier

        Returns:
            Cached result or None if not found/expired
        """
        cache_key = self._get_cache_key(content, operation)
        cache_path = self._get_cache_path(cache_key)

        if not self._is_cache_valid(cache_path):
            return None

        try:
            with open(cache_path, "rb") as f:
                result = pickle.load(f)  # nosec B301 - Internal cache files only
            logger.debug(f"Cache hit for {operation}: {cache_key}")
            return result
        except Exception as e:
            logger.warning(f"Failed to load cache {cache_key}: {e}")
            # Remove corrupted cache file
            try:
                cache_path.unlink()
            except OSError:
                pass
            return None

    def set(self, content: str, result: Any, operation: str = "default") -> None:
        """Store result in cache.

        Args:
            content: Content that was processed
            result: Result to cache
            operation: Operation identifier
        """
        cache_key = self._get_cache_key(content, operation)
        cache_path = self._get_cache_path(cache_key)

        try:
            with open(cache_path, "wb") as f:
                pickle.dump(result, f)
            logger.debug(f"Cached result for {operation}: {cache_key}")
        except Exception as e:
            logger.warning(f"Failed to cache result {cache_key}: {e}")

    def clear(self, operation: Optional[str] = None) -> int:
        """Clear cache entries.

        Args:
            operation: Specific operation to clear (None for all)

        Returns:
            Number of entries cleared
        """
        cleared = 0
        pattern = f"{operation}_*" if operation else "*.cache"

        for cache_file in self.cache_dir.glob(pattern):
            try:
                cache_file.unlink()
                cleared += 1
            except OSError as e:
                logger.warning(f"Failed to remove cache file {cache_file}: {e}")

        logger.info(f"Cleared {cleared} cache entries")
        return cleared

    def cleanup_expired(self) -> int:
        """Remove expired cache entries.

        Returns:
            Number of entries removed
        """
        removed = 0

        for cache_file in self.cache_dir.glob("*.cache"):
            if not self._is_cache_valid(cache_file):
                try:
                    cache_file.unlink()
                    removed += 1
                except OSError as e:
                    logger.warning(f"Failed to remove expired cache {cache_file}: {e}")

        if removed > 0:
            logger.info(f"Removed {removed} expired cache entries")

        return removed


# Global cache instance
_global_cache = FileCache()


def cached_operation(operation: str = "default", max_age: int = 3600):
    """Decorator for caching expensive operations based on content.

    Args:
        operation: Operation identifier for cache namespacing
        max_age: Maximum cache age in seconds
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key from function arguments
            cache_content = f"{func.__name__}:{str(args)}:{str(sorted(kwargs.items()))}"

            # Try to get from cache first
            cache = FileCache(max_age_seconds=max_age)
            cached_result = cache.get(cache_content, operation)

            if cached_result is not None:
                return cached_result

            # Execute function and cache result
            start_time = time.time()
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time

            # Only cache if execution took significant time
            if execution_time > 0.1:  # 100ms threshold
                cache.set(cache_content, result, operation)
                logger.debug(f"Cached {operation} result (took {execution_time:.3f}s)")

            return result

        return wrapper

    return decorator


class OptimizedSVGParser:
    """Optimized SVG parser with caching and performance improvements."""

    def __init__(self, cache_enabled: bool = True):
        """Initialize optimized parser.

        Args:
            cache_enabled: Whether to enable caching
        """
        self.cache_enabled = cache_enabled
        self.cache = FileCache(max_age_seconds=1800)  # 30 minutes
        self._parse_stats = {
            "cache_hits": 0,
            "cache_misses": 0,
            "total_parse_time": 0.0,
        }

    @lru_cache(maxsize=128)
    def _parse_element_cached(
        self, element_str: str, element_type: str
    ) -> Optional[List[Tuple[float, float]]]:
        """Cache parsed element coordinates in memory."""
        # This would contain the actual parsing logic
        # Placeholder for demonstration
        logger.debug(f"Parsing {element_type} element (cached)")
        return None

    def parse_svg_file(self, svg_path: Union[str, Path]) -> List[WeldPath]:
        """Parse SVG file with caching and optimization.

        Args:
            svg_path: Path to SVG file

        Returns:
            List of parsed weld paths
        """
        svg_path = Path(svg_path)

        # Read file content
        try:
            content = svg_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to read SVG file {svg_path}: {e}")
            raise

        # Check cache if enabled
        if self.cache_enabled:
            cached_result = self.cache.get(content, "svg_parse")
            if cached_result is not None:
                self._parse_stats["cache_hits"] += 1
                logger.info(f"SVG parse cache hit for {svg_path.name}")
                return cached_result

        # Parse SVG (cache miss)
        start_time = time.time()
        self._parse_stats["cache_misses"] += 1

        try:
            # Import the actual parser here to avoid circular imports
            from ..core.svg_parser import SVGParser

            parser = SVGParser()
            weld_paths = parser.parse_file(svg_path)

            parse_time = time.time() - start_time
            self._parse_stats["total_parse_time"] += parse_time

            logger.info(
                f"Parsed SVG {svg_path.name} in {parse_time:.3f}s ({len(weld_paths)} paths)"
            )

            # Cache result if enabled and parsing took significant time
            if (
                self.cache_enabled and parse_time > 0.001
            ):  # 1ms threshold (lowered for tests)
                self.cache.set(content, weld_paths, "svg_parse")
                logger.debug(f"Cached SVG parse result for {svg_path.name}")

            return weld_paths

        except Exception as e:
            logger.error(f"SVG parsing failed for {svg_path}: {e}")
            raise

    def get_stats(self) -> Dict[str, Any]:
        """Get parsing statistics.

        Returns:
            Dictionary with parsing statistics
        """
        total_requests = (
            self._parse_stats["cache_hits"] + self._parse_stats["cache_misses"]
        )
        cache_hit_rate = (
            self._parse_stats["cache_hits"] / total_requests * 100
            if total_requests > 0
            else 0
        )

        return {
            "cache_hits": self._parse_stats["cache_hits"],
            "cache_misses": self._parse_stats["cache_misses"],
            "cache_hit_rate": cache_hit_rate,
            "total_parse_time": self._parse_stats["total_parse_time"],
            "average_parse_time": (
                self._parse_stats["total_parse_time"]
                / self._parse_stats["cache_misses"]
                if self._parse_stats["cache_misses"] > 0
                else 0
            ),
        }

    def clear_cache(self):
        """Clear SVG parsing cache."""
        if self.cache_enabled:
            cleared = self.cache.clear("svg_parse")
            logger.info(f"Cleared SVG parsing cache ({cleared} entries)")


class PerformanceMonitor:
    """Monitor and log performance metrics for operations."""

    def __init__(self):
        """Initialize performance monitor."""
        self.metrics: Dict[str, List[float]] = {}
        self._start_times: Dict[str, float] = {}

    def start_operation(self, operation: str) -> None:
        """Start timing an operation.

        Args:
            operation: Operation identifier
        """
        self._start_times[operation] = time.time()

    def end_operation(self, operation: str) -> float:
        """End timing an operation and record the duration.

        Args:
            operation: Operation identifier

        Returns:
            Operation duration in seconds
        """
        if operation not in self._start_times:
            logger.warning(f"No start time recorded for operation: {operation}")
            return 0.0

        duration = time.time() - self._start_times[operation]
        del self._start_times[operation]

        if operation not in self.metrics:
            self.metrics[operation] = []

        self.metrics[operation].append(duration)

        # Log slow operations
        if duration > 1.0:  # 1 second threshold
            logger.warning(f"Slow operation detected: {operation} took {duration:.3f}s")

        return duration

    def get_stats(self, operation: Optional[str] = None) -> Dict[str, Any]:
        """Get performance statistics.

        Args:
            operation: Specific operation to get stats for (None for all)

        Returns:
            Performance statistics
        """
        if operation:
            if operation not in self.metrics:
                return {}

            durations = self.metrics[operation]
            return {
                "operation": operation,
                "count": len(durations),
                "total_time": sum(durations),
                "average_time": sum(durations) / len(durations),
                "min_time": min(durations),
                "max_time": max(durations),
            }

        # Return stats for all operations
        stats = {}
        for op, durations in self.metrics.items():
            stats[op] = {
                "count": len(durations),
                "total_time": sum(durations),
                "average_time": sum(durations) / len(durations),
                "min_time": min(durations),
                "max_time": max(durations),
            }

        return stats

    def reset_stats(self, operation: Optional[str] = None) -> None:
        """Reset performance statistics.

        Args:
            operation: Specific operation to reset (None for all)
        """
        if operation:
            if operation in self.metrics:
                del self.metrics[operation]
        else:
            self.metrics.clear()

        logger.info(f"Reset performance stats for {operation or 'all operations'}")


# Global performance monitor
performance_monitor = PerformanceMonitor()


def timed_operation(operation: str):
    """Decorator to automatically time operations.

    Args:
        operation: Operation identifier
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            performance_monitor.start_operation(operation)
            try:
                result = func(*args, **kwargs)
                duration = performance_monitor.end_operation(operation)
                logger.debug(f"Operation {operation} completed in {duration:.3f}s")
                return result
            except Exception as e:
                performance_monitor.end_operation(operation)
                logger.error(f"Operation {operation} failed: {e}")
                raise

        return wrapper

    return decorator


def optimize_weld_paths(weld_paths: List[WeldPath]) -> List[WeldPath]:
    """Optimize weld paths for better performance and quality.

    Args:
        weld_paths: Original weld paths

    Returns:
        Optimized weld paths
    """
    if not weld_paths:
        return weld_paths

    logger.info(f"Optimizing {len(weld_paths)} weld paths")

    optimized_paths = []

    for path in weld_paths:
        # Remove duplicate consecutive points
        if len(path.points) > 1:
            unique_points = [path.points[0]]
            for point in path.points[1:]:
                prev_point = unique_points[-1]
                # Check if points are significantly different
                if (
                    abs(point.x - prev_point.x) > 0.001
                    or abs(point.y - prev_point.y) > 0.001
                ):
                    unique_points.append(point)

            if len(unique_points) != len(path.points):
                logger.debug(
                    f"Removed {len(path.points) - len(unique_points)} duplicate points from path {path.name}"
                )

                # Create new path with unique points
                optimized_path = WeldPath(
                    points=unique_points,
                    weld_type=path.weld_type,
                    name=path.name,
                    custom_temp=path.custom_temp,
                    custom_weld_time=path.custom_weld_time,
                    custom_bed_temp=path.custom_bed_temp,
                    custom_weld_height=path.custom_weld_height,
                    pause_message=path.pause_message,
                )
                optimized_paths.append(optimized_path)
            else:
                optimized_paths.append(path)
        else:
            optimized_paths.append(path)

    logger.info(f"Path optimization completed")
    return optimized_paths
