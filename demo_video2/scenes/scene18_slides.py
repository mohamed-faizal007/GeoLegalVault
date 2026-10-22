"""Scene 18: summary, honest limits, future work, and ONE slide for the planned next version (no design details)."""
from common import *


def main(sc, browser):
    for key in ("a1", "b1", "c1", "d1"):
        sc.slide(key, key[0])


run_scene("scene18_slides", "Scene 18 - Summary and future work", "s18", main, headed=False)
