"""FEATURE: teaching content - a small lesson loaded from assets/lesson/lesson.json.

Page types:
  {"type": "text",  "title": "...", "bullets": ["...", "..."]}
  {"type": "image", "title": "...", "image": "relative/path.png", "caption": "..."}
  {"type": "draw",  "title": "...", "prompt": "..."}          (blank area to annotate)
The annotation layer (DrawingCanvas) is shared by all pages.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np


@dataclass
class Page:
    type: str
    title: str = ""
    bullets: List[str] = field(default_factory=list)
    image: Optional[str] = None
    caption: str = ""
    prompt: str = ""


class Lesson:
    def __init__(self, path: str):
        self.base = os.path.dirname(path)
        self.title = "Lesson"
        self.pages: List[Page] = []
        self.idx = 0
        self._images = {}
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            self.title = data.get("title", self.title)
            self.pages = [Page(**p) for p in data.get("pages", [])]
        if not self.pages:
            self.pages = [Page("text", "Empty lesson", ["Add pages to assets/lesson/lesson.json"])]

    @property
    def page(self) -> Page:
        return self.pages[self.idx]

    def next(self) -> bool:
        if self.idx < len(self.pages) - 1:
            self.idx += 1
            return True
        return False

    def prev(self) -> bool:
        if self.idx > 0:
            self.idx -= 1
            return True
        return False

    def restart(self):
        self.idx = 0

    def image_for(self, page: Page) -> Optional[np.ndarray]:
        if not page.image:
            return None
        if page.image not in self._images:
            import cv2
            p = os.path.normpath(os.path.join(self.base, page.image))
            self._images[page.image] = cv2.imread(p, cv2.IMREAD_COLOR) if os.path.exists(p) else None
        return self._images[page.image]
