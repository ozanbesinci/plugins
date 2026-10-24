// Native .NET Framework entry; asInvoker; no shell, service, PATH or policy changes.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Web.Script.Serialization;
#if SETUP
using System.Windows.Forms;
#endif
class Entry {
 [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)]
 static extern uint GetLongPathName(string shortPath,StringBuilder longPath,uint length);
 static JavaScriptSerializer Json = new JavaScriptSerializer { MaxJsonLength=8*1024*1024 };
 static string Plain(string path) {
  string full=Path.GetFullPath(path);
  for(string p=full;!String.IsNullOrEmpty(p);p=Path.GetDirectoryName(p))
   if((File.Exists(p)||Directory.Exists(p)) && (File.GetAttributes(p)&FileAttributes.ReparsePoint)!=0)
    throw new Exception("Bağlantılı dosya yolu kabul edilmedi.");
  string ancestor=full;
  while(!File.Exists(ancestor)&&!Directory.Exists(ancestor))ancestor=Path.GetDirectoryName(ancestor);
  var buffer=new StringBuilder(32768);
  uint size=GetLongPathName(ancestor,buffer,(uint)buffer.Capacity);
  if(size==0||size>=buffer.Capacity)throw new Exception("Windows yolu çözümlenemedi.");
  return buffer.ToString()+full.Substring(ancestor.Length);
 }
 static string Home() {
  string user=Environment.GetEnvironmentVariable("USERPROFILE");
  if(String.IsNullOrEmpty(user)||!Path.IsPathRooted(user)) throw new Exception("LOCAL_ACCESS_REQUIRED");
  return Plain(Path.Combine(user,"KilicPython"));
 }
 static Dictionary<string,object> Read(string path) {
  path=Plain(path);
  if(new FileInfo(path).Length>8*1024*1024)throw new Exception("Kayıt boyutu uygun değil.");
  return Json.Deserialize<Dictionary<string,object>>(File.ReadAllText(path,Encoding.UTF8));
 }
 static string HashRaw(string path) { using(var f=File.OpenRead(path))using(var h=SHA256.Create())return BitConverter.ToString(h.ComputeHash(f)).Replace("-","").ToLowerInvariant(); }
 static string Hash(string path) {return HashRaw(Plain(path));}
 static string Q(string s) {
  var b=new StringBuilder("\"");int slashes=0;
  foreach(char c in s) {if(c=='\\'){slashes++;continue;} if(c=='"'){b.Append('\\',slashes*2+1);b.Append('"');slashes=0;continue;}
    b.Append('\\',slashes);slashes=0;b.Append(c);}
  b.Append('\\',slashes*2);b.Append('"');return b.ToString();
 }
 static int Run(string exe, IEnumerable<string> args, bool capture, out string output) {
  var pi=new ProcessStartInfo(Plain(exe),String.Join(" ",args.Select(Q))) {UseShellExecute=false,CreateNoWindow=true};
  pi.EnvironmentVariables.Remove("PYTHONPATH");pi.EnvironmentVariables.Remove("PYTHONHOME");
  pi.EnvironmentVariables.Remove("SOZLESME_DEVELOPMENT");
  pi.RedirectStandardOutput=true;pi.RedirectStandardError=true;
  pi.StandardOutputEncoding=new UTF8Encoding(false);pi.StandardErrorEncoding=new UTF8Encoding(false);
  using(var p=new Process {StartInfo=pi}) {
   var log=new StringBuilder();var errors=new StringBuilder();object gate=new object();bool overflow=false;
   p.OutputDataReceived+=(s,e)=>{if(e.Data!=null)lock(gate){if(log.Length+e.Data.Length<4*1024*1024)log.AppendLine(e.Data);else overflow=true;}};
   p.ErrorDataReceived+=(s,e)=>{if(e.Data!=null)lock(gate){if(errors.Length+e.Data.Length<65536)errors.AppendLine(e.Data);else overflow=true;}};
   p.Start();p.BeginOutputReadLine();p.BeginErrorReadLine();
   if(!p.WaitForExit(600000)){p.Kill();p.WaitForExit();throw new Exception("İşlem süre sınırını aştı.");}
   p.WaitForExit();if(overflow)throw new Exception("CLI_OUTPUT_LIMIT");
   output=log.ToString();
   if(capture)output+=errors.ToString();else{Console.Write(output);Console.Error.Write(errors.ToString());}
   return p.ExitCode;
  }
 }
 static string Python() {
  var home=Home();var record=Read(Path.Combine(home,"sozlesme-runtime.json"));
  if((string)record["schema"]!="contract-runtime/v1")throw new Exception("RUNTIME_MISMATCH");
  string env=Plain((string)record["environment_root"]),exe=Plain((string)record["python_executable"]);
  if(!String.Equals(Path.GetDirectoryName(env),Path.Combine(home,"sozlesme-envs"),StringComparison.OrdinalIgnoreCase) ||
     !String.Equals(exe,Path.Combine(env,"python.exe"),StringComparison.OrdinalIgnoreCase))throw new Exception("RUNTIME_MISMATCH");
  if(Hash(exe)!=(string)record["python_sha256"] || Hash(Path.Combine(env,"runtime-files.json"))!=(string)record["inventory_sha256"])throw new Exception("REPAIR_REQUIRED");
  // Verify the entire private runtime before executing any of its code or DLLs.
  var inventory=Read(Path.Combine(env,"runtime-files.json"));
  var actual=new HashSet<string>(StringComparer.Ordinal);
  var queue=new Queue<string>();queue.Enqueue(env);
  while(queue.Count>0){
   string directory=queue.Dequeue();
   foreach(string entry in Directory.GetFileSystemEntries(directory)){
    string path=entry;var attributes=File.GetAttributes(path);
    if((attributes&FileAttributes.ReparsePoint)!=0)throw new Exception("REPAIR_REQUIRED");
    if((attributes&FileAttributes.Directory)!=0){queue.Enqueue(path);continue;}
    if(!String.Equals(path,Path.Combine(env,"runtime-files.json"),StringComparison.OrdinalIgnoreCase))
     actual.Add(path.Substring(env.Length+1).Replace('\\','/'));
   }
  }
  if(!actual.SetEquals(inventory.Keys))throw new Exception("REPAIR_REQUIRED");
  foreach(var kv in inventory) {
   string path=Path.GetFullPath(Path.Combine(env,kv.Key));
   if(kv.Key.Contains(":")||kv.Key.Contains("\\")||kv.Key.Split('/').Any(s=>s==""||s=="."||s=="..")||!path.StartsWith(env+Path.DirectorySeparatorChar,StringComparison.OrdinalIgnoreCase)||HashRaw(path)!=(string)kv.Value)throw new Exception("REPAIR_REQUIRED");
  }
  return exe;
 }
#if SETUP
 static void ExtractResource(string name,string destination) {
  destination=Plain(destination);Directory.CreateDirectory(destination);
  using(var input=Assembly.GetExecutingAssembly().GetManifestResourceStream(name))
  using(var archive=new ZipArchive(input,ZipArchiveMode.Read)) {
   long total=0;var names=new HashSet<string>(StringComparer.OrdinalIgnoreCase);
   foreach(var e in archive.Entries) {
    string relative=e.FullName.Replace('/',Path.DirectorySeparatorChar);
    string path=Plain(Path.Combine(destination,relative));
    if(!path.StartsWith(destination+Path.DirectorySeparatorChar,StringComparison.OrdinalIgnoreCase) ||
        e.FullName.Contains(":") || !names.Add(path) || e.Length>128*1024*1024 || (total+=e.Length)>600L*1024*1024)
     throw new Exception("Paket arşiv yolu/boyutu geçersiz.");
    if(e.FullName.EndsWith("/")){Directory.CreateDirectory(path);continue;}
    Directory.CreateDirectory(Path.GetDirectoryName(path));
    using(var src=e.Open())using(var dst=new FileStream(path,FileMode.CreateNew,FileAccess.Write))src.CopyTo(dst);
   }
  }
 }
 static void PublishLauncher(string home) {
  string folder=Plain(Path.Combine(home,"launcher"));Directory.CreateDirectory(folder);
  string target=Plain(Path.Combine(folder,"sozlesme.exe")),temp=target+"."+Guid.NewGuid().ToString("N")+".tmp";
  using(var source=Assembly.GetExecutingAssembly().GetManifestResourceStream("launcher.exe"))
  using(var output=new FileStream(temp,FileMode.CreateNew,FileAccess.Write)){source.CopyTo(output);output.Flush(true);}
  if(File.Exists(target))File.Replace(temp,target,null);else File.Move(temp,target);
 }
 static string Install() {
  if(!Environment.Is64BitOperatingSystem || Environment.GetEnvironmentVariable("PROCESSOR_ARCHITECTURE")=="ARM64")throw new Exception("Windows x64 (Intel/AMD) gerekli.");
  string home=Home();Directory.CreateDirectory(home);
  using(var installLock=new FileStream(Plain(Path.Combine(home,"sozlesme-install.lock")),FileMode.OpenOrCreate,FileAccess.ReadWrite,FileShare.None)) {
   string stage=Plain(Path.Combine(home,"sozlesme-setup",Guid.NewGuid().ToString("N")));
   ExtractResource("plugin.zip",stage);
   string output,existing=null;
   try { existing=Python(); } catch { }
   if(existing!=null && Run(existing,new[]{"-I","-B","-X","utf8",Path.Combine(stage,"scripts","runtime_kontrol.py"),"--action","probe"},true,out output)==0){
    PublishLauncher(home);return "Kurulum zaten hazır. Work içinde devam edebilirsiniz.";
   }
   string id=Guid.NewGuid().ToString("N");
   string env=Plain(Path.Combine(home,"sozlesme-envs",id));
   if(env.Length>140)throw new Exception("Kullanıcı ortam yolu çok uzun; kurulum yapılmadı.");
   ExtractResource("runtime.zip",env);
   string python=Path.Combine(env,"python.exe");
   // Extracted payload is part of this executable; record publication follows real readers.
   int code=Run(python,new[]{"-I","-B","-X","utf8",Path.Combine(env,"setup_runtime.py"),"--plugin-root",stage,"--runtime-id",id,"--check-only"},true,out output);
   File.WriteAllText(Path.Combine(stage,"verification.log"),output,new UTF8Encoding(false));
   if(code!=0)throw new Exception("Belge okuyucu doğrulaması başarısız. Önceki ortam korundu. Kayıt: "+stage);
   PublishLauncher(home);
   code=Run(python,new[]{"-I","-B","-X","utf8",Path.Combine(env,"setup_runtime.py"),"--plugin-root",stage,"--runtime-id",id},true,out output);
   File.AppendAllText(Path.Combine(stage,"verification.log"),output,new UTF8Encoding(false));
   if(code!=0)throw new Exception("Ortam kaydı yayımlanamadı. Kayıt: "+stage);
   return "Kılıç Sözleşme ortamı hazır. Work içinde sözleşme eklentisiyle devam edebilirsiniz.";
  }
 }
 [STAThread] static int Main(string[] args) {
  bool quiet=args.SequenceEqual(new[]{"--quiet"});
  if(args.Length!=0&&!quiet)return 2;
  try {string message=Install();if(!quiet)MessageBox.Show(message,"Kılıç Sözleşme Kurulumu",MessageBoxButtons.OK,MessageBoxIcon.Information);return 0;}
  catch(Exception e){if(quiet)Console.Error.WriteLine(e.Message);if(!quiet)MessageBox.Show(e.Message,"Kılıç Sözleşme — Kurulum tamamlanmadı",MessageBoxButtons.OK,MessageBoxIcon.Error);return 2;}
 }
#else
 static int Main(string[] args) {
  Console.OutputEncoding=new UTF8Encoding(false);
  try {
   if(args.Length<3||args[0]!="--plugin-root")throw new Exception("Kullanım: sozlesme.exe --plugin-root <plugin> prepare|run|cli ...");
   string root=Plain(args[1]),python=Python(),output;
   return Run(python,new[]{"-I","-B","-X","utf8",Path.Combine(root,"scripts","runtime_launcher.py")}.Concat(args.Skip(2)),false,out output);
  } catch(Exception e) {
   string error="LOCAL_ACCESS_REQUIRED";
   try {error=File.Exists(Path.Combine(Home(),"sozlesme-runtime.json"))?"RUNTIME_MISMATCH":"SETUP_REQUIRED";}catch{}
   Console.WriteLine("@@SONUC "+Json.Serialize(new {status="BLOCKED",error=error,message=e.Message,resume_allowed=false}));
   return 2;
  }
 }
#endif
}
