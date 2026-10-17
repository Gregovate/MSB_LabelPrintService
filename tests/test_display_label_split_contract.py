"""Static regression tests for Display one-line/two-line routing."""

from __future__ import annotations

import ast
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[1]
SERVICE_SOURCE = ROOT / "label_poll_service_v4.py"
SQL_DIR = ROOT / "sql"
TEMPLATE_DIR = ROOT / "templates" / "pt_p950nw"


def expected_split(display_name: str) -> tuple[str, str]:
    """Model the governed PostgreSQL split for concrete regression cases."""
    parts = display_name.split("-", 2)
    if len(parts) == 3 and parts[0] and parts[1]:
        return f"{parts[0]}-{parts[1]}", f"-{parts[2]}"
    return display_name, ""


class DisplayLabelSplitContractTests(unittest.TestCase):
    def test_24mm_two_line_template_has_distinct_required_objects(self) -> None:
        template_path = TEMPLATE_DIR / "QR_label_2_line_horz_24mm.lbx"

        with zipfile.ZipFile(template_path) as template:
            label_xml = template.read("label.xml")

        root = ElementTree.fromstring(label_xml)
        object_names = [
            element.attrib["objectName"]
            for element in root.iter()
            if "objectName" in element.attrib
        ]

        self.assertCountEqual(
            object_names,
            ["objQr", "objLine1", "objLine2"],
        )
        self.assertEqual(len(object_names), len(set(object_names)))

    def test_short_standard_names_are_two_line(self) -> None:
        self.assertEqual(
            expected_split("GG-Elden-20-03"),
            ("GG-Elden", "-20-03"),
        )
        self.assertEqual(
            expected_split("GG-Elden-20-04"),
            ("GG-Elden", "-20-04"),
        )
        self.assertEqual(
            expected_split("GG-EldenV2-30-01"),
            ("GG-EldenV2", "-30-01"),
        )

    def test_names_without_standard_split_remain_one_line(self) -> None:
        self.assertEqual(
            expected_split("CL-LollipopTrailerNetLights"),
            ("CL-LollipopTrailerNetLights", ""),
        )

    def test_snapshot_queries_do_not_use_character_count_for_layout(self) -> None:
        for filename in (
            "display_snapshot_v4.sql",
            "display_snapshot.sql",
            "display_labels_in_progress.sql",
        ):
            with self.subTest(filename=filename):
                sql = (SQL_DIR / filename).read_text(encoding="utf-8")
                self.assertNotIn("LENGTH(d.display_name) <= 20", sql)
                self.assertIn("d.display_name ~ '^[^-]+-[^-]+-'", sql)
                self.assertIn("END AS line1", sql)
                self.assertIn("END AS line2", sql)

    def test_preflight_counts_use_the_same_structure_rule(self) -> None:
        source = SERVICE_SOURCE.read_text(encoding="utf-8")
        tree = ast.parse(source)
        functions = {
            node.name: ast.get_source_segment(source, node) or ""
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
            and node.name in {
                "pending_display_families",
                "pending_display_preflight_plan",
            }
        }

        self.assertEqual(
            set(functions),
            {"pending_display_families", "pending_display_preflight_plan"},
        )
        for name, function_source in functions.items():
            with self.subTest(function=name):
                self.assertNotIn("LENGTH(d.display_name)", function_source)
                self.assertIn("d.display_name !~ '^[^-]+-[^-]+-'", function_source)
                self.assertIn("d.display_name ~ '^[^-]+-[^-]+-'", function_source)


if __name__ == "__main__":
    unittest.main()
