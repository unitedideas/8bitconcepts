import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('research_index', Path(__file__).with_name('generate-research-index.py'))
index = importlib.util.module_from_spec(spec)
spec.loader.exec_module(index)

class IndexTests(unittest.TestCase):
    def page(self, root, slug, date='2026-04-01', canonical=None):
        url = canonical or 'https://8bitconcepts.com/research/' + slug + '.html'
        Path(root, slug+'.html').write_text('<title>Example | 8bitconcepts</title><meta content="A team\'s work &amp; results" name="description"><link rel="canonical" href="'+url+'"><script type="application/ld+json">{"datePublished":"'+date+'"}</script>')

    def test_complete_ordered_index_preserves_tags_and_decodes_description(self):
        with tempfile.TemporaryDirectory() as root:
            self.page(root,'new','2026-09-01')
            self.page(root,'old')
            Path(root,'overview.html').write_text('not an article')
            rows=index.build_papers(Path(root),[{'slug':'old','tags':['governance']}])
            self.assertEqual([r['slug'] for r in rows],['old','new'])
            self.assertEqual(rows[0]['tags'],['governance'])
            self.assertEqual(rows[0]['summary'],"A team's work & results")
            self.assertEqual(rows[1]['date_published'],'2026-09-01')
            self.assertEqual(rows,index.build_papers(Path(root),rows))

    def test_missing_metadata_does_not_get_invented_date(self):
        with tempfile.TemporaryDirectory() as root:
            Path(root,'broken.html').write_text('<title>Missing date</title>')
            with self.assertRaises(ValueError):index.build_papers(Path(root),[])

    def test_offsite_canonical_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            self.page(root,'outside',canonical='https://example.org/')
            with self.assertRaises(ValueError):index.build_papers(Path(root),[])

    def test_empty_directory_is_not_a_successful_empty_index(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValueError):index.build_papers(Path(root),[])

    def test_feed_preserves_publication_date_and_xml_characters(self):
        import contextlib
        import io
        import json
        import shutil
        import xml.etree.ElementTree as ET
        spec = importlib.util.spec_from_file_location('pipeline', Path(__file__).resolve().parent.parent / 'research-pipeline.py')
        pipeline = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(pipeline)
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            (root/'research').mkdir()
            (root/'tools').mkdir()
            self.page(root/'research', 'sample', '2026-04-01')
            (root/'research.json').write_text(json.dumps({'papers':[]}))
            shutil.copy(Path(__file__).with_name('generate-research-index.py'),root/'tools/generate-research-index.py')
            pipeline.SCRIPT_DIR = root
            with contextlib.redirect_stdout(io.StringIO()):
                pipeline.update_feed_xml(None,None)
            item=ET.parse(root/'feed.xml').find('./channel/item')
            self.assertIn('01 Apr 2026',item.findtext('pubDate'))
            self.assertEqual(item.findtext('description'),"A team's work & results")

    def test_current_manifest_still_repairs_site_totals_without_changing_prices(self):
        import contextlib
        import io
        import json
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'research').mkdir()
            self.page(root / 'research', 'sample')
            (root / 'research/index.html').write_text('directory page')
            (root / 'research/overview.html').write_text('overview page')
            papers = index.build_papers(root / 'research', [])
            manifest = {'papers': papers, 'total': 1, 'updated_at': 'unchanged'}
            (root / 'research.json').write_text(json.dumps(manifest))
            pages = [root / name for name in ('index.html', 'work-with-us.html', 'case-studies.html', '404.html')]
            for page in pages:
                page.write_text('<span data-research-count>49</span> articles. Price $49.')
            previous = index.ROOT
            index.ROOT = root
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    index.main()
                for page in pages:
                    self.assertEqual(page.read_text(), '<span data-research-count>1</span> articles. Price $49.')
                self.assertEqual(json.loads((root / 'research.json').read_text()), manifest)
                mtimes = [page.stat().st_mtime_ns for page in pages]
                with contextlib.redirect_stdout(io.StringIO()):
                    index.main()
                self.assertEqual([page.stat().st_mtime_ns for page in pages], mtimes)
            finally:
                index.ROOT = previous

if __name__=='__main__':unittest.main()
