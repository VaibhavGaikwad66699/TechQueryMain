"""Small single-process rate limiter; proxy supplies a trusted scope.client IP."""
from threading import Lock
import time
from starlette.responses import JSONResponse
from app.core.config import settings


class ProductionRateLimit:
    def __init__(self, app):
        self.app = app
        self.clients = {}
        self.lock = Lock()

    async def __call__(self, scope, receive, send):
        path = scope.get('path', '')
        if (settings.ENVIRONMENT != 'production' or scope['type'] != 'http'
                or not path.startswith(settings.API_V1_STR + '/') or path == settings.API_V1_STR + '/ready'):
            return await self.app(scope, receive, send)
        now = time.monotonic()
        client = (scope.get('client') or ('unknown', 0))[0]
        maximum = settings.RATE_LIMIT_REQUESTS_PER_MINUTE
        category = 'all'
        if scope.get('method') == 'POST':
            if path.startswith(settings.API_V1_STR + '/auth/'):
                category, maximum = 'auth', settings.RATE_LIMIT_AUTH_PER_MINUTE
            elif path.endswith('/upload'):
                category, maximum = 'upload', settings.RATE_LIMIT_UPLOADS_PER_MINUTE
            elif path.endswith(('/query', '/messages', '/process')):
                category, maximum = 'query', settings.RATE_LIMIT_QUERIES_PER_MINUTE
        # Count all API traffic as well as expensive action categories.
        keys = [(client, 'all', settings.RATE_LIMIT_REQUESTS_PER_MINUTE)]
        if category != 'all':
            keys.append((client, category, maximum))
        with self.lock:
            if len(self.clients) + len(keys) >= settings.RATE_LIMIT_MAX_CLIENTS:
                self.clients = {key: value for key, value in self.clients.items() if value[1] > now}
            blocked, retry = False, 1
            for host, bucket, limit in keys:
                key = (host, bucket)
                count, reset = self.clients.get(key, (0, now + 60))
                if reset <= now:
                    count, reset = 0, now + 60
                if count >= limit or (key not in self.clients and len(self.clients) >= settings.RATE_LIMIT_MAX_CLIENTS):
                    blocked, retry = True, max(retry, int(reset - now) + 1)
                else:
                    self.clients[key] = (count + 1, reset)
        if blocked:
            response = JSONResponse({'detail': 'Too many requests. Please wait before trying again.'}, status_code=429,
                headers={'Retry-After': str(retry), 'Cache-Control': 'no-store'})
            return await response(scope, receive, send)
        await self.app(scope, receive, send)
