"""Reject oversized multipart bodies while streaming, before unbounded spooling."""
from starlette.formparsers import MultiPartException
from starlette.responses import JSONResponse
from app.core.config import settings


class UploadBodyLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope.get('method') != 'POST' or scope.get('path') != settings.API_V1_STR + '/documents/upload':
            return await self.app(scope, receive, send)
        limit = settings.MAX_PDF_BYTES + 1024 * 1024  # Bounded multipart envelope.
        headers = dict(scope.get('headers', []))
        try:
            too_large = int(headers.get(b'content-length', b'0')) > limit
        except ValueError:
            too_large = False
        if too_large:
            return await JSONResponse({'detail': 'PDF upload exceeds the configured size limit.'}, status_code=413)(scope, receive, send)
        size, exceeded = 0, False

        async def bounded_receive():
            nonlocal size, exceeded
            message = await receive()
            if message['type'] == 'http.request':
                size += len(message.get('body', b''))
                if size > limit:
                    exceeded = True
                    # Starlette closes partially spooled files on this exception.
                    raise MultiPartException('PDF upload exceeds the configured size limit.')
            return message

        async def bounded_send(message):
            if exceeded and message['type'] == 'http.response.start':
                message = {**message, 'status': 413}
            await send(message)
        await self.app(scope, bounded_receive, bounded_send)
