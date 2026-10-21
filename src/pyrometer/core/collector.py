"""Collector interface and the name-based registry."""

from __future__ import annotations

from typing import Callable, Protocol, TypeVar, runtime_checkable

from pyrometer.core.sample import Sample


class CollectorUnavailable(RuntimeError):
    """Raised by a collector factory when it cannot run here.

    For example the GPU collector raises this when ``nvidia-ml-py`` is not
    installed or no NVIDIA driver is present.
    """


@runtime_checkable
class Collector(Protocol):
    """Anything with a ``name`` and a ``collect()`` method is a collector.

    ``collect`` receives the timestamp to stamp on its samples so every
    sample from one sampler tick shares the same time.
    """

    name: str

    def collect(self, timestamp: float) -> list[Sample]: ...


CollectorFactory = Callable[[], Collector]
F = TypeVar("F", bound=CollectorFactory)


class Registry:
    """Maps collector names to factories that build them."""

    def __init__(self) -> None:
        self._factories: dict[str, CollectorFactory] = {}

    def register(self, name: str) -> Callable[[F], F]:
        def decorator(factory: F) -> F:
            if name in self._factories:
                raise ValueError(f"collector {name!r} is already registered")
            self._factories[name] = factory
            return factory

        return decorator

    def names(self) -> list[str]:
        return sorted(self._factories)

    def create(self, name: str) -> Collector:
        try:
            factory = self._factories[name]
        except KeyError:
            known = ", ".join(self.names()) or "none"
            raise KeyError(f"unknown collector {name!r} (known: {known})") from None
        return factory()

    def create_available(
        self, names: list[str] | None = None
    ) -> tuple[list[Collector], dict[str, str]]:
        """Build the named collectors (all registered ones by default).

        Returns the collectors that could be built and a mapping of
        name -> reason for those that are unavailable here.
        """
        built: list[Collector] = []
        skipped: dict[str, str] = {}
        for name in names if names is not None else self.names():
            try:
                built.append(self.create(name))
            except CollectorUnavailable as exc:
                skipped[name] = str(exc)
        return built, skipped


registry = Registry()
