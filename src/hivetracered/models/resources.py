"""Own all models created during one asynchronous pipeline execution."""
from contextvars import ContextVar
from functools import wraps
import logging

logger = logging.getLogger(__name__)
_current_resources = ContextVar("hivetracered_model_resources", default=None)


class ModelResources:
    """Close models in their owning loop, including partially initialized models.

    Every Model allocated inside this context is registered automatically. A
    model created outside it remains the caller's responsibility. Nested scopes
    own only their newly created models; shared references are never closed twice.
    """
    def __init__(self):
        self._models = []
        self._token = None

    async def __aenter__(self):
        if self._token is not None:
            raise RuntimeError("ModelResources is already active")
        self._token = _current_resources.set(self)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        try:
            await self.aclose()
        except Exception:
            if exc is None:
                raise
            logger.exception("Model cleanup failed while handling a pipeline error")
        finally:
            _current_resources.reset(self._token)
            self._token = None

    async def aclose(self):
        models, self._models = self._models, []
        errors = []
        # Stop requests to every model before closing any transport.
        for model in reversed(models):
            try:
                await model._cancel_requests()
            except Exception as exc:
                errors.append(exc)
        for model in reversed(models):
            try:
                await model.aclose()
            except Exception as exc:
                logger.exception("Failed to close %s", type(model).__name__)
                errors.append(exc)
        if errors:
            raise errors[0]


def register_model(model):
    resources = _current_resources.get()
    if resources is not None:
        resources._models.append(model)


def with_model_resources(function):
    """Give a standalone runner call a scope, or reuse its enclosing run scope."""
    @wraps(function)
    async def scoped(*args, **kwargs):
        if _current_resources.get() is not None:
            return await function(*args, **kwargs)
        async with ModelResources():
            return await function(*args, **kwargs)
    return scoped
