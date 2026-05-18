"""Tests for process bottleneck analysis."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.ontology.generate_processes import write_processes
from scripts.ontology.process_config_loader import load_all_process_configs
from scripts.ontology.process_models import BottleneckSeverity, StageType
from ontology_query import LocalVaultReader, ProcessSearch
from ontology_query.process_index import ProcessIndex

_CONFIGS = load_all_process_configs()
LOAN_ORIGINATION = _CONFIGS["loan-origination"]


def _make_vault() -> tuple[Path, str]:
    tmpdir = tempfile.mkdtemp()
    write_processes(Path(tmpdir))
    return Path(tmpdir), tmpdir


class TestProcessModels(unittest.TestCase):
    def test_total_stages(self):
        self.assertEqual(len(LOAN_ORIGINATION.stages), 18)

    def test_sequential_stages(self):
        seq = LOAN_ORIGINATION.sequential_stages
        self.assertEqual(len(seq), 12)

    def test_stage_types(self):
        par = [s for s in LOAN_ORIGINATION.stages if s.stage_type == StageType.PARALLEL]
        pc = [s for s in LOAN_ORIGINATION.stages if s.stage_type == StageType.POST_CLOSE]
        self.assertEqual(len(par), 3)
        self.assertEqual(len(pc), 3)

    def test_cycle_time_positive(self):
        self.assertGreater(LOAN_ORIGINATION.total_cycle_time_days, 0)

    def test_throughput(self):
        self.assertGreater(LOAN_ORIGINATION.throughput, 0)
        self.assertLess(LOAN_ORIGINATION.throughput, 1000)

    def test_volume_funnel_consistency(self):
        seq = LOAN_ORIGINATION.sequential_stages
        for i in range(1, len(seq)):
            prev_exit = seq[i - 1].metrics.exit_count
            curr_entry = seq[i].metrics.entry_count
            self.assertLessEqual(curr_entry, prev_exit,
                                 f"Stage {seq[i].name} entry > prev exit")

    def test_bottleneck_stages(self):
        bottlenecks = LOAN_ORIGINATION.bottleneck_stages
        self.assertEqual(len(bottlenecks), 3)
        names = [s.name for s in bottlenecks]
        self.assertIn("Credit Underwriting", names)
        self.assertIn("Compliance", names)
        self.assertIn("Doc Prep", names)

    def test_critical_bottleneck_first(self):
        bottlenecks = LOAN_ORIGINATION.bottleneck_stages
        self.assertEqual(bottlenecks[0].metrics.bottleneck_severity, BottleneckSeverity.CRITICAL)

    def test_drop_off_rate(self):
        qual = LOAN_ORIGINATION.stages[0]
        self.assertAlmostEqual(qual.metrics.drop_off_rate, 0.4, places=2)

    def test_all_stages_have_entities(self):
        for stage in LOAN_ORIGINATION.stages:
            self.assertTrue(len(stage.involved_entities) > 0,
                            f"Stage {stage.name} has no entities")


class TestProcessGeneration(unittest.TestCase):
    def test_write_processes_stats(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            stats = write_processes(Path(tmpdir))
            self.assertEqual(stats["processes"], 1)
            self.assertEqual(stats["stages"], 18)

    def test_process_file_exists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            write_processes(Path(tmpdir))
            self.assertTrue((Path(tmpdir) / "processes" / "loan-origination.md").exists())

    def test_process_index_exists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            write_processes(Path(tmpdir))
            idx_path = Path(tmpdir) / "_meta" / "process_index.json"
            self.assertTrue(idx_path.exists())
            data = json.loads(idx_path.read_text())
            self.assertIn("loan-origination", data)

    def test_frontmatter_parseable(self):
        from ontology_query.frontmatter import parse_frontmatter
        with tempfile.TemporaryDirectory() as tmpdir:
            write_processes(Path(tmpdir))
            content = (Path(tmpdir) / "processes" / "loan-origination.md").read_text()
            fm, body = parse_frontmatter(content)
            self.assertEqual(fm["process_id"], "loan-origination")
            self.assertEqual(fm["total_stages"], 18)
            self.assertEqual(fm["data_source"], "synthetic")

    def test_frontmatter_bottlenecks(self):
        from ontology_query.frontmatter import parse_frontmatter
        with tempfile.TemporaryDirectory() as tmpdir:
            write_processes(Path(tmpdir))
            content = (Path(tmpdir) / "processes" / "loan-origination.md").read_text()
            fm, _ = parse_frontmatter(content)
            bns = fm.get("top_bottlenecks", [])
            self.assertEqual(len(bns), 3)
            self.assertEqual(bns[0]["stage"], "Credit Underwriting")
            self.assertEqual(bns[0]["severity"], "critical")

    def test_process_index_entity_participation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            write_processes(Path(tmpdir))
            data = json.loads((Path(tmpdir) / "_meta" / "process_index.json").read_text())
            entry = data["loan-origination"]
            self.assertIn("entity_participation", entry)
            self.assertIn("LLC_BI__Loan__c", entry["entity_participation"])


class TestProcessIndex(unittest.TestCase):
    def test_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            write_processes(Path(tmpdir))
            reader = LocalVaultReader(Path(tmpdir))
            idx = ProcessIndex(reader)
            entry = idx.get("loan-origination")
            self.assertIsNotNone(entry)
            self.assertEqual(entry.label, "Loan Origination")
            self.assertEqual(entry.stage_count, 18)

    def test_list_all(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            write_processes(Path(tmpdir))
            reader = LocalVaultReader(Path(tmpdir))
            idx = ProcessIndex(reader)
            entries = idx.list_all()
            self.assertEqual(len(entries), 1)

    def test_entity_lookup(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            write_processes(Path(tmpdir))
            reader = LocalVaultReader(Path(tmpdir))
            idx = ProcessIndex(reader)
            procs = idx.get_processes_for_entity("LLC_BI__Loan__c")
            self.assertIn("loan-origination", procs)

    def test_missing_process(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            write_processes(Path(tmpdir))
            reader = LocalVaultReader(Path(tmpdir))
            idx = ProcessIndex(reader)
            self.assertIsNone(idx.get("nonexistent"))


class TestProcessSearch(unittest.TestCase):
    def test_list_processes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            write_processes(Path(tmpdir))
            reader = LocalVaultReader(Path(tmpdir))
            ps = ProcessSearch(reader)
            procs = ps.list_processes()
            self.assertEqual(len(procs), 1)
            self.assertEqual(procs[0]["name"], "loan-origination")

    def test_get_process(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            write_processes(Path(tmpdir))
            reader = LocalVaultReader(Path(tmpdir))
            ps = ProcessSearch(reader)
            proc = ps.get_process("loan-origination")
            self.assertIsNotNone(proc)
            self.assertEqual(proc.label, "Loan Origination")
            self.assertEqual(proc.total_stages, 18)

    def test_get_process_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            write_processes(Path(tmpdir))
            reader = LocalVaultReader(Path(tmpdir))
            ps = ProcessSearch(reader)
            self.assertIsNone(ps.get_process("nonexistent"))

    def test_get_bottlenecks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            write_processes(Path(tmpdir))
            reader = LocalVaultReader(Path(tmpdir))
            ps = ProcessSearch(reader)
            bns = ps.get_bottlenecks("loan-origination")
            self.assertEqual(len(bns), 3)
            self.assertEqual(bns[0].severity, "critical")
            self.assertEqual(bns[0].stage_name, "Credit Underwriting")

    def test_bottleneck_has_entities(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            write_processes(Path(tmpdir))
            reader = LocalVaultReader(Path(tmpdir))
            ps = ProcessSearch(reader)
            bns = ps.get_bottlenecks("loan-origination")
            for bn in bns:
                self.assertTrue(len(bn.entities) > 0, f"{bn.stage_name} has no entities")

    def test_bottleneck_has_reason(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            write_processes(Path(tmpdir))
            reader = LocalVaultReader(Path(tmpdir))
            ps = ProcessSearch(reader)
            bns = ps.get_bottlenecks("loan-origination")
            for bn in bns:
                self.assertTrue(len(bn.reason) > 0, f"{bn.stage_name} has no reason")

    def test_get_stage(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            write_processes(Path(tmpdir))
            reader = LocalVaultReader(Path(tmpdir))
            ps = ProcessSearch(reader)
            stage = ps.get_stage("loan-origination", "Credit Underwriting")
            self.assertIsNotNone(stage)
            self.assertEqual(stage.avg_days, 5.0)
            self.assertEqual(stage.p90_days, 10.0)
            self.assertTrue(stage.is_bottleneck)

    def test_get_stage_case_insensitive(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            write_processes(Path(tmpdir))
            reader = LocalVaultReader(Path(tmpdir))
            ps = ProcessSearch(reader)
            stage = ps.get_stage("loan-origination", "credit underwriting")
            self.assertIsNotNone(stage)

    def test_get_stage_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            write_processes(Path(tmpdir))
            reader = LocalVaultReader(Path(tmpdir))
            ps = ProcessSearch(reader)
            self.assertIsNone(ps.get_stage("loan-origination", "Nonexistent Stage"))

    def test_get_process_flow(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            write_processes(Path(tmpdir))
            reader = LocalVaultReader(Path(tmpdir))
            ps = ProcessSearch(reader)
            flow = ps.get_process_flow("loan-origination")
            self.assertIsNotNone(flow)
            self.assertEqual(len(flow), 18)
            self.assertEqual(flow[0].order, 1)
            self.assertEqual(flow[0].name, "Qualification")

    def test_get_entity_stages(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            write_processes(Path(tmpdir))
            reader = LocalVaultReader(Path(tmpdir))
            ps = ProcessSearch(reader)
            stages = ps.get_entity_stages("Loan")
            self.assertGreater(len(stages), 5)
            stage_names = [s["stage"] for s in stages]
            self.assertIn("Credit Underwriting", stage_names)

    def test_compliance_stage_metrics(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            write_processes(Path(tmpdir))
            reader = LocalVaultReader(Path(tmpdir))
            ps = ProcessSearch(reader)
            stage = ps.get_stage("loan-origination", "Compliance")
            self.assertIsNotNone(stage)
            self.assertEqual(stage.error_rate, 0.15)
            self.assertTrue(stage.is_bottleneck)


if __name__ == "__main__":
    unittest.main()
