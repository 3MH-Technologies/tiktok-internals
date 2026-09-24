# تقرير: خوارزميات ونقاط API الداخلية لموقع TikTok

> **التاريخ:** 2026-09-24
> **طريقة التجميع:** فحص حي مباشر لنقاط النهاية (live probes) + مراجعة الأبحاث والمستودعات مفتوحة المصدر الموثقة للهندسة العكسية لتوقيعات TikTok.
> **ملاحظة مسؤولية:** كل المعلومات أدناه ناتجة عن بحث عام مفتوح المصدر وفحص لسلوك الخادم. الاستخدام مخالف لشروط استخدام TikTok (خاصة السحب الجماعي للبيانات) وقد يؤدي لحظر الحسابات/العناوين. استخدمها للأغراض التعليمية والبحثية فقط.

---

## 1) الصورة العامة: ثلاث طبقات

أثناء فحص الموقع مباشرةً:

1. **واجهة الموقع** `https://www.tiktok.com/` محمية بـ **WAF** (Slardar) — أي طلب HTTP عادي بدون تنفيذ JavaScript يُرد عليه بشاشة تحدي (`web_browser_challenge`)، حتى لو أرسلت User-Agent لمتصفح حقيقي.
2. **نقطة API نفسها** تُسجّل كـ `www.tiktok.com/api/<module>/<action>/` — بعضها يرد بيانات حقيقية بدون أي توقيع، والأغلبية يرد عليها الخادم بخطأ توقيع `"url doesn't match"` إذا لم تُرسل `X-Bogus` / `X-Gnarly` + `msToken`.
3. **الطبقة الداخلية (موبايل)** على خوادم منفصلة `*.tiktokv.com` بعلامات رأسية `X-Argus / X-Gorgan / X-Ladon / X-Khronos`.

رسائل الخطأ التي رصدتها حيًا من الخادم عند استدعاء نقاط النهاية بدون توقيع:

```json
{"log_pb":{"impr_id":"2026092416..."},"status_code":0,"status_msg":"url doesn't match"}
{"status_code":2483,"status_msg":"Please login your account first"}
{"statusCode":205001,"status_msg":""}   // poi/detail بمعرّف غير صالح
```

---

## 2) نقاط API الويب (www.tiktok.com/api/...)

كل نقطة نهاية تم التحقق منها مباشرة (ترد 200 + application/json) وكذلك موثقة في العميل مفتوح المصدر `TikTok-Api`.

| النقطة | الوظيفة | البارامترات الأساسية | التوقيع |
|---|---|---|---|
| `/api/user/detail/` | بيانات المستخدم | `uniqueId` / `secUid` | مطلوب |
| `/api/post/item_list/` | فيديوهات المستخدم | `secUid`, `cursor`, `count` | مطلوب |
| `/api/user/playlist` | قوائم تشغيل المستخدم | `secUid`, `cursor`, `count` | مطلوب |
| `/api/favorite/item_list` | فيديوهات أعجب بها (يتطلب تسجيل دخول) | `secUid`, `cursor`, `count` | جلسة |
| `/api/item/detail/` | تفاصيل فيديو واحد | `itemId` | مطلوب |
| `/api/comment/list/` | التعليقات على فيديو | `itemId`, `cursor`, `count` | مطلوب \(\*\) |
| `/api/comment/list/reply/` | ردود على تعليق | `itemId`, `commentId`, `cursor` | مطلوب |
| `/api/related/item_list/` | فيديوهات مشابهة | `itemId`, `cursor`, `count` | مطلوب |
| `/api/challenge/detail/` | بيانات الهاشتاج | `challengeName` | **يعمل بدون توقيع** ✅ (تحقق حي) |
| `/api/challenge/item_list/` | فيديوهات الهاشتاج | `challengeName`, `cursor`, `count` | مطلوب |
| `/api/mix/detail/` | بيانات قائمة تشغيل (Mix) | `mixId` | مطلوب |
| `/api/mix/item_list/` | فيديوهات القائمة | `mixId`, `cursor`, `count` | مطلوب |
| `/api/music/detail/` | بيانات الصوت | `musicId` | مطلوب |
| `/api/music/item_list/` | فيديوهات الصوت | `musicId`, `cursor`, `count` | مطلوب |
| `/api/search/{user\|item\|challenge\|music}/full/` | بحث متخصص بالكائن | `keyword`, `cursor`, `count`, `search_id`, `from_page=search` | مطلوب |
| `/api/search/general/full/` | بحث عام | `keyword`, `cursor`, `count` | مطلوب |
| `/api/recommend/item_list/` | تدفق "لك/For You" (الأقدم) | `count`, `cursor` | مطلوب |
| `/api/recommend/video/list/` | تدفق "لك" (الأحدث) | `count`, `cursor` | مطلوب |
| `/api/discover/full/` | اكتشاف/ترندات | `category`, maxCursor | مطلوب |
| `/api/feed/list/` | عرض كامل فيديوهات | `count` | مطلوب |
| `/api/poi/detail/` | بيانات مكان | `poiId` | مطلوب |
| `/api/note/detail/` | تفاصيل منشور صور (Note) | `noteId` | مطلوب |
| `/api/following/list/` & `/api/follower/list/` | المتابَعون/المتابِعون (يتطلب جلسة) | `secUid`, `cursor`, `count`, `sourceType=8` | جلسة |
| `/api/search/live/full/` | بحث البث المباشر | `keyword` | جلسة (2483 بدون) |
| `/api/graphql` | نقطة GraphQL (POST) | — | مطلوب |

\(\*\) الرد قد يحتوي على `error` لبعض العناصر المحذوفة؛ واجهة الويب تعيد الكيانات في حقول `itemList` / `comments` (بـ camelCase على الويب، مقابل snake_case في تطبيق الموبايل).

### البارامترات العامة (تُرسلها الواجهة مع كل طلب)

```
aid=1988
app_language=en
app_name=tiktok_web
browser_language=en
browser_name=Mozilla
browser_online=true
browser_platform=Win32
channel=tiktok_web
cookie_enabled=true
device_platform=web_pc
focus_state=true
history_len=2
is_fullscreen=false
is_page_visible=true
language=en
os=windows
priority_region=
region=US
screen_height=900
screen_width=1600
timezone_name=America/New_York
webcast_language=en
```

### الترحيل (Pagging)

نقاط النهاية المتسلسلة تستخدم `cursor` (رقم/string اعتمادًا على النقطة) + `count` + `maxCursor` أو `hasMore` في الرد، وبعضها يرد `has_more`.

---

## 3) خوارزميات توقيع الويب (الطبقة التي تمنع السحب)

هذه هي "الخوارزميات" القابلة للاستخراج فعليًا من كود الويب. كل طلب API مصحوب بها:

| الخوارزمية | الدور | الحالة الحالية |
|---|---|---|
| **msToken** | توكن منع إعادة الإرسال يُصدره الخادم (يُمرَّر في الـ query string) | إلزامي لمعظم النقاط |
| **ttwid** | معرف جلسة/جهاز في الكوكيز — يُحصل عليه بزيارة أولى للواجهة | إلزامي |
| **verifyFp** | بصمة المتصفح (من SDK التابع للتحقق) | مطلوب لبعض النقاط |
| **X-Bogus** | توقيع URL سابق — MD5 مزدوج + RC4 + Base64 بأبجدية منقولة، البادئة `\x02\xFF` | قديم (لا يزال يُقبل أحيانًا) |
| **X-Gnarly** | توقيع URL الحالي من `webmssdk` (إصدارات 5.x) | **الحالي إلزامي** |
| **X-Mssdk-Info** | بيانات تتبع مرافقة في الهيدر | مرافق |
| **strData / eData / ecData** | بيانات بصمة لتحديث msToken / بيانات كابتشا | موسمية |

### تنسيق X-Gnarly (توقيع الويب الحالي)

يبني التوقيع كائنًا ثم يشفّره بتيار تشفير من نوع ChaCha مخصص (مع مفتاح 48 بايت مدمج في النص المشفر) بتنسيق TLV:

| الحقل | المعنى |
|---|---|
| 0 | رأس XOR يربط كل الأعداد الصحيحة (يُكتب أخيرًا) |
| 1 | ثابت `65` |
| 2 | `ubcode` — فئة النقطة (افتراضي `4` لـ `/api/post/...`) |
| 3 | MD5(QueryString) — hex |
| 4 | MD5(body) — `""` (للـ GET) |
| 5 | MD5(User-Agent) |
| 6 | Unix seconds |
| 7 | ثابت مبني داخل الـ SDK (مثل `3181061566`) |
| 8 | `now % 0x80000000` (المللي ثانية منخفضة 31 بت) |
| 9 | إصدار الحمولة (مثل `5.1.3-ZTCA`) |
| 10 | إصدار `webmssdk` (مثل `1.0.0.368`) |
| 11 | ثابت `1` |
| 12–13 | عدادات الطلبات المعترضة (XHR + fetch) |
| 14 | مرتفع 16 بت = `1 << 16`، منخفض 16 بت = عشوائي |
| 15 | uint32 عشوائي |

إصدارات الحمولة الموثقة: `5.1.0` (2025-05)، `5.1.3` (2025-11)، `5.1.3-ZTCA` (2026-04)، `5.2.x`، ثم `5.3.0` و`5.3.1` (2026-07). **النسخة الحية على الـ CDN الرسمي وقت الفحص (2026-09): `webmssdk 2.0.0.520` ← حمولة `5.3.0`.**

### تنسيق X-Bogus (القديم)

1. MD5 مزدوج لبارامترات URL + الجسم.
2. RC4 لـ User-Agent بمفتاح `[0,1,14]` ثم Base64 + MD5.
3. بناء مصفوفة (طابع زمني + ثابت `536919696` + الهاشات).
4. تصفية/خلط → RC4 بمفتاح `[255]` → بادئة `\x02\xFF` → Base64 بأبجدية `Dkdpgh4ZKsQB80/Mfvw36XI1R25-WUAlEi7NLboqYTOPuzmFjJnryx9HVGcaStCe`.

### خط سير الاستخدام العملي للويب

1. زيارة أولى للواجهة للحصول على كوكيز `ttwid` + `msToken` (أو استخراج msToken من كوكيز متصفح مسجّل دخول).
2. بناء البارامترات العامة + بارامترات النقطة.
3. حساب `X-Bogus`/`X-Gnarly` على الـ query string (مع ثبات نفس User-Agent المستخدم في الحساب — أي تغيير فيه يكسر MD5 الحقل 5).
4. إضافة `msToken` داخل الـ query string قبل التوقيع.
5. إرسال مع إبقاء نفس الجلسة (كوكيز) لفترة.

---

## 4) خوارزميات توقيع الموبايل (خوادم *.tiktokv.com)

المضيف: `api{N}-{zone}.tiktokv.com` مثل `api19-core-c-alisg.tiktokv.com` وقواعد `useast1a / useast8 / maliva / useast5`، والنقاط بصيغة `/aweme/v1/<module>/<action>/` (feed, aweme/detail, user/profile, comment/list, user/follower/list...).

كل طلب يحمل 5 قيم أمنية تتفق مع بعضها ومع جهاز ثابت (`device_id` الرقمي):

| الرأس | الخوارزمية | الوصف |
|---|---|---|
| `X-Khronos` | XOR + طابع زمني | ختم الزمن: `XOR(md5(key)[:4], pack(ts))` — يمنع إعادة اللعب |
| `X-Gorgon` | سلسلة MD5 من 4 جولات + XOR | سلامة الطلب — MD5 لـ `(path|md5(body)|khronos)` ثم 4 جولات بشرائح مختلفة من الهاش السابق + الطابع الزمني والمفتاح، والمخرج النهائي XOR مع المفتاح ثم hex (بدون هاش ختامي)، البادئة `0404` |
| `X-Ladon` | AES-128 (SPN) | إثبات أن الطلب من تطبيق حقيقي على جهاز حقيقي |
| `X-Argus` | protobuf → SM3 → SIMON → AES | التوقيع الرئيسي للموبايل |
| `X-TT-Ticket-Guard` | SECP256k1 ECDSA | زوج مفاتيح لكل جلسة؛ يوقع كل طلب (`public_x.signature_hex`) مع إصدار=3 ومعرّف مفتاح=1 |
| الجسم `TTEncrypt` | ChaCha20 stream | تشفير جسم الطلب (ثابت "expand 32-byte k") |

المفتاح الجذع لكل هذه الطبقات: `MD5(f"{device_id}|{version_code}|{aid}")`. تغيير أي عنصر في هذه الثلاثية يغير كل التوقيعات.

ملاحظة: `X-Gorgon` مهجور في أحدث النسخ، والنسبة الأحدث تعتمد `X-Argus/X-Ladon/X-Khronos` + `TicketGuard`.

---

## 5) خوارزمية التوصيات ("لك / For You")

**التفسير الرسمي من TikTok:**

الترتيب يعتمد على عوامل مُرجّحة:
- تفاعلات المستخدم: إعجاب، مشاركة، متابعة، تعليق، محتوى تنشره.
- معلومات الفيديو: الوصف (caption)، الصوت، الهاشتاج.
- إعدادات الجهاز والحساب: اللغة، البلد، نوع الجهاز (وزن أقل).

تفاصيل رسمية مهمة:
- إتمام مشاهدة فيديو طويل من البداية للنهاية = إشارة قوية جدًا (أقوى بكثير من "المشاهد والمنشئ من نفس البلد").
- **عدد المتابَعين ليس عاملًا مباشرًا** في التوصية (لكن الفيديوهات من الحسابات الكبيرة تجد جمهورها أسرع).
- المستخدم الجديد يختار اهتمامات؛ ومن لم يختر يبدأ بتدفق عام.
- تنويع مقصود: لا يُعرض فيديوهان متتاليان بنفس الصوت أو لنفس المنشئ؛ لا يُعاد المحتوى الذي شوهد؛ يُخلط محتوى خارج الاهتمامات (استكشاف vs. استغلال).
- المحتوى قيد المراجعة/السبام غير مؤهل للتوصية.

**النتائج البحثية القابلة للتحقق (audits من 2023–2025):**

| النتيجة | المرجع |
|---|---|
| الاستغلال (exploit) للاهتمامات في **30–50%** من أول 1000 فيديو موصى به | arxiv 2403.12410 |
| **الإعجاب والمتابعة** هما أقوى محرّكي التخصيص | arxiv 2403.12410 + audits أخرى |
| ~50% من وقت المشاهدة اليومي على أفضل 5 مجموعات محتوى، لكن عبر 6 أشهر فقط ~22% من الوقت فيها (التناوب طويل المدى) | arxiv 2503.20030 |
| فقط ~45% من المشاهدات تكتمل (والمكتمل لا يزيد مع الوقت) — دليل على خلط "تعزيز/تثبيط" مقصود للاحتفاظ | ACM CHI 2024 |
| موضوعات شائعة (طعام/عناية) → تشابه 60–80% في النوافذ المنزلقة؛ لا يوجد دليل على "أرانب معلومات" للموضوعات المتطرفة | ICWSM 2025 (ClipMind) |
| شرح "لماذا هذا الفيديو؟" غير دقيق غالبًا (مثال: حساب بلا أي تعليقات يرى "علّقت على فيديوهات مشابهة" في 34% من الحالات) | ICWSM 2024 |

**البنية الداخلية الفعلية (غير موثقة علنًا):** النموذج الحقيقي غير منشور؛ TikTok يوفر "مركز الشفافية" في لوس أنجلوس لمراجعة كود الخوارزمية للمختصين المدعوين فقط. ما سبق هو آخر ما يصل إليه البحث الخارجي.

---

## 6) ملخص خطوات "استخراج" أعمق (لو أردت التأكد مستقبلًا)

1. افتح `tiktok.com` في متصفح حقيقي (مع فاتح DevTools → Network) واجمع الطلبات — ستشاهد نقاط النهاية أعلاه بنفسها.
2. الـ JS الخاص بالتوقيع يُسحب من CDN التابع لـ ByteDance (`*.ttwstatic.com`) باسم `webmssdk`/`secsdk`، والإصدار الحالي `5.3.1`.
3. قارن معتادًا: `X-Gnarly` يُحدَّث كل بضعة أسابيع — أي تكامل جاد يحتاج لمتابعة إصدار الـ SDK.

**أدوات/مراجع مفتوحة المصدر للدراسة:** `TikTok-Api` (davidteather)، `tiktok-web-reverse-engineering` (justscrapeme)، `tiktok-xgnarly-decoded`، repo الخاص بـ `armxe/tiktok-api` لطبقة الموبايل (Python)، ومدونة `mumd.dev` "Reversing TikTok's Request Signing and Encryption".

---

---

## 7) الفحص العميق (جلسة استخراج فعلية — 2026-09-24)

### 7.1 حزم webmssdk الحية (سُحبت من الـ CDN الرسمي وحُللت)

| الحزمة | الحجم | الإصدار المضمّن | ملاحظات |
|---|---|---|---|
| `webmssdk/1.0.0.170` (login CDN) | 90KB | — | سابقة: X-Bogus فقط |
| `webmssdk/1.0.0.195` (secsdk CDN) | 288KB | — | `X-Bogus`, `frontierSign`, `ubcode`, `strData` |
| `webmssdk/2.0.0.447` (tx CDN) | 223KB | **5.1.3** | أول ما يحمل `X-Gnarly` |
| `webmssdk/2.0.0.485` (tx CDN) | 237KB | **5.1.3-ZTCA** | علامات ZTCA (تحميل سكربت ZTCA + التوقيع) |
| `webmssdk/2.0.0.520` (tx CDN) — **الحي** | 229KB | **5.3.0** | النسخة الحالية وقت الفحص |

المسارات: `lf16-tiktok-web.tiktokcdn-us.com/obj/tiktok-web-tx/webmssdk/<v>/webmssdk.js` و`sf16-website-login.neutral.ttwstatic.com/obj/tiktok_web_login_static/webmssdk/<v>/webmssdk.js`.

### 7.2 ما استُخرج من داخل الحزمة 2.0.0.520 (تحليل سلاسل)

- **`frontierSign`** — مدخل التوقيع العام: `prototype.frontierSign=V` (يستدعي VM عبر `K(<id>, r, ...)`) — أي طلب بدون تسجيل دخول بيستخدمه.
- **سلسلة التوليد:** `c → addParam("X-Bogus", a) → addParam("X-Gnarly", v)`.

  **📌 أي **X-Gnarly** لازم يُحسب فوق الـ query **مع إضافة **X-Bogus** فيها** (مش فوق الـ query الخام): أي توقيع X-Gnarly بدون X-Bogus صحاح = لكن التطبيق يبنيهما معًا بهذا الترتيب.
- **`ubcode`** — القيمة الافتراضية `0` في الكائن، والـ UB code بتختلف حسب فئة النقطة (0 لمعظم القراءة/الكتابة، 4 لـ `/api/post/...`، 14 لوحظ في عينات من 2025).
- **`strData`** → `{"magic":538969122,"version":1,"dataType":8,"strData":"...","tspFromClient":<ms>}` — نفس البنية اللي بتتبعت لـ `mssdk.bytedance.com/web/common` لتجديد **msToken**.
- **`msToken`** — بيمرر في الـ query داخل التوقيع: `["msToken", msToken]` (وأحيانًا `__ac_testid`).
- نقاط `/api/` داخل الحزمة: `/web/report`, `/web/common` (نقطتا الـ MSSDK).

### 7.3 إعادة إنتاج X-Gnarly للنسخة الحية (5.3.0) والتحقق

بنينا مُولِّد X-Gnarly نقيًا (من الـ clean-room reference الموسّع) بمفاتيح:

```
x-gnarly = encode(queryString+msToken+X-Bogus, body="", userAgent,
                   counters, {ubcode, sdkVersion:"2.0.0.520", payloadVersion:"5.3.0"})
```

نتيجة تدوير `encode → decode` على توليدتنا:

| الحقل | القيمة المولّدة | التحقق |
|---|---|---|
| 0 | XOR header: 3522928782 | ✓ يسترده الـ decoder |
| 1 | 65 | ✓ |
| 2 | ubcode=4 | ✓ |
| 3 | MD5(query) = `36b162dbe…` | **✓ طابق الـ MD5 المستقل اللي حسبناه** |
| 4 | `d41d8cd98f00b204e9800998ecf8427e` = MD5("") | ✓ جسم GET فارغ |
| 5 | MD5(UA) | ✓ |
| 6 | Unix timestamp | ✓ |
| 7 | 3181061566 (ثابت SDK) | ✓ |
| 8 | ts % 0x80000000 | ✓ |
| 9 | `5.3.0` | ✓ |
| 10 | `2.0.0.520` | ✓ |
| 14 | (65<<16) | عشوائي منخفض ✓ |
| 15 | uint32 عشوائي | ✓ |

المفتاح اختُزن داخل النص المشفر في `keyStart=185` واسترجعناه ✓ — الإخراج 316 حرفًا (الطول الصحيح لفئة 5.1.3/5.3.0، مقابل ~332 لـ ZTCA).

الطول الفعلي لوحظ: **X-Bogus = 28 حرفًا** و**X-Gnarly = 316 حرفًا**.

### 7.4 اختبارات الـ API الحي (بالتوقيع + كوكيز حقيقية) — النتائج والحواجز

خطوات الاختبار الفعلي:
1. زيارة `/player/v1/` + نقط `/api/` → جمع الكوكيز → **الخادم يمنح `msToken` (120 حرفًا)** في `set-cookie` **وهيدر `x-ms-token` معًا** (لا يوجد "تدوير" — نفس القيمة).
2. بناء الـ query بترتيب الويب + `device_id` + `fromWeb=1` + msToken.
3. توقيع `X-Bogus` ثم `X-Gnarly` فوق الـ query كاملًا.
4. إرسال مع الكوكيز ومراعاة فترة هدوء بين الطلبات.

النتيجة: **`POST /api/user/detail/` و`/api/post/item_list/` و`/api/challenge/item_list/` و`/api/comment/list/` ردّت `200` + جسم فارغ** — مع هيدرات دالة:

| الهيدر | القيمة | الدلالة |
|---|---|---|
| `tt-ticket-guard-result` | `0` | ✅ بوابة التذكرة **تعدّي** — التوقيع مقبول هيكليًا |
| `tt_orcas_res` | `1` | ⛔ محرك الخطر **Orcas** مسك الطلب وحذف الرد |
| `x-janus-mini-api-forward` | `Janus-Mini(fast)` | بوابة Janus-Mini (مسار النقاط المحمية) |
| `x-ms-token` | (نفس الـ cookie) | إصدار/تعزيز msToken |
| `x-cache` / `x-akamai-request-id` | Akamai | البنية أمام CDN/أكاماى |

المقارنة مع نقطة الشالنج الشغالة `/api/challenge/detail/` (رد كامل 724B) — **لا يوجد** `tt_orcas_res` ولا `x-janus-mini-api-forward`: تعمل بمسار غير محمي.

**الخلاصة التقنية:** حاجز القراءة-البيانات الحالي في الويب ليس "التوقيع" فقط — التوقيع مررناه (TicketGuard=0) — بل **التقييم الكامل لبيئة المتصفح** (بصمة canvas، `verifyFp`، هيدر `X-Mssdk-Info`، `ttwid`/`tt_webid`، hit-rate سلوكي) اللي بيقيمها محرك Orcas فترد فارغة دون أي رسالة. لهذا كل الأدوات المحترمة (مثل TikTok-Api) تشغّل **متصفحًا حقيقيًا (Playwright + stealth)** وتقرأ الـ msToken من الجلسة.

### 7.5 msToken — التدفق الكامل

- **منح:** أي طلب `/api/*` محمي يرد بهيدر `x-ms-token` + `set-cookie` بنفس القيمة (~120 حرفًا URL-safe base64).
- **تجديد:** الحزمة تبني `strData` (بصمة مضغوطة/مشفرة) وترسله `POST https://mssdk.bytedance.com/web/common` بـ `{magic:538969122,version:1,dataType:8,strData,tspFromClient:Date.now(),ulr:0}`.
- فحصناه حيًا: جلب بـ strData عتيق → `{"maigc":538051346,"version":1,"resultCode":-7,"dataType":8}` (رفض). تحويل strData سليم يتطلب توليده من كود الحزمة (خوارزمية ضغط+تشفير خاصة).
- ملاحظة: أدوات سحب بسيطة ترسل **msToken وهمي (سلسلة عشوائية 156 حرفًا)** — يقرّب البعض النقاط لكنه غير مضمون؛ الخادم يقيّم صلاحية التوكن.

### 7.6 X-Mssdk-Info (هيدر بصمة البيئة) — البنية المفككة

| الخاصية | القيمة |
|---|---|
| التشفير | **XXTEA** (دلتا `0x9E3779B9`) |
| الجولات | `6 + floor(52/n)` (n = عدد الكلمات) |
| المفتاح | بذرة 4 بايت ASCII عشوائية (مثل `spum`) معبأة LE حتى 4 كلمات |
| الحمولة | JSON تتبع (hardwareConcurrency, WebGL renderer, الشاشة, plugins...) معبأة كلمات LE + طول البايت الأصلي كذيل |
| الإخراج | `البذرة4 + Base64(النص المشفر)` — الخادم يفكها لتقييم الثقة |

### 7.7 خريطة الردود (لو صدفتهم بنفسك — كيف تقرأ النتيجة)

| الرد | المعنى |
|---|---|
| `{"status_code":0,"status_msg":"url doesn't match"}` | التوقيع ناقص/خاطئ (X-Bogus/X-Gnarly) |
| `200` + جسم فارغ + `tt_orcas_res:1` | Orcas حذف الطلب: بيئة المتصفح غير مكتملة |
| `{"status_code":2483,...}"Please login your account first"` | يتطلب تسجيل دخول |
| `{"statusCode":205001,...}` | معرّف/سؤال غير صالح (POI...) |
| 400 (oEmbed/embed/v2) | الفيديو المحذوف/غير متاح إقليميًا |
| 404/200-HTML (rss) | طرق RSS تعود بصفحة SPA بدل XML حقيقي |
| 429 (خوادم tiktokv.com) | "ratelimit triggered" — خنق المعدل |

---

## 8) الطريق العام النظيف — يعمل الآن من غير توقيع ومن غير متصفح (مُفحص حي)

في 2026-09-24 اكتُشف أن **واجهتَين رسميتين عامتين** ما زالتا تمنحان بيانات فيديوهات كاملة **بدون X-Gnarly ولا X-Bogus ولا كوكيز** (حالة طلب نظيفة من أي سكربت):

### 8.1 oEmbed — الميتاداتا الرسمية (تعمل 100%)

```
GET https://www.tiktok.com/oembed?url=https://www.tiktok.com/@USER/video/ITEMID&format=json
```

مُتحقق حيًا (200 JSON) على فيديوهات حية من الحساب الرسمي:

| الحقل | مثال فعلي |
|---|---|
| `title` | "why do fans keep posting 🥚 …" |
| `author_name` / `author_url` | TikTok / https://www.tiktok.com/@tiktok |
| `author_unique_id` | tiktok |
| `thumbnail_url` | (رابط CDN للغلاف) |
| `html` | كود تضمين `<blockquote class="tiktok-embed" data-video-id="…">` |
| `embed_product_id` / `embed_type` | معرف المنتج ونوع التضمين |

✓ بدون أي توقيع. الوحيد حساس لصحة الـ itemId (400 لو الفيديو محذوف/محجوب إقليميًا).

### 8.2 embed/v2 — بيانات الفيديو الكاملة + رابط التشغيل (الجوهرة الفعلية)

```
GET https://www.tiktok.com/embed/v2/ITEMID   ← HTML حوالي 311KB
```

الرد SSR يحوي JSON `videoData` متضمّنًا **كل شيء** (استخرجناه وبنيناه ملفات JSON حقيقية):

| المسار في الـ JSON | المحتوى | مثال حي |
|---|---|---|
| `itemInfos.id` | رقم الفيديو | 7673909736131038495 |
| `itemInfos.text` | الوصف | "…Safety first, inspiration second…" |
| `itemInfos.createTime` | تاريخ النشر (يونكس) | 1786721366 |
| `itemInfos.video.urls[0]` | **رابط تشغيل MP4 موقّع** | `https://v45.tiktokcdn.com/…?a=1233&bti=…&ft=…&rc=…&vvpl=1&l=…&VExpiration=1790412151&VSignature=…&btag=e00095000&sp_exp=hash_v0` |
| `itemInfos.video.videoMeta` | الأبعاد/المدة | 720×1280 / 63ث |
| `itemInfos.diggCount/playCount/commentCount/shareCount` | الإحصائيات | 22500 / 598400 / 4112 / 2437 |
| `itemInfos.covers[0]` | الغلاف (CDN موقّع x-signature) | p16-common-sign.tiktokcdn.com… |
| `authorInfos` | secUid / userId / nickName / verified | TikTok / 107955 / موثّق |
| `authorStats` | متابعون/قلوب/فيديوهات | 95.9M / 464.6M / 1507 |
| `musicInfos` | اسم الأغنية + رابط صوت (v16m…) | "original sound" |
| `challengeInfoList` | الهاشتاجات بأرقامها | fyp=229207, learnontiktok=1636483010861062 |

**التحقق:** طلب `Range: bytes=0-2048` على روابط التشغيل الأربعة كلها رجع **`206 Partial Content` + `Content-Type: video/mp4`** والبايتات الأولى = `00000020 66747970 69736f6d` = **صندوق `ftyp isom`** — ملفات فيديو MP4 حقيقية تُبث من `*.tiktokcdn.com` (v16m/45/58...).

**فك رابط CDN الموقّع:**
`a=1233` (playback aid) · `bt`/`bti` = ترميز تجاري · `ft` = مفتاح بث مشفر · `rc` = بيانات تحكم تدفق · `VVPL=1` · `l` = معرّف سجل · **`VExpiration` + `VSignature`** = توقيع بزمن صلاحية (ينتهي التدفق بعدها) · `btag=e00095000` · `sp_exp=hash_v0`.

**طريقة استخراج JSON من HTML (التي استخدمناها):**
1. ابحث عن `"videoData"` داخل النص، ثم خذ الكتلة بميزان الأقواس `{}` مع تجاهل ما بين علامتي اقتباس.
2. لُفّها: `JSON.parse("{" + بلوك + "}").videoData`.
3. أصلح `U+2028/U+2029` (يكسران JSON.parse) إن لزم.
4. احفظ واحلل.

### 8.3 سلوك الحد الأقصى وقيوده

- أحيانًا `embed/v2` يعيد **503** عند إطلاق الطلبات بسرعة → انتظر (نوم 5-8ث) وأعد المحاولة (أفلح في فحصنا).
- **يعمل لكل فيديو على حدة** — تحتاج معرّفات `ITEMID` (مصادرها: محركات البحث، صفحات المؤثرين، أي مصدر يعدد الروابط).
- **لا يوجد بحث/تغذية/قائمة مقاطع** هنا: أي نقاط قائمة (feed/search/challenge/item_list) تظل خلف Orcas (انظر 7.4).
- روابط CDN للتشغيل **تنتهي** عند `VExpiration` — يجب تخزين الفيديو فورًا إن رغبت.

### 8.4 لماذا هذا مهم (وما زال قائمًا)

هذا **المسار الوحيد الحالي لجلب بيانات/فيديو حقيقي بدون متصفح وبدون فك أكثر للتشفير**:
`معرف الفيديو → oEmbed (ميتاداتا) + embed/v2 (الكل) → MP4 من CDN`.
أي أداة سحب "خفيفة" (Python/Node بلا متصفح) تستطيع البناء عليه مباشرة، مع مراعاة ملاحظة المسؤولية أدناه وبقاء التحقق من الامتثال مسؤوليتك.

### 8.5 الأداة الجاهزة (مفحوصة حيًا)

`webmssdk-analysis/get-video.mjs` — CLI كامل على هذا المسار:

```
node get-video.mjs https://www.tiktok.com/@tiktok/video/7673909736131038495 --download video.mp4
node get-video.mjs 7673909736131038495                    (ميتاداتا فقط + ملف JSON)
```

تعمل: oEmbed (200) ← استخراج videoData من embed/v2 ← حفظ `ITEMID.json` ← تحميل MP4 من CDN. **فُحصت حيًا ونزّلت 5MB فيديو حقيقي** بعلامة `ftyp` سليمة. ملفات JSON الفعلية للأمثلة الأربعة في `webmssdk-analysis/live-videos/`.

### 8.6 الجامع الآلي للحساب الكامل (مُفحص حيًا — حسابان، 13/14 فيديو)

**معضلة الجمع:** قائمة فيديوهات اليوزر تأتي أساسًا من `POST /api/post/item_list/` الموقّعة (خلف Orcas — انظر 7.4). الحل العملي بدون متصفح: **أنبوب ثلاثي المصادر** للـ IDs، ثم أنبوبنا الرسمي للإثراء:

```
node user-collect.mjs USERNAME [--limit N] [--delay MS] [--download DIR] [--maxdl K] [--ids 'id1,id2,...' | --ids @file.txt]
```

**طبقة الجمع (best-effort، أي مصدر ينجح يكفي):**
1. **Urlebird** (`https://www.urlebird.com/user/<USER>/`) — مرآة عامة بلا WAF بنفسها، تعرض **أول ~18 فيديو** لكل حساب مع روابط CDN مضمّنة أحيانًا؛ ثبت محليًا إمكانية تحدّي Cloudflare للـ IP أحيانًا (403 "Just a moment…").
2. **Jina Reader** (`https://r.jina.ai/https://www.tiktok.com/@USER`) — بروكسي قراءة خلف متصفح حقيقي يعبر بصفحة البروفايل خلف الـ Slardar WAF ويحوّلها Markdown → ~12 معرّف (فُحص حيًا على `@tiktok`). قد يخرج بدون قائمة الفيديو لبعض الحسابات (SSR ناقص).
3. **يدوي `--ids`** — يمرر أي قائمة (من بحث ويب، أرشيف، أو أي مصدر) ويحوّل الجامع لآلة إثراء خالصة. **هذا الوضع هو الأقوى** لأنه لا يعتمد على أي مصدر خارجي.

**طبقة الإثراء (لكل ID):** oEmbed (رسمي) + embed/v2 (قسم 8.2) → `accounts/<USER>/<ID>.json` + CSV ملخص بترميز UTF-8-BOM + تحميل MP4 اختياري (`--maxdl`).

| الاختبار الحي (2026-09-24) | `@tiktok` | `@charlidamelio` |
|---|---|---|
| طريقة الجمع | Jina تلقائي (12 ID) | `--ids` يدوي (6 من بحث ويب) |
| النتيجة | **8/8 ✓** | **5/6 ✓** (واحد محذوف → HTTP 400 وتُخطّى) |
| المشاهدات الحية | 597.6K / 486.4K / 378.3K… | **54.7M / 22.3M / 20.3M / 19M / 15M** |
| تحقق خارجي | — | فيديو 7663656667132857613: Toklytics قال 50.5M (يوليو) والأنبوب الرسمي **54.7M الآن** — حيّ وأحدث |
| الملفات | `accounts/tiktok/*.json` + CSV + فيديوهات 7MB/8MB | `accounts/charlidamelio/*.json` + CSV |
| بيانات حية إضافية | hashtag `songsofthesummer2026` | secUid، digg 6.8M، shares 60.3K، music ID |

**سلوك الأخطاء:** فيديو محذوف/مقفول → oEmbed 400 و embed/v2 400 → يُخطّى ويكمل؛ ضغطة 503 على embed/v2 → إعادة محاولة بنوم 6 ثوانٍ.

**حدود معلنة (بأمانة):** المصادر الخارجية للجمع (Urlebird/Jina) قد تفرض تحدّي Cloudflare مؤقتًا على IP بعض الأجهزة، لكن **أنبوب الإثراء الرسمي (oEmbed + embed/v2) مستقل عنها ويعمل دائمًا** — ولهذا `--ids` هو المخرج الموثوق. **جمع الأرشيف الكامل** لحساب قديم يتطلب تمرير `cursor` عبر الـ API الموقّع (بكسر Orcas أو بمتصفح حقيقي — ممنوع هنا) — هذا هو السقف الحالي للطريقة الخفيفة.

### 8.7 التشخيص السريع لسلوك الجدران (أداة `probe-local.mjs`)

سكربت تشخيص محلي يوضح الفرق بين الـ egresses: في نفس اللحظة، الوصول عبر `execute` runtime اخترق Urlebird (200/18 ID) بينما `node` المحلي حصل على 403 "Just a moment…" من Cloudflare — دليل أن **النافذة تختلف حسب بصمة TLS ومصداقية IP وليس بالروابط أو الـ UA** (جرّبنا UA كامل مع sec-fetch-* ولم يتغير شيء). يستخدم للتمييز بين «الرابط انكسر» و«الواجهة تحدي الـ IP».

### 8.8 تحويل الأدوات إلى بايثون (حزمة `tiktok-py` — أداة لكل وظيفة)

تم نقل المجموعة كاملة إلى **بايثون خالص (stdlib فقط، بدون متصفح)** في `tiktok-py/`، مقسّمة بوضوح — كل ملف أداة بوظيفة مستقلة:

| # | الأداة | الملف | الوظيفة |
|---|---|---|---|
| ⚙️ | HTTP | `tiktok_tools/http.py` | طلبات موحّدة بهوية Chrome، بلا استثناءات مفاجئة |
| 🔎 | المعرّفات | `tiktok_tools/ids.py` | Urlebird → Jina → يدوي `--ids` |
| 📊 | البيانات | `tiktok_tools/metadata.py` | oEmbed + embed/v2 (أعد المحاولة عند 503) |
| ⬇️ | التنزيل | `tiktok_tools/download.py` | MP4 من CDN بطلبات Range |
| 💾 | الحفظ | `tiktok_tools/storage.py` | JSON + CSV بـ UTF-8-BOM |
| 🧠 | الجمع | `tiktok_tools/collector.py` | مدير حساب كامل |
| 🔬 | التشخيص | `tiktok_tools/probe.py` | يميز مكسور الرابط من تحدي الـ IP |
| ✍️ | التوقيعات | `tiktok_tools/sign.py` | **نقل كامل** X-Gnarly + X-Bogus + تحقق ذاتي |

**نقل التوقيعات مُثبت رياضيًا:** `python main.py selftest` يفك X-Gnarly (يسترجع المفتاح من موضع الإدراج ← يشتق الجولات `[5,20]` ← يفك ChaCha) ويثبت مطابقة الحقول 3/4/5 لـ MD5 المدخلات. و **X-Bogus مطابق بتّة-بتّة لمرجع الـ node** — لنفس الزمن والمدخلات أخرج الطرفان حرفياً:
`DFtzs1rXVpR-pNbPq-XJ-xoHc/PB`.

**التحقق الحي من البايثون (2026-09-24):** `video 7673909736131038495` → 598,500 مشاهدة + تنزيل 5.3MB؛ `user tiktok --ids …` → 3/3 مجمعة. الإخراج في `tiktok-py/outputs/accounts/`.

**أوامر الاستخدام:**
```bash
python main.py video <url|id> -o out --download out/v.mp4
python main.py user <يوزر> --limit 5 --download vids --maxdl 2 [--ids 'a,b,c' | --ids @ملف]
python main.py probe <رابط>          # تشخيص الجدران
python main.py selftest              # إثبات سليمة التوقيعين
```

---

*تنبيه أخير: هذه المعلومات لأغراض التوعية الأمنية والبحث الأكاديمي. السحب الآلي الجماعي من TikTok، وتجاوز توقيعاتها، واستخدام الحسابات المؤتمتة قد يخالف شروط الخدمة وقوانين بلدك وقد يؤدي لحظر نهائي.*