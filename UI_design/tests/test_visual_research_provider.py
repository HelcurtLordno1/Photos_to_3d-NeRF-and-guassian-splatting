"""Synthetic CPU publication contracts, never used as measured evidence."""
import tempfile
import unittest
from pathlib import Path
from topic16.contracts import write_json,sha256
from UI_design.backend.visual_research_provider import read_research


class VisualResearchProviderTests(unittest.TestCase):
    def test_unplanned_study_does_not_affect_baseline(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(read_research(Path(d),lambda p:'/test',{})['status'],'unavailable')

    def test_partial_study_does_not_publish_incomplete_cells(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);folder=root/'upgrade/artifacts/jobs/research/tea-research-v3'
            write_json(folder/'declaration.json',{'fixture':True})
            write_json(folder/'state.json',{'status':'paused','phase':'q15','stages':{},
                                         'declaration_sha256':sha256(folder/'declaration.json')})
            result=read_research(root,lambda p:'/test',{})
            self.assertEqual(result['status'],'paused');self.assertEqual(result['q15'],[])
            self.assertIsNone(result['q2'])

    def test_modified_declaration_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);folder=root/'upgrade/artifacts/jobs/research/tea-research-v3'
            write_json(folder/'declaration.json',{'fixture':True})
            write_json(folder/'state.json',{'status':'running','phase':'qa','stages':{},'declaration_sha256':'0'*64})
            with self.assertRaisesRegex(ValueError,'declaration changed'):read_research(root,lambda p:'/test',{})

    def test_modified_completed_evidence_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);folder=root/'upgrade/artifacts/jobs/research/tea-research-v3'
            write_json(folder/'declaration.json',{'fixture':True})
            path=root/'upgrade/reports/tea-research-v3/q15/report.json';write_json(path,{'rows':[]})
            write_json(folder/'state.json',{'status':'running','phase':'qa','declaration_sha256':sha256(folder/'declaration.json'),
                'stages':{'q15':{'references':[{'path':'reports/tea-research-v3/q15/report.json','sha256':'0'*64}]}}})
            with self.assertRaisesRegex(ValueError,'evidence changed'):read_research(root,lambda p:'/test',{})
