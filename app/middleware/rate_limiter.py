from fastapi import Request
import redis
from ..config.redis_config import get_redis
from ..util.exceptions import RateLimitException
from ..util.logger import logger


class RateLimiter:
    def __init__(self, requests: int = 10, window: int = 60):
        self.requests = requests
        self.window = window
        self.redis = get_redis()

    async def __call__(self, request: Request) -> bool:
        # Identificador único
        client_id = f"{request.client.host}:{request.url.path}"
        key = f"rate_limit:{client_id}"

        try:
            current = self.redis.incr(key)

            if current == 1:
                self.redis.expire(key, self.window)

            # Headers informativos
            request.state.rate_limit_remaining = max(0, self.requests - current)
            request.state.rate_limit_limit = self.requests

            if current > self.requests:
                ttl = self.redis.ttl(key)

                # LOG DE RATE LIMIT
                logger.warning(f"Rate limit exceeded for {client_id}")

                raise RateLimitException(retry_after=ttl)

            return True

        except redis.RedisError as e:
            logger.error(f"Redis error in rate limiter: {e}")
            return True


# Criar limitadores específicos
login_limiter = RateLimiter(requests=5, window=300)  # 5 tentativas em 5 minutos
register_limiter = RateLimiter(requests=3, window=3600)  # 3 registros por hora
api_limiter = RateLimiter(requests=60, window=60)  # 60 requisições por minuto
