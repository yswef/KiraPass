/* KiraPass web UI - vanilla JS, no build step, no internet needed. */
"use strict";

/* ------------------------------------------------------------------ i18n */
const I18N = {
  ar: {
    /* interface */
    step_scan: "فحص الشبكة", step_format: "صيغة البطاقة",
    step_run: "التشغيل", step_results: "النتائج",
    scan_title: "1) افحص صفحة الدخول",
    scan_hint: "الصق رابط صفحة دخول الهوتسبوت كما تفتحها في المتصفح. الأداة تقرأ الصفحة بنفسها وتكتشف نوع الطلب (POST/GET) وأسماء الحقول من دون أسئلة.",
    scan_button: "افحص الآن",
    next_format: "التالي: صيغة البطاقة ←",
    next_run: "التالي: التشغيل ←",
    format_title: "2) صيغة البطاقة",
    format_hint: "اكتب شكل الكرت: البادئة الثابتة + طول الكرت الكامل. الأرقام المتغيّرة هي التي سيتم تخمينها. المعاينة تحت تخبرك فوراً بعدد الاحتمالات.",
    f_prefix: "البادئة الثابتة", f_length: "طول الكرت الكامل",
    saved_profiles: "الملف التعريفي المحفوظ", prof_new: "— جديد —",
    btn_delete_profile: "حذف هذا الملف",
    f_charset: "الحروف/الأرقام المتغيّرة", f_custom: "محارف مخصّصة",
    f_pass_mode: "قيمة كلمة المرور", f_dst: "قيمة dst (وجهة الضيف)",
    f_name: "اسم الملف التعريفي",
    f_method: "طريقة الطلب", f_user_field: "اسم حقل المستخدم",
    f_pass_field: "اسم حقل كلمة المرور", f_login_url: "رابط إرسال الدخول (action)",
    f_send_dst: "إرسال الحقول المخفية dst/popup",
    f_extra: "حقول ثابتة إضافية (name=value)",
    f_words: "كلمات النجاح (اختياري)",
    f_known: "بطاقة تعرف أنها تعمل (اختياري)",
    adv_open: "خيارات متقدمة (عادة لا تحتاجها)",
    p_space: "عدد الاحتمالات", p_samples: "أمثلة على البطاقات",
    p_covered: "مغطى سابقاً",
    btn_calibrate: "تعلّم من البطاقة المعروفة + قياس الشبكة",
    btn_save: "احفظ الملف التعريفي",
    run_title: "3) التشغيل",
    run_hint: "اختر قوة مناسبة: كل ما زادت السرعة زاد احتمال أن يقطع الراوتر الاتصال أو يحجبك. الأداة تخبرك داخل النتائج بسبب كل توقف.",
    r_threads: "عدد المسارات (Threads)", r_attempts: "عدد المحاولات",
    r_delay: "الانتظار بين الطلبات (ms)",
    r_verify: "تأكيد الإنترنت بعد أي بطاقة مقبولة",
    r_autostop: "إيقاف تلقائي عند أول نتيجة قوية",
    r_resume: "المتابعة من حيث توقفت (بلا تكرار)",
    btn_lockout: "قِس حدّ الحظر",
    lockout_measuring: "جارٍ قياس حدّ الحظر (قد يستغرق دقائق)...",
    lockout_after: "الراوتر يحجب بعد",
    lockout_clears: "ويفكّ الحظر بعد",
    lockout_never: "لم يحجبك الراوتر بعد",
    lockout_never_clears: "ولم يفتح الحظر خلال الانتظار",
    lockout_pace: "أسرع وتيرة آمنة: محاولة كل",
    lockout_pace_hint: "ضع هذه المهلة في خانة «مهلة بين المحاولات» واستخدم خيطاً واحداً أو اثنين.",
    lockout_impossible: "على هذا الراوتر لا يمكن التخمين دون حظر متكرر: إما مهلة طويلة جداً، أو تعديل الإعداد من الراوتر نفسه.",
    seconds: "ثانية",
    attempt: "محاولة",
    netadvice_blocked_from_the_start: "الراوتر حاجب هذا الجهاز قبل أن نقيس: أعد الاتصال لتغيير الـ IP أو أعد تشغيل الراوتر، ثم قِس من جديد.",
    btn_diagnose: "تشخيص الشبكة أولاً",
    btn_clear_review: "مسح صفحات المراجعة",
    license_check: "أتعهّد بأنني أملك هذه الشبكة أو لدي إذن كتابي من صاحبها لاختبارها.",
    btn_start: "ابدأ التخمين", btn_stop: "إيقاف",
    res_title: "4) النتائج الحيّة",
    s_speed: "السرعة", s_sent: "أُرسل", s_covered: "المغطى",
    s_latency: "زمن الرد", s_delay: "التباطؤ الحالي", s_state: "الحالة",
    t_card: "البطاقة", t_result: "النتيجة", t_why: "السبب", t_ms: "ms", t_len: "الحجم",
    btn_clear_log: "تفريغ السجل", btn_download: "تنزيل آخر تقرير",
    hits_title: "البطاقات المقبولة", hits_none: "لا شيء بعد.",
    review_title: "ردود غير واضحة (تحتاج نظرة منك)",
    review_hint: "هذه ردود ليست مثل صفحة الرفض وليست نجاحاً مؤكداً. محفوظة لك لتفتحها وتقرأها بنفسك - الأداة لا تخمّن مكانك.",
    review_none: "لا شيء بعد.",
    state_idle: "جاهز", state_calibrating: "جاري التعلّم", state_running: "يعمل",
    job_timeout: "انتهت مدة الانتظار - راجع السجل أسفل الشاشة",
    state_done: "انتهى", state_stopping: "يتوقف",
    preset_safe: "آمن (4 مسارات)", preset_normal: "عادي (12)",
    preset_fast: "سريع (40)", preset_custom: "مخصّص",
    cache_title: "الكاش ومسحه",
    cache_hint: "الكاش = صفحات المراجعة + التقارير + السجلات. الملفات التعريفية منفصلة، و«مسح التقارير» يحذف أيضاً سجل البطاقات.",
    cache_temp: "مسح المؤقت وصفحات المراجعة",
    cache_results: "مسح التقارير والسجلات",
    cache_profiles: "مسح الملفات التعريفية",
    cache_all: "مسح كل شيء",
    cache_freed: "تم المسح. حجم ما أُزيل:",
    license_title: "ترخيص الاستخدام",
    license_body: "١) الأداة للاختبار على شبكة تملكها أو لديك إذن كتابي من صاحبها.\n٢) لا تستخدمها للوصول غير المصرّح به أو لتخمين أكواد لا تملكها.\n٣) أنت المسؤول قانونياً عن أي استخدام غير مصرّح به.\n\nالملف AUTHORIZED_USE_LICENSE.md في المستودع هو الترخيص الكامل.",
    scan_ok: "الصفحة قُرئت", scan_fail: "تعذّر فتح الصفحة",
    internet_ONLINE: "متصل بالإنترنت فعلاً الآن",
    internet_WALLED: "خلف بوابة الدخول (يحتاج بطاقة)",
    internet_OFFLINE: "لا يوجد اتصال بالشبكة",
    internet_BLOCKED: "محجوب من قِبل الشبكة",
    internet_detail_expected_answer: "الرابط الخارجي رد كما يجب",
    internet_detail_portal_redirect: "الشبكة حوّلت الطلب إلى صفحة الدخول",
    internet_detail_portal_page: "الشبكة ردّت بصفحتها بدل الموقع",
    detected: "ما اكتشفته الأداة", form_action: "رابط الإرسال",
    form_method: "طريقة الإرسال", user_field: "حقل المستخدم",
    pass_field: "حقل كلمة المرور", extra_fields: "حقول ثابتة",
    dst_values: "قيم dst الموجودة", chap_detected: "يستخدم تشفير MD5 الخاص بميكروتك",
    chap_hint: "تم اكتشاف md5.js لذلك ستُستخدم صيغة chap تلقائياً.",
    no_form: "لم أجد نموذج دخول في الصفحة - جرّب رابط الصفحة نفسها التي تظهر للضيف.",
    running_now: "يعمل الآن", done_now: "انتهى",
    why_stopped: "لماذا توقف",
    advice: "ماذا أفعل الآن",
    review_open: "افتح الصفحة المحفوظة",
    review_diff: "كلمات ظهرت في هذا الرد ولم تظهر في صفحة الرفض",
    missing_words: "كلمات كانت في صفحة الرفض واختفت",
    report_saved: "حُفظ التقرير",
    confirm_clear_all: "سيتم مسح كل شيء بما فيها الملفات التعريفية. متأكد؟",
    confirm_profiles: "سيتم مسح الملفات التعريفية. متأكد؟",
    yes: "نعم", no: "إلغاء", close: "إغلاق",
    loading: "جاري العمل...",
    quit_tool: "إيقاف الأداة", confirm_quit: "سيتم إيقاف الأداة وإغلاق الصفحة. متأكد؟",
    quit_done: "تم إيقاف الأداة - يمكنك إغلاق هذه الصفحة.",
    resume_from: "متابعة من",
    server_gone_title: "الأداة توقفت",
    server_gone: "انقطع الاتصال بالأداة. إذا كنت أوقفتها فهذا طبيعي - شغّلها من جديد لتكمل.",
    /* why nothing was tried: the initial learning failed */
    cal_failed_title: "لم أبدأ التخمين: فشل التعلّم الأولي",
    cal_failed_hint: "لم تُجرَ أي محاولة لأن الأداة لم تستطع تعلّم شكل صفحة الرفض. هذا ما فعله الراوتر:",
    no_attempt_was_made: "المحاولات التي أُجريت فعلاً: صفر - لم يتم تخمين أي بطاقة.",
    netadvice_refused: "تأكد أنك متصل بشبكة هذا الراوتر وأن الرابط صحيح (البورت مقفل أو الحماية رفضت جهازك).",
    netadvice_dns: "اسم العنوان لم يُترجم: اكتب IP الراوتر بدل الاسم (مثل 10.5.50.1).",
    netadvice_connect_timeout: "لا يوجد رد عند فتح الاتصال: الراوتر بعيد أو مزدحم، أو لست متصلاً بشبكته.",
    netadvice_read_timeout: "الراوتر فتح الاتصال ولم يرد: انتظر قليلاً وقلّل عدد المسارات.",
    netadvice_reset: "الراوتر قطع الاتصال فجأة: أعد الاتصال بالشبكة ثم أعد المحاولة.",
    netadvice_stale: "اتصال قديم أُغلق من الراوتر: أعد المحاولة.",
    netadvice_tls: "خطأ في شهادة TLS: جرّب http:// بدل https://",
    netadvice_unreachable: "لست متصلاً بهذه الشبكة: اتصل بواي فاي الراوتر أولاً.",
    netadvice_bad_response: "رد غير مفهوم من الراوتر: جرّب رابط صفحة الدخول الذي يظهر للضيف فعلاً.",
    netadvice_too_many_redirects: "الراوتر يحوّل الطلب بلا نهاية: انسخ الرابط النهائي من المتصفح.",
    netadvice_proto: "الرابط غير مدعوم: يجب أن يبدأ بـ http:// أو https://",
    netadvice_unknown: "خطأ غير متوقع: أعد المحاولة، وإن تكرر شغّل «تشخيص الشبكة أولاً».",
    netadvice_blocked_already: "الراوتر حاجب جهازك الآن: أعد تشغيل الراوتر أو أعد الاتصال لتغيير الـ IP، ثم ابدأ من جديد.",
    netadvice_blocked_before_probes: "الحجب سابق علينا: أعد الاتصال بالشبكة لتغيير الـ IP (أو فعّل «عنوان MAC عشوائي/خاص» لهذه الشبكة في إعدادات الهاتف) أو أعد تشغيل الراوتر، ثم ابدأ من جديد.",
    netadvice_blocked_by_our_probes: "نحن من ملأنا عداد الفشل: الأداة تنتظر ٤٥ ثانية ثم تعيد التعلّم ببطاقتي تجربة بدل ثلاث. إن تكرّر: أعد الاتصال لتغيير الـ IP، وقلّل عدد الخيوط وأضف مهلة بين المحاولات.",
    netadvice_no_rejection_baseline: "لم يصل أي رد على بطاقات التجربة: تحقق من الاتصال بالشبكة.",
    netadvice_card_space_empty: "صيغة البطاقة لا تترك شيئاً للتخمين: البادئة + اللاحقة أطول من طول الكرت، أو المحارف المتغيّرة قليلة جداً.",
    netadvice_calibration_failed: "أصلح السبب أعلاه، ثم اضغط «ابدأ التخمين» من جديد.",
    block_but_form_present: "لكن الصفحة ما زال فيها نموذج الدخول",
    probe_cards: "بطاقات تجربة",
    http_ok_word_ignored: "الصفحة ترد سليم وفيها كلمة حجب، لكن ما زال فيها نموذج الدخول فاعتبرناها صفحة دخول",
    internet_opened_title: "الإنترنت فتح أثناء التشغيل - أحد هذه الكروت هو الصحيح",
    internet_opened_hint: "الراوتر أدخلك ولم يرد برد نجاح واضح، فلم نستطع تسمية الكرت من الرد وحده. أوقف الجلسة ثم جرّب هذه الكروت واحداً واحداً في صفحة الدخول - أحدها هو الذي فتح الشبكة. الأحدث في الآخر.",
    stop_internet_opened: "توقف لأن الإنترنت فتح أثناء التشغيل: أحد آخر الكروت المجربة هو الصحيح.",
    retry_now: "↻ أعد المحاولة الآن",
    retry_after_wait: "⏳ أعد المحاولة بعد ٤٥ ثانية",
    block_wait: "الراوتر حجبنا بعد بطاقات التجربة - انتظار",
    /* verdicts */
    v_ACCEPTED_VERIFIED: "مقبولة ومؤكدة",
    v_ACCEPTED: "مقبولة",
    v_ACCEPTED_UNVERIFIED: "قبلها الراوتر (تأكيد الإنترنت فشل)",
    v_REJECTED: "مرفوضة",
    v_UNKNOWN: "رد غير واضح",
    v_BANNED: "محظور من الراوتر",
    v_RATE_LIMITED: "الشبكة تبطّئك/تحدّ من الطلبات",
    v_CHALLENGE: "ظهر اختبار كابتشا",
    v_NET_ERROR: "خطأ في الاتصال",
    v_INTERNAL_ERROR: "خلل داخلي بالأداة (يُبلَّغ عنه)",
    /* reasons */
    r_same_as_rejection_page_exact: "رد مطابق لصفحة الرفض",
    r_same_as_rejection_page_shape: "نفس صفحة الرفض (مع اختلاف الرموز المؤقتة)",
    r_same_as_rejection_page_similar: "يشبه صفحة الرفض بشدة",
    r_same_as_rejection_page_empty: "رد فارغ مثل صفحة الرفض",
    r_same_as_rejection_page_redirect: "نفس تحويل صفحة الرفض (نفس المكان)",
    r_redirect_differs_from_rejection: "الراوتر حوّل هذه البطاقة إلى مكان غير مكان البطاقات المرفوضة",
    r_ban_page: "ظهرت صفحة حجب صريحة من الراوتر",
    r_http_403: "الراوتر يرفض الطلب (403)",
    r_http_429: "طلبات كثيرة جداً (429) - تهدئة مطلوبة",
    r_captcha_present: "الصفحة فيها كابتشا - التخمين لم يعد مجدياً",
    r_redirect_out_of_portal_and_online: "الراوتر أعطى إنترنت فعلياً لهذه البطاقة",
    r_accepted_internet_already_open: "قبلها الراوتر (لم أستطع إثبات الإنترنت لأن جهازك كان متصلاً أصلاً)",
    internet_online_verification_limited: "جهازك متصل بالإنترنت مسبقاً - سأعتمد على تحويل الراوتر وصفحة الحالة",
    r_redirect_out_of_portal: "الراوتر حوّل المتصفح خارج البوابة",
    r_redirect_to_another_portal_page: "التحويل كان إلى صفحة داخل البوابة نفسها - ليس خروجاً",
    r_http_503: "الراوتر أو خدمة RADIUS مشغولة/غير متاحة (503) - أبطأت الطلبات",
    r_success_url_contains: "عنوان النجاح المتوقع ظهر في الرد",
    r_learned_success_words: "ظهرت كلمات النجاح التي تعلّمتها الأداة",
    r_welcome_words: "كلمات ترحيب لا تظهر في صفحة الرفض",
    r_rejection_wording: "نص الرفض موجود في الصفحة",
    r_reply_differs_not_proven: "الرد مختلف لكن لا دليل على القبول - احفظته للمراجعة",
    r_looks_rejected_but_success_words_found: "الرد يشبه الرفض لكن فيه كلمات نجاح تعلّمتها - يحتاج نظرة منك",
    /* network error kinds */
    net_dns: "اسم العنوان لم يُترجم (DNS)",
    net_refused: "الراوتر رفض الاتصال (البورت مقفول أو الحماية منعتك)",
    net_connect_timeout: "لا يوجد رد عند فتح الاتصال",
    net_read_timeout: "الاتصال نجح لكن الرد تأخر (راوتر مشغول أو RADIUS بطيء)",
    net_reset: "الراوتر قطع الاتصال فجأة",
    net_stale: "اتصال قديم أُغلق من الراوتر (أُعيد تلقائياً)",
    net_tls: "خطأ في شهادة TLS",
    net_unreachable: "الشبكة غير قابلة للوصول (لست متصلاً بها)",
    net_bad_response: "رد غير مفهوم من الراوتر",
    net_too_many_redirects: "دوران لا نهائي في التحويل",
    net_proto: "رابط غير مدعوم",
    net_unknown: "خطأ غير متوقع",
    /* stop reasons */
    stop_found_verified: "وجدت بطاقة تعمل وتحقّقت من الإنترنت فعلياً.",
    stop_found_strong_evidence: "ظهرت بطاقة بدليل قوي (تحويل خارج البوابة) وتوقفت.",
    stop_user_stop: "أوقفت التشغيل بنفسك.",
    stop_banned_by_router: "الراوتر حجبك. غيّر الـ IP (أعد تشغيل الراوتر أو أعد الاتصال) وقلّل المسارات.",
    stop_rate_limited_by_router: "الشبكة تحدّ من الطلبات (429). قلّل المسارات أو أضف انتظاراً.",
    stop_target_unreachable: "انقطع الوصول إلى الراوتر تماماً: تحقق من الشبكة.",
    why_title: "لماذا انتهت كل محاولة بهذه النتيجة؟",
    stop_attempts_done: "انتهى عدد المحاولات المطلوب. شغّل مرة أخرى - ستكمل من حيث توقفت.",
    stop_space_done: "غطّيت كل الاحتمالات في هذا النطاق.",
    stop_calibration_failed: "لم أبدأ التخمين لأن التعلّم الأولي فشل - السبب مكتوب بالأسفل.",
    stop_engine_error: "خطأ داخلي - التفاصيل في السجل.",
    stop_captcha_challenge: "ظهرت كابتشا، والتخمين بعدها بلا فائدة.",
    stop_found_unverified: "قبل الراوتر البطاقة لكن لم أستطع تأكيد الإنترنت.",
    /* throttle */
    th_rate_limited_slowing_down: "أبطأت الطلبات بسبب تحديد المعدل (429)",
    th_ban_page_slowing_down: "أبطأت الطلبات بسبب ظهور صفحة حجب",
    th_connections_refused_slowing_down: "أبطأت الطلبات لأن الراوتر يرفض الاتصالات",
    th_network_errors_slowing_down: "أبطأت الطلبات بسبب أخطاء شبكة متكررة",
    th_recovering_speed: "الشبكة هدأت - أعيد رفع السرعة تدريجياً",
    /* calibration + diagnostics */
    cal_blocked_already: "الراوتر حاجب جهازك (ظهرت صفحة حجب قبل أي محاولة)",
    cal_blocked_before_probes: "صفحة الحجب ظهرت قبل أن نجرّب أي بطاقة: الراوتر حاجب هذا الجهاز من قبل",
    cal_blocked_by_our_probes: "بطاقات التجربة ملأت عداد المحاولات الفاشلة عند الراوتر، فحجبنا قبل أن نبدأ",
    cal_card_space_empty: "صيغة البطاقة لا تترك شيئاً للتخمين",
    cal_no_rejection_baseline: "لم يصل أي رد من الراوتر على بطاقات التجربة",
    cal_reach_login_page: "الوصول إلى صفحة الدخول",
    cal_internet_state: "حالة الإنترنت قبل أي محاولة",
    cal_rejection_baseline: "تعلّم شكل صفحة الرفض",
    cal_rejection_probe: "إرسال بطاقات تجريبية",
    cal_probe_looked_accepted: "بطاقة تجريبية بدت مقبولة",
    cal_shape_tuned: "ضبط شكل الطلب باستخدام البطاقة المعروفة",
    cal_http_ok: "الصفحة ردت بشكل سليم",
    cal_learned: "تم التعلّم بنجاح",
    cal_known_card_works: "البطاقة المعروفة تعمل مع هذا الشكل",
    cal_known_card_not_proven: "لم أستطع إثبات أن البطاقة المعروفة تعمل بهذه الإعدادات",
    cal_browser_trace: "افتح F12 في المتصفح وانسخ بيانات نموذج الدخول وأرسلها لي",
    dyn_tokens: "رموز متغيّرة تم تجاهلها", exact_mode: "مقارنة دقيقة جاهزة",
    shape_mode: "مقارنة بالشكل (الصفحة تتغير وحدها)",
    diag_reach: "الوصول للراوتر", diag_internet: "حالة الإنترنت",
    diag_sample_single: "قياس بمسار واحد", diag_sample_parallel: "قياس بعدة مسارات",
    diag_ban_check: "فحص الحجب",
    diag_ok: "سليم", diag_errors_present: "توجد أخطاء", diag_errors_rising: "الأخطاء تزيد مع السرعة",
    diag_no_ban_seen: "لا يوجد حجب", diag_ban_page_seen: "ظهرت صفحة حجب",
    advice_blocked_already: "أنت محجوب بالفعل: أعد تشغيل الراوتر أو أعد الاتصال لتغيير الـ IP.",
    advice_router_pressure: "الأخطاء سببها ضغط على الراوتر: قلّل عدد المسارات.",
    advice_slow_router: "الراوتر بطيء في الرد: استخدم مسارات أقل وانتظاراً أطول.",
    advice_already_online_no_captive_portal: "أنت متصل بالإنترنت فعلاً - تأكد أنك على شبكة الضيف الصحيحة.",
    suggest_threads: "المسارات المقترحة",
    /* profile problems */
    prob_url_missing_or_invalid: "رابط صفحة الدخول غير صالح",
    prob_user_field_missing: "اسم حقل المستخدم مفقود",
    prob_length_not_bigger_than_prefix_and_suffix: "البادئة + اللاحقة أطول من طول الكرت",
    prob_charset_too_small: "المحارف المتغيّرة قليلة جداً",
    prob_unknown_pass_mode: "طريقة كلمة المرور غير معروفة",
    prob_fixed_password_empty: "كلمة المرور الثابتة فارغة",
    prob_space_is_astronomically_big: "عدد الاحتمالات ضخم جداً - استخدم طولاً أقل أو مسارات أكثر",
    /* pass modes */
    pm_same: "نفس البطاقة", pm_empty: "فارغة", pm_omit: "بدون إرسال الحقل",
    pm_fixed: "قيمة ثابتة", pm_chap: "MD5 تشفير ميكروتك (chap) للبطاقة",
    pm_chap_empty: "chap على قيمة فارغة",
    pm_md5user: "MD5 للبطاقة فقط",
    /* charsets */
    cs_digits: "أرقام فقط", cs_lower: "حروف صغيرة", cs_upper: "حروف كبيرة",
    cs_alnum: "أرقام وحروف صغيرة", cs_alnum_upper: "أرقام وحروف كبيرة",
    cs_hex: "سداسي عشري صغير", cs_hex_upper: "سداسي عشري كبير",
  },
  en: {
    step_scan: "Scan", step_format: "Card format", step_run: "Run", step_results: "Results",
    scan_title: "1) Scan the login page",
    scan_hint: "Paste the hotspot login URL exactly as you open it in the browser. The tool reads the page and detects POST/GET and the field names by itself.",
    scan_button: "Scan now", next_format: "Next: card format →", next_run: "Next: run →",
    format_title: "2) Card format",
    format_hint: "Describe the card: fixed prefix + full length. The variable part is what gets guessed. The preview shows how many combinations exist.",
    f_prefix: "Fixed prefix", f_length: "Full card length",
    saved_profiles: "Saved profile", prof_new: "- new -",
    btn_delete_profile: "Delete this profile",
    f_charset: "Variable characters", f_custom: "Custom characters",
    f_pass_mode: "Password value", f_dst: "dst value (guest destination)",
    f_name: "Profile name",
    f_method: "Request method", f_user_field: "Username field",
    f_pass_field: "Password field", f_login_url: "Form action URL",
    f_send_dst: "Send the hidden dst/popup fields",
    f_extra: "Extra fixed fields (name=value)",
    f_words: "Success words (optional)",
    f_known: "A card you know works (optional)",
    adv_open: "Advanced options (usually not needed)",
    p_space: "Combinations", p_samples: "Sample cards",
    p_covered: "covered",
    btn_calibrate: "Learn from the known card + measure the network",
    btn_save: "Save profile",
    run_title: "3) Run",
    run_hint: "Pick the load: faster means more chance the router cuts you off or blocks you. Results always tell you why a run stopped.",
    r_threads: "Threads", r_attempts: "Attempts", r_delay: "Delay between requests (ms)",
    r_verify: "Verify internet after any accepted card",
    r_autostop: "Auto-stop on the first strong result",
    r_resume: "Continue where you stopped (no repeats)",
    btn_lockout: "measure the lock-out",
    lockout_measuring: "measuring the lock-out (this can take minutes)...",
    lockout_after: "the router blocks after",
    lockout_clears: "and the block clears after",
    lockout_never: "the router never blocked us in",
    lockout_never_clears: "and the block never cleared while we waited",
    lockout_pace: "fastest pace that stays under the limit: one attempt every",
    lockout_pace_hint: "put that in the delay box and use one or two threads.",
    lockout_impossible: "guessing on this router means getting blocked over and over: either a very long delay, or change the setting in the router itself.",
    seconds: "seconds",
    attempt: "attempt",
    netadvice_blocked_from_the_start: "the router was already blocking this device: reconnect for a new IP or restart the router, then measure again.",
    btn_diagnose: "Diagnose the network first", btn_clear_review: "Clear review pages",
    license_check: "I confirm I own this network or hold written permission from its owner.",
    btn_start: "Start guessing", btn_stop: "Stop",
    res_title: "4) Live results",
    s_speed: "Speed", s_sent: "Sent", s_covered: "Covered",
    s_latency: "Latency", s_delay: "Current slowdown", s_state: "State",
    t_card: "Card", t_result: "Result", t_why: "Reason", t_ms: "ms", t_len: "Size",
    btn_clear_log: "Clear log", btn_download: "Download last report",
    hits_title: "Accepted cards", hits_none: "Nothing yet.",
    review_title: "Unclear replies (need your eyes)",
    review_hint: "Replies that are neither the rejection page nor a proven success. Saved for you to inspect - the tool does not guess.",
    review_none: "Nothing yet.",
    state_idle: "Ready", state_calibrating: "Learning", state_running: "Running",
    job_timeout: "timed out waiting - check the log",
    state_done: "Finished", state_stopping: "Stopping",
    preset_safe: "Safe (4 threads)", preset_normal: "Normal (12)",
    preset_fast: "Fast (40)", preset_custom: "Custom",
    cache_title: "Cache & cleanup",
    cache_hint: "Cache = review pages + reports + logs. Profiles are separate; clearing the results also deletes the hits log.",
    cache_temp: "Clear temp + review pages", cache_results: "Clear reports, logs & hits",
    cache_profiles: "Clear profiles", cache_all: "Clear everything",
    cache_freed: "Cleared. Freed:",
    license_title: "Authorized use",
    license_body: "1) Use only on networks you own or have written permission to test.\n2) Never use it for unauthorized access or to guess codes you do not own.\n3) You are legally responsible for any unauthorized use.\n\nAUTHORIZED_USE_LICENSE.md in the repository is the full license.",
    scan_ok: "Page read", scan_fail: "Could not open the page",
    internet_ONLINE: "Actually online right now",
    internet_WALLED: "Behind the login portal (needs a card)",
    internet_OFFLINE: "No network connection",
    internet_BLOCKED: "Blocked by the network",
    internet_detail_expected_answer: "the outside URL answered as expected",
    internet_detail_portal_redirect: "the network redirected us to the login page",
    internet_detail_portal_page: "the network answered with its own page",
    detected: "What the tool detected", form_action: "Form action",
    form_method: "Method", user_field: "Username field", pass_field: "Password field",
    extra_fields: "Fixed fields", dst_values: "dst values found",
    chap_detected: "uses the MikroTik MD5 (chap) scheme",
    chap_hint: "md5.js detected - the chap formula will be used automatically.",
    no_form: "No login form found on this page - try the exact URL the guest sees.",
    running_now: "Running", done_now: "Finished",
    why_stopped: "Why it stopped", advice: "What to do next",
    review_open: "Open the saved page",
    review_diff: "Words in this reply that are not on the rejection page",
    missing_words: "Words that were on the rejection page and are gone",
    report_saved: "Report saved",
    confirm_clear_all: "Everything will be deleted, including profiles. Sure?",
    confirm_profiles: "Profiles will be deleted. Sure?",
    yes: "Yes", no: "Cancel", close: "Close", loading: "Working...",
    quit_tool: "Stop the tool", confirm_quit: "The tool will shut down and this page will stop working. Sure?",
    quit_done: "The tool is stopped - you can close this page.",
    resume_from: "continuing from",
    server_gone_title: "The tool stopped",
    server_gone: "Lost contact with the tool. If you stopped it, that is expected - start it again to continue.",
    cal_failed_title: "Nothing was tried: the initial learning failed",
    cal_failed_hint: "No attempt was made because the tool could not learn what a rejected card looks like. This is what the router did:",
    no_attempt_was_made: "Attempts actually made: zero - no card was guessed.",
    netadvice_refused: "Check that you are on this router's network and the URL is right (the port is closed or the router refused your device).",
    netadvice_dns: "The host name did not resolve: use the router's IP instead (like 10.5.50.1).",
    netadvice_connect_timeout: "No answer when opening the connection: the router is far, busy, or you are not on its network.",
    netadvice_read_timeout: "The router opened the connection but never answered: wait a little and lower the thread count.",
    netadvice_reset: "The router cut the connection: reconnect to the network and try again.",
    netadvice_stale: "An old keep-alive connection was closed by the router: try again.",
    netadvice_tls: "TLS certificate error: try http:// instead of https://",
    netadvice_unreachable: "You are not connected to this network: join the router's wifi first.",
    netadvice_bad_response: "The router sent an unreadable reply: use the exact login URL a guest sees.",
    netadvice_too_many_redirects: "Endless redirect loop: copy the final URL from the browser.",
    netadvice_proto: "Unsupported URL: it must start with http:// or https://",
    netadvice_unknown: "Unexpected error: try again, and if it repeats run \"diagnose the network first\".",
    netadvice_blocked_already: "The router is blocking your device right now: restart the router or reconnect to change your IP, then start again.",
    netadvice_blocked_before_probes: "The block is older than we are: reconnect to the network to change your IP (or turn on the per-network \"randomized / private MAC\" in the phone settings), or restart the router, then start again.",
    netadvice_blocked_by_our_probes: "We filled the failure counter ourselves: the tool waits 45s, then relearns with two test cards instead of three. If it repeats: reconnect to change your IP, lower the threads and add a delay between attempts.",
    netadvice_no_rejection_baseline: "No answer at all to the test cards: check the connection to the network.",
    netadvice_card_space_empty: "The card format leaves nothing to guess: prefix + suffix are longer than the card, or there are too few variable characters.",
    netadvice_calibration_failed: "Fix the reason above, then press \"start guessing\" again.",
    block_but_form_present: "but the page still has the login form",
    probe_cards: "test cards",
    http_ok_word_ignored: "the page answers fine and mentions blocking, but it still offers the login form - treated as a login page",
    internet_opened_title: "the internet opened during the run - one of these cards is the working one",
    internet_opened_hint: "the router let us in but never answered with a clear success page, so the card could not be named from the reply alone. End the session and try these cards one by one in the login page - one of them opened the network. Newest last.",
    stop_internet_opened: "stopped because the internet opened during the run: one of the last cards tried is the working one.",
    retry_now: "↻ Try again now",
    retry_after_wait: "⏳ Try again after 45 seconds",
    block_wait: "the router locked us after the test cards - waiting",
    v_ACCEPTED_VERIFIED: "Accepted & verified",
    v_ACCEPTED: "Accepted",
    v_ACCEPTED_UNVERIFIED: "Router accepted (internet check failed)",
    v_REJECTED: "Rejected", v_UNKNOWN: "Unclear reply", v_BANNED: "Blocked by router",
    v_RATE_LIMITED: "Throttled / rate limited", v_CHALLENGE: "Captcha appeared",
    v_NET_ERROR: "Network error",
    v_INTERNAL_ERROR: "Internal tool error (reported)",
    r_same_as_rejection_page_exact: "identical to the rejection page",
    r_same_as_rejection_page_shape: "same page as a rejection (temporary tokens differ)",
    r_same_as_rejection_page_similar: "very close to the rejection page",
    r_same_as_rejection_page_empty: "empty reply, like the rejection page",
    r_same_as_rejection_page_redirect: "same redirect as a rejected card",
    r_redirect_differs_from_rejection: "the router sent this card somewhere else than a rejected one",
    r_ban_page: "an explicit block page from the router",
    r_http_403: "the router refuses the request (403)",
    r_http_429: "too many requests (429) - slow down",
    r_captcha_present: "the page has a captcha - guessing is over",
    r_redirect_out_of_portal_and_online: "the router gave this card real internet",
    r_accepted_internet_already_open: "router accepted (internet proof skipped: you were online already)",
    internet_online_verification_limited: "you are online already - I will rely on the portal redirect and status page",
    r_redirect_out_of_portal: "the router redirected the browser out of the portal",
    r_redirect_to_another_portal_page: "the redirect stayed inside the portal - not an exit",
    r_http_503: "the router or RADIUS is unavailable (503) - slowed down",
    r_success_url_contains: "the learned success URL appeared",
    r_learned_success_words: "the success words learned from your own card appeared",
    r_welcome_words: "welcome words that never appear on the rejection page",
    r_rejection_wording: "the rejection wording is on the page",
    r_reply_differs_not_proven: "reply differs but nothing proves acceptance - saved for review",
    r_looks_rejected_but_success_words_found: "looks like the rejection page but contains success words - needs your eyes",
    net_dns: "host name could not be resolved",
    net_refused: "the router refused the connection",
    net_connect_timeout: "no answer while opening the connection",
    net_read_timeout: "connected but the reply was too slow",
    net_reset: "the router cut the connection",
    net_stale: "a stale keep-alive socket was closed (auto-retried)",
    net_tls: "TLS/certificate error",
    net_unreachable: "network unreachable (you are not connected to it)",
    net_bad_response: "unreadable reply from the router",
    net_too_many_redirects: "redirect loop", net_proto: "unsupported URL",
    net_unknown: "unexpected error",
    stop_found_verified: "Found a working card and verified real internet access.",
    stop_found_strong_evidence: "A card produced strong evidence (redirect out of the portal).",
    stop_user_stop: "You stopped it.", 
    stop_banned_by_router: "The router blocked you. Change your IP (restart the router / reconnect) and lower the threads.",
    stop_rate_limited_by_router: "The network is rate limiting (429). Lower the threads or add a delay.",
    stop_target_unreachable: "Lost contact with the router completely: check the network.",
        why_title: "Why each attempt ended the way it did",
stop_attempts_done: "Requested attempts finished. Run again - it continues, it does not repeat.",
    stop_space_done: "Every combination in this range has been covered.",
    stop_calibration_failed: "Nothing was started because the initial learning failed - the reason is written below.",
    stop_engine_error: "Internal error - see the log.",
    stop_captcha_challenge: "A captcha appeared; guessing is pointless after that.",
    stop_found_unverified: "The router accepted the card but the internet check failed.",
    th_rate_limited_slowing_down: "Slowed down because of rate limiting (429)",
    th_ban_page_slowing_down: "Slowed down because a block page appeared",
    th_connections_refused_slowing_down: "Slowed down because the router refuses connections",
    th_network_errors_slowing_down: "Slowed down because of repeated network errors",
    th_recovering_speed: "Network calmed down - raising the speed again",
    cal_blocked_already: "the router is blocking this device (a block page came back before any attempt)",
    cal_blocked_before_probes: "the block page was already there before we tried any card - the router blocked this device earlier",
    cal_blocked_by_our_probes: "our own test cards filled the router's failed-login counter, so it locked us before the run started",
    cal_card_space_empty: "the card format leaves nothing to guess",
    cal_no_rejection_baseline: "no reply came back for the test cards",
    cal_reach_login_page: "Reaching the login page",
    cal_internet_state: "Internet state before any attempt",
    cal_rejection_baseline: "Learning the rejection page",
    cal_rejection_probe: "Sending test cards",
    cal_probe_looked_accepted: "A test card looked accepted",
    cal_shape_tuned: "Tuning the request shape with your known card",
    cal_http_ok: "the page answered", cal_learned: "learned",
    cal_known_card_works: "the known card works with this shape",
    cal_known_card_not_proven: "could not prove the known card works with these settings",
    cal_browser_trace: "open F12 in the browser and copy the login form data",
    dyn_tokens: "dynamic tokens ignored", exact_mode: "exact comparison ready",
    shape_mode: "comparing by shape (page changes by itself)",
    diag_reach: "Reaching the router", diag_internet: "Internet state",
    diag_sample_single: "Measuring with one thread", diag_sample_parallel: "Measuring under load",
    diag_ban_check: "Block check",
    diag_ok: "clean", diag_errors_present: "errors present", diag_errors_rising: "errors rise with speed",
    diag_no_ban_seen: "no blocking seen", diag_ban_page_seen: "a block page appeared",
    advice_blocked_already: "You are already blocked: restart the router or reconnect to change your IP.",
    advice_router_pressure: "The errors come from router pressure: lower the thread count.",
    advice_slow_router: "The router answers slowly: fewer threads and more delay.",
    advice_already_online_no_captive_portal: "You are online already - make sure you are on the guest network.",
    suggest_threads: "Suggested threads",
    prob_url_missing_or_invalid: "the login URL is invalid",
    prob_user_field_missing: "the username field is missing",
    prob_length_not_bigger_than_prefix_and_suffix: "prefix + suffix are longer than the card",
    prob_charset_too_small: "too few variable characters",
    prob_unknown_pass_mode: "unknown password mode",
    prob_fixed_password_empty: "the fixed password is empty",
    prob_space_is_astronomically_big: "the space is enormous - shorten it or use more threads",
    pm_same: "same as card", pm_empty: "empty", pm_omit: "field omitted",
    pm_fixed: "fixed value", pm_chap: "MikroTik MD5 (chap) of the card",
    pm_chap_empty: "chap over an empty value", pm_md5user: "MD5 of the card only",
    cs_digits: "digits", cs_lower: "lowercase", cs_upper: "uppercase",
    cs_alnum: "digits + lowercase", cs_alnum_upper: "digits + uppercase",
    cs_hex: "hex lowercase", cs_hex_upper: "hex uppercase",
  }
};

let LANG = "ar";
const t = (key, fallback) => (I18N[LANG] && I18N[LANG][key]) || fallback || key;

/* ------------------------------------------------------------------ state */
const S = { meta: null, lastSeq: 0, poll: null, running: false, rows: 0,
            lastReport: "", profile: {}, knownCard: "", portal: null,
            state: "idle" };

const $ = (id) => document.getElementById(id);

/* ------------------------------------------------------------------ access */
/* When the tool is opened to the LAN it prints a link with ?token=...
   The token is kept in localStorage so the user types it only once. */
const TOKEN = (() => {
  const fromUrl = new URLSearchParams(location.search).get("token");
  if (fromUrl) { localStorage.setItem("kirapass_token", fromUrl); return fromUrl; }
  return localStorage.getItem("kirapass_token") || "";
})();

function withToken(path) {
  if (!TOKEN) return path;
  return path + (path.includes("?") ? "&" : "?") + "token=" + encodeURIComponent(TOKEN);
}

function askToken() {
  modal("Access token", "<p>هذه الأداة مفتوحة على الشبكة المحلية، أدخل الرمز الذي طبعته في الطرفية.<br>" +
    "Enter the token printed in the terminal.</p>" +
    "<input id='tokIn' placeholder='token' autocomplete='off'>" +
    "<div class='row end'><button class='btn primary' id='tokOk'>OK</button></div>");
  $("tokOk").addEventListener("click", () => {
    const v = $("tokIn").value.trim();
    if (v) { localStorage.setItem("kirapass_token", v); location.reload(); }
  });
}
const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g,
  (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

async function api(path, body, method) {
  const opt = { method: method || (body ? "POST" : "GET"), headers: {} };
  if (body) { opt.headers["Content-Type"] = "application/json";
              opt.body = JSON.stringify(body); }
  let res;
  try {
    res = await fetch(withToken(path), opt);
  } catch (e) {
    /* the tool was stopped (or the phone slept): say so instead of freezing */
    return { ok: false, error: "server_gone" };
  }
  if (res.status === 401) { askToken(); return { ok: false, error: "unauthorized" }; }
  try { return await res.json(); } catch (e) { return { ok: false, error: "bad_response" }; }
}

function toast(msg, ms) {
  const pill = $("statePill");
  pill.textContent = msg;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => { pill.textContent = stateLabel(S.state); }, ms || 2500);
}

/* ------------------------------------------------------------------ i18n render */
function setLang(lang) {
  LANG = lang === "en" ? "en" : "ar";
  const html = document.documentElement;
  html.lang = LANG; html.dir = LANG === "ar" ? "rtl" : "ltr";
  document.querySelectorAll("[data-i18n]").forEach((node) => {
    const key = node.getAttribute("data-i18n");
    const txt = t(key);
    if (txt) node.textContent = txt;
  });
  $("langBtn").textContent = LANG === "ar" ? "EN" : "عربي";
  buildSelects();
  $("footText").textContent = LANG === "ar"
    ? "KiraPass — أداة اختبار أمن الشبكات. الاستخدام بدون إذن صاحب الشبكة مخالف للقانون."
    : "KiraPass — network security testing tool. Using it without the owner's permission is unlawful.";
  localStorage.setItem("kirapass_lang", LANG);
  api("/api/settings", { lang: LANG });
}

/* ------------------------------------------------------------------ helpers */
const codeLabel = (code) => t("v_" + code, code);

function reasonLabel(code, reason, data) {
  if (code === "NET_ERROR") return t("net_" + reason, reason);
  if (reason && reason.startsWith("net_")) return t(reason, reason.slice(4));
  if (reason && reason.startsWith("internet_")) return t(reason, reason.slice(9));
  if (reason === "ban_page" && data && data.word)
    return t("r_ban_page") + " — «" + esc(data.word) + "»";
  if (reason === "cache_cleared") return "";
  return t("r_" + reason, reason);
}

/* a reason code from the report: r_<code> first, then the network-kind name */
function whyLabel(code) {
  const table = I18N[LANG] || {};
  if (code === "NET_ERROR") return codeLabel("NET_ERROR");
  return table["r_" + code] || table["net_" + code] || code;
}

function stateLabel(state) {
  if (state === "running") return t("state_running");
  if (state === "calibrating") return t("state_calibrating");
  if (state === "stopping") return t("state_stopping");
  if (state === "done") return t("state_done");
  return t("state_idle");
}

function fmtSpace(n) {
  if (!n && n !== 0) return "—";
  if (n >= 1e15) return n.toExponential(2);
  return n.toLocaleString(LANG === "ar" ? "ar-EG" : "en-US");
}

function step(name) {
  document.querySelectorAll(".panel").forEach((p) =>
    p.classList.toggle("active", p.id === "panel-" + name));
  document.querySelectorAll(".step").forEach((b) =>
    b.classList.toggle("active", b.dataset.step === name));
  window.scrollTo({ top: 0, behavior: "smooth" });
}

/* ------------------------------------------------------------------ selects */
function buildSelects() {
  const cs = $("f_charset");
  if (cs && S.meta) {
    const keep = cs.value;
    cs.innerHTML = "";
    for (const [key, chars] of Object.entries(S.meta.charsets)) {
      const opt = document.createElement("option");
      opt.value = key; opt.dataset.chars = chars;
      opt.textContent = t("cs_" + key, key) + "  (" + chars.length + ")";
      cs.appendChild(opt);
    }
    const custom = document.createElement("option");
    custom.value = "_custom"; custom.textContent = t("f_custom");
    cs.appendChild(custom);
    if (keep) cs.value = keep;
    if (!["digits", "lower", "upper", "alnum", "alnum_upper", "hex",
          "hex_upper", "_custom"].includes(cs.value)) cs.value = "digits";
  }
  const pm = $("f_pass_mode");
  if (pm && S.meta) {
    const keep = pm.value;
    pm.innerHTML = "";
    S.meta.pass_modes.forEach((mode) => {
      const opt = document.createElement("option");
      opt.value = mode; opt.textContent = t("pm_" + mode, mode);
      pm.appendChild(opt);
    });
    pm.value = keep && S.meta.pass_modes.includes(keep) ? keep : "empty";
  }
  const row = $("presetRow");
  if (row && S.meta && !row.children.length) {
    S.meta.presets.forEach((p) => {
      const b = document.createElement("button");
      b.className = "chip"; b.dataset.preset = p.id;
      b.textContent = t("preset_" + p.id, p.id + " (" + p.threads + ")");
      row.appendChild(b);
    });
  }
}

/* ------------------------------------------------------------------ profile */
function charsetValue() {
  const sel = $("f_charset");
  if (sel.value === "_custom") return $("f_custom").value || "0123456789";
  const opt = (sel.selectedOptions && sel.selectedOptions[0]) || null;
  return (opt && opt.dataset.chars) || "0123456789";
}

/* where the last run stopped - kept so "start" continues instead of repeating.
   It travels with the profile, because that is what the engine saves back. */
function progressFromProfile(p) {
  p = p || {};
  const resume = $("r_resume") ? $("r_resume").checked : true;
  if (!resume) return { space_pos: 0, walk_a: 0, walk_b: 0 };
  return {
    space_pos: parseInt(p.space_pos || 0, 10) || 0,
    space_pass: parseInt(p.space_pass || 0, 10) || 0,
    walk_a: parseInt(p.walk_a || 0, 10) || 0,
    walk_b: parseInt(p.walk_b || 0, 10) || 0,
  };
}

function profileFromForm() {
  const extras = {};
  ($("f_extra").value || "").split(",").forEach((part) => {
    const i = part.indexOf("=");
    if (i > 0) extras[part.slice(0, i).trim()] = part.slice(i + 1).trim();
  });
  const words = ($("f_words").value || "").split(/[,;\n]/).map((w) => w.trim())
    .filter(Boolean);
  return Object.assign({
    name: $("f_name").value.trim() || "profile",
    login_url: $("f_login_url").value.trim() || $("scanUrl").value.trim(),
    method: $("f_method").value,
    user_field: $("f_user_field").value.trim() || "username",
    pass_field: $("f_pass_field").value.trim() || "password",
    pass_mode: $("f_pass_mode").value,
    charset: charsetValue(),
    length: parseInt($("f_length").value || "0", 10),
    prefix: $("f_prefix").value.trim(),
    suffix: "",
    dst_value: $("f_dst").value.trim(),
    send_dst: $("f_send_dst").checked,
    send_popup: $("f_send_dst").checked,
    extra_fields: extras,
    success_words: words,
    /* the chap formula comes from the scanned page - but a SAVED profile knows
       it too, and loading one must not silently forget it */
    chap: (S.portal && S.portal.form && S.portal.form.chap) ||
          (S.profile && S.profile.chap) || null,
  }, progressFromProfile(S.profile));
}

function fillFormFromProfile(p) {
  if (!p) return;
  S.profile = p;                       /* keeps space_pos / walk for resume */
  $("f_name").value = p.name || "";
  $("f_login_url").value = p.login_url || "";
  $("scanUrl").value = p.login_url || "";
  $("f_method").value = p.method === "get" ? "get" : "post";
  $("f_user_field").value = p.user_field || "username";
  $("f_pass_field").value = p.pass_field || "password";
  $("f_pass_mode").value = p.pass_mode || "empty";
  $("f_prefix").value = p.prefix || "";
  $("f_length").value = p.length || 10;
  $("f_dst").value = p.dst_value || "";
  $("f_send_dst").checked = p.send_dst !== false;
  $("f_words").value = (p.success_words || []).join(", ");
  const extras = Object.entries(p.extra_fields || {}).map(([k, v]) => k + "=" + v);
  $("f_extra").value = extras.join(", ");
  const sel = $("f_charset");
  const known = Object.entries(S.meta.charsets).find(([, c]) => c === p.charset);
  if (known) sel.value = known[0];
  else { sel.value = "_custom"; $("f_custom").value = p.charset || ""; }
  toggleCustomCharset();
  showCovered(p);
  previewFormat();
}

/* how much of this space has been tried in earlier runs */
function showCovered(p) {
  const box = $("pvCovered");
  if (!box) return;
  const pos = parseInt((p && p.space_pos) || 0, 10) || 0;
  const space = parseInt((p && p.space) || 0, 10) || 0;
  box.classList.toggle("hidden", !pos);
  $("pvCoveredVal").textContent = fmtSpace(pos) + (space ? " / " + fmtSpace(space) : "");
}

function renderProfiles(list) {
  const sel = $("profSel");
  const keep = sel.value;
  sel.innerHTML = "<option value=''>" + t("prof_new") + "</option>" +
    (list || []).map((p) => "<option value='" + esc(p.name) + "'>" + esc(p.name) +
      " — " + esc(p.cards || "") + " (" + fmtSpace(p.space || 0) +
      (p.covered ? " · " + t("p_covered") + " " + fmtSpace(p.covered) : "") +
      ")</option>").join("");
  sel.value = (list || []).some((p) => p.name === keep) ? keep : "";
}

/* after a run the engine has saved how far it got - pull it back so the
   "continue where you stopped" checkbox has something to continue from */
async function refreshProfiles() {
  const r = await api("/api/profiles");
  if (!r.ok) return;
  renderProfiles(r.profiles || []);
  const name = (S.profile || {}).name;
  if (!name) return;
  const fresh = (r.profiles || []).find((p) => p.name === name);
  if (fresh) {
    S.profile = Object.assign({}, S.profile,
      { space_pos: fresh.covered || 0, space: fresh.space || 0 });
    showCovered(S.profile);
  }
}

async function loadProfile(name) {
  if (!name) return;
  const r = await api("/api/profiles/get?name=" + encodeURIComponent(name));
  if (r.ok && r.profile) {
    fillFormFromProfile(r.profile);
    toast("📂 " + name);
  } else { toast(t("scan_fail")); }
}

function toggleCustomCharset() {
  $("f_customWrap").classList.toggle("hidden", $("f_charset").value !== "_custom");
}

/* ------------------------------------------------------------------ scan */
async function doScan() {
  const url = $("scanUrl").value.trim();
  if (!url) return;
  $("scanBtn").disabled = true; $("scanBtn").textContent = t("loading");
  const res = await api("/api/scan", { url });
  $("scanBtn").disabled = false; $("scanBtn").textContent = t("scan_button");
  const card = $("portalCard"); const net = $("internetCard");
  card.classList.remove("hidden"); net.classList.remove("hidden");

  if (!res.ok) {
    card.innerHTML = '<h4 class="bad">' + t("scan_fail") + "</h4>" +
      '<div class="kv"><dt>' + (res.hint || "") + "</dt><dd>" + esc(res.detail || res.error) + "</dd></div>";
    net.classList.add("hidden");
    $("toFormat").disabled = true;
    return;
  }
  S.portal = res.portal;
  renderInternet(res.internet, net);

  const f = res.portal.form || {};
  card.innerHTML =
    "<h4>" + t("detected") + "</h4><dl class='kv'>" +
    "<dt>" + t("form_action") + "</dt><dd>" + esc(f.action) + "</dd>" +
    "<dt>" + t("form_method") + "</dt><dd>" + esc((f.method || "").toUpperCase()) +
      " · " + res.ms + " ms · HTTP " + res.portal.status + "</dd>" +
    "<dt>" + t("user_field") + "</dt><dd>" + esc(f.user_field || "—") + "</dd>" +
    "<dt>" + t("pass_field") + "</dt><dd>" + esc(f.pass_field || "—") + "</dd>" +
    "<dt>" + t("extra_fields") + "</dt><dd>" +
      esc(Object.entries(f.extra_fields || {}).map(([k, v]) => k + "=" + v).join("  ") || "—") +
    "</dd><dt>" + t("dst_values") + "</dt><dd>" +
      esc((res.portal.dst_candidates || []).join("  |  ") || "—") + "</dd>" +
    (f.chap ? "<dt class='ok'>" + t("chap_detected") + "</dt><dd>" + t("chap_hint") + "</dd>" : "") +
    "</dl>" +
    (f.all_fields && f.all_fields.length ? "" :
      "<div class='warn'>" + t("no_form") + "</div>");

  /* auto-fill the format step with what the page told us */
  $("f_login_url").value = f.action || res.portal.url;
  $("f_method").value = (f.method || "post").toLowerCase() === "get" ? "get" : "post";
  $("f_user_field").value = f.user_field || "username";
  $("f_pass_field").value = f.pass_field || "password";
  const dsts = res.portal.dst_candidates || [];
  $("f_dst").value = dsts.find((d) => d) || "";
  if (f.chap) $("f_pass_mode").value = "chap";
  if (!($("f_extra").value)) {
    $("f_extra").value = Object.entries(f.extra_fields || {})
      .map(([k, v]) => k + "=" + v).join(", ");
  }
  if (!($("f_name").value)) {
    try { $("f_name").value = new URL(res.portal.url).hostname; }
    catch (e) { $("f_name").value = "profile"; }
  }
  /* a network we scanned before: load its saved profile, so a run can
     continue where it stopped instead of starting over */
  const same = ((S.meta || {}).profiles || []).find((p) => p.name === $("f_name").value);
  if (same) await loadProfile(same.name);
  else { S.profile = null; showCovered(null); }
  $("toFormat").disabled = false;
  previewFormat();
}

function renderInternet(info, node) {
  if (!info) { node.classList.add("hidden"); return; }
  const state = info.state || "OFFLINE";
  const cls = state === "ONLINE" ? "ok" : (state === "WALLED" ? "warn" : "bad");
  node.classList.remove("hidden");
  node.innerHTML = "<h4 class='" + cls + "'>" + t("internet_" + state) + "</h4>" +
    "<div class='kv'><dt>" + t("internet_detail_" + (info.detail || ""),
                               t("net_" + (info.detail || ""), info.detail || "")) +
    "</dt><dd>" + esc(info.url || "") + (info.location ? " → " + esc(info.location) : "") +
    "</dd></div>";
}

/* ------------------------------------------------------------------ preview */
let previewTimer = null;
function previewFormat() {
  clearTimeout(previewTimer);
  previewTimer = setTimeout(async () => {
    const res = await api("/api/format/preview", { profile: profileFromForm() });
    if (!res.ok) return;
    $("pvSpace").textContent = fmtSpace(res.space);
    $("pvSamples").innerHTML = (res.samples || [])
      .map((c) => "<span class='sample'>" + esc(c) + "</span>").join("");
    const box = $("pvProblems");
    const hard = (res.problems || []).filter((p) => p !== "space_is_astronomically_big");
    box.classList.toggle("hidden", !hard.length);
    box.innerHTML = hard.map((p) => "• " + t("prob_" + p, p)).join("<br>");
  }, 350);
}

/* ------------------------------------------------------------------ jobs */
async function waitJob(jobId, onTick) {
  /* never spin forever: 240 x 0.7s ~ 2.8 minutes is well past every job we run */
  for (let i = 0; i < 240; i++) {
    await new Promise((r) => setTimeout(r, 700));
    const res = await api("/api/job?id=" + encodeURIComponent(jobId));
    if (!res.ok) return null;
    if (onTick) onTick(res.job);
    if (res.job.state !== "running") return res.job;
  }
  return { state: "error", error: t("job_timeout"), result: {} };
}

async function runCalibration() {
  const btn = $("calibrateBtn"); btn.disabled = true;
  const card = $("calibCard"); card.classList.remove("hidden");
  card.innerHTML = "<h4>" + t("loading") + "</h4>";
  const known = $("f_known").value.trim();
  const res = await api("/api/calibrate", { profile: profileFromForm(),
                                            known_card: known });
  if (!res.ok) { card.innerHTML = "<div class='bad'>" + esc(res.error) + "</div>"; btn.disabled = false; return; }
  const job = await waitJob(res.job.id);
  btn.disabled = false;
  if (!job) { card.innerHTML = "<div class='bad'>job lost</div>"; return; }
  renderCalibration(job, card);
  if (known) S.knownCard = known;
}

function renderCalibration(job, node) {
  if (job.state === "error") {
    node.innerHTML = "<h4 class='bad'>" + esc(job.error) + "</h4>";
    return;
  }
  const r = job.result || {};
  let html = "<h4>" + (r.ok ? t("cal_known_card_works") : t("scan_fail")) + "</h4>";

  const fp = r.fingerprint;
  if (fp) {
    html += "<div class='kv'><dt>" + t("cal_rejection_baseline") + "</dt><dd>" +
      (fp.exact ? t("exact_mode") : t("shape_mode")) + " · " +
      t("dyn_tokens") + ": " + fp.dynamic_tokens + " · HTTP " + fp.reject_status +
      " · " + fp.reject_length + " bytes</dd></div>";
  }
  html += "<ul style='margin:.4rem 0 0;padding-inline-start:1.1rem'>";
  (r.steps || []).forEach((s) => {
    const mark = s.ok ? "✔" : "✖";
    const cls = s.ok ? "ok" : "warn";
    let extra = "";
    const d = s.detail || {};
    if (s.id === "internet_state") extra = " — " + t("internet_" + (d.state || ""));
    if (s.id === "reach_login_page" && d.ms) extra = " — HTTP " + d.status + " · " + d.ms + " ms";
    if (s.id === "shape_tuned" && d.tuned)
      extra = " — " + t("pm_" + d.tuned.mode, d.tuned.mode) +
              (d.tuned.dst ? " · dst=" + esc(d.tuned.dst) : "");
    html += "<li class='" + cls + "'>" + mark + " " + t("cal_" + s.id, s.id) + ": " +
            t("cal_" + s.reason, s.reason) + esc(extra) + "</li>";
  });
  html += "</ul>";
  if (r.success_words && r.success_words.length)
    html += "<div class='kv'><dt>" + t("f_words") + "</dt><dd>" +
            esc(r.success_words.join(", ")) + "</dd></div>";
  if (r.error) html += "<div class='bad mono'>" + esc(r.error) + "</div>";
  node.innerHTML = html;
}

async function runDiagnose() {
  const btn = $("diagnoseBtn"); btn.disabled = true;
  const card = $("diagCard"); card.classList.remove("hidden");
  card.innerHTML = "<h4>" + t("loading") + "</h4>";
  const res = await api("/api/diagnose", { profile: profileFromForm(),
                                           threads: parseInt($("r_threads").value || "12", 10) });
  if (!res.ok) { card.innerHTML = "<div class='bad'>" + esc(res.error) + "</div>"; btn.disabled = false; return; }
  const job = await waitJob(res.job.id);
  btn.disabled = false;
  if (!job) return;
  renderDiagnose(job, card);
}

async function runLockoutProbe() {
  const btn = $("lockoutBtn"); btn.disabled = true;
  const card = $("lockoutCard"); card.classList.remove("hidden");
  card.innerHTML = "<h4>" + t("lockout_measuring") + "</h4>";
  const res = await api("/api/lockout", { profile: profileFromForm(),
                                          max_failures: 30, wait_limit: 240 });
  if (!res.ok) {
    card.innerHTML = "<div class='bad'>" + esc(res.error) + "</div>";
    btn.disabled = false; return;
  }
  const job = await waitJob(res.job.id);
  btn.disabled = false;
  if (!job) return;
  renderLockout(job, card);
}

function renderLockout(job, node) {
  if (job.state === "error") {
    node.innerHTML = "<div class='bad'>" + esc(job.error) + "</div>";
    return;
  }
  const r = job.result || {};
  let html = "<h4>" + t("btn_lockout") + "</h4>";
  if (r.error) {
    html += "<div class='bad mono'>" + esc(r.error) + "</div>" +
            "<div class='warn'>" + esc(t("netadvice_" + r.error, "")) + "</div>";
    node.innerHTML = html;
    return;
  }
  if (r.ban_after == null) {
    html += "<div class='ok'>" + t("lockout_never", "") + " " +
            esc(String(r.tried || 0)) + "</div>";
  } else {
    html += "<div class='bad'>" + t("lockout_after") + ": <b>" + r.ban_after +
            "</b></div>";
    if (r.clears_after != null) {
      html += "<div class='ok'>" + t("lockout_clears") + ": <b>" + r.clears_after +
              "</b> " + t("seconds") + "</div>";
    } else {
      html += "<div class='bad'>" + t("lockout_never_clears") + " (" +
              esc(String(r.waited || 0)) + " " + t("seconds") + ")</div>";
    }
  }
  if (r.safe_delay_ms) {
    html += "<div class='warn' style='margin-top:6px'>→ " + t("lockout_pace") +
            ": <b>" + (r.safe_delay_ms / 1000).toFixed(1) + "</b> " + t("seconds") +
            " / " + t("attempt") + "</div>" +
            "<div class='hint'>" + t("lockout_pace_hint") + "</div>";
  } else if (r.ban_after != null) {
    html += "<div class='warn' style='margin-top:6px'>→ " +
            t("lockout_impossible") + "</div>";
  }
  node.innerHTML = html;
}

function renderDiagnose(job, node) {
  if (job.state === "error") { node.innerHTML = "<div class='bad'>" + esc(job.error) + "</div>"; return; }
  const r = job.result || {};
  let html = "<h4>" + t("btn_diagnose") + "</h4><ul style='margin:.2rem 0 0;padding-inline-start:1.1rem'>";
  (r.steps || []).forEach((s) => {
    let extra = "";
    const d = s.detail || {};
    if (s.id === "internet") extra = " — " + t("internet_" + (d.state || ""));
    if (s.id === "sample_single" || s.id === "sample_parallel")
      extra = " — " + (d.sent || 0) + " req · " + (d.avg_ms || 0) + " ms · " +
              (d.error_rate || 0) + "% " + (LANG === "ar" ? "أخطاء" : "errors");
    if (s.id === "ban_check") extra = " — " + (d.ban_pages || 0);
    html += "<li class='" + (s.ok ? "ok" : "warn") + "'>" +
            (s.ok ? "✔" : "✖") + " " + t("diag_" + s.id, s.id) + ": " +
            t("diag_" + s.reason, t("cal_" + s.reason, s.reason)) + esc(extra) + "</li>";
  });
  html += "</ul>";
  (r.advice || []).forEach((a) => {
    html += "<div class='warn'>→ " + t("advice_" + a.reason, a.reason) +
      (a.suggest_threads ? " (" + t("suggest_threads") + ": " + a.suggest_threads + ")" : "") +
      "</div>";
  });
  node.innerHTML = html;
}

/* ------------------------------------------------------------------ run */
async function startRun() {
  const profile = profileFromForm();
  const known = $("f_known").value.trim();
  const payload = {
    profile, known_card: known,
    attempts: parseInt($("r_attempts").value || "2000", 10),
    threads: parseInt($("r_threads").value || "12", 10),
    delay_ms: parseInt($("r_delay").value || "0", 10),
    verify: $("r_verify").checked, auto_stop: $("r_autostop").checked,
    resume: $("r_resume").checked,
  };
  S.lastStart = payload;
  const res = await api("/api/run/start", payload);
  if (!res.ok) {
    modal(t("scan_fail"), "<pre>" + esc(JSON.stringify(res, null, 2)) + "</pre>");
    return;
  }
  S.lastSeq = 0; S.rows = 0;
  $("logBody").innerHTML = ""; $("hitsBox").innerHTML = t("hits_none");
  $("reviewBox").innerHTML = t("review_none");
  $("startBtn").classList.add("hidden"); $("stopBtn").classList.remove("hidden");
  S.running = true;
  step("results");
  pollStatus();
}

async function stopRun() {
  await api("/api/run/stop", {});
  toast(t("state_stopping"));
}

function pollStatus() {
  clearTimeout(S.poll);
  S.poll = setTimeout(async () => {
    const res = await api("/api/run/status?since=" + S.lastSeq);
    if (!res.ok) {
      S.running = false;
      if (res.error === "server_gone")
        modal(t("server_gone_title"), "<div>" + esc(t("server_gone")) + "</div>");
      return;
    }
    renderStatus(res.status, res.events);
    if (res.status.state === "idle" && !S.running) return;
    if (res.status.state === "done" && S.running) {
      S.running = false;
      $("startBtn").classList.remove("hidden");
      $("stopBtn").classList.add("hidden");
      renderStop(res.status);
      refreshProfiles();          /* the engine saved where the run stopped */
      setTimeout(pollStatus, 1500);
      return;
    }
    pollStatus();
  }, 550);
}

function renderStatus(st, events) {
  S.state = st.state;
  const statePill = $("statePill");
  statePill.textContent = stateLabel(st.state);
  statePill.className = "pill " + (st.state === "running" ? "run"
    : st.state === "done" ? "done" : st.error ? "err" : "");
  $("stState").textContent = stateLabel(st.state);
  $("stSpeed").textContent = (st.speed || 0) + "/s";
  $("stSent").textContent = fmtSpace((st.progress || {}).attempts || 0);
  $("stCovered").textContent = fmtSpace((st.progress || {}).covered || 0);
  $("stLatency").textContent = ((st.latency || {}).avg_ms || 0) + " ms";
  $("stDelay").textContent = ((st.throttle || {}).delay_ms || 0) + " ms";
  const total = (st.progress || {}).total || 1;
  const pct = Math.min(100, ((st.progress || {}).attempts || 0) / total * 100);
  $("bar").style.width = pct.toFixed(1) + "%";

  /* counters */
  const order = ["ACCEPTED_VERIFIED", "ACCEPTED", "ACCEPTED_UNVERIFIED", "REJECTED",
                 "UNKNOWN", "BANNED", "RATE_LIMITED", "CHALLENGE", "NET_ERROR"];
  const counters = st.counters || {};
  $("counterChips").innerHTML = order.filter((c) => counters[c])
    .map((c) => "<span class='cchip'><span class='vcode v-" + c + "'>" +
           esc(codeLabel(c)) + "</span><b>" + counters[c] + "</b></span>").join("");

  /* why each attempt ended the way it did - the whole point of the results page */
  const whyBox = $("whyCard");
  const whyList = Object.entries(st.reason_counts || {})
    .sort((a, b) => b[1] - a[1]).filter(([, n]) => n);
  if (whyList.length) {
    whyBox.classList.remove("hidden");
    whyBox.innerHTML = "<h4>" + t("why_title") + "</h4><table class='why'><tbody>" +
      whyList.map(([code, n]) => "<tr><td>" + esc(whyLabel(code)) + "</td><td><b>" +
        fmtSpace(n) + "</b></td></tr>").join("") + "</tbody></table>";
  } else { whyBox.classList.add("hidden"); }

  /* throttle note */
  const th = (st.throttle || {}).reason;
  const thCard = $("throttleCard");
  if (th) {
    thCard.classList.remove("hidden");
    thCard.innerHTML = "<span class='warn'>⏳ " + t("th_" + th, th) + "</b> — " +
      ((st.throttle || {}).delay_ms || 0) + " ms</span>";
  } else { thCard.classList.add("hidden"); }

  /* while the run is still going, the stop card shows the learning progress -
     never after it, because renderStop owns that card once the run is over */
  if (st.calibration && st.calibration.steps && S.rows === 0 && st.state !== "done") {
    const c = $("stopCard");
    const okSteps = st.calibration.steps.filter((s) => s.ok).length;
    c.classList.remove("hidden");
    c.innerHTML = "<h4>" + t("cal_rejection_baseline") + "</h4><div>" +
      okSteps + "/" + st.calibration.steps.length + " ✔ · " +
      (st.calibration.fingerprint ?
        (st.calibration.fingerprint.exact ? t("exact_mode") : t("shape_mode")) : "") +
      "</div>";
  }

  (events || []).forEach((ev) => {
    S.lastSeq = Math.max(S.lastSeq, ev.seq);
    if (ev.kind === "attempt") addRow(ev.data);
    else if (ev.kind === "hit") renderHits(ev.data);
    else if (ev.kind === "resume")
      toast("↪ " + t("resume_from") + " " + fmtSpace((ev.data || {}).from || 0));
    else if (ev.kind === "review") renderReview(st.review || []);
    else if (ev.kind === "error") modal("Error", "<pre>" + esc(ev.data.message) + "</pre>");
    else if (ev.kind === "report") S.lastReport = ev.data.file;
    else if (ev.kind === "internet_opened")
      toast("\uD83C\uDF10 " + t("internet_opened_title"));
    else if (ev.kind === "block_wait") {
      S.retryWait = (ev.data || {}).seconds || 45;
      toast("⏳ " + t("block_wait") + " " + S.retryWait + "s");
    }
  });
  if (st.review && st.review.length) renderReview(st.review);
  if (st.hits && st.hits.length) renderHits(null, st.hits);
}

function addRow(d) {
  if (S.rows > 400) { $("logBody").removeChild($("logBody").firstChild); }
  const tr = document.createElement("tr");
  tr.className = d.code;
  const reason = d.code === "NET_ERROR" ? t("net_" + d.reason, d.reason)
    : reasonLabel(d.code, d.reason, d.data);
  tr.innerHTML =
    "<td>" + (d.index != null ? d.index + 1 : "—") + "</td>" +
    "<td>" + esc(d.card) + "</td>" +
    "<td>" + (d.status || "—") + "</td>" +
    "<td><span class='vcode v-" + d.code + "'>" + esc(codeLabel(d.code)) + "</span></td>" +
    "<td class='why'>" + esc(reason) + "</td>" +
    "<td>" + (d.ms || 0) + "</td>" +
    "<td>" + (d.length || 0) + "</td>";
  $("logBody").appendChild(tr);
  const wrap = $("logBody").closest(".logwrap");
  if (wrap) wrap.scrollTop = 0;
  S.rows++;
}

function renderHits(hit, all) {
  if (hit) toast("🎯 " + hit.card);
  const hits = all || [];
  const box = $("hitsBox");
  if (!hits.length && !hit) return;
  const list = hit && !all ? [hit] : hits;
  box.className = "card";
  box.innerHTML = list.map((h) =>
    "<div><span class='vcode v-" + h.code + "'>" + esc(codeLabel(h.code)) + "</span> " +
    "<b class='mono' style='font-size:1rem'>" + esc(h.card) + "</b> — " +
    esc(reasonLabel(h.code, h.reason, h.data)) +
    (h.data && h.data.internet ? " · internet: " + esc(h.data.internet) : "") +
    "</div>").join("");
}

function renderReview(items) {
  const box = $("reviewBox");
  if (!items || !items.length) return;
  box.className = "card";
  box.innerHTML = items.slice(-30).reverse().map((r) => {
    const d = r.data || {};
    const diff = (d.diff && d.diff.new_words) || [];
    return "<div style='margin-bottom:8px'>" +
      "<button class='btn tiny' data-review='" + esc(r.file) + "'>" +
      t("review_open") + "</button> <b class='mono'>" + esc(r.card) + "</b>" +
      (diff.length ? "<div class='hint'>" + t("review_diff") + ": " +
        esc(diff.slice(0, 8).join(", ")) + "</div>" : "") +
      "</div>";
  }).join("");
  box.querySelectorAll("[data-review]").forEach((b) =>
    b.addEventListener("click", () => openReview(b.dataset.review)));
}

async function openReview(name) {
  const res = await fetch(withToken("/api/review/file?name=" + encodeURIComponent(name)));
  const html = await res.text();
  modal(name, "<iframe class='pagereview' sandbox srcdoc='" +
        esc(html) + "'></iframe>");
}

/* The worst case used to be silent: the run said "finished", the log was
   empty and the only text was "details in the log".  Now the page spells out
   what the router did, step by step, and what to do about it. */
function calReasonLabel(reason) {
  reason = reason || "";
  if (reason.startsWith("net_")) return t("net_" + reason.slice(4), reason.slice(4));
  if (reason.startsWith("internet_")) return t(reason, reason.slice(9));
  return t("cal_" + reason, reason);
}

function renderCalFailure(st) {
  const cal = st.calibration || {};
  const kind = String(st.error || cal.error || "").replace(/^net_/, "");
  const steps = cal.steps || [];
  const failed = steps.filter((s) => !s.ok);
  /* the failed step knows the exact cause ("our three test cards did it"
     vs "the router was already blocking us"), the error code only knows
     the family - prefer the step when we have one */
  const why = failed.length ? String(failed[failed.length - 1].reason || "") : "";
  let html = "<div class='bad' style='margin-top:8px;font-weight:600'>" +
    esc(t("cal_failed_title")) + "</div>" +
    "<div class='hint'>" + esc(t("cal_failed_hint")) + "</div>";
  if (kind) {
    html += "<div class='bad mono'>" +
      esc(t("cal_" + (why || kind), t("net_" + kind, t("cal_" + kind, kind)))) +
      "</div>";
    const advice = t("netadvice_" + (why || kind), "") || t("netadvice_" + kind, "");
    if (advice) html += "<div class='warn'>→ " + esc(advice) + "</div>";
  }
  if (cal.steps && cal.steps.length) {
    html += "<ul style='margin:.4rem 0 0;padding-inline-start:1.1rem'>";
    cal.steps.forEach((s) => {
      const d = s.detail || {};
      let extra = "";
      if (s.id === "profile_valid" && d.problems)
        extra = " — " + (d.problems || []).map((p) => t("prob_" + p, p)).join("، ");
      if (s.id === "reach_login_page" && d.text)
        extra = " — <span class='mono'>" + esc(String(d.text).slice(0, 120)) + "</span>";
      if (s.id === "internet_state" && d.state) extra = " — " + t("internet_" + d.state);
      /* a block is decided from a word and/or a status code: show them, so the
         user can see WHY we called this page a block page */
      if (/blocked|ban/.test(s.reason)) {
        const bits = [];
        if (d.word) bits.push("«" + d.word + "»");
        if (d.status) bits.push("HTTP " + (Array.isArray(d.status) ? d.status.join("/") : d.status));
        if (d.has_form) bits.push(t("block_but_form_present"));
        if (d.probes_sent) bits.push(d.probes_sent + " " + t("probe_cards"));
        if (bits.length) extra += " — " + esc(bits.join(" · "));
      }
      html += "<li class='" + (s.ok ? "ok" : "bad") + "'>" + (s.ok ? "✔" : "✖") +
        " " + t("cal_" + s.id, s.id) + ": " + calReasonLabel(s.reason) + extra + "</li>";
    });
    html += "</ul>";
  }
  html += "<div class='hint'>" + esc(t("no_attempt_was_made")) + "</div>";
  return html;
}

function renderStop(st) {
  const card = $("stopCard");
  card.classList.remove("hidden");
  let html = "<h4>" + t("why_stopped") + "</h4><div>" +
    t("stop_" + st.stop_reason, st.stop_reason || "") + "</div>";
  const tried = (st.progress || {}).attempts || 0;
  if ((st.calibration && st.calibration.ok === false) ||
      st.stop_reason === "calibration_failed") {
    html += renderCalFailure(st);
  } else if (!tried) {
    html += "<div class='warn' style='margin-top:6px'>" + esc(t("no_attempt_was_made")) +
      (st.error ? " — <span class='mono'>" + esc(st.error) + "</span>" : "") + "</div>";
  }
  if (st.hits && st.hits.length) {
    html += "<div class='ok' style='margin-top:6px'>" + t("hits_title") + ": " +
      st.hits.map((h) => "<b class='mono'>" + esc(h.card) + "</b> (" +
      esc(codeLabel(h.code)) + ")").join(", ") + "</div>";
  }
  /* the wall came down while we were guessing: one of these cards did it */
  const opened = st.internet_opened;
  if (opened && opened.suspects && opened.suspects.length) {
    html += "<div class='warn' style='margin-top:8px;font-weight:600'>\u24d8 " +
      esc(t("internet_opened_title")) + "</div>" +
      "<div class='hint'>" + esc(t("internet_opened_hint")) + "</div>" +
      "<div class='mono' style='margin-top:4px;word-break:break-all'>" +
      opened.suspects.map((s) => esc(s.card)).join(" \u00b7 ") + "</div>";
  }
  const k = st.net_kinds || {};
  const parts = Object.entries(k).map(([kind, n]) => t("net_" + kind, kind) + " ×" + n);
  if (parts.length) html += "<div class='hint'>" + esc(parts.join(" · ")) + "</div>";
  if (S.lastReport)
    html += "<div class='hint'>" + t("report_saved") + ": <span class='mono'>" +
            esc(S.lastReport) + "</span></div>";
  /* a run that never started can simply be tried again - straight away, or
     after the router's lockout has passed */
  if (st.stop_reason === "calibration_failed") {
    html += "<div class='row wrap' style='margin-top:8px'>" +
            "<button class='btn' id='retryNowBtn'>" + esc(t("retry_now")) + "</button>" +
            "<button class='btn' id='retryWaitBtn'>" + esc(t("retry_after_wait")) +
            "</button></div>";
  }
  card.innerHTML = html;
  const now = $("retryNowBtn");
  if (now) now.addEventListener("click", () => startRun());
  const wait = $("retryWaitBtn");
  if (wait) wait.addEventListener("click", () => {
    let left = S.retryWait || 45;
    wait.disabled = true;
    if (now) now.disabled = true;
    const tick = () => {
      if (left <= 0) { startRun(); return; }
      wait.textContent = t("retry_after_wait") + " (" + left + ")";
      left -= 1;
      setTimeout(tick, 1000);
    };
    tick();
  });
}

/* ------------------------------------------------------------------ modal */
function modal(title, html) {
  $("modalTitle").textContent = title;
  $("modalBody").innerHTML = html;
  $("modal").classList.remove("hidden");
}

async function cacheModal() {
  const res = await api("/api/cache");
  const c = res.cache || {};
  let html = "<p>" + t("cache_hint") + "</p><ul>";
  Object.entries(c.folders || {}).forEach(([name, v]) => {
    html += "<li>" + esc(name) + ": " + v.files + " " +
      (LANG === "ar" ? "ملف" : "files") + " · " +
      (v.bytes / 1024).toFixed(1) + " KB</li>";
  });
  if (c.profiles) html += "<li>profiles: " + c.profiles.count + "</li>";
  html += "</ul><div class='row wrap'>" +
    "<button class='btn' data-scope='temp'>" + t("cache_temp") + "</button>" +
    "<button class='btn' data-scope='results'>" + t("cache_results") + "</button>" +
    "<button class='btn danger' data-scope='profiles'>" + t("cache_profiles") + "</button>" +
    "<button class='btn danger' data-scope='all'>" + t("cache_all") + "</button></div>";
  modal(t("cache_title"), html);
  $("modalBody").querySelectorAll("[data-scope]").forEach((b) =>
    b.addEventListener("click", async () => {
      const scope = b.dataset.scope;
      if (scope === "all" && !confirm(t("confirm_clear_all"))) return;
      if (scope === "profiles" && !confirm(t("confirm_profiles"))) return;
      const r = await api("/api/cache/clear", { scope });
      modal(t("cache_title"), "<div class='ok'>" + t("cache_freed") + " " +
        esc((r.cleared || {}).freed_human || "") + "</div>");
      setTimeout(() => $("modal").classList.add("hidden"), 1400);
    }));
}

/* ------------------------------------------------------------------ wire up */
function wire() {
  document.querySelectorAll(".step").forEach((b) =>
    b.addEventListener("click", () => step(b.dataset.step)));
  $("scanBtn").addEventListener("click", doScan);
  $("scanUrl").addEventListener("keydown", (e) => { if (e.key === "Enter") doScan(); });
  document.querySelectorAll(".chip[data-url]").forEach((c) =>
    c.addEventListener("click", () => { $("scanUrl").value = c.dataset.url; doScan(); }));
  $("toFormat").addEventListener("click", () => step("format"));
  $("toRun").addEventListener("click", () => step("run"));
  $("langBtn").addEventListener("click", () => setLang(LANG === "ar" ? "en" : "ar"));
  $("cacheBtn").addEventListener("click", cacheModal);
  $("bannerMore").addEventListener("click", () =>
    modal(t("license_title"), "<pre>" + esc(t("license_body")) + "</pre>"));
  $("licenseLink").addEventListener("click", (e) => { e.preventDefault();
    modal(t("license_title"), "<pre>" + esc(t("license_body")) + "</pre>"); });
  const quitLink = $("quitLink");
  if (quitLink) quitLink.addEventListener("click", async (e) => {
    e.preventDefault();
    if (!window.confirm(t("confirm_quit"))) return;
    await api("/api/quit", {});
    modal(t("quit_tool"), "<div class='ok'>" + esc(t("quit_done")) + "</div>");
  });
  $("modalClose").addEventListener("click", () => $("modal").classList.add("hidden"));
  $("modal").addEventListener("click", (e) => {
    if (e.target === $("modal")) $("modal").classList.add("hidden"); });
  $("licenseOk").addEventListener("change", () =>
    $("startBtn").disabled = !$("licenseOk").checked);
  $("startBtn").addEventListener("click", startRun);
  $("stopBtn").addEventListener("click", stopRun);
  $("calibrateBtn").addEventListener("click", runCalibration);
  $("diagnoseBtn").addEventListener("click", runDiagnose);
  $("lockoutBtn").addEventListener("click", runLockoutProbe);
  $("saveProfileBtn").addEventListener("click", async () => {
    const r = await api("/api/profiles/save", { profile: profileFromForm() });
    toast(r.ok ? "💾 OK" : t("scan_fail"));
    if (r.ok) renderProfiles(r.profiles);
    if (!r.ok) modal("!", "<pre>" + esc(JSON.stringify(r.problems || r, null, 2)) + "</pre>");
  });
  const profSel = $("profSel");
  if (profSel) {
    profSel.addEventListener("change", () => loadProfile(profSel.value));
    $("profDelBtn").addEventListener("click", async () => {
      const name = profSel.value;
      if (!name || !window.confirm(name + " ?")) return;
      const r = await api("/api/profiles/delete", { name });
      renderProfiles(r.profiles);
      toast("🗑 " + name);
    });
  }
  $("clearLogBtn").addEventListener("click", () => { $("logBody").innerHTML = ""; S.rows = 0; });
  $("downloadBtn").addEventListener("click", () => {
    if (!S.lastReport) { toast("—"); return; }
    window.open(withToken("/api/report?name=" + encodeURIComponent(S.lastReport)), "_blank");
  });
  $("clearReviewBtn").addEventListener("click", async () => {
    await api("/api/cache/clear", { scope: "temp" });
    $("reviewBox").innerHTML = t("review_none");
    toast("🧹");
  });
  $("presetRow").addEventListener("click", (e) => {
    const id = e.target.dataset && e.target.dataset.preset;
    if (!id || !S.meta) return;
    const p = S.meta.presets.find((x) => x.id === id);
    if (!p) return;
    $("r_threads").value = p.threads;
    $("r_attempts").value = p.attempts;
    $("r_delay").value = p.delay_ms;
  });
  ["f_prefix", "f_length", "f_custom", "f_pass_mode", "f_charset", "f_login_url",
   "f_method", "f_user_field", "f_pass_field", "f_name"].forEach((id) => {
    const node = $(id);
    if (node) { node.addEventListener("input", previewFormat);
                node.addEventListener("change", previewFormat); }
  });
  $("f_charset").addEventListener("change", () => { toggleCustomCharset(); previewFormat(); });
}

/* ------------------------------------------------------------------ boot */
(async function boot() {
  const meta = await api("/api/meta");
  S.meta = meta || {};
  if (meta.app) document.title = meta.app + " — " + meta.version;
  $("verPill").textContent = "v" + (meta.version || "");
  buildSelects();
  const saved = localStorage.getItem("kirapass_lang") || meta.lang || "ar";
  setLang(saved);
  wire();
  toggleCustomCharset();
  previewFormat();
  renderProfiles(meta.profiles || []);
  if ((meta.profiles || []).length === 1) loadProfile(meta.profiles[0].name);
})();
