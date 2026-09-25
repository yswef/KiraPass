# Example pages · صفحات مثال

هذا المجلد مخصّص لنسخ من صفحات دخول الشبكات التي تختبرها، حتى تبقى موثّقة
داخل المستودع ويستخدمها التطوير لاحقاً للاختبار.

**الحالة الحالية: المجلد فارغ** — لم تُرفع أي صفحة بعد.

## كيف ترفع صفحة الدخول (خطوتان)

1. افتح صفحة الدخول في المتصفح، ثم:
   * **حفظ الصفحة:** `Ctrl+S` (ويندوز) أو `Cmd+S` (ماك) → اختر «صفحة HTML كاملة».
   * **أو الأفضل للتحليل:** `Ctrl+U` لعرض الكود المصدري ثم انسخه كاملاً والصقه في
     ملف نصي.
2. سمِّ الملف بوضوح وضعه هنا، مثال:

```
Example pages/
├── hotspot-login.html        # الصفحة كما تظهر للضيف
├── hotspot-login.md5.js      # ملف التشفير إن وُجد (md5.js)
└── router-status.html        # صفحة الحالة/الخروج إن أمكن
```

## لماذا يفيدنا هذا؟

* نتأكد أن قارئ الصفحة (POST/GET، أسماء الحقول، الحقول المخفية `dst` و`popup`،
  ووجود تشفير `chap`) يتعامل مع صفحتك بالضبط.
* يمكن إضافة الصفحة كحالة اختبار جديدة في `tests/` بدل الاعتماد على نموذج عام.

> ⚠️ إن كانت الصفحة تحتوي بيانات حقيقية (أرقام كروت، عناوين MAC/IP لزوار)،
> فاحذفها قبل الرفع. الأداة لا تحتاج إلا إلى **شكل** الصفحة.

---

**English (short):** keep unmodified copies of real hotspot login pages here
(`hotspot-login.html`, optional `md5.js`). They are committed on purpose so the
parser stays correct and new test cases can be added. Remove any real card
numbers, MAC or IP addresses first - only the page *shape* is needed.
