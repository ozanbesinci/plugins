"""Offline archive and transaction regression tests; no company documents or network."""
import importlib.util
import io
import json
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import teklif_paket_legacy as u
spec=importlib.util.spec_from_file_location('offer_update',Path(__file__).resolve().parents[1]/'scripts/teklif-guncelle.py')
o=importlib.util.module_from_spec(spec);spec.loader.exec_module(o)

def package(release='3.0.1',schema=1,versions=None,additions=None,rewrite=None):
    versions=versions or {x:release for x in (u.SKILLS[:1] if schema==3 else u.SKILLS)}
    files={}
    for name,v in versions.items():
        files[f'skills/{name}/SKILL.md']=f'---\nname: {name}\ndescription: Fixture\nmetadata:\n  version: "{v}"\n---\nFixture\n'.encode()
        files[f'skills/{name}/VERSION']=(v+'\n').encode()
        files[f'skills/{name}/CHANGELOG.md']=f'# Changes\n\n## v{v}\nFixture\n'.encode()
    files.update(additions or {})
    manifest={'schema':schema,'repository':u.REPO,'version':release,'files':{k:u.sha(v) for k,v in files.items()}}
    if schema in (2,3):manifest.update(versioning='independent/v1',skill_versions=versions)
    entries={**files,u.MANIFEST:json.dumps(manifest).encode()}
    if rewrite: rewrite(entries)
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w') as z:
        for k,v in entries.items():
            if isinstance(v,zipfile.ZipInfo):z.writestr(v,b'link')
            else:z.writestr(k,v)
    data=stream.getvalue();return data,u.sha(data)

class ArchiveTests(unittest.TestCase):
    def test_three_schemas(self):
        for schema in (1,2,3):
            with self.subTest(schema=schema):
                m,_=u.validate_archive(*package(schema=schema));self.assertEqual(m['schema'],schema)
    def test_hash_mismatch(self):
        data,_=package()
        with self.assertRaises(u.UpdateError):u.validate_archive(data,'0'*64)
    def test_release_mismatch(self):
        with self.assertRaises(u.UpdateError):u.validate_archive(*package(),'3.0.2')
    def test_semver(self):
        self.assertGreater(u.version('3.10.0'),u.version('3.9.99'))
        for v in ('3.0.1-beta','03.0.1','3.0',None,'main'):
            with self.subTest(v=v),self.assertRaises(u.UpdateError):u.version(v)
    def test_unsafe_paths(self):
        for suffix in ('../bad','x/../../bad','NUL.txt','COM¹.txt','bad.','bad ','A:B','a\\b','a?b','/absolute','a//b'):
            with self.subTest(suffix=suffix),self.assertRaises(u.UpdateError):
                u.validate_archive(*package(additions={'skills/'+u.SKILLS[0]+'/'+suffix:b'x'}))
    def test_case_collision(self):
        with self.assertRaises(u.UpdateError):u.validate_archive(*package(additions={'skills/'+u.SKILLS[0]+'/version':b'x'}))
    def test_unicode_collision(self):
        prefix='skills/'+u.SKILLS[0]+'/'
        with self.assertRaises(u.UpdateError):u.validate_archive(*package(additions={prefix+'café':b'x',prefix+'cafe\u0301':b'y'}))
    def test_file_directory_collision(self):
        prefix='skills/'+u.SKILLS[0]+'/'
        with self.assertRaises(u.UpdateError):u.validate_archive(*package(additions={prefix+'a':b'x',prefix+'a/b':b'y'}))
    def test_symlink(self):
        link=zipfile.ZipInfo('skills/'+u.SKILLS[0]+'/link');link.external_attr=(stat.S_IFLNK|0o777)<<16
        with self.assertRaises(u.UpdateError):u.validate_archive(*package(rewrite=lambda e:e.update({link.filename:link})))
    def test_manifest_mismatch(self):
        with self.assertRaises(u.UpdateError):u.validate_archive(*package(rewrite=lambda e:e.update({'skills/'+u.SKILLS[0]+'/VERSION':b'bad'})))
    def test_schema3_cannot_add_other_skill(self):
        with self.assertRaises(u.UpdateError):u.validate_archive(*package(schema=3,additions={'skills/'+u.SKILLS[1]+'/other.py':b'x'}))
    def test_expanded_and_download_and_count_limits(self):
        data,digest=package()
        for name in ('MAX_EXPANDED','MAX_DOWNLOAD','MAX_FILES'):
            with patch.object(u,name,1),self.subTest(limit=name),self.assertRaises(u.UpdateError):u.validate_archive(data,digest)
    def test_header_crlf(self):
        additions={f'skills/{name}/SKILL.md':f'---\r\nname: {name}\r\nmetadata:\r\n  version: "3.0.1"\r\n---\r\n'.encode() for name in u.SKILLS}
        self.assertEqual(u.validate_archive(*package(additions=additions))[0]['version'],'3.0.1')
    def test_v4_missing_runtime(self):
        with self.assertRaises(u.UpdateError):u.validate_archive(*package('4.0.0',schema=3))
    def test_bounded_replace_retry(self):
        with patch.object(u.os,'replace',side_effect=PermissionError('fixture')) as m,patch.object(u.time,'sleep'):
            with self.assertRaises(PermissionError):u.replace_path('a','b')
            self.assertEqual(m.call_count,5)
    def test_reject_foreign_http_and_invalid_port(self):
        for url in ('http://github.com/a','https://evil.example/a','https://github.com@evil.example/a','https://github.com:444/a','https://github.com:bad/a'):
            self.assertFalse(u.allowed_url(url))

class OfferTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)/'skills'
    def install(self,v='3.0.1'):
        return o.apply(self.root,*package(v),v,v)
    def test_fresh_install_only_offer(self):
        self.assertEqual(self.install()['status'],'installed')
        self.assertTrue((self.root/u.SKILLS[0]).is_dir());self.assertFalse((self.root/u.SKILLS[1]).exists())
    def test_upgrade_and_verify(self):
        self.install();self.install('3.0.2');self.assertEqual(o.state_for(self.root)['version'],'3.0.2')
        self.assertTrue(any(self.root.glob('.teklif-backup-*/old/VERSION')))
    def test_pinned_component_rejected(self):
        with self.assertRaises(u.UpdateError):o.apply(self.root,*package(),'3.0.1','3.0.2')
        self.assertFalse(self.root.exists())
    def test_bad_hash_no_mutation(self):
        self.install();before=o.tree(self.root);data,_=package('3.0.2')
        with self.assertRaises(u.UpdateError):o.apply(self.root,data,'0'*64,'3.0.2','3.0.2')
        self.assertEqual(o.tree(self.root),before)
    def test_downgrade_and_same_version_rejected(self):
        self.install('3.0.2')
        for v in ('3.0.2','3.0.1'):
            with self.subTest(v=v),self.assertRaises(u.UpdateError):self.install(v)
    def test_unmanaged_tree_preserved(self):
        folder=self.root/o.NAME;folder.mkdir(parents=True);(folder/'mine.txt').write_text('keep')
        with self.assertRaises(u.UpdateError):self.install()
        self.assertEqual((folder/'mine.txt').read_text(),'keep')
    def test_local_added_file_preserved(self):
        self.install();p=self.root/o.NAME/'notes.txt';p.write_text('keep')
        with self.assertRaises(u.UpdateError):self.install('3.0.2')
        self.assertEqual(p.read_text(),'keep')
    def test_state_version_mismatch_rejected(self):
        self.install();p=self.root/o.STATE;j=json.loads(p.read_text());j['version']='9.0.0';p.write_text(json.dumps(j))
        with self.assertRaises(u.UpdateError):o.state_for(self.root)
    def test_state_write_failure_rolls_back(self):
        self.install();before=o.tree(self.root);state=(self.root/o.STATE).read_bytes();real=o.replace_path
        def replace(src,dst):
            if Path(dst)==self.root/o.STATE:raise OSError('fixture state fail')
            return real(src,dst)
        with patch.object(o,'replace_path',side_effect=replace):
            with self.assertRaises(OSError):self.install('3.0.2')
        self.assertEqual(o.tree(self.root),before);self.assertEqual((self.root/o.STATE).read_bytes(),state)
        self.assertFalse((self.root/o.JOURNAL).exists())
    def test_rollback_failure_retains_journal(self):
        self.install();real=o.replace_path
        def replace(src,dst):
            if Path(dst)==self.root/o.NAME:raise OSError('fixture placement and recovery fail')
            return real(src,dst)
        with patch.object(o,'replace_path',side_effect=replace):
            with self.assertRaises(OSError):self.install('3.0.2')
        self.assertTrue((self.root/o.JOURNAL).exists())
        with self.assertRaises(u.UpdateError):self.install('3.0.2')
    def test_committed_cleanup_failure_is_warning(self):
        self.install();real=o.replace_path
        def replace(src,dst):
            if Path(dst).name.startswith('.teklif-backup-'):raise OSError('fixture cleanup fail')
            return real(src,dst)
        with patch.object(o,'replace_path',side_effect=replace):r=self.install('3.0.2')
        self.assertEqual(r['status'],'installed');self.assertTrue(r['warning']);self.assertEqual(o.state_for(self.root)['version'],'3.0.2')
        self.assertTrue((self.root/o.JOURNAL).exists())
    def test_existing_locks_never_removed(self):
        self.root.mkdir()
        for name in (u.UPDATE_LOCK,u.ANALYSIS_LOCK,u.JOURNAL):
            p=self.root/name;p.write_text('fixture')
            with self.subTest(name=name),self.assertRaises(u.UpdateError):self.install()
            self.assertEqual(p.read_text(),'fixture');p.unlink()
    def test_register_exact_tree(self):
        data,digest=package(schema=3);_,files=u.validate_archive(data,digest)
        for name,value in files.items():
            p=self.root/Path(name).relative_to('skills');p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(value)
        self.assertEqual(o.register(self.root,data,digest)['status'],'registered')
        (self.root/o.NAME/'new.txt').write_text('not packaged')
        with self.assertRaises(u.UpdateError):o.register(self.root,data,digest,replace_local=True)
    def test_component_version_not_release_label(self):
        self.install()
        data,digest=package('3.0.2',schema=2,versions={u.SKILLS[0]:'3.0.3',u.SKILLS[1]:'1.0.0'})
        r=o.apply(self.root,data,digest,'3.0.2','3.0.3');self.assertEqual(r['version'],'3.0.3')

if __name__=='__main__':unittest.main()
