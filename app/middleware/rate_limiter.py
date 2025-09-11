from fastapi import Request, HTTPException, status
import redis

from ..config.redis_config import get_redis


class RateLimiter:
    def __init__(self, requests: int = 10, window: int = 60):
        """
        requests: número de requisições permitidas
        window: janela de tempo em segundos
        """
        self.requests = requests
        self.window = window
        self.redis = get_redis()

    async def __call__(self, request: Request) -> bool:
        # Identificador único (IP + endpoint)
        client_id = f"{request.client.host}:{request.url.path}"

        print(client_id)
        # Chave Redis
        key = f"rate_limit:{client_id}"

        try:
            # Incrementar contador
            current = self.redis.incr(key)

            # Se é a primeira requisição, definir TTL
            if current == 1:
                self.redis.expire(key, self.window)

            # Verificar limite
            if current > self.requests:
                ttl = self.redis.ttl(key)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit excedido. Tente novamente em {ttl} segundos.",
                    headers={"Retry-After": str(ttl)}
                )

            return True

        except redis.RedisError:
            # Se Redis falhar, permitir requisição
            return True


# Criar limitadores específicos
login_limiter = RateLimiter(requests=5, window=300)  # 5 tentativas em 5 minutos
register_limiter = RateLimiter(requests=3, window=3600)  # 3 registros por hora
api_limiter = RateLimiter(requests=60, window=60)  # 60 requisições por minuto
