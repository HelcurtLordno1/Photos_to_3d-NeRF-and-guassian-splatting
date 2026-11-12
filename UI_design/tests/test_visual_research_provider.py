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

    def test_repaired_inspection_uses_its_own_committed_proof(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);up=root/'upgrade';reference=up/'artifacts/jobs/research/tea-research-v4'
            write_json(reference/'declaration.json',{'fixture':True})
            write_json(reference/'state.json',{'status':'succeeded','phase':'complete','stages':{},
                'declaration_sha256':sha256(reference/'declaration.json')})
            directory=up/'artifacts/jobs/confirmation/test'
            write_json(directory/'declaration.json',{'spec':{'ReferenceStudy':'tea-research-v4'}})
            path=up/'reports/test/inspection-r4.json'
            write_json(path,{'status':'passed','checks':{'renderer_parity':True},'viewer_encoding':'packed-ext','results':[]})
            state={'study':'test','status':'paused','phase':'review','stages':{
                'inspection-report':[{'path':'reports/test/original.json','sha256':'0'*64}],
                'inspection-repair-r4':[{'path':'reports/test/inspection-r4.json','sha256':sha256(path)}]}}
            write_json(directory/'state.json',state)
            write_json(up/'reports/confirmation-index.json',{'declaration':'artifacts/jobs/confirmation/test/declaration.json',
                'declaration_sha256':sha256(directory/'declaration.json'),'state':'artifacts/jobs/confirmation/test/state.json',
                'inspection':'reports/test/inspection-r4.json','report':'reports/test/report.json'})
            result=read_research(root,lambda p:'/test',{})
            self.assertEqual(result['inspection']['viewer_encoding'],'packed-ext')
            write_json(path,{'status':'passed','checks':{},'results':[]})
            with self.assertRaisesRegex(ValueError,'Inspection report changed'):read_research(root,lambda p:'/test',{})
