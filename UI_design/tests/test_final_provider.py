"""Local-only final pointers must never expose uncommitted or altered evidence."""
import tempfile
import unittest
from pathlib import Path
from topic16.contracts import write_json,sha256
from UI_design.backend.final_provider import read_final


class FinalPublicationContracts(unittest.TestCase):
    def test_absent_campaign_keeps_baseline_available(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);marker=root/'baseline.txt';marker.write_text('preserve')
            self.assertEqual(read_final(root,lambda *a:'/fixture',{})['status'],'unavailable')
            self.assertEqual(marker.read_text(),'preserve')

    def test_uncommitted_or_unknown_owner_report_is_isolated(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);up=root/'upgrade';directory=up/'artifacts/jobs/final/test'
            write_json(directory/'declaration.json',{'fixture':True})
            bad={'owner':'alien','path':'reports/test/report.json','sha256':'0'*64}
            write_json(directory/'state.json',{'phase':'test','status':'paused','scenes':[{'status':'computed','report':bad}],'stages':{}})
            write_json(up/'reports/final-index.json',{'study':'test','declaration':'artifacts/jobs/final/test/declaration.json',
                'declaration_sha256':sha256(directory/'declaration.json'),'state':'artifacts/jobs/final/test/state.json','reports':[bad]})
            result=read_final(root,lambda *a:'/fixture',{})
            self.assertEqual(result['scenes'],[]);self.assertIn('Unknown final reference owner',result['errors'][0]['reason'])
            write_json(directory/'declaration.json',{'fixture':'modified'})
            with self.assertRaisesRegex(ValueError,'declaration checksum'):read_final(root,lambda *a:'/fixture',{})
