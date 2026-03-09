import logging
import json
import re

class GDPRJsonFormatter(logging.Formatter):
    """
    Structured JSON logging with PII masking.
    Safe for production log aggregation systems.
    """
    
    SENSITIVE_PATTERNS = {
        r'"password":\s*".*?"': '"password": "***MASKED***"',
        r'"token":\s*".*?"': '"token": "***MASKED***"',
        r'"access_token":\s*".*?"': '"access_token": "***MASKED***"',
        r'"refresh_token":\s*".*?"': '"refresh_token": "***MASKED***"',
        r'"credit_card":\s*".*?"': '"credit_card": "***MASKED***"',
        r'"phone":\s*"\+?(\d{2,4})\d{6,}"': r'"phone": "\1******"',
    }

    SENSITIVE_KEYS = {'password', 'token', 'access', 'refresh', 'credit_card', 'secret', 'key', 'otp'}

    def format(self, record):
        log_record = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "path": record.pathname,
            "line_no": record.lineno,
            "correlation_id": getattr(record, "correlation_id", "N/A"),
        }

        if hasattr(record, "metadata") and isinstance(record.metadata, dict):
            log_record["metadata"] = self._recursive_scrub(record.metadata)

        try:
            json_output = json.dumps(log_record)
        except (TypeError, ValueError):
            log_record["metadata"] = str(getattr(record, "metadata", ""))
            json_output = json.dumps(log_record)

        for pattern, replacement in self.SENSITIVE_PATTERNS.items():
            json_output = re.sub(pattern, replacement, json_output)

        return json_output

    def _recursive_scrub(self, data, depth=0):
        """
        Recursively traverse dicts/lists to mask sensitive keys.
        SECURITY FIX: Added depth limit to prevent Stack Overflow attacks.
        """
        if depth > 10:
            return "[MAX_DEPTH_EXCEEDED]"

        if isinstance(data, dict):
            return {
                k: ("***MASKED***" if str(k).lower() in self.SENSITIVE_KEYS and isinstance(v, (str, int))
                    else self._recursive_scrub(v, depth + 1))
                for k, v in data.items()
            }
        elif isinstance(data, list):
            return [self._recursive_scrub(i, depth + 1) for i in data]
        
        return data