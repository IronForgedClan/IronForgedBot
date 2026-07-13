from datetime import timezone
from sqlalchemy.types import TypeDecorator, DateTime


class UTCDateTime(TypeDecorator):
    """A DateTime type that always stores timestamps in UTC."""

    impl = DateTime()
    cache_ok = True

    def process_bind_param(self, value, dialect):
        """Ensure that datetime values stored in the database are in UTC."""
        if value is not None:
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc)
        return None

    def process_result_value(self, value, dialect):
        """Ensure that datetime values retrieved are timezone-aware (UTC)."""
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
