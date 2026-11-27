"""Keyboard simulation of the presentation remote.

When no physical remote is available the same two click actions are
triggered with ordinary keys while the Pygame window is focused:

    Z  -> left click
    X  -> right click

(the keys are configurable in settings.json under ``sim_keys``).

Both this module and :class:`interaction.remote.RemoteListener` feed the
same :class:`interaction.event_manager.EventManager`, so switching between
physical and simulated remote requires no GUI changes.
"""

from __future__ import annotations

import pygame


def _pygame_key_code(name: str):
    """Map a config key name to a pygame key constant.

    Pygame names letter keys lowercase (K_z) but named keys uppercase
    without separators (K_PAGEDOWN, K_SPACE).  Single characters map to
    K_<char>; everything else maps to K_<NAME_WITHOUT_UNDERSCORES>.
    """
    if len(name) == 1:
        return getattr(pygame, f"K_{name}", None)
    return getattr(pygame, "K_" + name.replace("_", "").upper(), None)


class KeyboardSimulator:
    """Translates configured Pygame key presses into click buttons."""

    def __init__(self, key_map: dict):
        """key_map: {"left": "z", "right": "x"} (single-character names)."""
        self.key_map = {k: str(v).lower() for k, v in key_map.items()}
        self._pygame_keys = {
            button: _pygame_key_code(name)
            for button, name in self.key_map.items()
        }
        self._pressed: set[int] = set()

    def handle_event(self, event: pygame.event.Event):
        """Feed every Pygame event; returns a button name or None."""
        if event.type == pygame.KEYDOWN and event.key not in self._pressed:
            self._pressed.add(event.key)
            for button, k in self._pygame_keys.items():
                if k is not None and event.key == k:
                    return button
        elif event.type == pygame.KEYUP:
            self._pressed.discard(event.key)
        return None
