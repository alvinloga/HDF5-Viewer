"""Callback dispatch adapters used to marshal task events."""

from __future__ import annotations

from collections.abc import Callable
from typing import ParamSpec, TypeVar

P = ParamSpec("P")
R = TypeVar("R")


class CallbackDispatcher:
    """Injectable callback dispatcher.

    The default dispatcher runs callbacks immediately. GUI integrations can pass a
    `post` function that enqueues the zero-argument callback onto the GUI thread.
    """

    def __init__(
        self,
        post: Callable[[Callable[[], None]], None] | None = None,
    ) -> None:
        self._post = post or (lambda callback: callback())

    def dispatch(
        self,
        callback: Callable[P, R],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> None:
        def run() -> None:
            callback(*args, **kwargs)

        self._post(run)
