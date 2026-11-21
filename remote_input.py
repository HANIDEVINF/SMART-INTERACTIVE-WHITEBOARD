"""remote_input.py - Lecture de la telecommande (2 boutons = 2 touches clavier HID).

La telecommande se comporte comme un clavier : Next ~ PageDown, Previous ~ PageUp (en general).
Les codes reels sont mesures avec identify_keys.py et enregistres dans keymap.json.
  Next     -> "left"  (clic gauche)
  Previous -> "right" (clic droit)
"""
import json
import os
import queue
import time
import config as C


class RemoteInput:
    def __init__(self):
        km = dict(C.DEFAULT_KEYMAP)
        if os.path.exists(C.KEYMAP_FILE):
            with open(C.KEYMAP_FILE) as f:
                km.update(json.load(f))
        self.codes = {"left": set(km["left_codes"]), "right": set(km["right_codes"])}
        self.names = {"left": set(km["left_names"]), "right": set(km["right_names"])}
        self.q = queue.Queue()
        self.last = {"left": 0.0, "right": 0.0}
        self.listener = None
        if C.REMOTE_BACKEND == "pynput":
            self._start_pynput()

    def _start_pynput(self):
        try:
            from pynput import keyboard
        except ImportError:
            print("pynput non installe : pip install pynput (ou REMOTE_BACKEND='opencv')")
            return

        def on_press(key):
            name = key.char if getattr(key, "char", None) else str(key).replace("Key.", "")
            for ev in ("left", "right"):
                if name in self.names[ev]:
                    self.q.put(ev)

        self.listener = keyboard.Listener(on_press=on_press)
        self.listener.start()

    def poll(self, cv_key=-1):
        """Retourne la liste d'evenements ("left"/"right") depuis le dernier appel."""
        events = []
        if C.REMOTE_BACKEND == "opencv" and cv_key not in (-1, None):
            for ev in ("left", "right"):
                if cv_key in self.codes[ev]:
                    events.append(ev)
        while not self.q.empty():
            events.append(self.q.get())
        now, out = time.time(), []
        for ev in events:                       # anti-rebond / anti-repetition
            if now - self.last[ev] >= C.CLICK_DEBOUNCE:
                self.last[ev] = now
                out.append(ev)
        return out

    def stop(self):
        if self.listener:
            self.listener.stop()