"""strategies/ 폴더의 모든 모듈을 자동 스캔하여 registry를 구성한다."""

import importlib
import inspect
import pkgutil
from typing import Any

from .base import Action, Signal, Strategy, StrategyContext


REGISTRY: dict[str, type[Strategy]] = {}


def _discover() -> None:
    for _, module_name, _ in pkgutil.iter_modules(__path__):
        if module_name == 'base':
            continue
        module = importlib.import_module(f'.{module_name}', __package__)
        for _, cls in inspect.getmembers(module, inspect.isclass):
            if issubclass(cls, Strategy) and cls is not Strategy and cls.name:
                REGISTRY[cls.name] = cls


_discover()


def get_strategy(name: str, params: dict[str, Any]) -> Strategy:
    if name not in REGISTRY:
        raise KeyError(f"등록되지 않은 전략: '{name}'. 사용 가능: {list(REGISTRY)}")
    return REGISTRY[name](params)


def list_strategies() -> list[dict[str, Any]]:
    return [
        {
            'name': cls.name,
            'display_name': cls.display_name or cls.name,
            'supported_markets': list(cls.supported_markets),
            'params_schema': dict(cls.params_schema),
        }
        for cls in REGISTRY.values()
    ]


__all__ = [
    'REGISTRY',
    'Action',
    'Signal',
    'Strategy',
    'StrategyContext',
    'get_strategy',
    'list_strategies',
]
