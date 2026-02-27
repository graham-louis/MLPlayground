import importlib
import pathlib

from fastapi import APIRouter

from app.api.routes import data, datasources, ingest, training, utils

# ---------------------------------------------------------------------------
# Auto-discover datasource plugins: any ds_*.py file in app/ingest/ that
# subclasses BaseDatasource is imported here so __init_subclass__ fires and
# registers the datasource with DATASOURCE_REGISTRY at startup.
# ---------------------------------------------------------------------------
_ingest_dir = pathlib.Path(__file__).parent.parent / "ingest"
for _plugin_path in sorted(_ingest_dir.glob("ds_*.py")):
    _module_name = f"app.ingest.{_plugin_path.stem}"
    try:
        importlib.import_module(_module_name)
    except Exception as _exc:
        import logging
        logging.getLogger(__name__).warning("Failed to load datasource plugin %s: %s", _module_name, _exc)

api_router = APIRouter()
api_router.include_router(ingest.router)
api_router.include_router(training.router)
api_router.include_router(utils.router)
api_router.include_router(datasources.router)
api_router.include_router(data.router)
