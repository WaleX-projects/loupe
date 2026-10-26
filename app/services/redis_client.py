import redis.asyncio as redis



# Create async redis client
redis_client  = redis.Redis(
    host='localhost',
    port=6379,
    socket_timeout=10,  # Must be greater than BLPOP timeout
    socket_connect_timeout=5,
    decode_responses=True,
)
