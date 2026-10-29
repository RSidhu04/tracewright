import hmac
import os
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query, Depends, Header, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError
from .compare import compare
from .records import RunRecord, BaselineRequest
from .store import Store, Conflict


class BodyLimit:
    def __init__(self, app, limit=2_000_000):
        self.app, self.limit = app, limit

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        # Bound actual bytes, including chunked requests without Content-Length.
        chunks, total = [], 0
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect':
                return
            total += len(message.get('body', b''))
            if total > self.limit:
                return await JSONResponse({'detail': 'Request exceeds 2 MB'}, 413)(scope, receive, send)
            chunks.append(message)
            if not message.get('more_body'):
                break
        async def replay():
            if chunks:
                return chunks.pop(0)
            return await receive()
        await self.app(scope, replay, send)


def create_app(db_path=None, *, api_token=None):
    token = api_token or os.getenv('TRACEWRIGHT_API_TOKEN')
    if not token or len(token) < 16:
        raise RuntimeError('Set TRACEWRIGHT_API_TOKEN to at least 16 characters')
    secrets = tuple(filter(None, os.getenv('TRACEWRIGHT_REDACT_VALUES', '').split(','))) + (token,)
    store = Store(db_path, secrets=secrets)

    @asynccontextmanager
    async def lifespan(app):
        yield
        store.engine.dispose()

    app = FastAPI(title='Tracewright', version='0.2.0', lifespan=lifespan)
    app.state.store = store
    app.add_middleware(BodyLimit)

    @app.middleware('http')
    async def security_headers(request, call_next):
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Cache-Control'] = 'no-store'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'"
        # Swagger uses its own CDN assets; dashboard remains strict.
        if request.url.path in ('/docs', '/redoc'):
            del response.headers['Content-Security-Policy']
        return response

    def authorized(authorization: str = Header(default='')):
        if not hmac.compare_digest(authorization, 'Bearer ' + token):
            raise HTTPException(401, 'Valid bearer token required', headers={'WWW-Authenticate': 'Bearer'})

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        # Default FastAPI validation echoes raw input. Do not leak trace secrets.
        return JSONResponse({'detail': 'Invalid request; consult the API schema'}, 422)

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request, exc):
        return JSONResponse({'detail': 'Database unavailable or schema not migrated'}, 503)

    def get(run_id):
        try:
            return store.get(run_id)
        except KeyError:
            raise HTTPException(404, 'Run not found') from None

    @app.get('/health')
    def health():
        return {'status': 'ok'}

    @app.get('/ready')
    def ready():
        store.ready()
        return {'status': 'ready'}

    @app.get('/runs', dependencies=[Depends(authorized)])
    def runs(limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0)):
        return store.list(limit, offset)

    @app.post('/runs', dependencies=[Depends(authorized)], status_code=201)
    def ingest(run: RunRecord, response: Response):
        try:
            created = store.save(run.model_dump(mode='json'))
        except Conflict:
            raise HTTPException(409, 'Run ID already exists with different content') from None
        except ValueError:
            raise HTTPException(422, 'Run violates storage or redaction constraints') from None
        response.status_code = 201 if created else 200
        return {'id': str(run.id), 'created': created}

    @app.get('/runs/{run_id}', dependencies=[Depends(authorized)])
    def run(run_id: str):
        return get(run_id)

    @app.post('/baselines', dependencies=[Depends(authorized)], status_code=201)
    def promote(body: BaselineRequest):
        try:
            return store.promote(body.name, body.version, body.run_id, body.note)
        except KeyError:
            raise HTTPException(404, 'Run not found') from None
        except Conflict:
            raise HTTPException(409, 'Baseline version already exists') from None

    @app.get('/baselines', dependencies=[Depends(authorized)])
    def baselines(limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0)):
        return store.list_baselines(limit, offset)

    @app.get('/baselines/{name}/{version}', dependencies=[Depends(authorized)])
    def baseline(name: str, version: int):
        try:
            return store.baseline(name, version)
        except KeyError:
            raise HTTPException(404, 'Baseline not found') from None

    @app.get('/compare', dependencies=[Depends(authorized)])
    def comparison(baseline: str, candidate: str,
                   tolerance: float = Query(0, ge=0, le=1), alpha: float = Query(.05, gt=0, lt=1)):
        try:
            return compare(get(baseline), get(candidate), tolerance, alpha)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from None

    static = Path(__file__).parent / 'static'
    app.mount('/static', StaticFiles(directory=static), name='static')

    @app.get('/', include_in_schema=False)
    def dashboard():
        return FileResponse(static / 'index.html')

    return app
