# Güncelleyici 2.3.0: eksik bağımlılık ve aynı talebe dönüş

Motor `vendor/guncelleyici` altında yayımlanmış 2.3.0 kaynak dosyalarıyla birebirdir. Sözleşmeye özel giriş `scripts/beceri-baslat.ps1`, stdlib denetçisi `scripts/runtime_kontrol.py` ve `skills/guncelleyici` sarmalayıcısıdır. Sarmalayıcı motor sürümünü değiştirmez; paket sürümünden ayrı gösterir.

Her beceri çağrısı önce kendi `VERSION` kaynağına bağlı başlangıç satırını sohbet içinde gösterir. Eksik bileşen bulunursa Güncelleyici'nin adı, geliştiricisi ve 2.3.0 sürümü de gösterilir. Bu görünür mesajın sohbet ekranına aktarılması host ajanın görevidir; arka plan terminali kullanıcıya görünür sohbet mesajı yerine geçmez.

Ajan içi yerel Windows PowerShell 5.1 girişleri (son kullanıcı bunları çalıştırmaz):

```powershell
powershell.exe -NoProfile -File "<PLUGIN>\scripts\beceri-baslat.ps1" -Action prepare -SkillId K23 -AutoInstallMissing
```

`@@SONUC` status=READY ve resume_allowed=true ise dönen gerçek Python yolu kullanılarak aynı doğal dil talebi sürdürülür. Talep/bağlam hazırlanırken JSON dosyası ajan tarafından oluşturulur; kullanıcının önceki beyanı tekrar sorulmaz. Çekirdek değerlendirmeyi aynı dosyayla bitiren giriş:

```powershell
powershell.exe -NoProfile -File "<PLUGIN>\scripts\beceri-baslat.ps1" -Action run -SkillId K23 -AutoInstallMissing -RequestFile "<IZINLI_KOK>\request.json" -Workspace "<CASE_KOK>" -OutputRoot "<CIKTI_KOK>" -SourceRoot "<IZINLI_KOK>"
```

Yalnız kontrol için `-AutoInstallMissing` verilmez. Bu durumda eksik varsa kurulum başlamaz. Kullanıcıdan kurulum seçimi tekrar istemek otomatik eksik bağımlılık talimatının kapsamına aykırıdır. Genel program güncellemesi/onarımı hâlâ Güncelleyici'nin ayrı açık onay yoludur.

Denetim: Windows amd64 Python3.14, gereksinim dosyalarındaki 13 sabit paket, gerçek import, DuckDB SQL ve imza kontrolü açık PDF LOAD/API varlığı. PDF yoksa 2.3.0 motoru resmi Community dağıtımını planlar, SHA-256/imza/tek sayfa gerçek PDF okumasını doğrular. OCR ve gerçek sözleşme tablosu sadakati bu testin kapsamı değildir.

Python3.14 yoksa yalnız yeni kullanıcı kapsamındaki signed Python kurulur; mevcut desteklenen yorumlayıcı otomatik yükseltilmez. Python/Node işi varsa başlangıç kurulumu durur ve süreç kapatılmaz. Mevcut paketler eksik/uyumsuzsa `%LOCALAPPDATA%\KilicSozlesme\runtime\environments` altında yeni venv hazırlanır. Ortak Python paketleri veya PATH venv için değiştirilmez. Wheel çözümü yalnız resmi PyPI, sabit sürümler, wheel dosyaları ve zorunlu hash ile uygulanır; `pip check` ve yeni süreçte tüm kontroller geçmeden ortam seçilmez. Yeni PDF eklentisi plugin'in özel extensions kökünde kurulur; mevcut ortak ikili değiştirilmez. Mevcut bozuk ikili otomatik onarılmaz. Windows paket kaynak yolları için venv kökü140 UTF-16 biriminden uzunsa yazmadan durulur; registry/uzun-yol politikası değiştirilmez.

Run girişi ilk request byte hash'ini kurulum öncesi alır, sonrası tekrar karşılaştırır. Aynı request_id yalnız bir kez yürütüme alınır; çekirdek kaynak hash'leri ve context_version değerini kurulum sonrasında yeniden kontrol eder. Değişmiş kaynak/bağlam veya kurulum hatası devamı engeller. Başarısız süreç/yarım işlem günlüğü kör tekrar edilmez. Python/bootstrap ve private-env günlükleri otomatik silinmez; gerektiğinde gerçek durum incelenir.

Yerel dosya sistemi ve Windows shell bulunmayan bulut hostunda bilgisayara kurulum yapılamaz; TEKNIK_ENGEL açıkça belirtilir. Bu akış üretim gönderimi, imza yetkisi veya genel iş kabulü oluşturmaz. Paket testleri ile gerçek host sohbet görünürlüğü ayrı doğrulanır.
