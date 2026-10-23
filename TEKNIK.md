# Kino 🎬

## Her bilgisayarda çalıştırma (23 Ekim 2026)

Gereken yalnız **Python 3.9+** ve Chromium tabanlı bir tarayıcı (Chrome, Edge,
Brave ya da Chromium). pip/npm, WSL veya browser-harness gerekmez. Klasörü
(Drive'daki `kino/kino`) olduğu yerde çalıştır:

| Sistem | Başlat | Durdur |
|---|---|---|
| Windows | `Kino.bat` çift tıkla (ya da `py -3 start.py`) | `Kino.bat stop` |
| macOS | `Kino.command` çift tıkla (ilk sefer: `chmod +x Kino.command`) | `./Kino.command stop` |
| Linux / WSL | `./start.sh` | `./start.sh stop` |

`start.py status` çalışıp çalışmadığını gösterir, `start.py fg` sunucuyu ön planda
çalıştırır (log terminalde). Adres: **http://localhost:8484**.

- **Tarayıcı:** bölüm çekerken gerekirse ayrı bir profille (CDP 9222) kendisi açılır.
  Windows, WSL (Windows tarayıcısı, mirrored ağ), macOS ve Linux yolları otomatik
  bulunur; Chrome yoksa Edge kullanılır. Captcha da AI olmadan otomatik çözülür.
- **Paylaşılan (Drive'da):** `data.json` (kütüphane, ilerleme), `logs/`,
  `state/` (tranimeizle cookie'si, çekim kayıtları).
- **Makineye özel (Drive'a yazılmaz):** tarayıcı profili, `server-<port>.pid`,
  başlatıcı logu `kino.log` — Windows `%LOCALAPPDATA%\Kino`, macOS
  `~/Library/Application Support/Kino`, Linux `~/.local/share/Kino`.
  Windows'ta eski `C:\chrome-debug-profile` varsa o kullanılır.
- ⚠️ Aynı anda **iki bilgisayarda** açık tutma: ikisi de aynı `data.json`'a yazar ve
  Drive çakışan kopya üretebilir. Birinde kapat (`stop`), diğerinde aç.
- Dosyalar: `server.py` (HTTP + API), `fetcher.py` (tranimeizle çekici),
  `cdp.py` (bağımlılıksız CDP istemcisi), `browser.py` (tarayıcı bulma/başlatma),
  `start.py` (başlatıcı), `ram_cache.py`, `public/`.

## RAM'den oynatma (23 Ekim 2026)

RAM modu **isteğe bağlıdır ve varsayılan olarak kapalıdır**. Ayarlar → RAM'den
oynatma içinden açılır. Kapalıyken **İzle** normal akışla başlar; açıkken
bölümü sunucunun RAM'ine hazırlar. Tercih sonraki oynatımda geçerli olur.
Hazırlık ekranı parça sayısını, ilerlemeyi, indirilen MB'ı ve tahmini süreyi
gösterir. Yaklaşık 30 saniye bir hedeftir; bölümün tamamı hazır olmadan RAM modu
oynatımı başlatmaz. Uzarsa **Akışla izle** düğmesi hazırlamayı iptal edip normal
oynatıma geçer. Hazır kaynak yalnızca yerel `/ram/` adreslerini kullanır.

- Son **420 saniyede** (7 dakika) sıradaki kayıtlı bölüm arka planda hazırlanır.
  Sıradaki bölüme geçişte hazır bellek kaydı yeniden kullanılır ve önceki bölüm
  temizlenir. Yeni bölümün bağlantısı kütüphanede yoksa durum açıkça gösterilir.
- En fazla mevcut bölüm + sıradaki bölüm; varsayılan önbellek sınırı **1024 MiB**.
  Video dosyaları diske yazılmaz. Kullanılmayan kayıtlar 10 dakika sonra,
  sunucu kapanınca tüm RAM kayıtları temizlenir. İşletim sistemi/bellek ve
  oynatıcının kendi tamponları bu önbellek kotasından ayrıdır.
- **Ayarlar → RAM'den oynatma:** modu kalıcı aç/kapat, 360/480/720/1080p hedef
  kalite seç. Kaynakta hedef kalite yoksa en yakın alt kalite; alt kalite de yoksa
  sunulan en düşük kalite seçilir. Oynatıcıdaki **RAM açık/kapalı** düğmesi ve
  **Akışla izle** yalnızca o oynatımı değiştirir.
- Tamamlanmış HLS yayınları; ana/alt listeler, ayrı ses, AES-128 anahtarları,
  başlangıç parçaları ve byte-range kaynakları desteklenir. Canlı/DRM kaynaklar,
  tek parçası 32 MiB'ı aşan kaynaklar veya kota aşımı açık hata ve akış seçeneği
  gösterir. Hazırlanan kalite RAM oynatımı boyunca sabittir.
- Ortam değişkeni `KINO_RAM_MB`: önbellek kotası (128–4096 MiB, varsayılan 1024).
  Aynı yerel Kino sunucusunda tek aktif oynatım için iki bölümlük önbellek tutulur.

API: `POST /api/ram/prepare {animeId,ep,prefetch?,retry?}`;
`GET /api/ram/status?id=<id>`; `POST /api/ram/cancel {id}`;
`GET|HEAD /ram/<id>/<asset>` (HTTP Range destekli).

Testler: `python3 test_ram.py`, `python3 test_tracking.py`,
`node --test test_ram_player.cjs`. Yeni pip/npm bağımlılığı yok.

## Güncel & Takip (23 Ekim 2026)

- **Güncel & Takip** (`#/guncel`): AniList'ten sezon/yıl/yayın durumu ve
  popülerlik/puan/trend filtreleriyle anime keşfi; sayfalama ve tek tıkla takip.
- **Takip et** bölümleri çekmeden kütüphaneye kaydeder. Önceki **Ekle ve bölüm çek**
  işlemi çalışmaya devam eder. Aynı AniList kimliği farklı adla tekrar eklenmez.
- Takip kartları yayınlanan/izlenen bölüm sayısını, izlenmemiş bölümleri ve sonraki
  bölümün Türkiye saatini gösterir. **İzledim** işareti geri alınabilir; oynatıcıyla
  aynı `progress` verisini kullanır. Takipten çıkarmak kütüphaneyi silmez.
- **Takvim**: Türkiye gün sınırları, gün ve sadece takip edilenler filtreleri,
  gelecek haftalar ve seçili yayınları `.ics` dosyası olarak takvime aktarma.
- Uygulama açık ve görünürken takip verileri 5 dakikada bir yenilenir. AniList
  yanıtları 5 dakika önbellekte tutulur. Uygulama kapalıyken bildirim gönderilmez.
- AniList erişilemediğinde kayıtlar korunur ve güncellik uyarısı gösterilir.
  Yayın tarihi ile Türkçe altyazı/oynatma bağlantısının hazır olması farklıdır.
- Yeni dosya: `public/tracking.js`; yeni bağımlılık veya veritabanı geçişi yok.

Yeni API: `GET /api/tracking`, `POST /api/tracking/progress
{animeId,episode,done}`, `POST /api/add {media,fetchEpisodes:false}` ve
`POST /api/list {animeId,tracking:true|false}`. `lists` kayıtları opsiyonel
`tracking` alanını taşır. Eski kütüphane kayıtları (tamamlandı/bırakıldı/beklemede
hariç) varsayılan olarak takipte görünür. Mevcut veri dosyası korunur.

Test: `python3 test_tracking.py` (geçici veri dosyaları kullanır).

AniList kataloğu + tranimeizle m3u8 linkleriyle çalışan, tamamen yerel anime
platformu. Python standart kütüphanesi + tarayıcı; npm/pip yok. Başlatma ve
kapatma için yukarıdaki "Her bilgisayarda çalıştırma" bölümüne bak.

## Özellikler (v2)

- **Ana Sayfa** — hero (trend, 9 sn'de döner), *İzlemeye devam et*, Bu sezon,
  Trend, Kütüphanem, türüne göre "sevdin mi?", En yüksek puanlı, Popüler satırları.
- **Keşfet** — AniList'te 5000+ anime: tür çipleri, yıl/format/sıralama filtreleri,
  sayfalama. Arama çubuğu (üstte) doğrudan Keşfet'e gider.
- **Detay** — banner + poster, puan/tür/stüdyo pill'leri, sekmeler: Bölümler /
  Detaylar (etiketler, linkler) / Benzerler (AniList önerileri); listeme ekle
  (izleniyor/planlandı/tamamlandı/beklemede/bırakıldı), favori, 1-10 puan.
- **Player** — HLS (kalite seçimi, 0.75x-2x hız, PiP, tam ekran, klavye:
  boşluk/←→/f/m/n), kaldığın yerden devam, otomatik sonraki bölüm geri sayımı,
  hata paneli (tekrar dene / linki yenile). Tüm istekler `/px` proxy'sinden geçer (CORS + referer).
- **Listem** — durum sekmeleri + favoriler, ilerleme çubukları.
- **Takvim** — bu haftanın AniList yayın akışı; kütüphanende olanlar işaretli.
- **İstatistik** — toplam izleme, biten bölüm, seri, streak; 14 günlük grafik,
  tür dağılımı, son izlenenler.
- **Kuyruk** — canlı iş listesi (çalışıyor/sırada), ilerleme, iptal, son işler ve
  canlı log akışı.
- **Ayarlar** — oto-sonraki + geri sayım, varsayılan parti boyu, tema rengi
  (mor/yeşil/gül/amber/camgöbeği), hareketi azalt, veri indir, geçmişi temizle.
- **Ctrl+K** komut paleti — sayfalar, kütüphane ve AniList araması.

## Akış: ara → ekle → 10 bölüm → 9. bölümde sonraki 10

1. **Keşfet**'te animeye tıkla → **Ekle ve 10 bölüm çek** (veya ana sayfa hero'daki
   *Kütüphaneye ekle*). AniList meta'sı (poster, banner, özet, türler, puan) kaydedilir.
2. Sunucu tek worker'lı kuyruğa iş atar; `fetcher.py` ilk 10 bölümün
   m3u8'ini bulur, sonuçlar **canlı** DB'ye yazılır (detay sayfası 2.5 sn'de bir tazelenir).
3. 9. bölümü oynatınca (`POST /api/ep/open`, ayrıca `/api/progress`) sunucu sonraki
   10'u çeker: `autoFetch.nextAt = son bölüm - 1`. 12 bölümlük animede 11-12 gelir,
   `autoFetch.enabled` kapanır.

## Çekim nasıl çalışıyor?

`server.py` tek iş kuyruğu tutar (tek tarayıcı oturumu) ve çekiciyi alt süreç
olarak şu ortamla çağırır (elle de aynı şekilde çalışır):

```
ANIME="Frieren: Beyond Journey's End" N=10 START=0 PAGE="" python3 fetcher.py
```

- Çekici kaynakları AitrVip → Sibnet → diğerleri sırasıyla dener; sadece gerçekten
  oynayan m3u8'i döndürür (`EPn: OK -> kaynak | url` ve `KINO_RESULT:{...}`).
- İlk başarılı çekimde `sourcePage` sabitlenir → sonraki partiler aynı sayfadan gider.
- Tarayıcı CDP (9222) kapalıysa açılır (`browser.py`; `KINO_CHROME` ezer).
  Bot captcha'sı ("farklı olanı seçiniz") çıkarsa **AI olmadan** çözülür: 5 ikonun
  4'ü piksel piksel aynı, canvas'ta karşılaştırılıp farklı olana tıklanır; oturum
  cookie'si `state/tranimeizle-cookies.json`'a yazılır.
- Loglar: `kino/logs/<anime-id>.log` (Kuyruk sayfası canlı okur).
- İş iptali: `POST /api/queue/cancel` → process kill + durum `error / İptal edildi`.
- Tek bölüm linki yenileme: bölüm kartındaki ↻ → `POST /api/refresh {ep}`.
  Tümü: `POST /api/refresh {all:true}` (uzun sürer, onay ister).

## API

GET:
`/api/library` (animes, progress, lists, history, settings) ·
`/api/search?q=&page=&genre=&year=&format=&status=&sort=` → AniList browse ·
`/api/browse?sort=&season=&year=&genre=&format=&page=` ·
`/api/anime?id=<yerel>&anilistId=<id>` → `{local, detail}` ·
`/api/schedule?days=7` · `/api/stats` · `/api/queue` · `/api/log?animeId=` ·
`/px?u=<url>&ref=<referer>` (m3u8/segment proxy + playlist rewrite)

POST:
`/api/add {media}` · `/api/anime/fetch {animeId,count}` ·
`/api/ep/open {animeId,ep}` · `/api/progress {animeId,ep,pos,dur,done}` ·
`/api/list {animeId,status?,favorite?,rating?}` · `/api/settings {…}` ·
`/api/queue/cancel {animeId}` · `/api/refresh {animeId,ep|all}` ·
`/api/history/clear` · `/api/anime/delete {animeId}` · `/api/import {title,text}` ·
`/api/lookup {animeId}`

## Veri (`data.json`)

```
animes[]: {id, title, created, episodes[{n,url,title}], meta{anilistId,poster,banner,
           outline,year,score,genres,episodes,format}, searchTitles[], sourcePage,
           autoFetch{enabled,batch,nextAt}, fetch{status,message,got,requested,start,finished}}
progress["<id>:<n>"]: {pos,dur,done,updated}
lists["<id>"]: {status, favorite, rating, updated}
history[]: {animeId, ep, at, pos}        # 60 sn üzeri, seyrek
settings: {autoplayNext, autoplayCountdown, theme, rows, batch, reduceMotion, language}
```
Silme (`/api/anime/delete`) bölümleri, ilerlemeyi, liste kaydını ve geçmişi temizler.

## Ayarlar (ortam)

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `KINO_PORT` | 8484 | HTTP portu |
| `KINO_BATCH` | 10 | Varsayılan parti boyu (Ayarlar'daki `batch` bunu ezer) |
| `KINO_JOB_TIMEOUT` | 1800 | Tek iş için saniye üst sınırı |
| `KINO_HOST` | 0.0.0.0 | Dinlenen adres (yalnız bu bilgisayar için `127.0.0.1`) |
| `KINO_DATA` | `./data.json` | Kütüphane dosyası |
| `KINO_STATE` | `./state` | Cookie ve çekim kayıtları |
| `KINO_CHROME` | otomatik | CDP için açılacak tarayıcı yolu |
| `KINO_CHROME_PROFILE` | otomatik (makineye özel) | Tarayıcı profil klasörü |
| `KINO_CHROME_HEADLESS` | — | `1` ise tarayıcı görünmez açılır (deneysel) |
| `KINO_CDP_URL` | `http://127.0.0.1:9222` | CDP uç noktası (`BU_CDP_URL` da okunur) |

## Notlar

- AniList yanıtları 5-15 dk bellek içi cache'lenir (`API_CACHE`); 400 alırsan
  GraphQL değişken tiplerini kontrol et (`$format: MediaFormat`, `$genre: String`).
- Player doğrudan m3u8 açmaz; `optraco/…` CORS vermediği için `/px` üzerinden gider.
- `data.json` yedeği: Ayarlar → Kütüphaneyi indir ya da dosyayı kopyala.
- Skill çıktısını elle de gönderebilirsin:
  `curl -X POST localhost:8484/api/import -H 'Content-Type: application/json' -d '{"title":"<ANIME>","text":"<linkler>"}'`
