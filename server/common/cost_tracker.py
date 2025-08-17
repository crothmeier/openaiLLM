"""
Real-time Cost Analytics and Budget Management Module

Provides cost tracking, budget alerts, and department-level attribution
for AI model usage with real-time analytics.
"""

import json
import time
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, asdict
from collections import defaultdict
import logging
import threading
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class CostEntry:
    """Represents a single cost entry."""
    timestamp: float
    model_id: str
    provider: str
    user_id: str
    department: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    request_id: str
    metadata: Dict[str, Any]


@dataclass
class Budget:
    """Budget configuration for a department."""
    department: str
    monthly_limit_usd: float
    alert_threshold_percent: float  # Alert when this % is reached
    current_spend_usd: float
    period_start: datetime
    period_end: datetime
    alert_webhook: Optional[str] = None
    alert_email: Optional[str] = None
    is_hard_limit: bool = False  # If True, block requests when limit reached


class CostTracker:
    """Tracks costs and manages budgets for AI model usage."""
    
    # Updated pricing per 1K tokens (prompt + completion combined for simplicity)
    MODEL_PRICING = {
        # OpenAI models
        'gpt-4-turbo': 0.01,      # $10 per 1M tokens
        'gpt-4': 0.03,             # $30 per 1M tokens
        'gpt-3.5-turbo': 0.0015,   # $1.50 per 1M tokens
        
        # Anthropic models
        'claude-3-opus': 0.015,    # $15 per 1M tokens
        'claude-3-sonnet': 0.003,  # $3 per 1M tokens
        'claude-3-haiku': 0.00025, # $0.25 per 1M tokens
        
        # Open models (compute cost estimates)
        'llama-3-70b': 0.0009,     # ~$0.90 per 1M tokens
        'llama-3-8b': 0.0002,      # ~$0.20 per 1M tokens
        'llama-2-70b': 0.0007,     # ~$0.70 per 1M tokens
        'llama-2-13b': 0.00024,    # ~$0.24 per 1M tokens
        'llama-2-7b': 0.0002,      # ~$0.20 per 1M tokens
        'mistral-7b': 0.0002,      # ~$0.20 per 1M tokens
        'mixtral-8x7b': 0.0007,    # ~$0.70 per 1M tokens
        'qwen-72b': 0.0008,        # ~$0.80 per 1M tokens
        
        # Default for unknown models
        'default': 0.0005          # ~$0.50 per 1M tokens
    }
    
    def __init__(self, storage_path: str = "/mnt/nvme/costs"):
        """Initialize cost tracker.
        
        Args:
            storage_path: Path to store cost data and budgets
        """
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # In-memory storage
        self._costs: List[CostEntry] = []
        self._budgets: Dict[str, Budget] = {}
        self._department_spend: Dict[str, float] = defaultdict(float)
        self._user_spend: Dict[str, float] = defaultdict(float)
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Load existing data
        self._load_budgets()
        self._load_current_month_costs()
        
        # Start background tasks
        self._start_background_tasks()
    
    def _load_budgets(self):
        """Load budget configurations from disk."""
        budget_file = self.storage_path / "budgets.json"
        if budget_file.exists():
            try:
                with open(budget_file, 'r') as f:
                    data = json.load(f)
                    for dept, budget_data in data.items():
                        self._budgets[dept] = Budget(
                            department=dept,
                            monthly_limit_usd=budget_data['monthly_limit_usd'],
                            alert_threshold_percent=budget_data.get('alert_threshold_percent', 0.8),
                            current_spend_usd=budget_data.get('current_spend_usd', 0),
                            period_start=datetime.fromisoformat(budget_data['period_start']),
                            period_end=datetime.fromisoformat(budget_data['period_end']),
                            alert_webhook=budget_data.get('alert_webhook'),
                            alert_email=budget_data.get('alert_email'),
                            is_hard_limit=budget_data.get('is_hard_limit', False)
                        )
                logger.info(f"Loaded budgets for {len(self._budgets)} departments")
            except Exception as e:
                logger.error(f"Failed to load budgets: {e}")
    
    def _save_budgets(self):
        """Save budget configurations to disk."""
        budget_file = self.storage_path / "budgets.json"
        try:
            with self._lock:
                data = {}
                for dept, budget in self._budgets.items():
                    data[dept] = {
                        'monthly_limit_usd': budget.monthly_limit_usd,
                        'alert_threshold_percent': budget.alert_threshold_percent,
                        'current_spend_usd': budget.current_spend_usd,
                        'period_start': budget.period_start.isoformat(),
                        'period_end': budget.period_end.isoformat(),
                        'alert_webhook': budget.alert_webhook,
                        'alert_email': budget.alert_email,
                        'is_hard_limit': budget.is_hard_limit
                    }
            
            with open(budget_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save budgets: {e}")
    
    def _load_current_month_costs(self):
        """Load current month's cost data."""
        now = datetime.now(timezone.utc)
        month_file = self.storage_path / f"costs_{now.year}_{now.month:02d}.json"
        
        if month_file.exists():
            try:
                with open(month_file, 'r') as f:
                    data = json.load(f)
                    for entry_data in data.get('entries', []):
                        entry = CostEntry(**entry_data)
                        self._costs.append(entry)
                        self._department_spend[entry.department] += entry.cost_usd
                        self._user_spend[entry.user_id] += entry.cost_usd
                logger.info(f"Loaded {len(self._costs)} cost entries for current month")
            except Exception as e:
                logger.error(f"Failed to load current month costs: {e}")
    
    def _save_costs(self):
        """Save cost data to disk."""
        now = datetime.now(timezone.utc)
        month_file = self.storage_path / f"costs_{now.year}_{now.month:02d}.json"
        
        try:
            with self._lock:
                entries = [asdict(entry) for entry in self._costs]
            
            with open(month_file, 'w') as f:
                json.dump({'entries': entries, 'timestamp': time.time()}, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save costs: {e}")
    
    def _start_background_tasks(self):
        """Start background tasks for cost management."""
        # Budget monitor
        threading.Thread(target=self._budget_monitor, daemon=True).start()
        
        # Data persister
        threading.Thread(target=self._data_persister, daemon=True).start()
        
        # Month rollover checker
        threading.Thread(target=self._month_rollover_checker, daemon=True).start()
    
    def _budget_monitor(self):
        """Monitor budgets and send alerts."""
        while True:
            try:
                time.sleep(60)  # Check every minute
                self._check_budget_alerts()
            except Exception as e:
                logger.error(f"Budget monitor error: {e}")
    
    def _check_budget_alerts(self):
        """Check if any budgets need alerts."""
        with self._lock:
            for dept, budget in self._budgets.items():
                if budget.current_spend_usd >= budget.monthly_limit_usd * budget.alert_threshold_percent:
                    # Send alert
                    self._send_budget_alert(budget)
    
    def _send_budget_alert(self, budget: Budget):
        """Send budget alert via webhook or email."""
        alert_data = {
            'department': budget.department,
            'current_spend_usd': budget.current_spend_usd,
            'monthly_limit_usd': budget.monthly_limit_usd,
            'percentage_used': (budget.current_spend_usd / budget.monthly_limit_usd) * 100,
            'period_end': budget.period_end.isoformat(),
            'message': f"Department {budget.department} has used {budget.current_spend_usd:.2f} of ${budget.monthly_limit_usd:.2f} monthly budget ({(budget.current_spend_usd/budget.monthly_limit_usd)*100:.1f}%)"
        }
        
        if budget.alert_webhook:
            # Send to webhook (e.g., Slack, Teams)
            try:
                import requests
                response = requests.post(budget.alert_webhook, json=alert_data, timeout=5)
                logger.info(f"Sent budget alert for {budget.department} to webhook")
            except Exception as e:
                logger.error(f"Failed to send webhook alert: {e}")
        
        if budget.alert_email:
            # Log email alert (actual email sending would require SMTP config)
            logger.info(f"Email alert for {budget.department}: {alert_data['message']}")
    
    def _data_persister(self):
        """Periodically persist data to disk."""
        while True:
            try:
                time.sleep(30)  # Save every 30 seconds
                self._save_costs()
                self._save_budgets()
            except Exception as e:
                logger.error(f"Data persister error: {e}")
    
    def _month_rollover_checker(self):
        """Check for month rollover and reset budgets."""
        while True:
            try:
                time.sleep(3600)  # Check every hour
                self._check_month_rollover()
            except Exception as e:
                logger.error(f"Month rollover checker error: {e}")
    
    def _check_month_rollover(self):
        """Check if we need to roll over to a new month."""
        now = datetime.now(timezone.utc)
        
        with self._lock:
            for budget in self._budgets.values():
                if now > budget.period_end:
                    # Archive current month
                    self._archive_month_data(budget.period_start)
                    
                    # Reset budget for new month
                    budget.period_start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
                    
                    # Calculate period end (last day of month)
                    if now.month == 12:
                        budget.period_end = datetime(now.year + 1, 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)
                    else:
                        budget.period_end = datetime(now.year, now.month + 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)
                    
                    budget.current_spend_usd = 0
                    
                    logger.info(f"Reset budget for {budget.department} for new month")
            
            # Clear in-memory costs and spending
            self._costs.clear()
            self._department_spend.clear()
            self._user_spend.clear()
    
    def _archive_month_data(self, month_start: datetime):
        """Archive data for a completed month."""
        archive_dir = self.storage_path / "archive"
        archive_dir.mkdir(exist_ok=True)
        
        month_file = self.storage_path / f"costs_{month_start.year}_{month_start.month:02d}.json"
        if month_file.exists():
            archive_file = archive_dir / f"costs_{month_start.year}_{month_start.month:02d}.json"
            month_file.rename(archive_file)
            logger.info(f"Archived cost data for {month_start.year}-{month_start.month:02d}")
    
    def track_cost(self, model_id: str, provider: str, prompt_tokens: int,
                   completion_tokens: int, user_id: str, department: str,
                   request_id: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Track cost for a model usage.
        
        Args:
            model_id: Model identifier
            provider: Model provider
            prompt_tokens: Number of prompt tokens
            completion_tokens: Number of completion tokens
            user_id: User identifier
            department: Department identifier
            request_id: Request identifier
            metadata: Additional metadata
            
        Returns:
            Cost tracking result including cost and budget status
        """
        # Calculate cost
        total_tokens = prompt_tokens + completion_tokens
        
        # Get pricing for model
        pricing_key = model_id.lower()
        for key in self.MODEL_PRICING:
            if key in pricing_key:
                price_per_1k = self.MODEL_PRICING[key]
                break
        else:
            price_per_1k = self.MODEL_PRICING['default']
        
        cost_usd = (total_tokens / 1000.0) * price_per_1k
        
        # Check budget before tracking
        budget_status = self._check_budget(department, cost_usd)
        
        if budget_status['blocked']:
            return {
                'tracked': False,
                'cost_usd': cost_usd,
                'blocked': True,
                'reason': budget_status['reason'],
                'department_spend': budget_status['current_spend'],
                'department_limit': budget_status['limit']
            }
        
        # Create cost entry
        entry = CostEntry(
            timestamp=time.time(),
            model_id=model_id,
            provider=provider,
            user_id=user_id,
            department=department,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=cost_usd,
            request_id=request_id,
            metadata=metadata or {}
        )
        
        # Track the cost
        with self._lock:
            self._costs.append(entry)
            self._department_spend[department] += cost_usd
            self._user_spend[user_id] += cost_usd
            
            # Update budget current spend
            if department in self._budgets:
                self._budgets[department].current_spend_usd += cost_usd
        
        return {
            'tracked': True,
            'cost_usd': cost_usd,
            'total_tokens': total_tokens,
            'price_per_1k_tokens': price_per_1k,
            'department_spend': self._department_spend[department],
            'user_spend': self._user_spend[user_id],
            'budget_status': budget_status
        }
    
    def _check_budget(self, department: str, additional_cost: float) -> Dict[str, Any]:
        """Check if department has budget for additional cost.
        
        Args:
            department: Department identifier
            additional_cost: Additional cost to be incurred
            
        Returns:
            Budget status including whether request should be blocked
        """
        if department not in self._budgets:
            # No budget configured, allow
            return {
                'has_budget': True,
                'blocked': False,
                'current_spend': self._department_spend.get(department, 0),
                'limit': None,
                'percentage_used': 0
            }
        
        budget = self._budgets[department]
        projected_spend = budget.current_spend_usd + additional_cost
        
        if budget.is_hard_limit and projected_spend > budget.monthly_limit_usd:
            return {
                'has_budget': False,
                'blocked': True,
                'reason': f"Department {department} would exceed monthly budget limit",
                'current_spend': budget.current_spend_usd,
                'limit': budget.monthly_limit_usd,
                'percentage_used': (budget.current_spend_usd / budget.monthly_limit_usd) * 100
            }
        
        return {
            'has_budget': projected_spend <= budget.monthly_limit_usd,
            'blocked': False,
            'current_spend': budget.current_spend_usd,
            'limit': budget.monthly_limit_usd,
            'percentage_used': (budget.current_spend_usd / budget.monthly_limit_usd) * 100 if budget.monthly_limit_usd > 0 else 0,
            'warning': projected_spend > budget.monthly_limit_usd * budget.alert_threshold_percent
        }
    
    def set_budget(self, department: str, monthly_limit_usd: float,
                   alert_threshold_percent: float = 0.8,
                   alert_webhook: Optional[str] = None,
                   alert_email: Optional[str] = None,
                   is_hard_limit: bool = False) -> Dict[str, Any]:
        """Set or update budget for a department.
        
        Args:
            department: Department identifier
            monthly_limit_usd: Monthly budget limit in USD
            alert_threshold_percent: Alert when this percentage is reached
            alert_webhook: Webhook URL for alerts
            alert_email: Email for alerts
            is_hard_limit: If True, block requests when limit reached
            
        Returns:
            Budget configuration
        """
        now = datetime.now(timezone.utc)
        
        # Calculate period
        period_start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
        if now.month == 12:
            period_end = datetime(now.year + 1, 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)
        else:
            period_end = datetime(now.year, now.month + 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)
        
        with self._lock:
            if department in self._budgets:
                # Update existing budget
                budget = self._budgets[department]
                budget.monthly_limit_usd = monthly_limit_usd
                budget.alert_threshold_percent = alert_threshold_percent
                budget.alert_webhook = alert_webhook
                budget.alert_email = alert_email
                budget.is_hard_limit = is_hard_limit
            else:
                # Create new budget
                budget = Budget(
                    department=department,
                    monthly_limit_usd=monthly_limit_usd,
                    alert_threshold_percent=alert_threshold_percent,
                    current_spend_usd=self._department_spend.get(department, 0),
                    period_start=period_start,
                    period_end=period_end,
                    alert_webhook=alert_webhook,
                    alert_email=alert_email,
                    is_hard_limit=is_hard_limit
                )
                self._budgets[department] = budget
        
        self._save_budgets()
        
        return {
            'department': department,
            'monthly_limit_usd': monthly_limit_usd,
            'alert_threshold_percent': alert_threshold_percent,
            'current_spend_usd': budget.current_spend_usd,
            'remaining_usd': monthly_limit_usd - budget.current_spend_usd,
            'period': f"{period_start.date()} to {period_end.date()}",
            'is_hard_limit': is_hard_limit
        }
    
    def get_cost_report(self, start_date: Optional[datetime] = None,
                        end_date: Optional[datetime] = None,
                        department: Optional[str] = None,
                        user_id: Optional[str] = None) -> Dict[str, Any]:
        """Generate cost report.
        
        Args:
            start_date: Start date for report
            end_date: End date for report
            department: Filter by department
            user_id: Filter by user
            
        Returns:
            Cost report with breakdown and analytics
        """
        with self._lock:
            # Filter costs
            filtered_costs = self._costs
            
            if start_date:
                start_timestamp = start_date.timestamp()
                filtered_costs = [c for c in filtered_costs if c.timestamp >= start_timestamp]
            
            if end_date:
                end_timestamp = end_date.timestamp()
                filtered_costs = [c for c in filtered_costs if c.timestamp <= end_timestamp]
            
            if department:
                filtered_costs = [c for c in filtered_costs if c.department == department]
            
            if user_id:
                filtered_costs = [c for c in filtered_costs if c.user_id == user_id]
            
            # Calculate aggregates
            total_cost = sum(c.cost_usd for c in filtered_costs)
            total_tokens = sum(c.prompt_tokens + c.completion_tokens for c in filtered_costs)
            
            # Department breakdown
            dept_breakdown = defaultdict(lambda: {'cost': 0, 'requests': 0, 'tokens': 0})
            for cost in filtered_costs:
                dept_breakdown[cost.department]['cost'] += cost.cost_usd
                dept_breakdown[cost.department]['requests'] += 1
                dept_breakdown[cost.department]['tokens'] += cost.prompt_tokens + cost.completion_tokens
            
            # Model breakdown
            model_breakdown = defaultdict(lambda: {'cost': 0, 'requests': 0, 'tokens': 0})
            for cost in filtered_costs:
                model_breakdown[cost.model_id]['cost'] += cost.cost_usd
                model_breakdown[cost.model_id]['requests'] += 1
                model_breakdown[cost.model_id]['tokens'] += cost.prompt_tokens + cost.completion_tokens
            
            # User breakdown (top 10)
            user_costs = defaultdict(float)
            for cost in filtered_costs:
                user_costs[cost.user_id] += cost.cost_usd
            top_users = sorted(user_costs.items(), key=lambda x: x[1], reverse=True)[:10]
            
            return {
                'period': {
                    'start': start_date.isoformat() if start_date else None,
                    'end': end_date.isoformat() if end_date else None
                },
                'summary': {
                    'total_cost_usd': total_cost,
                    'total_requests': len(filtered_costs),
                    'total_tokens': total_tokens,
                    'avg_cost_per_request': total_cost / len(filtered_costs) if filtered_costs else 0
                },
                'department_breakdown': dict(dept_breakdown),
                'model_breakdown': dict(model_breakdown),
                'top_users': [
                    {'user_id': user_id, 'cost_usd': cost}
                    for user_id, cost in top_users
                ],
                'budgets': {
                    dept: {
                        'limit': budget.monthly_limit_usd,
                        'spent': budget.current_spend_usd,
                        'remaining': budget.monthly_limit_usd - budget.current_spend_usd,
                        'percentage_used': (budget.current_spend_usd / budget.monthly_limit_usd) * 100
                    }
                    for dept, budget in self._budgets.items()
                }
            }
    
    def get_real_time_stats(self) -> Dict[str, Any]:
        """Get real-time cost statistics.
        
        Returns:
            Real-time statistics for dashboard
        """
        now = datetime.now(timezone.utc)
        hour_ago = now - timedelta(hours=1)
        day_ago = now - timedelta(days=1)
        
        with self._lock:
            # Last hour costs
            hour_costs = [c for c in self._costs if c.timestamp >= hour_ago.timestamp()]
            hour_total = sum(c.cost_usd for c in hour_costs)
            
            # Last 24 hour costs
            day_costs = [c for c in self._costs if c.timestamp >= day_ago.timestamp()]
            day_total = sum(c.cost_usd for c in day_costs)
            
            # Current month total
            month_total = sum(c.cost_usd for c in self._costs)
            
            # Projected month cost (linear projection)
            days_in_month = 30  # Simplified
            days_elapsed = now.day
            if days_elapsed > 0:
                projected_month = (month_total / days_elapsed) * days_in_month
            else:
                projected_month = 0
            
            return {
                'timestamp': now.isoformat(),
                'last_hour': {
                    'cost_usd': hour_total,
                    'requests': len(hour_costs),
                    'rate_per_hour': hour_total
                },
                'last_24_hours': {
                    'cost_usd': day_total,
                    'requests': len(day_costs),
                    'avg_per_hour': day_total / 24
                },
                'current_month': {
                    'cost_usd': month_total,
                    'requests': len(self._costs),
                    'projected_total': projected_month,
                    'days_elapsed': days_elapsed
                },
                'active_departments': len(self._department_spend),
                'active_users': len(self._user_spend),
                'budget_alerts': [
                    {
                        'department': dept,
                        'percentage_used': (budget.current_spend_usd / budget.monthly_limit_usd) * 100,
                        'alert': budget.current_spend_usd >= budget.monthly_limit_usd * budget.alert_threshold_percent
                    }
                    for dept, budget in self._budgets.items()
                    if budget.current_spend_usd >= budget.monthly_limit_usd * 0.7  # Show when >70% used
                ]
            }