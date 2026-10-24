"""Offline coverage for public data selection and generated profile layout."""

import json
import re
import tempfile
import unittest
import urllib.error
from pathlib import Path
from html.parser import HTMLParser
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
        with patch.object(render, "get", return_value={"Python": 3, "Svelte": 1}), \
             patch.object(render, "warn"):
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
        self.assertNotIn('width="25%"', readme)
        self.assertIn("COMMITS BEHIND", outputs["section-forks-light.svg"])
        self.assertNotIn("forks/blank.svg", outputs)
        self.assertNotIn("forks/_ai-agents-light.svg", outputs)
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
        self.assertEqual(skills, {
            "MATLAB", "Python", "TypeScript", "JavaScript", "HTML", "CSS", "SQLite",
            "ARM", "FPGA", "Linux", "Hardware", "Signal integrity", "Power design",
            "Git", "Node.js", "PI Simulation", "SI Simulation", "High-Speed Signals",
            "PCIe", "USB", "MIPI"
        })
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


class ForkGridParser(HTMLParser):
    def __init__(self, content):
        super().__init__()
        self.images = []
        self.links = []
        self.feed(content)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "img":
            self.images.append(attrs)
        elif tag == "a":
            self.links.append(attrs["href"])


class ForkRenderingTests(unittest.TestCase):
    def metadata(self, **overrides):
        return repo("dsh-purge", fork=True, default_branch="master", parent={
            "private": False, "full_name": "mmparko/dsh-purge",
            "owner": {"login": "mmparko"}, "default_branch": "master"
        }, **overrides)

    def test_agent_fork_link_count_themes_and_complete_image_references(self):
        def get(url):
            if url.endswith("/FitTrack/languages"):
                return {"Python": 10}
            if "/compare/" in url:
                return {"ahead_by": 0, "behind_by": 99}
            if url.endswith("/dsh-purge"):
                return self.metadata()
            self.fail(f"unexpected API request: {url}")

        with patch.object(render, "get", side_effect=get), patch.object(render, "warn"):
            outputs, readme = render.render([repo(), self.metadata()])
        references = set(re.findall(re.escape(render.IMAGES) + r'([^"\s<>]+\.svg)', readme))
        self.assertEqual(references, set(outputs) | set(render.SNAKES))
        self.assertEqual(readme.count('href="https://github.com/LinZzzzJ/dsh-purge"'), 1)
        self.assertIn("dsh-purge, a fork of mmparko/dsh-purge", readme)
        self.assertNotIn("placeholder", readme)
        for theme in render.THEMES:
            for filename in (f"forks/_ai-agents-{theme}.svg", f"forks/dsh-purge-{theme}.svg",
                             f"section-forks-{theme}.svg"):
                root = ET.fromstring(outputs[filename])
                labels = [t.text for t in root.findall(".//{*}text")]
                if "forks/_" in filename:
                    self.assertEqual(labels, ["AI AGENTS", "1"])
                elif "section-" in filename:
                    self.assertEqual(labels[:2], ["FORKS", "1"])
                    self.assertRegex(labels[2], r"COMMITS BEHIND UPSTREAM · \d{4}-\d{2}-\d{2}")
                else:
                    self.assertIn("up to date with upstream", outputs[filename])
            for filename, content in outputs.items():
                ET.fromstring(content)
        parsed = ForkGridParser(render.grid_html([(False, [("AI AGENTS", ["dsh-purge"])])], {}))
        self.assertEqual(len(parsed.images), 8)
        self.assertTrue(all(image["width"] == "25%" for image in parsed.images))
        self.assertEqual(sum(image["src"].endswith("blank.svg") for image in parsed.images), 6)

    def test_fork_categories_keep_config_order_skip_missing_and_collect_new_forks(self):
        config = [("Agent", ["second", "first", "missing"]), ("Empty", ["gone"])]
        with patch.object(render, "FORKS", config), patch.object(render, "warn") as warn:
            columns = render.fork_columns({"first", "second", "Zulu", "alpha"})
        self.assertEqual(columns, [("Agent", ["second", "first"]), ("Uncategorized", ["alpha", "Zulu"])])
        warnings = " ".join(str(call.args[0]) for call in warn.call_args_list)
        self.assertIn("missing", warnings)
        self.assertIn("gone", warnings)
        self.assertIn("Uncategorized", warnings)

    def test_new_forks_are_grouped_by_category_and_agent_is_renamed(self):
        def get(url):
            if url.endswith("/FitTrack/languages"):
                return {"Python": 10}
            if "/compare/" in url:
                return {"ahead_by": 0, "behind_by": 0}
            if url.endswith("/dsh-purge"):
                return self.metadata()
            if url.endswith("/openGym_FitTrack"):
                return {"name": "openGym_FitTrack", "private": False, "fork": True,
                        "owner": {"login": render.USER}, "default_branch": "main",
                        "parent": {"private": False, "full_name": "DuarteSantos8/openGym",
                                   "owner": {"login": "DuarteSantos8"}, "default_branch": "main"}}
            if url.endswith("/hindsight_linzzzzj"):
                return {"name": "hindsight_linzzzzj", "private": False, "fork": True,
                        "owner": {"login": render.USER}, "default_branch": "main",
                        "parent": {"private": False, "full_name": "vectorize-io/hindsight",
                                   "owner": {"login": "vectorize-io"}, "default_branch": "main"}}
            if url.endswith("/brushgraft_enhance"):
                return {"name": "brushgraft_enhance", "private": False, "fork": True,
                        "owner": {"login": render.USER}, "default_branch": "main",
                        "parent": {"private": False, "full_name": "zeroherolin/brushgraft",
                                   "owner": {"login": "zeroherolin"}, "default_branch": "main"}}
            self.fail(f"unexpected API request: {url}")

        with patch.object(render, "get", side_effect=get):
            outputs, readme = render.render([
                repo(), self.metadata(),
                repo("openGym_FitTrack", fork=True, default_branch="main", parent={
                    "private": False, "full_name": "DuarteSantos8/openGym",
                    "owner": {"login": "DuarteSantos8"}, "default_branch": "main"}),
                repo("hindsight_linzzzzj", fork=True, default_branch="main", parent={
                    "private": False, "full_name": "vectorize-io/hindsight",
                    "owner": {"login": "vectorize-io"}, "default_branch": "main"}),
                repo("brushgraft_enhance", fork=True, default_branch="main", parent={
                    "private": False, "full_name": "zeroherolin/brushgraft",
                    "owner": {"login": "zeroherolin"}, "default_branch": "main"})
            ])
        self.assertIn('href="https://github.com/LinZzzzJ/openGym_FitTrack"', readme)
        self.assertIn("openGym_FitTrack, a fork of DuarteSantos8/openGym", readme)
        self.assertIn('href="https://github.com/LinZzzzJ/hindsight_linzzzzj"', readme)
        self.assertIn("hindsight_linzzzzj, a fork of vectorize-io/hindsight", readme)
        self.assertIn('href="https://github.com/LinZzzzJ/brushgraft_enhance"', readme)
        self.assertIn("brushgraft_enhance, a fork of zeroherolin/brushgraft", readme)
        self.assertIn("AI AGENTS", outputs["forks/_ai-agents-light.svg"])
        self.assertIn(">2</text>", outputs["forks/_ai-agents-light.svg"])
        self.assertIn("up to date with upstream", outputs["forks/hindsight_linzzzzj-light.svg"])
        self.assertIn("VIBECODING APP", outputs["forks/_vibecoding-app-light.svg"])
        self.assertIn(">2</text>", outputs["forks/_vibecoding-app-light.svg"])
        self.assertIn("up to date with upstream", outputs["forks/brushgraft_enhance-light.svg"])
        self.assertIn("up to date with upstream", outputs["forks/openGym_FitTrack-light.svg"])
        self.assertNotIn("forks/_agent-light.svg", outputs)
        references = set(re.findall(re.escape(render.IMAGES) + r'([^"\s<>]+\.svg)', readme))
        self.assertEqual(references, set(outputs) | set(render.SNAKES))

    def test_four_column_blocks_and_row_major_categories(self):
        columns = [("Agent", ["a1", "a2"]), ("Hardware", ["h1"]),
                   ("Data", ["d1"]), ("Tools", ["t1"]), ("More", ["m1"]),
                   ("Uncategorized", ["u1", "u2", "u3", "u4", "u5"]),
                   ("Learning", ["l1", "l2", "l3", "l4"])]
        blocks = render.grid_blocks(columns)
        self.assertEqual([wide for wide, _ in blocks], [False, False, True, True])
        self.assertEqual([block[0][0] for _, block in blocks], ["Agent", "More", "Learning", "Uncategorized"])
        parsed = ForkGridParser(render.grid_html(blocks, {}))
        self.assertEqual(len(parsed.images) % 4, 0)
        self.assertTrue(all(image["width"] == "25%" for image in parsed.images))
        self.assertEqual(parsed.links[:6], [f"https://github.com/{render.USER}/{name}"
                                          for name in ("a1", "h1", "d1", "t1", "a2", "m1")])
        self.assertEqual(parsed.links[-9:], [f"https://github.com/{render.USER}/{name}"
                                            for name in ("l1", "l2", "l3", "l4", "u1", "u2", "u3", "u4", "u5")])

    def test_no_unused_padding_asset_for_full_grid_and_private_forks_excluded(self):
        config = [(f"Category{i}", [f"fork{i}"]) for i in range(4)]
        owned = [repo()] + [repo(f"fork{i}", fork=True) for i in range(4)]
        owned += [repo("private-fork", fork=True, private=True),
                  repo("other-fork", fork=True, owner={"login": "other"})]
        with patch.object(render, "FORKS", config), \
             patch.object(render, "language_shares", return_value=[]), \
             patch.object(render, "fork_status", return_value=(None, None)) as status:
            outputs, readme = render.render(owned)
        self.assertEqual(status.call_count, 4)
        self.assertNotIn("forks/blank.svg", outputs)
        self.assertNotIn("blank.svg", readme)
        self.assertNotIn("private-fork", readme)
        self.assertNotIn("other-fork", readme)
        references = set(re.findall(re.escape(render.IMAGES) + r'([^"\s<>]+\.svg)', readme))
        self.assertEqual(references, set(outputs) | set(render.SNAKES))

    def test_sync_comparison_direction_branch_escaping_and_invalid_counts(self):
        data = self.metadata()
        data["default_branch"] = "work/branch"
        data["parent"]["default_branch"] = "upstream/main"
        with patch.object(render, "get", side_effect=[data, {"ahead_by": 5, "behind_by": 123}]) as get:
            self.assertEqual(render.fork_status("dsh-purge"), ("mmparko/dsh-purge", 5))
        self.assertTrue(get.call_args.args[0].endswith("/compare/work%2Fbranch...mmparko:upstream%2Fmain"))
        for count in (-1, None, True, "5"):
            with self.subTest(count=count), patch.object(render, "warn"), \
                 patch.object(render, "get", side_effect=[self.metadata(), {"ahead_by": count}]):
                self.assertEqual(render.fork_status("dsh-purge"), ("mmparko/dsh-purge", None))

    def test_unavailable_parent_and_compare_keep_card_and_do_not_block_other_forks(self):
        data = self.metadata()
        del data["parent"]
        missing_parent = self.metadata()
        missing_parent["parent"] = None
        failures = [([data], None), ([missing_parent], None), ([None], None),
                    ([urllib.error.URLError("network unavailable")], None),
                    ([self.metadata(), urllib.error.URLError("compare unavailable")], "mmparko/dsh-purge")]
        for responses, upstream in failures:
            with self.subTest(upstream=upstream), patch.object(render, "get", side_effect=responses), \
                 patch.object(render, "warn") as warn:
                self.assertEqual(render.fork_status("dsh-purge"), (upstream, None))
                warn.assert_called_once()
        with patch.object(render, "FORKS", [("Agent", ["dsh-purge", "second"])]), \
             patch.object(render, "language_shares", return_value=[]), \
             patch.object(render, "fork_status", side_effect=lambda name: (None, None) if name == "dsh-purge" else ("upstream/second", 0)):
            outputs, readme = render.render([repo(), repo("dsh-purge", fork=True), repo("second", fork=True)])
        self.assertIn("sync status unavailable", outputs["forks/dsh-purge-light.svg"])
        self.assertIn("up to date with upstream", outputs["forks/second-light.svg"])
        self.assertIn('href="https://github.com/LinZzzzJ/dsh-purge"', readme)

    def test_status_glyphs_counts_and_long_name_truncation_in_both_themes(self):
        for theme in render.THEMES.values():
            for behind, glyph, title in ((0, "check", "up to date with upstream"),
                                         (1234, "arrow-down", "1234 commits behind upstream"),
                                         (None, "x", "sync status unavailable")):
                long_name = "a-very-long-fork-name-that-cannot-fit"
                svg = render.render_fork(long_name, behind, theme)
                root = ET.fromstring(svg)
                self.assertIn(title, root.attrib["aria-label"])
                self.assertIn(render.icon(glyph, 0, 0, 12, "unused").split(">", 1)[1].rsplit("</g>", 1)[0], svg)
                name = root.findall(".//{*}text")[-1]
                self.assertTrue(name.text.endswith("…"))
                self.assertLess(float(name.attrib["x"]) + render.mono_width(name.text, 12), 177)
                if behind:
                    self.assertIn(">1.2k</text>", svg)


if __name__ == "__main__":
    unittest.main()
