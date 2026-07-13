import sys


def calculate_percentage(part, whole) -> float:
    whole = 1 if whole == 0 else whole
    return 100 * float(part) / float(whole)


def render_percentage(part, whole) -> str:
    value = calculate_percentage(part, whole)

    if value < 1:
        return "<1%"
    if value > 99:
        return ">99%"

    return f"{round(value)}%"


def format_duration(start: float, end: float) -> str:
    """Formats a time duration into the most relevant unit (ms, s, min, hr)."""
    duration = end - start

    if duration < 1e-3:  # Less than 1 ms
        return f"{duration * 1e6:.2f} µs"
    elif duration < 1:  # Less than 1 second
        return f"{duration * 1e3:.2f} ms"
    elif duration < 60:  # Less than 1 minute
        return f"{duration:.2f} s"
    elif duration < 3600:  # Less than 1 hour
        return f"{duration / 60:.2f} min"
    else:  # More than 1 hour
        return f"{duration / 3600:.2f} hr"


def deep_getsizeof(obj, seen=None):
    size = sys.getsizeof(obj)
    if seen is None:
        seen = set()
    obj_id = id(obj)
    if obj_id in seen:
        return 0
    seen.add(obj_id)

    if isinstance(obj, dict):
        size += sum(
            (deep_getsizeof(k, seen) + deep_getsizeof(v, seen)) for k, v in obj.items()
        )
    elif isinstance(obj, (list, tuple, set, frozenset)):
        size += sum(deep_getsizeof(i, seen) for i in obj)

    return size
