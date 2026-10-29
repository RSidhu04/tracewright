import os
from fastapi import FastAPI, HTTPException, Query
from .compare import compare
from .store import Store


def create_app(db_path=None):
    app = FastAPI(title="Tracewright", version="0.1.0")
    store = Store(db_path or os.getenv("TRACEWRIGHT_DB", "tracewright.db"))

    def get(run_id):
        try:
            return store.get(run_id)
        except KeyError:
            raise HTTPException(404, "Run not found") from None

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/runs")
    def runs(limit: int = Query(100, ge=1, le=1000)):
        return store.list(limit)

    @app.get("/runs/{run_id}")
    def run(run_id: str):
        return get(run_id)

    @app.get("/compare")
    def comparison(baseline: str, candidate: str,
                   tolerance: float = Query(0, ge=0, le=1), alpha: float = Query(.05, gt=0, lt=1)):
        try:
            return compare(get(baseline), get(candidate), tolerance, alpha)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from None

    return app
