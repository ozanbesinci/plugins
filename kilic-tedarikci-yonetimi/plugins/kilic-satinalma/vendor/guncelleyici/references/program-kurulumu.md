# Program ve ortam bileşenleri

Bu dosya yayımlanan `2.2.0` kaynak kodunun davranışını açıklar. Gerçek Windows kurulum
kabulü yapılmadan üretim dağıtımı onayı sayılmaz. `BUILD.json` ile `VERSION`
birlikte okunmalıdır.

## Bileşen sözleşmesi

| Bileşen | Planlanan kaynak / kimlik | Uygulama ve doğrulama |
|---|---|---|
| Python | python.org, 3.14 serisinin kararlı x64 yaması, boyut ve SHA-256 | Aynı kurucu baytları + PSF imzası; kurulum kodu, gerçek sürüm ve pip kontrolü |
| Python paket seti | `config/paket-seti.json`, 12 sabit sürüm ve wheel hash'leri | `--require-hashes`, hazır wheel; bağımsız süreçte sürümler, dosya işlevleri, Excel ve pip check |
| Node.js | nodejs.org son LTS, ZIP SHA-256 | OpenJS imzası, hazırlık ve son konumda Node/npm/hash testi; eski klasör korunur |
| pnpm | npm kararlı sürüm, ilk metadata içindeki SHA-512; pnpm 12+ için `@pnpm/exe.win32-x64` aynı sürüm tarball'ı ve SHA-512'si de planda sabitlenir | İndirilen aynı tarball(lar) doğrulanır; yerel/offline npm kurulumu, yaşam döngüsü scriptleri ve isteğe bağlı bağımlılıklar kapalı; yerel `pnpm.exe` doğrulanmış paketten çıkarılır, shim'ler doğrudan bu ikiliyi çağırır; hazırlık ve son konum testi |
| DuckDB | Bu Python ile uyumlu PyPI wheel çözümü, tam sürüm/hash listesi | Çözülen listeye hash zorunluluğuyla kurulum; Türkçe CSV/gruplu toplam testi |
| Power BI MCP | Microsoft Marketplace kararlı win32-x64 VSIX, planlama anında hesaplanan hash | Aynı VSIX + kimlik + Microsoft ana EXE imzası; initialize/tools/list doğrulaması; yeni sürüm ayrı klasöre |
| PDF eklentisi | Açık istekle DuckDB sürüm/platformuna ait Community ikilisi | İmza kontrolleri açık; izole kurulum testi, son konum testi, eski ikili yedeği |

pnpm 12+ npm paketi bir JS başlatıcı ve `@pnpm/exe.<platform>` yerel ikilisinden oluşur.
Tespit yerel düzende `node_modules\pnpm\pnpm.exe --version` komutunu doğrudan çalıştırır;
`.exe` hiçbir zaman Node'a betik olarak verilmez, scriptsiz kurulumdaki başlatıcı çalıştırılmaz.
Komut dosyası bulunup sürümü doğrulanamayan kurulum "Yüklü · sürüm doğrulanamadı" olarak
gösterilir, gerekçesiyle engellenir ve değiştirilmez.

Kaynak türleri farklı güven zincirleridir: dosya hash'i yayıncı güvenliğini tek başına
kanıtlamaz. PBI VSIX için planlama anında hesaplanan hash, bağımsız bir Microsoft
paket imzası değildir. Aynı kaynağın ele geçirilmesine karşı bağımsız imza sistemi
bu adayın kapsamı dışındadır.

## Önce plan, sonra uygulama

`scan` geçici plan/önbellek üretir; kurulu program, PATH, istemci ayarı veya önceki
kurulum/sağlık kayıtlarını değiştirmez. Paket indirmenin kendisi üçüncü taraf kodu
çalıştırmaz; PDF'nin `LOAD` komutu ancak açık kontrol/uygulama isteğinde kullanılır.
Planın süresi bir saattir. Plan dosyasının tam SHA-256 değeri, kullanıcı/bilgisayar/
skill kökü, operasyonel script/config/referans talimatlarının parmak izi, bileşenlerin
önceki yerel durumları, tam hedefleri ve yan etki kayıtları saklanır. Uygulama ayrıca
açık `-ConfirmApply` bayrağı olmadan reddedilir. Uygulama, ortak dosya kilidini aldıktan sonra yerel durumu yeniden kontrol
eder; yeni bir çevrimiçi hedef seçmez.

İlk kez kurulan bilgisayarda Python yoksa bağımlı paketlerin doğru hedefi henüz
çözülemez. Bu satırlar engellenir; Python kurulduktan sonra ikinci tarama gerekir.
Bu davranış bir hata değil, bilinmeyen bağımlılığı kullanıcı adına onaylamamaktır.

`repair` varsayılan değildir. Node/pnpm/kütüphane/DuckDB/PBI aynı sürüm onarımı yeni
plan ve yeni açık onay gerektirir. Python kurucusu aynı sürümde zorla üzerine
yazılmaz. Sürüm numarasının büyük olması kurulum sağlığının kanıtı değildir.

## Paylaşılan Python ve bakım penceresi

Bu aday, mevcut teklif iş akışını sessizce farklı Python yoluna taşımamak için
`--user` yaklaşımını otomatik olarak venv'e dönüştürmez. Bu **artık risk** açıkça
korunur: pip tüm paketler için atomik bir geri dönüş sağlamaz. Kurulum öncesinde
bakım penceresi istenir, görünür Python/Node iş yükleri kontrol edilir; kullanıcı
programları zorla kapatılmaz. Bu kontrol, başka bir işlemin hemen sonra başlamasını
engelleyen OS düzeyinde sandbox değildir. Çalışma penceresi operasyonel olarak da
korunmalıdır.

Pip kısmi başarısızlık veya doğrulanamayan son durumda `recovery_required` kaydı
bırakır; yeni toplu kurulum durur. BT önce ortamı ölçer. Otomatik global paket silme,
sanal ortama geçiş, güvenlik istisnası ekleme veya eski sürüme körlemesine dönüş yoktur.

İleride ayrı venv kullanılacaksa `teklif-degerlendirme` koşularının yorumlayıcı
seçimiyle birlikte tasarlanmalıdır. Yalnız bu güncelleyiciye venv eklemek yeterli
değildir. Onaylı şirket sürüm kataloğu da ayrı yönetişim işidir; bu aday upstream
kararlı sürümü seçip **işlem başına sabitler**, şirketçe onaylandı iddiasında bulunmaz.

## MCP ayar bağlama

Codex TOML ve Claude Desktop JSON'da yalnız desteklenen kayıt biçimindeki `command`
alanı değiştirilir. Ortam değişkenleri, zaman aşımı, enabled ve bilinmeyen alanlar
korunur. Belirsiz/özel/uzak kayıt değiştirilmez. Dosya birebir yedeklenir; geçici
yazım, semantik doğrulama ve değişiklik kontrolü yapılır. Bu bir düşmanca eşzamanlı
yazara karşı kernel CAS değildir; istemciler kapalı olmalıdır.

Claude Code'un `.claude.json` dosyası doğrudan yazılmaz. Yerel `claude.exe` varsa
sadece basit stdio kaydı kendi `mcp add/remove --scope user` komutlarıyla değiştirilir.
Özel env/argüman/kayıt alanları veya yalnız `.cmd` kurulum varsa bağlama ertelenir.
Başarısız basit kayıtta CLI ile önceki sunucuya geri dönme denenip doğrulanır.

Açık Codex/ChatGPT/Claude bulunduğunda sunucu kurulabilir, ancak ayar bağlama ertelenir.
Kullanıcı istemcileri kapatıp sohbette bağlamayı yeniden istediğinde **Work/Codex yerel
yürütme aracı** aşağıdaki iç bakım adımını çalıştırır. Son kullanıcıdan PowerShell veya
terminal açması istenmez.

```powershell
powershell.exe -NoProfile -File "<SKILL>\scripts\powerbi-mcp-kur.ps1" -BindOnly -ExePath "<doğrulanmış sunucunun tam exe yolu>" -PythonYolu "<Python 3.14 tam yolu>"
```

Bu iç adım sunucunun imzasını/çalışmasını yeniden sınar, ortak güncelleme kilidini
kullanır. Yarım işlem günlüğü varsa çalışmaz. Sunucu testi, bütün istemcilerin gerçekten
bağlandığını kanıtlamaz; uygulamalar yeniden açıldıktan sonra araçların görünmesi
Windows kabul kontrolünde ayrıca doğrulanır. Kullanım sözleşmesi kabul edilmez.

## Gözlem, sağlık ve rapor

Sağlık makbuzu gözlenen yerel durum hash'ine bağlıdır. Kurulum sonrası yerel sürüm
onaylanan hedefle tam eşleşmelidir; daha yeni bir sürümün ortaya çıkması sessizce
başarı sayılmaz. `NOT_RUN`, `PASS`, `FAIL` ve `WARNING` sonuçları birbirinden ayrıdır.

Kayıtlar `%LOCALAPPDATA%\guncelleyici\sessions` ve `health` altındadır.
`active-transaction.json` yarım/şüpheli değişikliği işaret eder; kendiliğinden silinmez.
İndirilen paket, kurulum yedeği ve raporların saklama/silme politikası BT tarafından
yönetilmelidir. Bu aday eski yedekleri otomatik topluca silmez.
