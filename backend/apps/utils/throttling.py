
def check_throttle(user_key, limit=5, period=60):
    """
    Token Bucket Algorithm via Redis
    """
    key = f"throttle:{user_key}"
    current_count = cache.incr(key)
    
    if current_count == 1:
        cache.expire(key, period)
        
    if current_count > limit:
        raise ThrottlingException(f"Rate limit exceeded. Try again in {period}s.")