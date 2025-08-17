"""Intelligent Model Caching with LRU eviction and predictive pre-loading."""

import time
import json
import logging
import asyncio
from pathlib import Path
from typing import Dict, Optional, List, Tuple, Any
from datetime import datetime, timedelta
from collections import OrderedDict
from dataclasses import dataclass, asdict
import threading
import pickle

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Represents a cached model entry."""
    model_id: str
    provider: str
    size_gb: float
    last_accessed: float
    access_count: int
    load_time_ms: float
    path: str
    metadata: Dict[str, Any]


@dataclass
class UsagePattern:
    """Tracks model usage patterns for predictive loading."""
    model_id: str
    hour_histogram: List[int]  # 24 hours
    day_histogram: List[int]   # 7 days
    total_requests: int
    avg_daily_requests: float
    peak_hour: int
    peak_day: int


class ModelCacheManager:
    """Manages model caching with LRU eviction and predictive pre-loading."""
    
    def __init__(self, nvme_path: str, max_cache_size_gb: int = 500, 
                 target_free_space_percent: float = 0.2):
        """Initialize the cache manager.
        
        Args:
            nvme_path: Base path for NVMe storage
            max_cache_size_gb: Maximum cache size in GB
            target_free_space_percent: Target free space (0.2 = 20%)
        """
        self.nvme_path = Path(nvme_path)
        self.cache_dir = self.nvme_path / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.max_cache_size_gb = max_cache_size_gb
        self.target_free_space_percent = target_free_space_percent
        
        # LRU cache (most recently used at the end)
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._cache_lock = threading.RLock()
        
        # Usage patterns for predictive loading
        self._usage_patterns: Dict[str, UsagePattern] = {}
        self._pattern_file = self.cache_dir / "usage_patterns.pkl"
        
        # Load existing cache metadata and patterns
        self._load_cache_metadata()
        self._load_usage_patterns()
        
        # Start background tasks
        self._start_background_tasks()
    
    def _load_cache_metadata(self):
        """Load cache metadata from disk."""
        metadata_file = self.cache_dir / "cache_metadata.json"
        if metadata_file.exists():
            try:
                with open(metadata_file, 'r') as f:
                    data = json.load(f)
                    for entry_data in data.get('entries', []):
                        entry = CacheEntry(**entry_data)
                        # Verify the model still exists on disk
                        if Path(entry.path).exists():
                            self._cache[entry.model_id] = entry
                logger.info(f"Loaded {len(self._cache)} cached models")
            except Exception as e:
                logger.error(f"Failed to load cache metadata: {e}")
    
    def _save_cache_metadata(self):
        """Save cache metadata to disk."""
        metadata_file = self.cache_dir / "cache_metadata.json"
        try:
            with self._cache_lock:
                entries = [asdict(entry) for entry in self._cache.values()]
            
            with open(metadata_file, 'w') as f:
                json.dump({'entries': entries, 'timestamp': time.time()}, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save cache metadata: {e}")
    
    def _load_usage_patterns(self):
        """Load usage patterns from disk."""
        if self._pattern_file.exists():
            try:
                with open(self._pattern_file, 'rb') as f:
                    self._usage_patterns = pickle.load(f)
                logger.info(f"Loaded usage patterns for {len(self._usage_patterns)} models")
            except Exception as e:
                logger.error(f"Failed to load usage patterns: {e}")
    
    def _save_usage_patterns(self):
        """Save usage patterns to disk."""
        try:
            with open(self._pattern_file, 'wb') as f:
                pickle.dump(self._usage_patterns, f)
        except Exception as e:
            logger.error(f"Failed to save usage patterns: {e}")
    
    def _start_background_tasks(self):
        """Start background tasks for cache management."""
        # Start eviction monitor
        threading.Thread(target=self._eviction_monitor, daemon=True).start()
        
        # Start predictive pre-loader
        threading.Thread(target=self._predictive_preloader, daemon=True).start()
        
        # Start metadata persister
        threading.Thread(target=self._metadata_persister, daemon=True).start()
    
    def _eviction_monitor(self):
        """Monitor cache size and evict if necessary."""
        while True:
            try:
                time.sleep(60)  # Check every minute
                self._check_and_evict()
            except Exception as e:
                logger.error(f"Eviction monitor error: {e}")
    
    def _check_and_evict(self):
        """Check cache size and evict LRU models if needed."""
        with self._cache_lock:
            total_size_gb = sum(entry.size_gb for entry in self._cache.values())
            
            # Calculate target size based on free space requirement
            target_size_gb = self.max_cache_size_gb * (1 - self.target_free_space_percent)
            
            if total_size_gb > target_size_gb:
                logger.info(f"Cache size {total_size_gb:.1f}GB exceeds target {target_size_gb:.1f}GB, evicting...")
                
                # Sort by last accessed time (LRU)
                sorted_entries = sorted(self._cache.items(), 
                                       key=lambda x: x[1].last_accessed)
                
                evicted_size = 0
                evicted_models = []
                
                for model_id, entry in sorted_entries:
                    if total_size_gb - evicted_size <= target_size_gb:
                        break
                    
                    # Don't evict recently accessed models (within 1 hour)
                    if time.time() - entry.last_accessed < 3600:
                        continue
                    
                    # Evict the model
                    evicted_size += entry.size_gb
                    evicted_models.append(model_id)
                    
                    # Mark for deletion (actual deletion happens async)
                    self._mark_for_deletion(entry)
                
                # Remove from cache
                for model_id in evicted_models:
                    del self._cache[model_id]
                    logger.info(f"Evicted model: {model_id}")
                
                logger.info(f"Evicted {len(evicted_models)} models, freed {evicted_size:.1f}GB")
    
    def _mark_for_deletion(self, entry: CacheEntry):
        """Mark a model for deletion (async cleanup)."""
        # Create a deletion marker file
        marker_file = self.cache_dir / f".delete_{entry.model_id}"
        marker_file.touch()
        
        # Actual deletion will be handled by a cleanup process
        logger.debug(f"Marked {entry.model_id} for deletion")
    
    def _predictive_preloader(self):
        """Pre-load models based on usage patterns."""
        while True:
            try:
                time.sleep(300)  # Check every 5 minutes
                self._check_predictive_loading()
            except Exception as e:
                logger.error(f"Predictive preloader error: {e}")
    
    def _check_predictive_loading(self):
        """Check if any models should be pre-loaded based on patterns."""
        current_hour = datetime.now().hour
        current_day = datetime.now().weekday()
        
        for model_id, pattern in self._usage_patterns.items():
            # Skip if already cached
            if model_id in self._cache:
                continue
            
            # Check if we're approaching peak hour
            if pattern.peak_hour == (current_hour + 1) % 24:
                # Check if this day typically has high usage
                if pattern.day_histogram[current_day] > pattern.avg_daily_requests * 0.5:
                    logger.info(f"Predictive pre-loading {model_id} for peak hour {pattern.peak_hour}")
                    self._trigger_model_load(model_id, pattern)
    
    def _trigger_model_load(self, model_id: str, pattern: UsagePattern):
        """Trigger asynchronous model loading."""
        # This would integrate with the actual model loading system
        logger.info(f"Triggering load for {model_id} based on usage pattern")
        # Implementation would call the actual model loading logic
    
    def _metadata_persister(self):
        """Periodically persist metadata to disk."""
        while True:
            try:
                time.sleep(30)  # Save every 30 seconds
                self._save_cache_metadata()
                self._save_usage_patterns()
            except Exception as e:
                logger.error(f"Metadata persister error: {e}")
    
    def record_access(self, model_id: str, provider: str, size_gb: float = 0,
                      load_time_ms: float = 0, path: str = None) -> CacheEntry:
        """Record model access for cache tracking.
        
        Args:
            model_id: Model identifier
            provider: Model provider (huggingface, ollama, vllm)
            size_gb: Model size in GB
            load_time_ms: Time taken to load model
            path: Path to model files
            
        Returns:
            CacheEntry: The cache entry for the model
        """
        with self._cache_lock:
            if model_id in self._cache:
                # Update existing entry (move to end for LRU)
                entry = self._cache.pop(model_id)
                entry.last_accessed = time.time()
                entry.access_count += 1
                self._cache[model_id] = entry
            else:
                # Create new entry
                entry = CacheEntry(
                    model_id=model_id,
                    provider=provider,
                    size_gb=size_gb,
                    last_accessed=time.time(),
                    access_count=1,
                    load_time_ms=load_time_ms,
                    path=path or str(self.nvme_path / "models" / model_id),
                    metadata={}
                )
                self._cache[model_id] = entry
            
            # Update usage pattern
            self._update_usage_pattern(model_id)
            
            return entry
    
    def _update_usage_pattern(self, model_id: str):
        """Update usage pattern for a model."""
        current_hour = datetime.now().hour
        current_day = datetime.now().weekday()
        
        if model_id not in self._usage_patterns:
            self._usage_patterns[model_id] = UsagePattern(
                model_id=model_id,
                hour_histogram=[0] * 24,
                day_histogram=[0] * 7,
                total_requests=0,
                avg_daily_requests=0,
                peak_hour=current_hour,
                peak_day=current_day
            )
        
        pattern = self._usage_patterns[model_id]
        pattern.hour_histogram[current_hour] += 1
        pattern.day_histogram[current_day] += 1
        pattern.total_requests += 1
        
        # Update peak hour and day
        pattern.peak_hour = pattern.hour_histogram.index(max(pattern.hour_histogram))
        pattern.peak_day = pattern.day_histogram.index(max(pattern.day_histogram))
        
        # Update average daily requests (rolling average over last 7 days)
        if pattern.total_requests > 0:
            days_active = max(1, sum(1 for d in pattern.day_histogram if d > 0))
            pattern.avg_daily_requests = pattern.total_requests / days_active
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get current cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        with self._cache_lock:
            total_size_gb = sum(entry.size_gb for entry in self._cache.values())
            
            # Calculate hit rate (would need request tracking for accuracy)
            total_accesses = sum(entry.access_count for entry in self._cache.values())
            
            # Get most/least recently used
            sorted_entries = sorted(self._cache.items(), 
                                   key=lambda x: x[1].last_accessed)
            
            most_recent = sorted_entries[-5:] if sorted_entries else []
            least_recent = sorted_entries[:5] if sorted_entries else []
            
            return {
                'cache_size_gb': total_size_gb,
                'max_cache_size_gb': self.max_cache_size_gb,
                'cache_utilization': total_size_gb / self.max_cache_size_gb if self.max_cache_size_gb > 0 else 0,
                'num_cached_models': len(self._cache),
                'total_accesses': total_accesses,
                'target_free_space_percent': self.target_free_space_percent,
                'most_recently_used': [
                    {
                        'model_id': entry.model_id,
                        'last_accessed': datetime.fromtimestamp(entry.last_accessed).isoformat(),
                        'access_count': entry.access_count
                    }
                    for _, entry in most_recent
                ],
                'least_recently_used': [
                    {
                        'model_id': entry.model_id,
                        'last_accessed': datetime.fromtimestamp(entry.last_accessed).isoformat(),
                        'access_count': entry.access_count
                    }
                    for _, entry in least_recent
                ],
                'usage_patterns': {
                    model_id: {
                        'peak_hour': pattern.peak_hour,
                        'peak_day': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][pattern.peak_day],
                        'avg_daily_requests': pattern.avg_daily_requests,
                        'total_requests': pattern.total_requests
                    }
                    for model_id, pattern in list(self._usage_patterns.items())[:10]
                }
            }
    
    def should_cache(self, model_id: str, size_gb: float) -> bool:
        """Determine if a model should be cached.
        
        Args:
            model_id: Model identifier
            size_gb: Model size in GB
            
        Returns:
            bool: True if model should be cached
        """
        with self._cache_lock:
            current_size_gb = sum(entry.size_gb for entry in self._cache.values())
            
            # Check if we have space
            if current_size_gb + size_gb > self.max_cache_size_gb * (1 - self.target_free_space_percent):
                # Would need eviction
                return self._can_evict_for_space(size_gb)
            
            return True
    
    def _can_evict_for_space(self, required_gb: float) -> bool:
        """Check if we can evict enough models to make space.
        
        Args:
            required_gb: Required space in GB
            
        Returns:
            bool: True if enough space can be made
        """
        # Find models that haven't been accessed recently
        evictable_size = 0
        current_time = time.time()
        
        for entry in self._cache.values():
            # Consider models not accessed in last hour as evictable
            if current_time - entry.last_accessed > 3600:
                evictable_size += entry.size_gb
                if evictable_size >= required_gb:
                    return True
        
        return False
    
    def get_model_load_time_estimate(self, model_id: str) -> float:
        """Estimate load time for a model.
        
        Args:
            model_id: Model identifier
            
        Returns:
            float: Estimated load time in milliseconds
        """
        if model_id in self._cache:
            # Already cached, very fast
            return 100.0
        
        # Check historical load times
        if model_id in self._usage_patterns:
            # Use historical average if available
            entry = self._cache.get(model_id)
            if entry and entry.load_time_ms > 0:
                return entry.load_time_ms
        
        # Default estimates based on model size patterns
        if '70b' in model_id.lower():
            return 30000.0  # 30 seconds
        elif '13b' in model_id.lower() or '15b' in model_id.lower():
            return 15000.0  # 15 seconds
        elif '7b' in model_id.lower() or '8b' in model_id.lower():
            return 8000.0   # 8 seconds
        elif '3b' in model_id.lower():
            return 4000.0   # 4 seconds
        else:
            return 10000.0  # 10 seconds default
    
    def clear_cache(self, force: bool = False) -> Dict[str, Any]:
        """Clear the cache.
        
        Args:
            force: If True, clear all entries. If False, keep frequently used.
            
        Returns:
            Dictionary with clearing statistics
        """
        with self._cache_lock:
            if force:
                cleared_count = len(self._cache)
                cleared_size = sum(entry.size_gb for entry in self._cache.values())
                
                # Mark all for deletion
                for entry in self._cache.values():
                    self._mark_for_deletion(entry)
                
                self._cache.clear()
                self._usage_patterns.clear()
                
                return {
                    'cleared_models': cleared_count,
                    'cleared_size_gb': cleared_size,
                    'force': True
                }
            else:
                # Keep frequently accessed models (top 20%)
                sorted_entries = sorted(self._cache.items(),
                                       key=lambda x: x[1].access_count,
                                       reverse=True)
                
                keep_count = max(1, len(sorted_entries) // 5)
                to_clear = sorted_entries[keep_count:]
                
                cleared_count = len(to_clear)
                cleared_size = sum(entry.size_gb for _, entry in to_clear)
                
                for model_id, entry in to_clear:
                    self._mark_for_deletion(entry)
                    del self._cache[model_id]
                
                return {
                    'cleared_models': cleared_count,
                    'cleared_size_gb': cleared_size,
                    'kept_models': keep_count,
                    'force': False
                }