"""Scene 1: the problem and the idea (title card is added by assemble.py; these are two narrated slides)."""
from common import *


def main(sc, browser):
    for key in ("a1", "a2", "a3"):
        sc.slide(key, "a")
    for key in ("b1", "b2", "b3", "b4", "b5", "b6", "b7"):
        sc.slide(key, "b")


run_scene("scene01_slides", "Scene 1 - The problem and the idea", "s01", main, headed=False)
