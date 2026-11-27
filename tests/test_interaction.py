"""Tests for the interaction layer: keyboard simulation and event manager."""

import pygame
import pytest

from interaction.event_manager import EventManager
from interaction.keyboard_simulator import KeyboardSimulator


def make_key_event(key, event_type=pygame.KEYDOWN):
    ev = pygame.event.Event(event_type, key=key)
    return ev


def test_keyboard_simulator_left_right():
    sim = KeyboardSimulator({"left": "z", "right": "x"})
    assert sim.handle_event(make_key_event(pygame.K_z)) == "left"
    assert sim.handle_event(make_key_event(pygame.K_x)) == "right"
    assert sim.handle_event(make_key_event(pygame.K_a)) is None


def test_keyboard_simulator_debounce():
    sim = KeyboardSimulator({"left": "z", "right": "x"})
    assert sim.handle_event(make_key_event(pygame.K_z)) == "left"
    # Holding the key (repeat KEYDOWN without KEYUP) must not re-trigger.
    assert sim.handle_event(make_key_event(pygame.K_z)) is None
    sim.handle_event(make_key_event(pygame.K_z, pygame.KEYUP))
    assert sim.handle_event(make_key_event(pygame.K_z)) == "left"


def test_event_manager_poll_empty():
    settings = {"sim_keys": {"left": "z", "right": "x"},
                "remote_mode": "keyboard"}
    em = EventManager(settings)
    em.start()
    assert em.poll() == []
    em.stop()


def test_event_manager_sim_click():
    settings = {"sim_keys": {"left": "z", "right": "x"},
                "remote_mode": "keyboard"}
    em = EventManager(settings)
    em.start()
    button = em.handle_pygame_event(make_key_event(pygame.K_z))
    assert button == "left"
    em.stop()


def test_remote_key_mapping_normalisation():
    from interaction.remote import _key_name
    # pynput key objects expose .name or .char; test the fallback logic
    # with a tiny fake object.
    class FakeKey:
        name = "Page_Down"
    assert _key_name(FakeKey()) == "page_down"

    class FakeChar:
        char = "a"
    assert _key_name(FakeChar()) == "a"
