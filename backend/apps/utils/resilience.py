# apps/utils/resilience.py
import logging
from functools import wraps
from django.core.cache import cache

logger = logging.getLogger(__name__)

class CircuitBreakerOpenException(Exception):
    pass

class CircuitBreaker:
    """
    Prevents cascading failures by stopping requests to a failing service.
    """
    def __init__(self, service_name, failure_threshold=5, recovery_timeout=60):
        self.service_name = service_name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.key_failures = f"cb:fails:{service_name}"
        self.key_open = f"cb:open:{service_name}"

    def __call__(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 1. Check Circuit State (Fail Open if Redis Error)
            try:
                if cache.get(self.key_open):
                    logger.warning(f"Circuit OPEN: {self.service_name}. Fast failing.")
                    raise CircuitBreakerOpenException(f"{self.service_name} is temporarily down")
            except Exception as e:
                if isinstance(e, CircuitBreakerOpenException):
                    raise e
                logger.error(f"CircuitBreaker Redis Check Failed: {e}")

            # 2. Attempt Execution
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                # 3. Record Failure
                self._safe_record_failure()
                raise e

        return wrapper

    def _safe_record_failure(self):
        try:
            fails = cache.incr(self.key_failures)
            
            # Set expiry on first fail
            if fails == 1:
                cache.expire(self.key_failures, self.recovery_timeout)

            # Trip Circuit
            if fails >= self.failure_threshold:
                logger.critical(f"Circuit TRIPPED for {self.service_name}!")
                cache.set(self.key_open, "OPEN", timeout=self.recovery_timeout)
                cache.delete(self.key_failures)
        except Exception:
            pass