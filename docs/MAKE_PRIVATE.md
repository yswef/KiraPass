# جعل المستودع خاصاً · Making the repository private
### yswef/KiraPass

> **ملاحظة صريحة قبل البدء:** التحويل إلى «خاص» يمنع الناس من **رؤية** المستودع
> من الآن فصاعداً، لكنه **لا يستعيد** ما نُسخ أو استُنسخ سابقاً (Fork/Clone).
> لذلك ملف الترخيص [AUTHORIZED_USE_LICENSE.md](../AUTHORIZED_USE_LICENSE.md)
> مهم: يجعل الاستخدام بدون إذن مخالفاً صراحةً حتى لو حصل أحد على نسخة.

---

> ⚠️ **إن ظهرت لك رسالة** `Resource not accessible by integration` (أو 403) عند
> تنفيذ الأمرين بالأسفل، فالسبب أن **الرمز (token) المستخدم لا يملك صلاحية
> admin على المستودع** — صلاحية الكتابة على الكود لا تكفي لتغيير الإعدادات.
> الحل: استخدم طريق الواجهة (الطريقة ١) أو سجّل الدخول بحسابك أنت على جهازك
> (`gh auth login`) ثم نفّذ الأمر. لا تشارك رمزاً يملك صلاحية إعدادات مع أي
> أداة لا تثق بها.

---

## الطريقة ١ — من واجهة GitHub (الأسهل)

1. افتح المستودع: <https://github.com/yswef/KiraPass>
2. **Settings** (أعلى الصفحة).
3. انزل إلى آخر الصفحة حتى قسم **Danger Zone**.
4. عند **Change repository visibility** اضغط **Change visibility**.
5. اختر **Make private**.
6. اكتب اسم المستودع كما يطلبه: `yswef/KiraPass` ثم أكّد.
7. اخرج من الصفحة وافتح الرابط في نافذة متصفح **متخفّية (Incognito)** — يجب أن
   ترى «404» أو دعوة لتسجيل الدخول. هذا هو التحقق العملي.

## الطريقة ٢ — من الطرفية (مع `gh`)

```bash
# تأكد من الحساب المسجَّل
gh auth status

# الحالة الحالية
gh repo view yswef/KiraPass --json visibility,nameWithOwner

# التحويل إلى خاص
gh repo edit yswef/KiraPass --visibility private \
  --accept-visibility-change-consequences

# التحقق
gh repo view yswef/KiraPass --json visibility
# الناتج المتوقع: {"visibility":"PRIVATE"}
```

---

## ماذا يحدث فعلاً (حقائق يجب أن تعرفها)

| الأمر | النتيجة |
|---|---|
| المستودع يصبح خاصاً | لا يستطيع أحد غيرك (وغير من تضيفه كمتعاون) رؤيته أو استنساخه |
| **Forks الموجودة** | GitHub **يفصلها** إلى شبكة مستقلة وتبقى **عامة كما هي** — لا تصبح خاصة ولا تُحذف تلقائياً [1](https://docs.github.com/articles/setting-repository-visibility) |
| **النسخ المستنسخة (clones)** | تبقى على أجهزة من نزّلها — لا يمكن سحبها |
| GitHub Pages | يُنشر تلقائياً من النشر إن كان منشوراً |
| سجلّ Git (history) | يبقى كما هو — الملفات المحذوفة سابقاً تظل في السجل |

## خطوات إضافية أنصح بها (بالترتيب)

### ١) تأكد أن ملفات بياناتك ليست في Git
الأداة الجديدة تحفظ كل شيء في `kirapass_data/` وهي مُستثناة في `.gitignore`.
تأكد دائماً:

```bash
git status --short          # يجب ألا يظهر أي ملف من kirapass_data/
git check-ignore -v kirapass_data/settings.json
```

### ٢) احذف من «السجل» ما لا تريد بقاءه (اختياري لكن مستحسن)
الملف القديم `kirapass_hits.txt` يحتوي أرقام بطاقات من شبكة صديقك. حُذف من
النسخة الحالية، لكنه باقٍ في تاريخ المستودع. لتنظيف التاريخ:

```bash
# نسخة احتياطية أولاً
cp -r .. /path/to/backup/KiraPass-backup    # أو git clone --mirror

pip install git-filter-repo
git filter-repo --invert-paths --path kirapass_hits.txt
git push origin --force --all
git push origin --force --tags
```

بعد تغيير التاريخ: أي شخص لديه نسخة قديمة لن يستطيع الدمج بسهولة (يجب أن
يعيد الاستنساخ). هذا متوقع ومقبول في مستودع خاص.

### ٣) أضف الترخيص إلى مقدمة المستودع
GitHub يعرض الملفات حسب الاسم. ملفنا `AUTHORIZED_USE_LICENSE.md` واضح، ويمكنك
أيضاً إضافة سطر في الوصف (About):

```
Authorized security testing only - use requires written permission from the network owner
```

### ٤) حماية الفرع (Branch protection) — للمستودعات الخاصة في GitHub Free
`Settings → Branches → Add branch protection rule` لفرع `main`: منع الحذف
والدفع القسري. مفيد إن أردت أن يبقى السجل نظيفاً.

### ٥) تعطيل الميزات التي لا تحتاجها
`Settings → General → Features`: ألغِ **Wikis** و**Discussions** و**Projects**
إن لم تستخدمها. و`Settings → Code security`: فعّل **Secret scanning** (تنبيهك
إذا رفعت شيئاً حساساً بالخطأ).

---

# English (short version)

> **If you get** `Resource not accessible by integration` (or HTTP 403) while
> running the commands below, the token simply has no **admin** permission on
> the repository - write access to the code is not enough to change settings.
> Use the web path (method 1), or run `gh auth login` with your own account
> first. Never hand a settings-capable token to a tool you do not trust.

## Make it private - GitHub web
1. Open <https://github.com/yswef/KiraPass> → **Settings**.
2. Scroll to **Danger Zone** → **Change repository visibility**.
3. Choose **Make private**, type `yswef/KiraPass` to confirm.
4. Verify in an incognito window: you should get a 404 / sign-in page.

## Make it private — CLI
```bash
gh repo edit yswef/KiraPass --visibility private \
  --accept-visibility-change-consequences
gh repo view yswef/KiraPass --json visibility      # {"visibility":"PRIVATE"}
```

## What it does and does not do
* Private = nobody else can **see** or clone it from now on.
* **Existing public forks are detached and stay public** — GitHub documents this
  and does not delete or privatise them on its own ([docs](https://docs.github.com/articles/setting-repository-visibility)).
* Existing clones stay on the machines that have them.
* Git **history** is unchanged: deleted files (like the old `kirapass_hits.txt`
  with card numbers from your friend's network) remain in the log until you
  rewrite history with `git filter-repo` and force-push.
* Because copies can exist, the license file is your real protection: it states
  that any use requires the network owner's written permission.

## Recommended extras
1. Keep `kirapass_data/` out of git (already in `.gitignore`) - verify with
   `git check-ignore -v kirapass_data/settings.json`.
2. Rewrite history if you want the old hits file gone for good.
3. Add a branch protection rule for `main`.
4. Turn off Wikis/Discussions/Projects if unused, and enable secret scanning.
