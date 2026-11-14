"""Read-only checks for the module evidence cards under docs/evidence_cards.

Added to the standard unittest suite on 2026-11-15 so that every full run of
`python -m unittest discover -s tests` also re-checks the deliverables:
source-id integrity, citation counts, the percentage / percentage-point
arithmetic, and the README database description.

Rules for this module (do not break them):
  * ASCII-only source and ASCII-only console output, so a GBK console on
    Windows can never raise UnicodeEncodeError.
  * No absolute path outside the repository. The external 20.7 MB database
    copy is never opened; only REPO/data/app.db is read, read-only.
  * Never writes to the deliverables, the database, or any other file.
  * Never let a failed assertion dump Chinese text into the console; use
    assertTrue/assertFalse with an ASCII message instead of assertIn.
"""

from __future__ import annotations

import csv
import io
import os
import re
import sqlite3
import sys
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
CARDS_DIR = REPO / "docs" / "evidence_cards"
CARDS_MD = CARDS_DIR / "module_evidence_cards_v0.1.md"
CARDS_CSV = CARDS_DIR / "module_evidence_cards_v0.1.csv"
MATRIX_CSV = CARDS_DIR / "source_matrix_v0.1.csv"
AUDIT_MD = CARDS_DIR / "module_audit_v0.1.md"
SIM_CSV = REPO / "data" / "simulation" / "lizaso_maize_1991_summary.csv"
README_MD = REPO / "README.md"
REPO_DB = REPO / "data" / "app.db"

# Aliases used inside source_matrix_v0.1.csv reference_location, and the
# Chinese keywords this module has to recognise. They are written as
# escapes so this file stays pure ASCII.
CARD_MD_ALIAS = "\u8bc1\u636e\u5361.md"
CARD_CSV_ALIAS = "\u8bc1\u636e\u5361.csv"
AUDIT_MD_ALIAS = "\u5ba1\u8ba1.md"
YES = "\u662f"
NO = "\u5426"
NOT_CITED = "\u8bc1\u636e\u5361\u672a\u5f15\u7528"
PRELOADED = "\u5df2\u9884\u8f7d"
NOT_PRELOADED = "\u672a\u9884\u8f7d"
HISTORY_EMPTY = "\u8ba1\u7b97\u5386\u53f2\u4e3a\u7a7a"
PP_UNIT = "\u4e2a\u767e\u5206\u70b9"
MISS_RATE = "\u6f0f\u62a5"
DB_HEADING = "\u6570\u636e\u5e93\u9ed8\u8ba4\u4f4d\u7f6e"

ARCHIVED_WRONG = re.compile(r"\u300c[^\u300d]*\u300d")
PERCENT_RE = re.compile(r"[-+\u2212]?\d+(?:\.\d+)?\s*%")
PP_RE = re.compile(r"(\d+(?:\.\d+)?)\s*" + PP_UNIT)
SENSITIVITY_TRAP = (34.7, 35.0, 41.7, 42.0)

# Personal path fragments and SQL write keywords are assembled from parts so
# that this file does not contain them verbatim.
FORBIDDEN_FRAGMENTS = tuple(
    "".join(parts)
    for parts in (("360", "Move", "Data"), ("Use", "rs"), ("Leno", "vo"), ("Desk", "top"))
)
FORBIDDEN_SQL = tuple(
    "".join(parts)
    for parts in (("INS", "ERT "), ("UPDA", "TE "), ("DELE", "TE "), ("DRO", "P "))
)
USER_DIR = "Us" + "ers"

# Audit headings for the two remediation tables (Chinese, kept as escapes).
DISPLAY_HEADING = "### \u4fee\u6539\uff08\u4e0d\u6539\u7b97\u6cd5\uff0c\u4e0d\u6539\u8f93\u5165\u63a5\u53e3\uff09"
INTERFACE_HEADING = "### \u4fee\u6539\u8f93\u5165\u63a5\u53e3"
INTERFACE_ITEMS = frozenset({"F01b", "F05a", "F13", "F16"})

# The four Lizaso scenarios: name -> (simulated relative loss %, observed
# relative loss %, gap in percentage points, relative yield deviation %).
LIZASO = {
    "Exp4_1991_WL_early_4d": (-28.53, -45.38, 16.85, 26.28),
    "Exp4_1991_WL_late_4d": (-28.75, -48.66, 19.91, 33.94),
    "Exp4_1991_WL_early_8d": (-46.97, -49.02, 2.05, 0.39),
    "Exp4_1991_WL_late_8d": (-45.78, -48.62, 2.84, 1.85),
}


def read_text(path: Path) -> str:
    with io.open(path, encoding="utf-8") as handle:
        return handle.read()


def read_csv_rows(path: Path) -> list[list[str]]:
    with io.open(path, encoding="utf-8", newline="") as handle:
        return list(csv.reader(handle))


def split_ids(value: str) -> list[str]:
    return [tok for tok in re.split(r"[;,\u3001\s]+", value.strip()) if tok]


def parse_reference_location(location: str) -> list[tuple[str, int]]:
    """Return (file_key, line_number) pairs cited by one reference_location.

    Line numbers are 1-based file lines; for the evidence CSV line 1 is the
    header row. An alias applies to the following parts until another alias
    appears.
    """
    alias_map = {
        CARD_MD_ALIAS: "cards_md",
        CARD_CSV_ALIAS: "cards_csv",
        AUDIT_MD_ALIAS: "audit_md",
    }
    found: list[tuple[str, int]] = []
    alias = None
    for part in re.split(r"[;\uff1b]\s*|\s+\+\s+", location):
        part = part.strip()
        if not part:
            continue
        match = re.match(r"^(\S+\.(?:md|csv))\s+(.*)$", part)
        if match:
            alias = alias_map.get(match.group(1))
            if alias is None:
                continue
            rest = match.group(2)
        else:
            rest = part
        if alias is None:
            continue
        for number in re.findall(r"L(\d+)", rest):
            found.append((alias, int(number)))
    return found


class EvidenceCardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.matrix_rows = read_csv_rows(MATRIX_CSV)
        cls.matrix_header = cls.matrix_rows[0]
        cls.matrix = [dict(zip(cls.matrix_header, row)) for row in cls.matrix_rows[1:]]
        cls.evidence_rows = read_csv_rows(CARDS_CSV)
        cls.evidence_header = cls.evidence_rows[0]
        cls.evidence = [
            dict(zip(cls.evidence_header, row)) for row in cls.evidence_rows[1:]
        ]
        cls.cards_md_lines = read_text(CARDS_MD).splitlines()
        cls.audit_md_lines = read_text(AUDIT_MD).splitlines()
        cls.readme = read_text(README_MD)

    # --- helpers ---------------------------------------------------------

    def line_of(self, file_key: str, number: int) -> str:
        if file_key == "cards_md":
            return self.cards_md_lines[number - 1]
        if file_key == "audit_md":
            return self.audit_md_lines[number - 1]
        return ",".join(self.evidence_rows[number - 1])

    def deliverables(self) -> list[tuple[str, str]]:
        units: list[tuple[str, str]] = []
        for index, line in enumerate(self.cards_md_lines, start=1):
            units.append(("cards_md:%d" % index, line))
        for index, line in enumerate(self.audit_md_lines, start=1):
            units.append(("audit_md:%d" % index, line))
        for index, row in enumerate(self.evidence_rows, start=1):
            units.append(("cards_csv:%d" % index, ",".join(row)))
        for index, row in enumerate(self.matrix_rows, start=1):
            units.append(("matrix_csv:%d" % index, ",".join(row)))
        return units

    # --- 1. source id integrity ------------------------------------------

    def test_evidence_source_ids_exist_in_matrix(self) -> None:
        matrix_ids = {row["source_id"] for row in self.matrix}
        missing = []
        for row in self.evidence:
            for token in split_ids(row["source_id"]):
                if token not in matrix_ids:
                    missing.append((row["module_id"], row["source_id"], token))
        self.assertEqual(
            [],
            missing,
            "evidence.source_id not found in source_matrix.source_id: %s" % missing,
        )

    def test_source_matrix_ids_are_unique(self) -> None:
        ids = [row["source_id"] for row in self.matrix]
        duplicates = sorted({item for item in ids if ids.count(item) > 1})
        self.assertEqual([], duplicates, "duplicate source_id: %s" % duplicates)

    # --- 2. used flag matches the real citations -------------------------

    def test_used_flag_matches_actual_citations(self) -> None:
        problems = []
        for row in self.matrix:
            source_id = row["source_id"]
            used = row["used_in_evidence_cards"]
            location = row["reference_location"]
            refs = parse_reference_location(location)
            card_refs = [ref for ref in refs if ref[0] in ("cards_md", "cards_csv")]
            if used not in (YES, NO):
                problems.append((source_id, "used flag is neither yes nor no"))
                continue
            if used == YES and not card_refs:
                problems.append((source_id, "marked as used but no card citation"))
            if used == NO and card_refs:
                problems.append((source_id, "marked as unused but cites the cards"))
            if used == NO and NOT_CITED not in location:
                problems.append((source_id, "unused row does not say cards not cited"))
            for file_key, number in refs:
                if number < 1:
                    problems.append((source_id, "line number below 1"))
                    continue
                try:
                    line = self.line_of(file_key, number)
                except IndexError:
                    problems.append(
                        (source_id, "line %d out of range in %s" % (number, file_key))
                    )
                    continue
                if file_key in ("cards_md", "cards_csv") and source_id not in line:
                    problems.append(
                        (
                            source_id,
                            "cited line %d in %s lacks the id" % (number, file_key),
                        )
                    )
        self.assertEqual([], problems, "citation problems: %s" % problems[:10])

    # --- 3. dynamic counts ------------------------------------------------

    def test_citation_counts_are_consistent(self) -> None:
        md_ids = set(re.findall(r"S\d\d", read_text(CARDS_MD)))
        csv_ids: set[str] = set()
        for row in self.evidence:
            csv_ids.update(split_ids(row["source_id"]))
        union = md_ids | csv_ids
        used_ids = {
            row["source_id"] for row in self.matrix if row["used_in_evidence_cards"] == YES
        }
        unused_ids = {
            row["source_id"] for row in self.matrix if row["used_in_evidence_cards"] == NO
        }
        print(
            "\n[evidence-cards] matrix rows=%d cited-in-cards-md=%d "
            "cited-in-cards-csv=%d union=%d marked-used=%d marked-unused=%d"
            % (
                len(self.matrix),
                len(md_ids),
                len(csv_ids),
                len(union),
                len(used_ids),
                len(unused_ids),
            )
        )
        self.assertEqual(union, used_ids, "cited ids and rows marked as used differ")
        self.assertEqual(set(), union & unused_ids, "id both cited and marked unused")
        self.assertEqual(
            len(self.matrix),
            len(used_ids) + len(unused_ids),
            "used flags are not exhaustive",
        )

    # --- 4. APSIM arithmetic ---------------------------------------------

    def test_apsim_relative_bias_formula(self) -> None:
        rows = read_csv_rows(SIM_CSV)
        header = rows[0]
        by_name = {row[header.index("simulation_name")]: row for row in rows[1:]}
        for name, (sim_pct, obs_pct, gap_pp, bias_pct) in LIZASO.items():
            self.assertIn(name, by_name, "scenario %s missing" % name)
            row = by_name[name]
            sim_yield = float(row[header.index("simulated_yield_kg_ha")])
            obs_yield = float(row[header.index("observed_yield_kg_ha")])
            stated_bias = float(row[header.index("simulation_minus_observed_pct")])
            stated_sim = float(
                row[header.index("simulated_yield_relative_to_control_pct")]
            )
            stated_obs = float(
                row[header.index("observed_yield_relative_to_control_pct")]
            )
            recomputed_bias = (sim_yield - obs_yield) / obs_yield * 100.0
            self.assertAlmostEqual(
                recomputed_bias, stated_bias, places=2, msg="%s bias column" % name
            )
            self.assertAlmostEqual(
                recomputed_bias, bias_pct, places=1, msg="%s bias 26.28/33.94" % name
            )
            self.assertAlmostEqual(stated_sim, sim_pct, places=2, msg="%s sim %%" % name)
            self.assertAlmostEqual(stated_obs, obs_pct, places=2, msg="%s obs %%" % name)
            self.assertAlmostEqual(
                abs(obs_pct - sim_pct), gap_pp, places=2, msg="%s gap in points" % name
            )

    def test_apsim_gap_and_bias_are_stated_separately(self) -> None:
        text = ARCHIVED_WRONG.sub("", "\n".join(line for _, line in self.deliverables()))
        for _, (_, _, gap_pp, bias_pct) in LIZASO.items():
            self.assertTrue(
                "%.2f" % gap_pp in text,
                "gap %.2f is not stated in the deliverables" % gap_pp,
            )
            self.assertTrue(
                "%.2f%%" % bias_pct in text, "bias %.2f%% is not stated" % bias_pct
            )
        for bias in (26.28, 33.94, 0.39, 1.85):
            self.assertIsNone(
                re.search(r"%.2f\s*%s" % (bias, PP_UNIT), text),
                "relative deviation %.2f%% is written as percentage points" % bias,
            )

    # --- 5. percentage points --------------------------------------------

    def test_percentage_point_claims_match_relative_percents(self) -> None:
        problems = []
        for where, raw in self.deliverables():
            text = ARCHIVED_WRONG.sub("", raw)
            claims = [float(value) for value in PP_RE.findall(text)]
            if not claims:
                continue
            percents = [percent_value(match.group(0)) for match in PERCENT_RE.finditer(text)]
            for claim in claims:
                if not any(
                    abs(abs(a - b) - claim) < 0.06 for a in percents for b in percents
                ):
                    problems.append((where, claim, percents))
        self.assertEqual(
            [],
            problems,
            "percentage-point claims without a matching pair of percents: %s" % problems[:5],
        )

    def test_miss_rate_is_not_mixed_with_sensitivity(self) -> None:
        problems = []
        for where, raw in self.deliverables():
            text = ARCHIVED_WRONG.sub("", raw)
            if MISS_RATE not in text:
                continue
            for match in PERCENT_RE.finditer(text):
                value = percent_value(match.group(0))
                if any(abs(value - trap) < 0.05 for trap in SENSITIVITY_TRAP):
                    problems.append((where, value))
        self.assertEqual([], problems, "sensitivity used as miss rate: %s" % problems[:5])

    # --- 6. encoding and paths -------------------------------------------

    def test_deliverables_are_utf8_and_module_output_is_ascii(self) -> None:
        for path in (CARDS_MD, CARDS_CSV, MATRIX_CSV, AUDIT_MD, README_MD, SIM_CSV):
            with self.subTest(path=path.name):
                path.read_bytes().decode("utf-8")
        source = Path(__file__).read_text(encoding="utf-8")
        self.assertTrue(source.isascii(), "test module must stay ASCII for GBK consoles")

    def test_no_personal_absolute_paths(self) -> None:
        source = Path(__file__).read_text(encoding="utf-8")
        self.assertIsNone(
            re.search(r"[A-Za-z]:[\\/]", source),
            "hardcoded absolute path in the test module",
        )
        for fragment in FORBIDDEN_FRAGMENTS:
            self.assertTrue(
                fragment not in source, "personal path fragment in the test module"
            )
        self.assertIsNone(
            re.search(r"[A-Za-z]:\\" + USER_DIR + r"\\", self.readme),
            "personal absolute path in README",
        )

    def test_only_the_repository_database_is_read(self) -> None:
        default_db = default_database_path()
        self.assertEqual(
            REPO_DB.resolve(),
            default_db,
            "the default database is not the repository one",
        )
        self.assertTrue(REPO_DB.exists(), "repository database missing")
        self.assertLess(
            REPO_DB.stat().st_size,
            5 * 1024 * 1024,
            "repository database looks like the large external copy",
        )
        source = Path(__file__).read_text(encoding="utf-8")
        for statement in FORBIDDEN_SQL:
            self.assertTrue(
                statement not in source, "the check must stay read-only"
            )
        self.assertTrue(
            "mode=ro" in source, "the database must be opened read-only"
        )

    # --- 8. remediation table structure ----------------------------------

    def test_interface_changes_are_not_listed_as_display_only(self) -> None:
        text = "\n".join(self.audit_md_lines)

        def section(pattern: str) -> str:
            match = re.search(
                re.escape(pattern) + r"[^\n]*\n(.*?)(?=\n### |\n## |\Z)", text, re.S
            )
            return match.group(1) if match else ""

        display = set(re.findall(r"^\|\s*(F\d+[ab]?)\s*\|", section(DISPLAY_HEADING), re.M))
        interface = set(
            re.findall(r"^\|\s*(F\d+[ab]?)\s*\|", section(INTERFACE_HEADING), re.M)
        )
        self.assertTrue(display, "the display-only remediation table is empty")
        self.assertTrue(interface, "the interface-change remediation table is empty")
        self.assertEqual(
            set(), display & interface, "a remediation item is in both tables"
        )
        self.assertTrue(
            INTERFACE_ITEMS.issubset(interface),
            "interface-changing items missing from the interface table: %s"
            % sorted(INTERFACE_ITEMS - interface),
        )
        self.assertEqual(
            set(), INTERFACE_ITEMS & display, "interface-changing item listed as display only"
        )

    # --- 9. README database description ----------------------------------

    def test_readme_database_path_and_preload_state(self) -> None:
        default_db = default_database_path()
        block = re.search(
            DB_HEADING + r"[^\n]*\n\s*```text\s*\n(.+?)\n```", self.readme, re.S
        )
        self.assertTrue(block is not None, "README has no default database path block")
        stated = block.group(1).strip()
        if re.match(r"^[A-Za-z]:", stated):
            self.assertEqual(default_db, Path(stated).resolve(), "README path mismatch")
        else:
            self.assertEqual(
                default_db, (REPO / stated).resolve(), "README path mismatch"
            )

        counts = {}
        connection = sqlite3.connect("file:%s?mode=ro" % REPO_DB.as_posix(), uri=True)
        try:
            for table in ("field_observations", "external_records", "assessment_runs"):
                counts[table] = connection.execute(
                    'SELECT COUNT(*) FROM "%s"' % table
                ).fetchone()[0]
        finally:
            connection.close()

        for table in ("field_observations", "external_records"):
            match = re.search(r"`%s=(\d+)`" % table, self.readme)
            self.assertTrue(match is not None, "README does not state %s" % table)
            self.assertEqual(
                counts[table],
                int(match.group(1)),
                "README %s count differs from the database" % table,
            )
        if counts["field_observations"] == 0:
            self.assertTrue(
                NOT_PRELOADED in self.readme, "README must say the database is not preloaded"
            )
        else:
            self.assertTrue(
                PRELOADED in self.readme, "README must say the database is preloaded"
            )
        if counts["assessment_runs"] > 0:
            self.assertTrue(
                HISTORY_EMPTY not in self.readme,
                "README claims an empty history while the database has runs",
            )


def percent_value(token: str) -> float:
    """Turn a matched percentage token into a float (-28.53% -> -28.53)."""
    cleaned = token.replace(" ", "").replace("\u2212", "-").rstrip("%")
    return float(cleaned)


def default_database_path() -> Path:
    """The database storage.py opens by default.

    Other tests in this suite set FLOOD_APP_DB_PATH to a temporary file, so
    the built-in default is taken from DATA_DIR instead of the environment.
    """
    sys.path.insert(0, str(REPO))
    try:
        import storage
    finally:
        sys.path.pop(0)
    built_in = (Path(storage.DATA_DIR) / "app.db").resolve()
    if not os.environ.get("FLOOD_APP_DB_PATH"):
        assert Path(storage.DEFAULT_DB_PATH).resolve() == built_in
    return built_in


if __name__ == "__main__":
    unittest.main()
