"""Exercise the app callback without executing app startup or database access."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest


class NavigationTests(unittest.TestCase):
    def callback(self, state):
        source = Path(__file__).resolve().parents[2] / "app.py"
        tree = ast.parse(source.read_text(encoding="utf-8-sig"))
        function = next(node for node in tree.body
                        if isinstance(node, ast.FunctionDef)
                        and node.name == "select_navigation")
        namespace = {
            "st": SimpleNamespace(session_state=state),
            "NAVIGATION_WIDGET_KEYS": ("diagnostic_navigation", "gis_navigation"),
        }
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), "exec"), namespace)
        return namespace["select_navigation"]

    def test_empty_missing_or_stale_selection_preserves_navigation(self):
        for value in (None, "obsolete", "missing"):
            with self.subTest(value=value):
                state = {"active_page": "Base histórica electoral", "gis_navigation": "History"}
                if value != "missing":
                    state["diagnostic_navigation"] = value
                previous = state.copy()
                self.callback(state)("diagnostic_navigation", {"Motor": "Motor de indicadores"})
                self.assertEqual(state, previous)

    def test_valid_selection_changes_page_and_clears_other_group(self):
        state = {"active_page": "Inicio", "diagnostic_navigation": "Motor",
                 "gis_navigation": "History"}
        callback = self.callback(state)
        callback("diagnostic_navigation", {"Motor": "Motor de indicadores"})
        self.assertEqual(state["active_page"], "Motor de indicadores")
        self.assertEqual(state["diagnostic_navigation"], "Motor")
        self.assertIsNone(state["gis_navigation"])
        callback("gis_navigation", {"History": "Base histórica electoral"})
        self.assertEqual(state["active_page"], "Motor de indicadores")
