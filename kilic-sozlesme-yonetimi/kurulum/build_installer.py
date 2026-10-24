"""Build an offline per-user installer; only build-time downloads, all hash pinned.
Signing is reported separately from the requested product release version.
"""
import argparse,hashlib,importlib.util,json,os,shutil,subprocess,sys,tempfile,urllib.request,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent/"plugins/kilic-sozlesme-yonetimi"
sys.dont_write_bytecode=True
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def get(url,path,digest):
    if path.exists():
        if sha(path)!=digest:raise ValueError("Cached bytes differ: "+str(path))
        return path
    path.parent.mkdir(parents=True,exist_ok=True)
    with urllib.request.urlopen(url,timeout=120) as response:
        if not response.url.startswith(("https://www.python.org/","https://files.pythonhosted.org/","https://download.visualstudio.microsoft.com/")):
            raise ValueError("Unapproved redirect")
        data=response.read(256*1024*1024+1)
    if len(data)>256*1024*1024 or hashlib.sha256(data).hexdigest()!=digest:raise ValueError("Download hash mismatch: "+url)
    path.write_bytes(data);return path
def unpack(path,dest,wheel=False):
    with zipfile.ZipFile(path) as archive:
        for item in archive.infolist():
            name=item.filename
            parts=Path(name).parts
            if "\\" in name or ":" in name or name.startswith("/") or ".." in parts or item.file_size>128*1024*1024:
                raise ValueError("Unsafe archive entry")
            if wheel and ".data/" in name:
                prefix,tail=name.split(".data/",1);kind,tail=tail.split("/",1)
                if kind not in ("purelib","platlib"):raise ValueError("Unsupported wheel data section "+kind)
                name=tail
            target=dest/name
            if item.is_dir():target.mkdir(parents=True,exist_ok=True);continue
            target.parent.mkdir(parents=True,exist_ok=True)
            if target.exists():raise ValueError("Archive collision: "+name)
            target.write_bytes(archive.read(item))
def vc_runtime(env,cache,area):
    p=json.loads((HERE/"native-runtime.json").read_text(encoding="utf-8"))
    data=get(p["url"],cache/"VC_redist.x64.exe",p["sha256"]).read_bytes()
    folder=area/"vc";folder.mkdir()
    def extract(section,name,out):
        part=p[section];raw=data[part["offset"]:part["offset"]+part["bytes"]]
        if hashlib.sha256(raw).hexdigest()!=part["sha256"]:raise ValueError("VC cabinet differs")
        cab=folder/(section+".cab");cab.write_bytes(raw);out.mkdir()
        subprocess.run([str(Path(os.environ["SystemRoot"])/"System32/expand.exe"),"-F:"+name,str(cab),str(out)],
                       check=True,stdout=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
    extract("outer_cab",p["minimum_payload"],folder/"outer")
    minimum=folder/"outer"/p["minimum_payload"]
    if sha(minimum)!=p["minimum_sha256"]:raise ValueError("VC payload differs")
    dlls=folder/"dlls";dlls.mkdir()
    subprocess.run([str(Path(os.environ["SystemRoot"])/"System32/expand.exe"),"-F:*",str(minimum),str(dlls)],
                   check=True,stdout=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
    for name,digest in p["dlls"].items():
        source=dlls/(name+"_amd64")
        if sha(source)!=digest:raise ValueError("VC DLL differs")
        # CPython carries two VC DLLs; replace them only in the new staged private bundle.
        shutil.copyfile(source,env/name)
    extract("license_cab",p["license_payload"],folder/"license")
    license=folder/"license"/p["license_payload"]
    if sha(license)!=p["license_sha256"]:raise ValueError("VC license differs")
    shutil.copyfile(license,env/"VC-RUNTIME-LICENSE.rtf")
def zip_tree(root,target):
    with zipfile.ZipFile(target,"x",zipfile.ZIP_DEFLATED) as archive:
        for p in sorted(root.rglob("*")):
            if p.is_file() and not {"__pycache__",".runtime"}.intersection(p.parts):archive.write(p,p.relative_to(root).as_posix())
def refresh():
    spec=importlib.util.spec_from_file_location("integrity",ROOT/"scripts/bootstrap_integrity.py")
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    value={"schema":"contract-bootstrap/v1","files":module.package_files(ROOT)}
    (ROOT/"references/bootstrap-manifest.json").write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
def package_version():
    primary=json.loads((ROOT/"plugin.json").read_text(encoding="utf-8"))
    compatible=json.loads((ROOT/".claude-plugin/plugin.json").read_text(encoding="utf-8"))
    if primary.get("name")!=compatible.get("name") or primary.get("version")!=compatible.get("version"):
        raise ValueError("OpenAI/Claude plugin manifest identity differs")
    return primary["version"]

def main():
    parser=argparse.ArgumentParser();parser.add_argument("--output",type=Path,required=True);parser.add_argument("--refresh-only",action="store_true")
    args=parser.parse_args();version=package_version();refresh()
    if args.refresh_only:return
    output=args.output.resolve()
    if output.is_relative_to(HERE.parent.resolve()):raise ValueError("Build output must be outside source repository")
    output.mkdir(parents=True,exist_ok=True)
    area=output/"build"
    area.mkdir(exist_ok=False)
    env=area/"runtime";env.mkdir()
    cache=output.parent/"download-cache"
    profile=json.loads((ROOT/"references/runtime-profile.json").read_text(encoding="utf-8"))
    archive=get(profile["python_download"],cache/"python-3.14.8-embed-amd64.zip",profile["python_archive_sha256"])
    unpack(archive,env)
    (env/"python314._pth").write_text("python314.zip\n.\nLib/site-packages\n",encoding="ascii")
    packages=env/"Lib/site-packages";packages.mkdir(parents=True)
    manifest=json.loads((ROOT/"references/windows-wheel-manifest.json").read_text(encoding="utf-8"))
    wheels=manifest["files"]
    if len(wheels)!=13:raise ValueError("Expected 13 locked wheel records")
    for item in wheels:
        wheel=get(item["download_url"],cache/item["filename"],item["sha256"])
        unpack(wheel,packages,wheel=True)
    vc_runtime(env,cache,area)
    shutil.copyfile(HERE/"setup_runtime.py",env/"setup_runtime.py")
    (env/"NOTICE.txt").write_text("CPython embedded distribution and 13 pinned wheels. Licenses remain in LICENSE.txt and each *.dist-info/licenses or metadata directory. Microsoft runtime: VC-RUNTIME-LICENSE.rtf. App-local runtime packaging only.\n",encoding="utf-8")
    runtimezip=area/"runtime.zip";zip_tree(env,runtimezip)
    pluginzip=area/"plugin.zip";zip_tree(ROOT,pluginzip)
    csc=Path(os.environ["SystemRoot"])/"Microsoft.NET/Framework64/v4.0.30319/csc.exe"
    common=[str(csc),"/nologo","/platform:x64","/optimize+","/win32manifest:"+str(HERE/"asInvoker.manifest"),
            "/r:System.Web.Extensions.dll","/r:System.IO.Compression.dll","/r:System.IO.Compression.FileSystem.dll"]
    launcher=area/"sozlesme.exe"
    subprocess.run([*common,"/target:exe","/out:"+str(launcher),str(HERE/"NativeEntry.cs")],check=True)
    setup=output/f"KilicSozlesmeKurulum-{version}.exe"
    subprocess.run([*common,"/target:winexe","/define:SETUP","/r:System.Windows.Forms.dll","/out:"+str(setup),
        "/resource:"+str(runtimezip)+",runtime.zip","/resource:"+str(pluginzip)+",plugin.zip",
        "/resource:"+str(launcher)+",launcher.exe",str(HERE/"NativeEntry.cs")],check=True)
    report={"schema":"contract-installer-build/v1","plugin_version":version,"installer":str(setup),"sha256":sha(setup),"bytes":setup.stat().st_size,
       "profile":profile["profile_id"],"bootstrap_manifest_sha256":sha(ROOT/"references/bootstrap-manifest.json"),
       "signing":"NOT_SIGNED","clean_standard_user_acceptance":"NOT_RUN","work_acceptance":"NOT_RUN"}
    (output/"BUILD.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report))
if __name__=="__main__":main()
