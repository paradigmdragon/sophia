from .analysis import RoughCutAnalyzer
from .rendering import RoughCutRenderer

class RoughCutEngine:
    def __init__(self):
        self.analyzer = RoughCutAnalyzer()
        self.renderer = RoughCutRenderer()
