"""Offline coverage for public data selection and generated profile layout."""

import json
import re
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree as ET

import render


def repo(name="FitTrack", **overrides):
    return {"name": name, "private": False, "fork": False,
            "owner": {"login": render.USER}, "language": "Python",
            "stargazers_count": 2, "forks_count": 1, **overrides}


class ProfileRenderingTests(unittest.TestCase):
    def test_public_projects_exclude_forks_profile_private_and_other_owners(self):
        repos = [repo(), repo(render.USER), repo("Fork", fork=True),
                 repo("Private", private=True), repo("Other", owner={"login": "other"})]
        self.assertEqual(list(render.public_projects(repos)), ["FitTrack"])

    def test_public_repo_pagination_and_private_metadata_guard(self):
        with patch.object(render, "get", side_effect=[[repo()] * 100, [repo("Second")]]) as get:
            self.assertEqual(len(render.owned_repos()), 101)
            self.assertIn("page=2", get.call_args.args[0])
        with patch.object(render, "get", return_value=[repo(private=True)]):
            with self.assertRaisesRegex(ValueError, "PRIVATE_REPOSITORY_VISIBLE"):
                render.owned_repos()

    def test_language_bytes_aggregate_and_group_small_languages(self):
        languages = {f"Language{i}": i for i in range(1, 10)}
        with patch.object(render, "get", return_value=languages):
            shares = render.language_shares([repo(), repo("Second")])
        self.assertEqual(len(shares), 8)
        self.assertEqual(shares[0][0], "Language9")
        self.assertEqual(shares[-1][0], "Other")
        self.assertAlmostEqual(sum(share for _, share in shares), 1)
        with patch.object(render, "get", return_value={}):
            self.assertEqual(render.language_shares([repo()]), [])

    def test_generated_readme_references_complete_themed_svg_set(self):
        with patch.object(render, "get", return_value={"Python": 3, "Svelte": 1}):
            outputs, readme = render.render([repo()])
        references = set(re.findall(re.escape(render.IMAGES) + r'([^"\s<>]+\.svg)', readme))
        self.assertEqual(references, set(outputs) | set(render.SNAKES))
        self.assertEqual(readme.count(render.MOTTO), 1)
        self.assertIn(f'alt="{render.NAME}"', readme)
        self.assertIn(f'>{render.NAME}</text>', outputs["name-light.svg"])
        self.assertIn(f'>{render.NAME}</text>', outputs["name-dark.svg"])
        self.assertIn(f"https://github.com/{render.USER}/FitTrack", readme)
        self.assertNotIn("zeroherolin", readme)
        self.assertNotIn("stats-", readme)
        self.assertNotIn("mailto:", readme)
        self.assertNotIn("SCROLL", outputs["section-projects-light.svg"])
        self.assertEqual(readme.count('width="25%"'), 4)
        self.assertNotIn("COMMITS BEHIND", outputs["section-forks-light.svg"])
        self.assertNotIn("<a", render.forks_html())
        self.assertEqual(render.forks_html().count('alt=""'), 4)
        self.assertEqual(readme.count("<pre>"), 1)
        self.assertNotIn("</a>\n</pre>", readme)
        for name, content in outputs.items():
            root = ET.fromstring(content)
            self.assertGreater(float(root.attrib["height"]), 0, name)
            if not name.startswith("projects/"):
                continue
            descriptions = root.findall('.//{*}text[@class="s"]')
            self.assertLessEqual(len(descriptions), 3)
            for element in descriptions:
                self.assertLessEqual(render.sans_width(element.text, 12) * render.SLACK, 200)

    def test_stack_has_real_glyphs_and_no_overflow_in_both_themes(self):
        skills = {name for _, items in render.STACK for name, _ in items}
        self.assertTrue({"PI Simulation", "SI Simulation", "High-Speed Signals", "PCIe", "USB", "MIPI"}.issubset(skills))
        self.assertTrue({"MATLAB", "Python", "ARM", "FPGA", "Linux"}.issubset(skills))
        self.assertTrue({"PowerShell", "Svelte", "FastAPI", "ECharts", "HDF5", "Windows"}.isdisjoint(skills))
        for theme in render.THEMES.values():
            content = render.render_stack(theme)
            root = ET.fromstring(content)
            for element in root.findall(".//{*}text"):
                end = float(element.attrib["x"]) + render.mono_width(
                    element.text or "", float(element.attrib["font-size"]),
                    float(element.attrib.get("letter-spacing", 0)))
                self.assertLessEqual(end, render.WIDTH)
            for label, items in render.STACK:
                for name, glyph in items:
                    self.assertIn(name.replace("&", "&amp;"), content)
                    if not glyph.startswith("#"):
                        self.assertIn("<path", render.icon(glyph, 0, 0, 12, theme["muted"]))
        self.assertEqual(render.sans_width("真实", 12), 24)
        lines = render.wrap(render.MOTTO, 12, 100, 10)
        self.assertEqual(" ".join(lines), render.MOTTO)
        self.assertTrue(all(render.sans_width(line, 12) * render.SLACK <= 100 for line in lines))

    def test_empty_languages_and_xml_escaping(self):
        svg = render.render_languages([], render.THEMES["light"])
        self.assertIn("No public language data", svg)
        ET.fromstring(svg)
        svg = render.render_project("A&B", "App", '<unsafe> & "safe"', repo(), False,
                                    render.THEMES["dark"])
        ET.fromstring(svg)
        self.assertIn("&lt;unsafe&gt;", svg)
        self.assertIn("#3d444d", svg)

    def test_api_failure_does_not_replace_previous_generated_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            readme, dist = root / "README.md", root / "dist"
            dist.mkdir()
            readme.write_text("previous README")
            (dist / "assets.json").write_text('["previous.svg"]')
            error = urllib.error.URLError("fixture unavailable")
            with patch.object(render, "README", readme), patch.object(render, "BUILD", dist), \
                 patch.object(render, "owned_repos", return_value=[repo()]), \
                 patch.object(render, "get", side_effect=error):
                with self.assertRaises(urllib.error.URLError):
                    render.main()
            self.assertEqual(readme.read_text(), "previous README")
            self.assertEqual(json.loads((dist / "assets.json").read_text()), ["previous.svg"])


if __name__ == "__main__":
    unittest.main()
