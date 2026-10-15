# Host giriş sözleşmesi

Host giriş noktası `python -B -X utf8 scripts/contract_cli.py <aynı izinli CLI argümanları>`; PowerShell beceri girişi bunu kullanır. Stdlib-only zarf, site paketleri henüz import edilemezken CONFIG_REQUIRED ve argüman hatasında CLI_ARGUMENT_ERROR ile tek yapılandırılmış BLOCKED JSON döndürür. İş/uzman kabulü NOT_GRANTED, iş durumu NOT_RUN, build bilinmiyorsa null olur. Kurulum, kimlik üretme veya başka bir host'a eylem yetkisi yoktur.

Normal çekirdek sonucu aynı operation_id/components ile aktarılır; technical_status/business_status/business_acceptance ayrı alanlardır. P6 exit0+TEKNIK_ENGEL veya BILGI_GEREKLI iş tamamlandı sayılmaz; output_ids boşsa dosya teslim iddiası yoktur. Geliştirici `--help` çıktısı insan okunur yardım metnidir, iş makbuzu değildir. Genel stdout64MiB büyüme sınırıyla kapalı ret vardır; bu host token kullanımını ölçmez.

Doğrudan `python -m sozlesme_cekirdek` geliştirici yolu paket import'undan önceki hataları normalize etmez; host için wrapper kullanılmalıdır. Gerçek ChatGPT/Claude host adapter, kurumsal erişim ve bağımsız kabul hâlâ NOT_RUN. K29 ve normal üretim Word kapıları kapalı kalır.
