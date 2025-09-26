from datetime import date, datetime
from typing import Dict, Any

from DB.db import (
    increment_message_count,
    get_message_count,
)  # Import from your DB/db.py


class MessageLimiter:
    def __init__(self, daily_limit: int = 100):
        self.daily_limit = daily_limit

    def check_message_limit(self, user_id: str) -> bool:
        """
        Check if the user has exceeded the daily message limit.
        If not, increment their count.
        """
        today = date.today()
        current_count = get_message_count(user_id, on_date=today)

        if current_count >= self.daily_limit:
            return False

        increment_message_count(user_id, on_date=today)
        return True

    def get_user_usage(self, user_id: str) -> Dict[str, Any]:
        today = date.today()
        current_count = get_message_count(user_id, on_date=today)

        return {
            "current_count": current_count,
            "daily_limit": self.daily_limit,
            "remaining": max(0, self.daily_limit - current_count),
            "date": today.isoformat(),
        }
