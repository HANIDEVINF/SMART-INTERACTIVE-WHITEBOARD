"""FEATURE: teaching content - a small lesson loaded from assets/lesson/lesson.json.

Page types:
  {"type": "text",  "title": "...", "bullets": ["...", "..."]}
  {"type": "image", "title": "...", "image": "relative/path.png", "caption": "..."}
  {"type": "draw",  "title": "...", "prompt": "..."}          (blank area to annotate)
  {"type": "quiz",  "title": "...", "question": "...", "options": ["a","b","c"], "answer": 1}
Every page has its own annotation layer (DrawingCanvas).  Quiz answers are remembered.
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
    question: str = ""
    options: List[str] = field(default_factory=list)
    answer: int = 0


class Lesson:
    def __init__(self, path: str):
        self.base = os.path.dirname(path)
        self.title = "Lesson"
        self.pages: List[Page] = []
        self.idx = 0
        self._images = {}
        self.chosen = {}                       # page index -> option chosen in a quiz page
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
        self.chosen = {}

    def goto_first(self, kind: str) -> bool:
        """Jump to the first page of a given type (e.g. the quiz)."""
        for i, p in enumerate(self.pages):
            if p.type == kind:
                self.idx = i
                return True
        return False

    def choose(self, option: int) -> bool:
        """Answer the quiz on the current page (once).  Returns True if it was correct."""
        if self.page.type != "quiz" or self.idx in self.chosen:
            return False
        self.chosen[self.idx] = option
        return option == self.page.answer

    @property
    def score(self):
        """(correct answers, number of quiz pages)"""
        quiz = [i for i, p in enumerate(self.pages) if p.type == "quiz"]
        return sum(1 for i in quiz if self.chosen.get(i) == self.pages[i].answer), len(quiz)

    def image_for(self, page: Page) -> Optional[np.ndarray]:
        if not page.image:
            return None
        if page.image not in self._images:
            import cv2
            p = os.path.normpath(os.path.join(self.base, page.image))
            self._images[page.image] = cv2.imread(p, cv2.IMREAD_COLOR) if os.path.exists(p) else None
        return self._images[page.image]
