"""Screen stack: push / back / home / reset."""
from __future__ import annotations

from typing import Callable, Dict, List

from .base import Screen


class Navigator:
    def __init__(self, ctx, factories: Dict[str, Callable[[], Screen]], root: str = "menu"):
        self.ctx = ctx
        self.factories = factories
        self.root = root
        self.stack: List[Screen] = []
        ctx.nav = self
        self.push(root)

    @property
    def current(self) -> Screen:
        return self.stack[-1]

    def push(self, name: str):
        scr = self.factories[name]()
        self.stack.append(scr)
        scr.on_enter(self.ctx)

    def back(self):
        if len(self.stack) > 1:
            self.stack.pop().on_exit(self.ctx)
            self.current.on_enter(self.ctx)
        else:
            self.ctx.toast("Already at the main menu")

    def home(self):
        """Return to the main menu (state of the features is kept)."""
        while len(self.stack) > 1:
            self.stack.pop().on_exit(self.ctx)
        menu = self.current
        if hasattr(menu, "go_root"):
            menu.go_root(self.ctx)

    def reset(self):
        """Back to the main menu AND restore every feature to its initial state."""
        self.home()
        self.ctx.build_features()
        self.ctx.toast("Application reset")
