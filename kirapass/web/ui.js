/* KiraPass web UI - vanilla JS, no build step, no internet needed. */
"use strict";  // الوضع الصارم: يمنع أخطاء JS الصامتة في كل الملف

/* ------------------------------------------------------------------ i18n */
const I18N = {  // تعريف الثابت I18N = كائن
  ar: {  // مفتاح ar في الكائن = كائن
    /* interface */
    step_start: "البداية",  // مفتاح step_start في الكائن = نص
    step_scan: "فحص الشبكة", step_format: "صيغة البطاقة",  // مفتاح step_scan في الكائن = نص
    step_run: "التشغيل", step_results: "النتائج",  // مفتاح step_run في الكائن = نص
    start_title: "KiraPass — البداية",  // مفتاح start_title في الكائن = نص
    start_hint: "اختر مسار العمل. لن يبدأ أي فحص أو تخمين تلقائياً قبل تأكيدك الصريح.",  // مفتاح start_hint في الكائن = نص
    btn_new_profile: "بروفايل جديد",  // مفتاح btn_new_profile في الكائن = نص
    btn_saved_profile: "استخدام بروفايل محفوظ",  // مفتاح btn_saved_profile في الكائن = نص
    saved_title: "البروفايلات المحفوظة",  // مفتاح saved_title في الكائن = نص
    saved_hint: "اختر بروفايل لمراجعة إعداداته قبل التشغيل. لن يبدأ أي فحص أو تخمين تلقائياً.",  // مفتاح saved_hint في الكائن = نص
    back_to_start: "رجوع للبداية",  // مفتاح back_to_start في الكائن = نص
    back_to_saved: "رجوع للقائمة",  // مفتاح back_to_saved في الكائن = نص
    back_to_scan: "رجوع للفحص",  // مفتاح back_to_scan في الكائن = نص
    back_to_format: "رجوع للصيغة",  // مفتاح back_to_format في الكائن = نص
    review_profile_title: "مراجعة البروفايل",  // مفتاح review_profile_title في الكائن = نص
    review_profile_hint: "راجع الإعدادات المحفوظة قبل التشغيل. إذا كانت مكتملة يمكنك البدء مباشرة، وإذا كانت ناقصة أصلحها يدوياً من دون إرسال طلبات تلقائية.",  // مفتاح review_profile_hint في الكائن = نص
    edit_settings: "تعديل الإعدادات",  // مفتاح edit_settings في الكائن = نص
    btn_start_from_review: "ابدأ التخمين",  // مفتاح btn_start_from_review في الكائن = نص
    no_saved_profiles: "لا توجد بروفايلات محفوظة بعد. أنشئ بروفايل جديد أولاً.",  // مفتاح no_saved_profiles في الكائن = نص
    saved_profile_count: "عدد البروفايلات المحفوظة",  // مفتاح saved_profile_count في الكائن = نص
    profile_summary: "ملخص البروفايل",  // مفتاح profile_summary في الكائن = نص
    profile_invalid: "البروفايل غير مكتمل",  // مفتاح profile_invalid في الكائن = نص
    profile_invalid_hint: "بعض الإعدادات المطلوبة مفقودة أو غير صالحة. أصلحها يدوياً قبل التشغيل؛ لن يتم تخمين قيم أو إرسال طلبات تلقائية.",  // مفتاح profile_invalid_hint في الكائن = نص
    profile_valid: "البروفايل مكتمل وجاهز للتشغيل",  // مفتاح profile_valid في الكائن = نص
    probe_link_title: "فحص الاتصال بالراوتر",  // مفتاح probe_link_title في الكائن = نص
    probe_link_hint: "طلب GET واحد فقط للرابط — يعرض النتيجة دون تخمين أو إرسال بطاقات.",  // مفتاح probe_link_hint في الكائن = نص
    probe_link_button: "افحص الاتصال",  // مفتاح probe_link_button في الكائن = نص
    probe_reachable: "الرابط يستجيب",  // مفتاح probe_reachable في الكائن = نص
    probe_unreachable: "تعذّر الوصول للرابط",  // مفتاح probe_unreachable في الكائن = نص
    probe_has_form: "صفحة الدخول ظاهرة",  // مفتاح probe_has_form في الكائن = نص
    probe_no_form: "لا يوجد نموذج دخول واضح",  // مفتاح probe_no_form في الكائن = نص
    saved_search: "بحث في البروفايلات",  // مفتاح saved_search في الكائن = نص
    saved_search_ph: "ابحث بالاسم أو الرابط…",  // مفتاح saved_search_ph في الكائن = نص
    btn_export_profile: "تصدير JSON",  // مفتاح btn_export_profile في الكائن = نص
    btn_import_profile: "استيراد JSON",  // مفتاح btn_import_profile في الكائن = نص
    import_ok: "تم استيراد البروفايل",  // مفتاح import_ok في الكائن = نص
    import_fail: "فشل الاستيراد",  // مفتاح import_fail في الكائن = نص
    export_ok: "تم تنزيل البروفايل",  // مفتاح export_ok في الكائن = نص
    lan_warning_title: "تحذير: الواجهة مفتوحة على الشبكة المحلية",  // مفتاح lan_warning_title في الكائن = نص
    lan_warning_body: "التوكن يُرسل بدون تشفير (HTTP). استخدم فقط على شبكة تثق بها، وفضّل 127.0.0.1 إن أمكن.",  // مفتاح lan_warning_body في الكائن = نص
    f_internet_check: "رابط اختبار الإنترنت المخصص",  // مفتاح f_internet_check في الكائن = نص
    f_internet_check_hint: "يُستخدم بدل روابط Google/Microsoft/Apple عندما تحظرها الشبكة. الصيغة: url|status|نص اختياري",  // مفتاح f_internet_check_hint في الكائن = نص
    f_connect_timeout: "مهلة فتح الاتصال (ثوانٍ)",  // مفتاح f_connect_timeout في الكائن = نص
    f_connect_timeout_hint: "ارفعها للراوترات البطيئة (RADIUS). القيمة تُحفظ محلياً.",  // مفتاح f_connect_timeout_hint في الكائن = نص
    f_read_timeout: "مهلة انتظار الرد (ثوانٍ)",  // مفتاح f_read_timeout في الكائن = نص
    btn_save_net_settings: "احفظ إعدادات الشبكة",  // مفتاح btn_save_net_settings في الكائن = نص
    adv_run_open: "خيارات متقدمة للتشغيل والشبكة",  // مفتاح adv_run_open في الكائن = نص
    net_settings_saved: "تم حفظ إعدادات الشبكة",  // مفتاح net_settings_saved في الكائن = نص
    warn_fast_preset: "الإعداد السريع قد يحظر جهازك بسرعة. راجع مسؤول الشبكة قبل المتابعة. هل أنت متأكد؟",  // مفتاح warn_fast_preset في الكائن = نص
    warn_big_space: "عدد الاحتمالات ضخم جداً — قد يستغرق وقتاً طويلاً ويزيد ضغط الراوتر.",  // مفتاح warn_big_space في الكائن = نص
    warn_many_threads: "عدد المسارات مرتفع وقد يؤدي إلى حظر سريع. قلّله إن أمكن.",  // مفتاح warn_many_threads في الكائن = نص
    online_already_banner: "جهازك متصل بالإنترنت مسبقاً — التحقق من نجاح البطاقة محدود ويعتمد على تحويل الراوتر وصفحة الحالة.",  // مفتاح online_already_banner في الكائن = نص
    ban_evidence_label: "دليل الحظر للمشرف",  // مفتاح ban_evidence_label في الكائن = نص
    ban_evidence_status: "حالة HTTP",  // مفتاح ban_evidence_status في الكائن = نص
    ban_evidence_word: "العبارة المكتشفة",  // مفتاح ban_evidence_word في الكائن = نص
    ban_evidence_form: "نموذج الدخول لا يزال ظاهراً",  // مفتاح ban_evidence_form في الكائن = نص
    ban_evidence_kind: "تصنيف مبدئي",  // مفتاح ban_evidence_kind في الكائن = نص
    capture_guide_link: "دليل المسجل اليدوي",  // مفتاح capture_guide_link في الكائن = نص
    capture_curl_label: "أمر curl منقّح (بدون أسرار)",  // مفتاح capture_curl_label في الكائن = نص
    target_unreachable_doc: "target_unreachable يعني انقطاعاً أو حظراً إدارياً لا يمكن تمييزهما تلقائياً — راجع المشرف يدوياً قبل أي استئناف.",  // مفتاح target_unreachable_doc في الكائن = نص
    manual_resume_button: "استئناف يدوياً بعد مراجعة المشرف",  // مفتاح manual_resume_button في الكائن = نص
    manual_resume_confirm_title: "تأكيد الاستئناف اليدوي",  // مفتاح manual_resume_confirm_title في الكائن = نص
    manual_resume_confirm_body: "سيتم استئناف التشغيل بالإعدادات المحفوظة وموضع التقدم المستأنف. تأكد أن المشرف راجع الحالة وأن الاستئناف مسموح. لن يتم تغيير IP أو MAC أو فصل Wi‑Fi.",  // مفتاح manual_resume_confirm_body في الكائن = نص
    btn_continue: "متابعة",  // مفتاح btn_continue في الكائن = نص
    btn_cancel: "إلغاء",  // مفتاح btn_cancel في الكائن = نص
    resume_report: "استئناف يدوي بعد توقف",  // مفتاح resume_report في الكائن = نص
    skip_content: "تجاوز إلى المحتوى",  // مفتاح skip_content في الكائن = نص
    brand_subtitle: "اختبار شبكات مصرح به",  // مفتاح brand_subtitle في الكائن = نص
    license_link: "الترخيص",  // مفتاح license_link في الكائن = نص
    progress_label: "تقدم التشغيل",  // مفتاح progress_label في الكائن = نص
    language_label: "تغيير اللغة",  // مفتاح language_label في الكائن = نص
    steps_label: "خطوات الاستخدام",  // مفتاح steps_label في الكائن = نص
    banner_title: "استخدام مصرّح به فقط",  // مفتاح banner_title في الكائن = نص
    banner_text: "هذه الأداة للاختبار على شبكة تملكها أو لديك إذن كتابي من صاحبها. لا تستخدمها على شبكة غيرك.",  // مفتاح banner_text في الكائن = نص
    banner_more: "التفاصيل",  // مفتاح banner_more في الكائن = نص
    scan_title: "1) فحص الشبكة واختبار البطاقة المعروفة",  // مفتاح scan_title في الكائن = نص
    scan_hint: "الصق رابط صفحة دخول الهوتسبوت كما تفتحه في المتصفح. بعد الفحص أدخل بطاقة مصرحاً بها تعرف أنها تعمل واختبرها هنا؛ لن تنتقل لصيغة التخمين حتى يُثبت الاختبار فتح الإنترنت وتأكيد الخروج.",  // مفتاح scan_hint في الكائن = نص
    scan_button: "افحص الآن",  // مفتاح scan_button في الكائن = نص
    scan_url_label: "رابط صفحة الدخول",  // مفتاح scan_url_label في الكائن = نص
    calibration_setup_title: "اختبار البطاقة المعروفة وتعلّم الطلب",  // مفتاح calibration_setup_title في الكائن = نص
    calibration_setup_hint: "أدخل بطاقة مصرحاً بها وتعرف أنها تعمل. لن تُفتح إعدادات التخمين قبل أن يثبت الاختبار انتقال الإنترنت ثم تأكيد الخروج.",  // مفتاح calibration_setup_hint في الكائن = نص
    calibration_required: "يجب إكمال الاختبار أولاً",  // مفتاح calibration_required في الكائن = نص
    calibration_required_hint: "ارجع إلى فحص الشبكة، أدخل بطاقة مصرحاً بها تعمل، ثم نفّذ الاختبار. ستُطبّق إعدادات الطلب التي أثبتت نجاحها على الصفحة التالية.",  // مفتاح calibration_required_hint في الكائن = نص
    calibration_shape_changed: "تغيّر شكل الطلب بعد الاختبار",  // مفتاح calibration_shape_changed في الكائن = نص
    calibration_shape_changed_hint: "لن يبدأ التشغيل بإعدادات لم تُختبر. ارجع إلى فحص الشبكة وأعد اختبار البطاقة بعد مراجعة إعدادات الطلب.",  // مفتاح calibration_shape_changed_hint في الكائن = نص
    calibration_applied: "نجح الاختبار وطُبّق شكل الطلب على الإعدادات",  // مفتاح calibration_applied في الكائن = نص
    known_card_format_mismatch: "صيغة البطاقة في الصفحة الثانية لا تطابق البطاقة التي اختُبرت؛ صحّح الطول والبادئة والمحارف قبل التشغيل.",  // مفتاح known_card_format_mismatch في الكائن = نص
    attempt_table: "سجل محاولات التشغيل",  // مفتاح attempt_table في الكائن = نص
    next_format: "التالي: صيغة البطاقة ←",  // مفتاح next_format في الكائن = نص
    next_run: "التالي: التشغيل ←",  // مفتاح next_run في الكائن = نص
    format_title: "2) صيغة البطاقة",  // مفتاح format_title في الكائن = نص
    format_hint: "اكتب شكل الكرت: البادئة الثابتة + طول الكرت الكامل. شكل طلب الدخول المعروض أدناه تعلّمناه واختبرناه في الخطوة السابقة؛ إذا غيّرت إعدادات الطلب المتقدمة سيُطلب اختبارها من جديد قبل التشغيل.",  // مفتاح format_hint في الكائن = نص
    f_prefix: "البادئة الثابتة", f_length: "طول الكرت الكامل",  // مفتاح f_prefix في الكائن = نص
    saved_profiles: "الملف التعريفي المحفوظ", prof_new: "— جديد —",  // مفتاح saved_profiles في الكائن = نص
    btn_delete_profile: "حذف هذا الملف",  // مفتاح btn_delete_profile في الكائن = نص
    f_charset: "الحروف/الأرقام المتغيّرة", f_custom: "محارف مخصّصة",  // مفتاح f_charset في الكائن = نص
    f_pass_mode: "قيمة كلمة المرور", f_dst: "قيمة dst (وجهة الضيف)",  // مفتاح f_pass_mode في الكائن = نص
    f_name: "اسم الملف التعريفي",  // مفتاح f_name في الكائن = نص
    f_method: "طريقة الطلب", method_post: "POST (الأكثر توافقاً)", method_get: "GET",  // مفتاح f_method في الكائن = نص
    f_user_field: "اسم حقل المستخدم",  // مفتاح f_user_field في الكائن = نص
    f_pass_field: "اسم حقل كلمة المرور", f_login_url: "رابط إرسال الدخول (action)",  // مفتاح f_pass_field في الكائن = نص
    f_send_dst: "إرسال حقل dst",  // مفتاح f_send_dst في الكائن = نص
    f_send_popup: "إرسال حقل popup",  // مفتاح f_send_popup في الكائن = نص
    f_extra: "حقول ثابتة إضافية (name=value)",  // مفتاح f_extra في الكائن = نص
    f_words: "كلمات النجاح (اختياري)",  // مفتاح f_words في الكائن = نص
    f_words_clear: "مسح",  // مفتاح f_words_clear في الكائن = نص
    f_words_hint: "تُطابق هذه الكلمات نص الصفحة الظاهر فقط. امسحها إذا كانت قديمة أو غير صحيحة.",  // مفتاح f_words_hint في الكائن = نص
    f_known: "بطاقة مصرح بها تعرف أنها تعمل",  // مفتاح f_known في الكائن = نص
    adv_open: "خيارات متقدمة (عادة لا تحتاجها)",  // مفتاح adv_open في الكائن = نص
    p_space: "عدد الاحتمالات", p_samples: "أمثلة على البطاقات",  // مفتاح p_space في الكائن = نص
    p_request_shape: "شكل الطلب المتوقع (القيم الحساسة مخفية)",  // مفتاح p_request_shape في الكائن = نص
    online_transition: "انتقال إلى الإنترنت", logout_state: "حالة ما بعد الخروج",  // مفتاح online_transition في الكائن = نص
    p_covered: "مغطى سابقاً",  // مفتاح p_covered في الكائن = نص
    btn_calibrate: "اختبر البطاقة وتعلّم شكل الطلب",  // مفتاح btn_calibrate في الكائن = نص
    btn_capture: "افتح البوابة وسجّل دخولاً ناجحاً",  // مفتاح btn_capture في الكائن = نص
    capture_hint: "تُفتح البوابة داخل إطار معزول (بدون allow-same-origin) ولا يصل JavaScript الصفحة إلى واجهة KiraPass. سجّل دخولاً ناجحاً ثم علّم صفحات النجاح/الرفض/الإحصائيات.",  // مفتاح capture_hint في الكائن = نص
    capture_opened: "فُتح المسجّل في نافذة جديدة.",  // مفتاح capture_opened في الكائن = نص
    capture_popup_blocked: "منع المتصفح فتح النافذة. اسمح بالنوافذ المنبثقة لهذا العنوان ثم حاول مجدداً.",  // مفتاح capture_popup_blocked في الكائن = نص
    capture_fail: "تعذّر بدء المسجّل",  // مفتاح capture_fail في الكائن = نص
    capture_blocked_title: "التخمين الآلي غير متاح لهذه البوابة",  // مفتاح capture_blocked_title في الكائن = نص
    capture_blocked_body: "تحويل كلمة المرور يستخدم JavaScript مخصصاً غير معروف. لا ندّعي أنه قابل للأتمتة.",  // مفتاح capture_blocked_body في الكائن = نص
    capture_blocked_next: "الخطوة التالية: سجّل الدخول يدوياً عند الحاجة. التقرير المنقّح لا يحتوي رقم البطاقة ولا كلمة المرور.",  // مفتاح capture_blocked_next في الكائن = نص
    capture_mark_success: "هذه صفحة النجاح",  // مفتاح capture_mark_success في الكائن = نص
    capture_mark_reject: "هذه صفحة رفض",  // مفتاح capture_mark_reject في الكائن = نص
    capture_mark_status: "هذه صفحة الإحصائيات",  // مفتاح capture_mark_status في الكائن = نص
    capture_finish: "إنهاء + تنزيل التقرير",  // مفتاح capture_finish في الكائن = نص
    btn_save: "احفظ الملف التعريفي",  // مفتاح btn_save في الكائن = نص
    run_title: "3) التشغيل",  // مفتاح run_title في الكائن = نص
    run_hint: "اختر قوة مناسبة: كل ما زادت السرعة زاد احتمال أن يقطع الراوتر الاتصال أو يحجبك. عند بدء التشغيل يعيد البرنامج اختبار البطاقة المعروفة مرة واحدة بنفس الإعدادات؛ إذا لم يثبت الإنترنت يتوقف قبل التخمين. بعد النجاح يسجّل الخروج ثم يحدّث خط أساس الرفض دون إعادة إرسال البطاقة.",  // مفتاح run_hint في الكائن = نص
    r_threads: "عدد المسارات (Threads)", r_attempts: "عدد المحاولات",  // مفتاح r_threads في الكائن = نص
    r_delay: "الانتظار بين الطلبات (ms)",  // مفتاح r_delay في الكائن = نص
    r_verify: "تأكيد الإنترنت بعد أي بطاقة مقبولة",  // مفتاح r_verify في الكائن = نص
    r_autostop: "إيقاف تلقائي عند أول نتيجة قوية",  // مفتاح r_autostop في الكائن = نص
    r_resume: "المتابعة من حيث توقفت (بلا تكرار)",  // مفتاح r_resume في الكائن = نص
    cal_internet_walled: "خلف بوابة الدخول (يحتاج بطاقة)",  // مفتاح cal_internet_walled في الكائن = نص
    cal_internet_online: "متصل بالإنترنت فعلاً",  // مفتاح cal_internet_online في الكائن = نص
    cal_internet_offline: "لا يوجد اتصال",  // مفتاح cal_internet_offline في الكائن = نص
    cal_internet_blocked: "محجوب من الشبكة",  // مفتاح cal_internet_blocked في الكائن = نص
    cal_internet_unknown: "حالة الشبكة غير معروفة",  // مفتاح cal_internet_unknown في الكائن = نص
    cal_known_card_out_of_format: "الكرت لا يطابق صيغة البطاقات",  // مفتاح cal_known_card_out_of_format في الكائن = نص
    cal_known_card_not_proven: "لم أستطع إثبات أن هذا الكرت يعمل",  // مفتاح cal_known_card_not_proven في الكائن = نص
    cal_logout_unconfirmed: "لم أستطع تأكيد تسجيل الخروج؛ أوقفت أي محاولات أخرى",  // مفتاح cal_logout_unconfirmed في الكائن = نص
    prob_length_mismatch: "طول الكرت لا يساوي الطول المضبوط",  // مفتاح prob_length_mismatch في الكائن = نص
    prob_prefix_mismatch: "الكرت لا يبدأ بالبادئة المضبوطة",  // مفتاح prob_prefix_mismatch في الكائن = نص
    prob_suffix_mismatch: "الكرت لا ينتهي باللاحقة المضبوطة",  // مفتاح prob_suffix_mismatch في الكائن = نص
    prob_charset_mismatch: "الكرت فيه رموز ليست ضمن الأبجدية المختارة",  // مفتاح prob_charset_mismatch في الكائن = نص
    known_card_tried: "جرّبنا هذا الكرت بعدة أشكال للطلب، وكان رد الراوتر:",  // مفتاح known_card_tried في الكائن = نص
    known_card_hint: "→ HTTP 400/405/415/422 يعني أن الراوتر رفض شكل الطلب قبل فحص الكرت. راجع الطريقة والرابط والحقول المعروضة، وطابقها مع طلب المتصفح الناجح. أما HTTP 200 المشابه لصفحة الرفض فلا يثبت نجاحاً. عند ظهور حجب: أوقف المحاولات واطلب من مسؤول الشبكة مراجعة الوصول؛ لا تعاود الاتصال تلقائياً.",  // مفتاح known_card_hint في الكائن = نص
    s_eta: "الوقت المتبقي",  // مفتاح s_eta في الكائن = نص
    th_auto_slowed_router_complaining: "أبطأت تلقائياً: الراوتر بدأ يشتكي (أخطاء/تقييد)",  // مفتاح th_auto_slowed_router_complaining في الكائن = نص
    th_auto_sped_up: "أسرعت تلقائياً: الراوتر يستجيب بلا أخطاء",  // مفتاح th_auto_sped_up في الكائن = نص
    th_auto_sped_up_more_threads: "أسرعت تلقائياً: أضفت مسارات لأن الراوتر يستجيب بلا أخطاء",  // مفتاح th_auto_sped_up_more_threads في الكائن = نص
    lockout_apply: "طبّق الوتيرة الآمنة على الإعدادات",  // مفتاح lockout_apply في الكائن = نص
    lockout_applied: "تم ضبط المهلة والمسارات",  // مفتاح lockout_applied في الكائن = نص
    f_ua: "هوية المتصفح User-Agent",  // مفتاح f_ua في الكائن = نص
    f_ua_custom: "User-Agent مخصص",  // مفتاح f_ua_custom في الكائن = نص
    ua_default: "المتصفح الافتراضي (Chrome/Windows)",  // مفتاح ua_default في الكائن = نص
    ua_android: "أندرويد Chrome", ua_iphone: "آيفون Safari",  // مفتاح ua_android في الكائن = نص
    ua_custom: "اكتبها بنفسك…",  // مفتاح ua_custom في الكائن = نص
    ua_hint: "غيّرها فقط إذا كان الكرت يعمل في متصفح هاتفك لكن الراوتر يرفض شكل طلب الأداة.",  // مفتاح ua_hint في الكائن = نص
    f_referer: "إرسال ترويسات المتصفح (Referer/Origin)",  // مفتاح f_referer في الكائن = نص
    btn_lockout: "قِس حدّ الحظر",  // مفتاح btn_lockout في الكائن = نص
    lockout_measuring: "يجري فحص محدود (بحد أقصى ٨ طلبات) ويتوقف فور ظهور الحجب...",  // مفتاح lockout_measuring في الكائن = نص
    lockout_confirm: "هذا الفحص الاختياري يرسل حتى ٨ محاولات دخول خاطئة وقد يفعّل حجب الشبكة. هل تريد المتابعة؟ إذا كانت الشبكة تحجبك الآن، ألغِ الفحص واتصل بمسؤول الشبكة.",  // مفتاح lockout_confirm في الكائن = نص
    lockout_after: "الراوتر يحجب بعد",  // مفتاح lockout_after في الكائن = نص
    lockout_clears: "ويفكّ الحظر بعد",  // مفتاح lockout_clears في الكائن = نص
    lockout_never: "لم يظهر حجب ضمن الحد الآمن من المحاولات",  // مفتاح lockout_never في الكائن = نص
    lockout_stopped_after_block: "توقفت الأداة فور ظهور الحجب؛ لم تنتظر زواله ولم ترسل طلبات أخرى. أوقف المحاولات واطلب من مسؤول الشبكة مراجعة الوصول.",  // مفتاح lockout_stopped_after_block في الكائن = نص
    lockout_pace: "أسرع وتيرة آمنة: محاولة كل",  // مفتاح lockout_pace في الكائن = نص
    lockout_pace_hint: "ضع هذه المهلة في خانة «مهلة بين المحاولات» واستخدم خيطاً واحداً أو اثنين.",  // مفتاح lockout_pace_hint في الكائن = نص
    lockout_impossible: "على هذا الراوتر لا يمكن التخمين دون حظر متكرر: إما مهلة طويلة جداً، أو تعديل الإعداد من الراوتر نفسه.",  // مفتاح lockout_impossible في الكائن = نص
    seconds: "ثانية",  // مفتاح seconds في الكائن = نص
    attempt: "محاولة",  // مفتاح attempt في الكائن = نص
    netadvice_blocked_from_the_start: "الشبكة كانت تحجب هذا الجهاز قبل القياس. أوقف المحاولات واطلب من مسؤول الشبكة مراجعة الوصول وإعادة الخدمة.",  // مفتاح netadvice_blocked_from_the_start في الكائن = نص
    btn_diagnose: "تشخيص الشبكة أولاً",  // مفتاح btn_diagnose في الكائن = نص
    btn_clear_review: "مسح صفحات المراجعة",  // مفتاح btn_clear_review في الكائن = نص
    license_check: "أتعهّد بأنني أملك هذه الشبكة أو لدي إذن كتابي من صاحبها لاختبارها.",  // مفتاح license_check في الكائن = نص
    btn_start: "ابدأ التخمين", btn_stop: "إيقاف التخمين",  // مفتاح btn_start في الكائن = نص
    run_stop_hint: "أوقف التشغيل قبل تجربة بطاقة يدوياً على نفس الجهاز؛ الجلسات المتزامنة قد تؤثر على ردّ البوابة.",
    res_title: "4) النتائج الحيّة",  // مفتاح res_title في الكائن = نص
    s_speed: "السرعة", s_sent: "أُرسل", s_covered: "المغطى",  // مفتاح s_speed في الكائن = نص
    s_latency: "زمن الرد", s_delay: "التباطؤ الحالي", s_eta: "الوقت المتبقي", s_state: "الحالة",  // مفتاح s_latency في الكائن = نص
    t_card: "البطاقة", t_result: "النتيجة", t_why: "السبب", t_ms: "ms", t_len: "الحجم",  // مفتاح t_card في الكائن = نص
    btn_clear_log: "تفريغ السجل", btn_download: "تنزيل آخر تقرير",  // مفتاح btn_clear_log في الكائن = نص
    hits_title: "البطاقات المقبولة", hits_none: "لا شيء بعد.",  // مفتاح hits_title في الكائن = نص
    review_title: "ردود غير واضحة (تحتاج نظرة منك)",  // مفتاح review_title في الكائن = نص
    review_hint: "هذه ردود ليست مثل صفحة الرفض وليست نجاحاً مؤكداً. محفوظة لك لتفتحها وتقرأها بنفسك - الأداة لا تخمّن مكانك.",  // مفتاح review_hint في الكائن = نص
    review_none: "لا شيء بعد.",  // مفتاح review_none في الكائن = نص
    state_idle: "جاهز", state_calibrating: "جارٍ فحص البطاقة وتحديث خط أساس الرفض", state_running: "يعمل",  // مفتاح state_idle في الكائن = نص
    job_timeout: "انتهت مدة الانتظار - راجع السجل أسفل الشاشة",  // مفتاح job_timeout في الكائن = نص
    state_done: "انتهى", state_stopping: "يتوقف",  // مفتاح state_done في الكائن = نص
    preset_safe: "آمن (4 مسارات)", preset_normal: "عادي (12)",  // مفتاح preset_safe في الكائن = نص
    preset_fast: "سريع (40)", preset_custom: "مخصّص",  // مفتاح preset_fast في الكائن = نص
    cache_title: "الكاش ومسحه",  // مفتاح cache_title في الكائن = نص
    cache_hint: "الكاش = صفحات المراجعة + التقارير + السجلات. الملفات التعريفية منفصلة، و«مسح التقارير» يحذف أيضاً سجل البطاقات.",  // مفتاح cache_hint في الكائن = نص
    cache_temp: "مسح المؤقت وصفحات المراجعة",  // مفتاح cache_temp في الكائن = نص
    cache_results: "مسح التقارير والسجلات",  // مفتاح cache_results في الكائن = نص
    cache_profiles: "مسح الملفات التعريفية",  // مفتاح cache_profiles في الكائن = نص
    cache_all: "مسح كل شيء",  // مفتاح cache_all في الكائن = نص
    cache_freed: "تم المسح. حجم ما أُزيل:",  // مفتاح cache_freed في الكائن = نص
    license_title: "ترخيص الاستخدام",  // مفتاح license_title في الكائن = نص
    license_body: "١) الأداة للاختبار على شبكة تملكها أو لديك إذن كتابي من صاحبها.\n٢) لا تستخدمها للوصول غير المصرّح به أو لتخمين أكواد لا تملكها.\n٣) أنت المسؤول قانونياً عن أي استخدام غير مصرّح به.\n\nالملف AUTHORIZED_USE_LICENSE.md في المستودع هو الترخيص الكامل.",  // مفتاح license_body في الكائن = نص
    scan_ok: "الصفحة قُرئت", scan_fail: "تعذّر فتح الصفحة",  // مفتاح scan_ok في الكائن = نص
    internet_ONLINE: "متصل بالإنترنت فعلاً الآن",  // مفتاح internet_ONLINE في الكائن = نص
    internet_WALLED: "خلف بوابة الدخول (يحتاج بطاقة)",  // مفتاح internet_WALLED في الكائن = نص
    internet_OFFLINE: "لا يوجد اتصال بالشبكة",  // مفتاح internet_OFFLINE في الكائن = نص
    internet_BLOCKED: "محجوب من قِبل الشبكة",  // مفتاح internet_BLOCKED في الكائن = نص
    internet_detail_expected_answer: "الرابط الخارجي رد كما يجب",  // مفتاح internet_detail_expected_answer في الكائن = نص
    internet_detail_portal_redirect: "الشبكة حوّلت الطلب إلى صفحة الدخول",  // مفتاح internet_detail_portal_redirect في الكائن = نص
    internet_detail_portal_page: "الشبكة ردّت بصفحتها بدل الموقع",  // مفتاح internet_detail_portal_page في الكائن = نص
    detected: "ما اكتشفته الأداة", form_action: "رابط الإرسال",  // مفتاح detected في الكائن = نص
    form_method: "طريقة الإرسال", user_field: "حقل المستخدم",  // مفتاح form_method في الكائن = نص
    pass_field: "حقل كلمة المرور", extra_fields: "حقول ثابتة",  // مفتاح pass_field في الكائن = نص
    dst_values: "قيم dst الموجودة", chap_detected: "يستخدم تشفير MD5 الخاص بميكروتك",  // مفتاح dst_values في الكائن = نص
    chap_hint: "تم اكتشاف md5.js لذلك ستُستخدم صيغة chap تلقائياً.",  // مفتاح chap_hint في الكائن = نص
    no_form: "لم أجد نموذج دخول في الصفحة - جرّب رابط الصفحة نفسها التي تظهر للضيف.",  // مفتاح no_form في الكائن = نص
    running_now: "يعمل الآن", done_now: "انتهى",  // مفتاح running_now في الكائن = نص
    why_stopped: "لماذا توقف",  // مفتاح why_stopped في الكائن = نص
    advice: "ماذا أفعل الآن",  // مفتاح advice في الكائن = نص
    review_open: "افتح الصفحة المحفوظة",  // مفتاح review_open في الكائن = نص
    review_diff: "كلمات ظهرت في هذا الرد ولم تظهر في صفحة الرفض",  // مفتاح review_diff في الكائن = نص
    missing_words: "كلمات كانت في صفحة الرفض واختفت",  // مفتاح missing_words في الكائن = نص
    report_saved: "حُفظ التقرير",  // مفتاح report_saved في الكائن = نص
    download_calibration_report: "تنزيل تقرير المعايرة المنقّح",  // مفتاح download_calibration_report في الكائن = نص
    confirm_clear_all: "سيتم مسح كل شيء بما فيها الملفات التعريفية. متأكد؟",  // مفتاح confirm_clear_all في الكائن = نص
    confirm_profiles: "سيتم مسح الملفات التعريفية. متأكد؟",  // مفتاح confirm_profiles في الكائن = نص
    yes: "نعم", no: "إلغاء", close: "إغلاق",  // مفتاح yes في الكائن = نص
    loading: "جاري العمل...",  // مفتاح loading في الكائن = نص
    quit_tool: "إيقاف الأداة", confirm_quit: "سيتم إيقاف الأداة وإغلاق الصفحة. متأكد؟",  // مفتاح quit_tool في الكائن = نص
    quit_done: "تم إيقاف الأداة - يمكنك إغلاق هذه الصفحة.",  // مفتاح quit_done في الكائن = نص
    resume_from: "متابعة من",  // مفتاح resume_from في الكائن = نص
    server_gone_title: "الأداة توقفت",  // مفتاح server_gone_title في الكائن = نص
    server_gone: "انقطع الاتصال بالأداة. إذا كنت أوقفتها فهذا طبيعي - شغّلها من جديد لتكمل.",  // مفتاح server_gone في الكائن = نص
    /* why nothing was tried: the initial learning failed */
    cal_failed_title: "لم أبدأ التخمين: فشل التعلّم الأولي",  // مفتاح cal_failed_title في الكائن = نص
    cal_failed_hint: "لم تُجرَ أي محاولة لأن الأداة لم تستطع تعلّم شكل صفحة الرفض. هذا ما فعله الراوتر:",  // مفتاح cal_failed_hint في الكائن = نص
    no_attempt_was_made: "لم يبدأ تخمين نطاق البطاقات؛ طلبات المعايرة (إن وجدت) ظاهرة أعلاه.",  // مفتاح no_attempt_was_made في الكائن = نص
    netadvice_refused: "تأكد أنك متصل بشبكة هذا الراوتر وأن الرابط صحيح (البورت مقفل أو الحماية رفضت جهازك).",  // مفتاح netadvice_refused في الكائن = نص
    netadvice_dns: "اسم العنوان لم يُترجم: اكتب IP الراوتر بدل الاسم (مثل 10.5.50.1).",  // مفتاح netadvice_dns في الكائن = نص
    netadvice_no_session: "صفحة الدخول لم تعطِ جلسة: تأكد من الرابط، ثم اختر هوية نفس متصفح هاتفك وأعد الفحص. لم تُحسب البطاقات كمجرّبة.",  // مفتاح netadvice_no_session في الكائن = نص
    netadvice_connect_timeout: "لا يوجد رد عند فتح الاتصال: الراوتر بعيد أو مزدحم، أو لست متصلاً بشبكته.",  // مفتاح netadvice_connect_timeout في الكائن = نص
    netadvice_read_timeout: "الراوتر فتح الاتصال ولم يرد: انتظر قليلاً وقلّل عدد المسارات.",  // مفتاح netadvice_read_timeout في الكائن = نص
    netadvice_reset: "الراوتر قطع الاتصال فجأة: أعد الاتصال بالشبكة ثم أعد المحاولة.",  // مفتاح netadvice_reset في الكائن = نص
    netadvice_stale: "اتصال قديم أُغلق من الراوتر: أعد المحاولة.",  // مفتاح netadvice_stale في الكائن = نص
    netadvice_tls: "خطأ في شهادة TLS: جرّب http:// بدل https://",  // مفتاح netadvice_tls في الكائن = نص
    netadvice_unreachable: "لست متصلاً بهذه الشبكة: اتصل بواي فاي الراوتر أولاً.",  // مفتاح netadvice_unreachable في الكائن = نص
    netadvice_bad_response: "رد غير مفهوم من الراوتر: جرّب رابط صفحة الدخول الذي يظهر للضيف فعلاً.",  // مفتاح netadvice_bad_response في الكائن = نص
    netadvice_too_many_redirects: "الراوتر يحوّل الطلب بلا نهاية: انسخ الرابط النهائي من المتصفح.",  // مفتاح netadvice_too_many_redirects في الكائن = نص
    netadvice_proto: "الرابط غير مدعوم: يجب أن يبدأ بـ http:// أو https://",  // مفتاح netadvice_proto في الكائن = نص
    netadvice_unknown: "خطأ غير متوقع: أعد المحاولة، وإن تكرر شغّل «تشخيص الشبكة أولاً».",  // مفتاح netadvice_unknown في الكائن = نص
    netadvice_blocked_already: "الشبكة تحجب هذا الجهاز. أوقف المحاولات واطلب من مسؤول الشبكة/الراوتر مراجعة الحجب وإعادة الخدمة.",  // مفتاح netadvice_blocked_already في الكائن = نص
    netadvice_blocked_before_probes: "ظهر الحجب قبل أي بطاقة تجربة. لا تحاول تجاوزه؛ اطلب من مسؤول الشبكة/الراوتر مراجعة الوصول وإعادة الخدمة.",  // مفتاح netadvice_blocked_before_probes في الكائن = نص
    netadvice_blocked_by_our_probes: "ظهر رد حجب أثناء المعايرة، فتوقفت الأداة دون إعادة المحاولة. أوقف المحاولات واطلب من مسؤول الشبكة/الراوتر مراجعة الوصول وإعادة الخدمة.",  // مفتاح netadvice_blocked_by_our_probes في الكائن = نص
    netadvice_no_rejection_baseline: "لم يصل أي رد على بطاقات التجربة: تحقق من الاتصال بالشبكة.",  // مفتاح netadvice_no_rejection_baseline في الكائن = نص
    netadvice_card_space_empty: "صيغة البطاقة لا تترك شيئاً للتخمين: البادئة + اللاحقة أطول من طول الكرت، أو المحارف المتغيّرة قليلة جداً.",  // مفتاح netadvice_card_space_empty في الكائن = نص
    netadvice_calibration_failed: "أصلح السبب أعلاه، ثم اضغط «ابدأ التخمين» من جديد.",  // مفتاح netadvice_calibration_failed في الكائن = نص
    block_but_form_present: "لكن الصفحة ما زال فيها نموذج الدخول",  // مفتاح block_but_form_present في الكائن = نص
    probe_cards: "بطاقات تجربة",  // مفتاح probe_cards في الكائن = نص
    http_ok_word_ignored: "الصفحة ترد سليم وفيها كلمة حجب، لكن ما زال فيها نموذج الدخول فاعتبرناها صفحة دخول",  // مفتاح http_ok_word_ignored في الكائن = نص
    internet_opened_title: "الإنترنت فتح أثناء التشغيل - أحد هذه الكروت هو الصحيح",  // مفتاح internet_opened_title في الكائن = نص
    internet_opened_hint: "الراوتر أدخلك ولم يرد برد نجاح واضح، فلم نستطع تسمية الكرت من الرد وحده. أوقف الجلسة ثم جرّب هذه الكروت واحداً واحداً في صفحة الدخول - أحدها هو الذي فتح الشبكة. الأحدث في الآخر.",  // مفتاح internet_opened_hint في الكائن = نص
    stop_internet_opened: "توقف لأن الإنترنت فتح أثناء التشغيل: أحد آخر الكروت المجربة هو الصحيح.",  // مفتاح stop_internet_opened في الكائن = نص
    retry_now: "↻ أعد المحاولة الآن",  // مفتاح retry_now في الكائن = نص
    /* verdicts */
    v_ACCEPTED_VERIFIED: "مقبولة ومؤكدة",  // مفتاح v_ACCEPTED_VERIFIED في الكائن = نص
    v_ACCEPTED: "مقبولة",  // مفتاح v_ACCEPTED في الكائن = نص
    v_ACCEPTED_UNVERIFIED: "قبلها الراوتر (تأكيد الإنترنت فشل)",  // مفتاح v_ACCEPTED_UNVERIFIED في الكائن = نص
    v_REJECTED: "مرفوضة",  // مفتاح v_REJECTED في الكائن = نص
    v_UNKNOWN: "رد غير واضح",  // مفتاح v_UNKNOWN في الكائن = نص
    v_BANNED: "محظور من الراوتر",  // مفتاح v_BANNED في الكائن = نص
    v_RATE_LIMITED: "الشبكة تبطّئك/تحدّ من الطلبات",  // مفتاح v_RATE_LIMITED في الكائن = نص
    v_CHALLENGE: "ظهر اختبار كابتشا",  // مفتاح v_CHALLENGE في الكائن = نص
    v_NET_ERROR: "خطأ في الاتصال",  // مفتاح v_NET_ERROR في الكائن = نص
    v_INTERNAL_ERROR: "خلل داخلي بالأداة (يُبلَّغ عنه)",  // مفتاح v_INTERNAL_ERROR في الكائن = نص
    /* reasons */
    r_same_as_rejection_page_exact: "رد مطابق لصفحة الرفض",  // مفتاح r_same_as_rejection_page_exact في الكائن = نص
    r_same_as_rejection_page_shape: "نفس صفحة الرفض (مع اختلاف الرموز المؤقتة)",  // مفتاح r_same_as_rejection_page_shape في الكائن = نص
    r_same_as_rejection_page_similar: "يشبه صفحة الرفض بشدة",  // مفتاح r_same_as_rejection_page_similar في الكائن = نص
    r_same_as_rejection_page_empty: "رد فارغ مثل صفحة الرفض",  // مفتاح r_same_as_rejection_page_empty في الكائن = نص
    r_same_as_rejection_page_redirect: "نفس تحويل صفحة الرفض (نفس المكان)",  // مفتاح r_same_as_rejection_page_redirect في الكائن = نص
    r_redirect_differs_from_rejection: "الراوتر حوّل هذه البطاقة إلى مكان غير مكان البطاقات المرفوضة",  // مفتاح r_redirect_differs_from_rejection في الكائن = نص
    r_ban_page: "ظهرت صفحة حجب صريحة من الراوتر",  // مفتاح r_ban_page في الكائن = نص
    r_http_403: "الراوتر يرفض الطلب (403)",  // مفتاح r_http_403 في الكائن = نص
    r_http_429: "طلبات كثيرة جداً (429) - تهدئة مطلوبة",  // مفتاح r_http_429 في الكائن = نص
    r_captcha_present: "الصفحة فيها كابتشا - التخمين لم يعد مجدياً",  // مفتاح r_captcha_present في الكائن = نص
    r_redirect_out_of_portal_and_online: "الراوتر أعطى إنترنت فعلياً لهذه البطاقة",  // مفتاح r_redirect_out_of_portal_and_online في الكائن = نص
    r_accepted_internet_already_open: "قبلها الراوتر (لم أستطع إثبات الإنترنت لأن جهازك كان متصلاً أصلاً)",  // مفتاح r_accepted_internet_already_open في الكائن = نص
    internet_online_verification_limited: "جهازك متصل بالإنترنت مسبقاً - سأعتمد على تحويل الراوتر وصفحة الحالة",  // مفتاح internet_online_verification_limited في الكائن = نص
    r_redirect_out_of_portal: "الراوتر حوّل المتصفح خارج البوابة",  // مفتاح r_redirect_out_of_portal في الكائن = نص
    r_redirect_to_another_portal_page: "التحويل كان إلى صفحة داخل البوابة نفسها - ليس خروجاً",  // مفتاح r_redirect_to_another_portal_page في الكائن = نص
    r_http_503: "الراوتر أو خدمة RADIUS مشغولة/غير متاحة (503) - أبطأت الطلبات",  // مفتاح r_http_503 في الكائن = نص
    r_success_url_contains: "عنوان النجاح المتوقع ظهر في الرد",  // مفتاح r_success_url_contains في الكائن = نص
    r_learned_success_words: "ظهرت كلمات النجاح التي تعلّمتها الأداة",  // مفتاح r_learned_success_words في الكائن = نص
    r_welcome_words: "كلمات ترحيب لا تظهر في صفحة الرفض",  // مفتاح r_welcome_words في الكائن = نص
    r_rejection_wording: "نص الرفض موجود في الصفحة",  // مفتاح r_rejection_wording في الكائن = نص
    r_reply_differs_not_proven: "الرد مختلف لكن لا دليل على القبول - احفظته للمراجعة",  // مفتاح r_reply_differs_not_proven في الكائن = نص
    r_looks_rejected_but_success_words_found: "الرد يشبه الرفض لكن فيه كلمات نجاح تعلّمتها - يحتاج نظرة منك",  // مفتاح r_looks_rejected_but_success_words_found في الكائن = نص
    r_redirect_out_of_portal_but_page_matches: "الراوتر حوّلنا لجهة أخرى لكن الصفحة تشبه الرفض - لا نسمّيها رفضاً، محفوظة للمراجعة",  // مفتاح r_redirect_out_of_portal_but_page_matches في الكائن = نص
    /* network error kinds */
    net_dns: "اسم العنوان لم يُترجم (DNS)",  // مفتاح net_dns في الكائن = نص
    net_refused: "الراوتر رفض الاتصال (البورت مقفول أو الحماية منعتك)",  // مفتاح net_refused في الكائن = نص
    net_connect_timeout: "لا يوجد رد عند فتح الاتصال",  // مفتاح net_connect_timeout في الكائن = نص
    net_read_timeout: "الاتصال نجح لكن الرد تأخر (راوتر مشغول أو RADIUS بطيء)",  // مفتاح net_read_timeout في الكائن = نص
    net_reset: "الراوتر قطع الاتصال فجأة",  // مفتاح net_reset في الكائن = نص
    net_stale: "اتصال قديم أُغلق من الراوتر (أُعيد تلقائياً)",  // مفتاح net_stale في الكائن = نص
    net_tls: "خطأ في شهادة TLS",  // مفتاح net_tls في الكائن = نص
    net_unreachable: "الشبكة غير قابلة للوصول (لست متصلاً بها)",  // مفتاح net_unreachable في الكائن = نص
    net_bad_response: "رد غير مفهوم من الراوتر",  // مفتاح net_bad_response في الكائن = نص
    net_too_many_redirects: "دوران لا نهائي في التحويل",  // مفتاح net_too_many_redirects في الكائن = نص
    net_proto: "رابط غير مدعوم",  // مفتاح net_proto في الكائن = نص
    net_unknown: "خطأ غير متوقع",  // مفتاح net_unknown في الكائن = نص
    net_no_session: "لم نستطع أخذ جلسة من صفحة الدخول - لم يُجرَّب الكرت",  // مفتاح net_no_session في الكائن = نص
    /* stop reasons */
    stop_found_verified: "وجدت بطاقة تعمل وتحقّقت من الإنترنت فعلياً.",  // مفتاح stop_found_verified في الكائن = نص
    stop_found_strong_evidence: "ظهرت بطاقة بدليل قوي (تحويل خارج البوابة) وتوقفت.",  // مفتاح stop_found_strong_evidence في الكائن = نص
    stop_user_stop: "أوقفت التشغيل بنفسك.",  // مفتاح stop_user_stop في الكائن = نص
    stop_banned_by_router: "الراوتر حجب الطلبات. أوقف المحاولات واطلب من مسؤول الشبكة مراجعة الوصول وإعادة الخدمة.",  // مفتاح stop_banned_by_router في الكائن = نص
    stop_rate_limited_by_router: "الشبكة حدّت من الطلبات (429). أوقفت الأداة المحاولات؛ اطلب من مسؤول الشبكة مراجعة الوصول قبل المتابعة.",  // مفتاح stop_rate_limited_by_router في الكائن = نص
    stop_target_unreachable: "توقفت بعد تكرر فشل الاتصال؛ قد يكون انقطاعاً أو حظراً ولا يمكن تمييزهما من التقرير. أوقفت الطلبات ولم أعد الاتصال تلقائياً. راجع مسؤول الشبكة قبل المحاولة.",  // مفتاح stop_target_unreachable في الكائن = نص
    manual_resume_title: "يلزم تأكيد المشرف قبل الاستئناف",  // مفتاح manual_resume_title في الكائن = نص
    manual_resume_hint: "لا تستأنف بعد حظر أو انقطاع إلا بعد مراجعة مسؤول الشبكة وتأكيده أن المتابعة مسموحة.",  // مفتاح manual_resume_hint في الكائن = نص
    manual_resume_ack: "راجعت مسؤول الشبكة وأكد أن الشبكة جاهزة وأن الاستئناف مسموح",  // مفتاح manual_resume_ack في الكائن = نص
    why_title: "لماذا انتهت كل محاولة بهذه النتيجة؟",  // مفتاح why_title في الكائن = نص
    stop_attempts_done: "انتهى عدد المحاولات المطلوب. شغّل مرة أخرى - ستكمل من حيث توقفت.",  // مفتاح stop_attempts_done في الكائن = نص
    stop_space_done: "غطّيت كل الاحتمالات في هذا النطاق.",  // مفتاح stop_space_done في الكائن = نص
    stop_calibration_failed: "لم أبدأ التخمين لأن التعلّم الأولي فشل - السبب مكتوب بالأسفل.",  // مفتاح stop_calibration_failed في الكائن = نص
    stop_engine_error: "خطأ داخلي - التفاصيل في السجل.",  // مفتاح stop_engine_error في الكائن = نص
    stop_captcha_challenge: "ظهرت كابتشا، والتخمين بعدها بلا فائدة.",  // مفتاح stop_captcha_challenge في الكائن = نص
    stop_found_unverified: "قبل الراوتر البطاقة لكن لم أستطع تأكيد الإنترنت.",  // مفتاح stop_found_unverified في الكائن = نص
    /* throttle */
    th_rate_limited_slowing_down: "أوقفت الطلبات بعد رد تحديد المعدل (429)",  // مفتاح th_rate_limited_slowing_down في الكائن = نص
    th_ban_page_slowing_down: "أوقفت الطلبات بعد ظهور صفحة حجب",  // مفتاح th_ban_page_slowing_down في الكائن = نص
    th_connections_refused_slowing_down: "أبطأت الطلبات لأن الراوتر يرفض الاتصالات",  // مفتاح th_connections_refused_slowing_down في الكائن = نص
    th_network_errors_slowing_down: "أبطأت الطلبات بسبب أخطاء شبكة متكررة",  // مفتاح th_network_errors_slowing_down في الكائن = نص
    th_recovering_speed: "الشبكة هدأت - أعيد رفع السرعة تدريجياً",  // مفتاح th_recovering_speed في الكائن = نص
    /* calibration + diagnostics */
    cal_blocked_already: "الراوتر يرفض الطلبات بسبب حجب نشط (توقفت الأداة دون إعادة المحاولة)",  // مفتاح cal_blocked_already في الكائن = نص
    cal_blocked_before_probes: "صفحة الحجب ظهرت قبل أن نجرّب أي بطاقة: الراوتر حاجب هذا الجهاز من قبل",  // مفتاح cal_blocked_before_probes في الكائن = نص
    cal_blocked_by_our_probes: "ظهر رد حجب أثناء المعايرة فتوقفت الأداة دون انتظار أو إعادة محاولة",  // مفتاح cal_blocked_by_our_probes في الكائن = نص
    cal_captcha_challenge: "ظهرت كابتشا أو خطوة تحقق؛ توقفت الأداة ولن تتابع الطلبات",  // مفتاح cal_captcha_challenge في الكائن = نص
    cal_card_space_empty: "صيغة البطاقة لا تترك شيئاً للتخمين",  // مفتاح cal_card_space_empty في الكائن = نص
    cal_no_rejection_baseline: "لم يصل أي رد من الراوتر على بطاقات التجربة",  // مفتاح cal_no_rejection_baseline في الكائن = نص
    cal_request_shape_rejected: "الراوتر رفض شكل الطلب قبل أن يفحص الكرت (HTTP 400/405/415/422). الأداة أخذت الكوكي والرمز المخفي؛ جرّب هوية نفس متصفحك، وإن استمر فالصفحة تنفّذ JavaScript خاصاً يحتاج تسجيل الطلب الناجح.",  // مفتاح cal_request_shape_rejected في الكائن = نص
    cal_reach_login_page: "الوصول إلى صفحة الدخول",  // مفتاح cal_reach_login_page في الكائن = نص
    cal_internet_state: "حالة الإنترنت قبل أي محاولة",  // مفتاح cal_internet_state في الكائن = نص
    cal_rejection_baseline: "تعلّم شكل صفحة الرفض",  // مفتاح cal_rejection_baseline في الكائن = نص
    cal_rejection_probe: "إرسال بطاقات تجريبية",  // مفتاح cal_rejection_probe في الكائن = نص
    cal_probe_looked_accepted: "بطاقة تجريبية بدت مقبولة",  // مفتاح cal_probe_looked_accepted في الكائن = نص
    cal_shape_tuned: "ضبط شكل الطلب باستخدام البطاقة المعروفة",  // مفتاح cal_shape_tuned في الكائن = نص
    cal_http_ok: "الصفحة ردت بشكل سليم",  // مفتاح cal_http_ok في الكائن = نص
    cal_learned: "تم التعلّم بنجاح",  // مفتاح cal_learned في الكائن = نص
    cal_known_card_works: "البطاقة المعروفة تعمل مع هذا الشكل",  // مفتاح cal_known_card_works في الكائن = نص
    cal_known_card_not_proven: "لم أستطع إثبات أن البطاقة المعروفة تعمل بهذه الإعدادات",  // مفتاح cal_known_card_not_proven في الكائن = نص
    cal_logout_unconfirmed: "لم أستطع تأكيد تسجيل الخروج؛ أوقفت أي محاولات أخرى",  // مفتاح cal_logout_unconfirmed في الكائن = نص
    cal_browser_trace: "افتح F12 في المتصفح وانسخ بيانات نموذج الدخول وأرسلها لي",  // مفتاح cal_browser_trace في الكائن = نص
    dyn_tokens: "رموز متغيّرة تم تجاهلها", exact_mode: "مقارنة دقيقة جاهزة",  // مفتاح dyn_tokens في الكائن = نص
    shape_mode: "مقارنة بالشكل (الصفحة تتغير وحدها)",  // مفتاح shape_mode في الكائن = نص
    diag_reach: "الوصول للراوتر", diag_internet: "حالة الإنترنت",  // مفتاح diag_reach في الكائن = نص
    diag_sample_single: "قياس بمسار واحد", diag_sample_parallel: "قياس بعدة مسارات",  // مفتاح diag_sample_single في الكائن = نص
    diag_ban_check: "فحص الحجب",  // مفتاح diag_ban_check في الكائن = نص
    diag_ok: "سليم", diag_errors_present: "توجد أخطاء", diag_errors_rising: "الأخطاء تزيد مع السرعة",  // مفتاح diag_ok في الكائن = نص
    diag_no_ban_seen: "لا يوجد حجب", diag_ban_page_seen: "ظهرت صفحة حجب",  // مفتاح diag_no_ban_seen في الكائن = نص
    advice_blocked_already: "الشبكة تحجب هذا الجهاز. أوقف المحاولات واطلب من مسؤول الشبكة مراجعة الوصول وإعادة الخدمة.",  // مفتاح advice_blocked_already في الكائن = نص
    advice_router_pressure: "الأخطاء سببها ضغط على الراوتر: قلّل عدد المسارات.",  // مفتاح advice_router_pressure في الكائن = نص
    advice_slow_router: "الراوتر بطيء في الرد: استخدم مسارات أقل وانتظاراً أطول.",  // مفتاح advice_slow_router في الكائن = نص
    advice_already_online_no_captive_portal: "أنت متصل بالإنترنت فعلاً - تأكد أنك على شبكة الضيف الصحيحة.",  // مفتاح advice_already_online_no_captive_portal في الكائن = نص
    suggest_threads: "المسارات المقترحة",  // مفتاح suggest_threads في الكائن = نص
    /* profile problems */
    prob_url_missing_or_invalid: "رابط صفحة الدخول غير صالح",  // مفتاح prob_url_missing_or_invalid في الكائن = نص
    prob_user_field_missing: "اسم حقل المستخدم مفقود",  // مفتاح prob_user_field_missing في الكائن = نص
    prob_length_not_bigger_than_prefix_and_suffix: "البادئة + اللاحقة أطول من طول الكرت",  // مفتاح prob_length_not_bigger_than_prefix_and_suffix في الكائن = نص
    prob_charset_too_small: "المحارف المتغيّرة قليلة جداً",  // مفتاح prob_charset_too_small في الكائن = نص
    prob_unknown_pass_mode: "طريقة كلمة المرور غير معروفة",  // مفتاح prob_unknown_pass_mode في الكائن = نص
    prob_fixed_password_empty: "كلمة المرور الثابتة فارغة",  // مفتاح prob_fixed_password_empty في الكائن = نص
    prob_needs_browser_js: "تحويل كلمة المرور في هذه البوابة يحتاج متصفحاً ولا يمكن تشغيله آلياً",  // مفتاح prob_needs_browser_js في الكائن = نص
    prob_space_is_astronomically_big: "عدد الاحتمالات ضخم جداً - استخدم طولاً أقل أو مسارات أكثر",  // مفتاح prob_space_is_astronomically_big في الكائن = نص
    /* pass modes */
    pm_same: "نفس البطاقة", pm_empty: "فارغة", pm_omit: "بدون إرسال الحقل",  // مفتاح pm_same في الكائن = نص
    pm_fixed: "قيمة ثابتة", pm_chap: "MD5 تشفير ميكروتك (chap) للبطاقة",  // مفتاح pm_fixed في الكائن = نص
    pm_chap_empty: "chap على قيمة فارغة",  // مفتاح pm_chap_empty في الكائن = نص
    pm_md5user: "MD5 للبطاقة فقط",  // مفتاح pm_md5user في الكائن = نص
    pm_sha1user: "SHA1 للبطاقة فقط",  // مفتاح pm_sha1user في الكائن = نص
    pm_sha256user: "SHA256 للبطاقة فقط",  // مفتاح pm_sha256user في الكائن = نص
    /* charsets */
    cs_digits: "أرقام فقط", cs_lower: "حروف صغيرة", cs_upper: "حروف كبيرة",  // مفتاح cs_digits في الكائن = نص
    cs_alnum: "أرقام وحروف صغيرة", cs_alnum_upper: "أرقام وحروف كبيرة",  // مفتاح cs_alnum في الكائن = نص
    cs_hex: "سداسي عشري صغير", cs_hex_upper: "سداسي عشري كبير",  // مفتاح cs_hex في الكائن = نص
  },  // إغلاق الكتلة السابقة
  en: {  // مفتاح en في الكائن = كائن
    step_start: "Start",  // مفتاح step_start في الكائن = نص
    step_scan: "Scan", step_format: "Card format", step_run: "Run", step_results: "Results",  // مفتاح step_scan في الكائن = نص
    start_title: "KiraPass — Start",  // مفتاح start_title في الكائن = نص
    start_hint: "Choose your workflow. No scan or guessing starts automatically before your explicit confirmation.",  // مفتاح start_hint في الكائن = نص
    btn_new_profile: "New profile",  // مفتاح btn_new_profile في الكائن = نص
    btn_saved_profile: "Use saved profile",  // مفتاح btn_saved_profile في الكائن = نص
    saved_title: "Saved profiles",  // مفتاح saved_title في الكائن = نص
    saved_hint: "Pick a profile to review its settings before running. No automatic scan or guessing will start.",  // مفتاح saved_hint في الكائن = نص
    back_to_start: "Back to start",  // مفتاح back_to_start في الكائن = نص
    back_to_saved: "Back to list",  // مفتاح back_to_saved في الكائن = نص
    back_to_scan: "Back to scan",  // مفتاح back_to_scan في الكائن = نص
    back_to_format: "Back to format",  // مفتاح back_to_format في الكائن = نص
    review_profile_title: "Profile review",  // مفتاح review_profile_title في الكائن = نص
    review_profile_hint: "Review saved settings before running. If complete you can start directly; if incomplete fix it manually without automatic requests.",  // مفتاح review_profile_hint في الكائن = نص
    edit_settings: "Edit settings",  // مفتاح edit_settings في الكائن = نص
    btn_start_from_review: "Start guessing",  // مفتاح btn_start_from_review في الكائن = نص
    no_saved_profiles: "No saved profiles yet. Create a new profile first.",  // مفتاح no_saved_profiles في الكائن = نص
    saved_profile_count: "Saved profiles count",  // مفتاح saved_profile_count في الكائن = نص
    profile_summary: "Profile summary",  // مفتاح profile_summary في الكائن = نص
    profile_invalid: "Profile incomplete",  // مفتاح profile_invalid في الكائن = نص
    profile_invalid_hint: "Some required settings are missing or invalid. Fix them manually before running; no values will be guessed and no automatic requests will be sent.",  // مفتاح profile_invalid_hint في الكائن = نص
    profile_valid: "Profile complete and ready to run",  // مفتاح profile_valid في الكائن = نص
    probe_link_title: "Check router connectivity",  // مفتاح probe_link_title في الكائن = نص
    probe_link_hint: "A single GET to the URL — shows the result with no guessing and no card posts.",  // مفتاح probe_link_hint في الكائن = نص
    probe_link_button: "Check link",  // مفتاح probe_link_button في الكائن = نص
    probe_reachable: "URL is reachable",  // مفتاح probe_reachable في الكائن = نص
    probe_unreachable: "URL could not be reached",  // مفتاح probe_unreachable في الكائن = نص
    probe_has_form: "login form is present",  // مفتاح probe_has_form في الكائن = نص
    probe_no_form: "no clear login form",  // مفتاح probe_no_form في الكائن = نص
    saved_search: "Search profiles",  // مفتاح saved_search في الكائن = نص
    saved_search_ph: "Search by name or URL…",  // مفتاح saved_search_ph في الكائن = نص
    btn_export_profile: "Export JSON",  // مفتاح btn_export_profile في الكائن = نص
    btn_import_profile: "Import JSON",  // مفتاح btn_import_profile في الكائن = نص
    import_ok: "Profile imported",  // مفتاح import_ok في الكائن = نص
    import_fail: "Import failed",  // مفتاح import_fail في الكائن = نص
    export_ok: "Profile downloaded",  // مفتاح export_ok في الكائن = نص
    lan_warning_title: "Warning: UI is open on the LAN",  // مفتاح lan_warning_title في الكائن = نص
    lan_warning_body: "The access token is sent without TLS (plain HTTP). Use only on a network you trust; prefer 127.0.0.1 when possible.",  // مفتاح lan_warning_body في الكائن = نص
    f_internet_check: "Custom internet-check URL",  // مفتاح f_internet_check في الكائن = نص
    f_internet_check_hint: "Used instead of Google/Microsoft/Apple when the network blocks them. Format: url|status|optional text",  // مفتاح f_internet_check_hint في الكائن = نص
    f_connect_timeout: "Connect timeout (seconds)",  // مفتاح f_connect_timeout في الكائن = نص
    f_connect_timeout_hint: "Raise this for slow RADIUS routers. The value is stored locally.",  // مفتاح f_connect_timeout_hint في الكائن = نص
    f_read_timeout: "Read timeout (seconds)",  // مفتاح f_read_timeout في الكائن = نص
    btn_save_net_settings: "Save network settings",  // مفتاح btn_save_net_settings في الكائن = نص
    adv_run_open: "Advanced run & network options",  // مفتاح adv_run_open في الكائن = نص
    net_settings_saved: "Network settings saved",  // مفتاح net_settings_saved في الكائن = نص
    warn_fast_preset: "The fast preset can lock your device out quickly. Confirm with the network admin before continuing. Are you sure?",  // مفتاح warn_fast_preset في الكائن = نص
    warn_big_space: "The combination space is huge — it may take a long time and put pressure on the router.",  // مفتاح warn_big_space في الكائن = نص
    warn_many_threads: "Thread count is high and may trigger a quick lockout. Lower it if you can.",  // مفتاح warn_many_threads في الكائن = نص
    online_already_banner: "Your device is already online — card verification is limited and relies on the portal redirect and status page.",  // مفتاح online_already_banner في الكائن = نص
    ban_evidence_label: "Block evidence for the admin",  // مفتاح ban_evidence_label في الكائن = نص
    ban_evidence_status: "HTTP status",  // مفتاح ban_evidence_status في الكائن = نص
    ban_evidence_word: "Matched phrase",  // مفتاح ban_evidence_word في الكائن = نص
    ban_evidence_form: "Login form still visible",  // مفتاح ban_evidence_form في الكائن = نص
    ban_evidence_kind: "Soft classification",  // مفتاح ban_evidence_kind في الكائن = نص
    capture_guide_link: "Manual recorder guide",  // مفتاح capture_guide_link في الكائن = نص
    capture_curl_label: "Redacted curl command (no secrets)",  // مفتاح capture_curl_label في الكائن = نص
    target_unreachable_doc: "target_unreachable means an outage or an admin block that cannot be told apart automatically — ask the admin to review before any resume.",  // مفتاح target_unreachable_doc في الكائن = نص
    manual_resume_button: "Manual resume after admin review",  // مفتاح manual_resume_button في الكائن = نص
    manual_resume_confirm_title: "Confirm manual resume",  // مفتاح manual_resume_confirm_title في الكائن = نص
    manual_resume_confirm_body: "The run will resume with saved settings and progress. Make sure the administrator reviewed the state and resume is allowed. No IP or MAC change and no Wi-Fi disconnect will happen.",  // مفتاح manual_resume_confirm_body في الكائن = نص
    btn_continue: "Continue",  // مفتاح btn_continue في الكائن = نص
    btn_cancel: "Cancel",  // مفتاح btn_cancel في الكائن = نص
    resume_report: "Manual resume after stop",  // مفتاح resume_report في الكائن = نص
    skip_content: "Skip to content",  // مفتاح skip_content في الكائن = نص
    brand_subtitle: "Authorized network testing",  // مفتاح brand_subtitle في الكائن = نص
    license_link: "License",  // مفتاح license_link في الكائن = نص
    progress_label: "Run progress",  // مفتاح progress_label في الكائن = نص
    language_label: "Change language",  // مفتاح language_label في الكائن = نص
    steps_label: "Workflow steps",  // مفتاح steps_label في الكائن = نص
    banner_title: "Authorized use only",  // مفتاح banner_title في الكائن = نص
    banner_text: "Use this tool only on a network you own or have written permission to test. Never test someone else's network.",  // مفتاح banner_text في الكائن = نص
    banner_more: "Details",  // مفتاح banner_more في الكائن = نص
    scan_title: "1) Check the network and test the known card",  // مفتاح scan_title في الكائن = نص
    scan_hint: "Paste the hotspot login URL as it opens in your browser. After scanning, enter an authorized card you know works and test it here. You cannot continue to card-format settings until the test confirms internet access and logout.",  // مفتاح scan_hint في الكائن = نص
    scan_button: "Scan now", scan_url_label: "Login page URL",  // مفتاح scan_button في الكائن = نص
    calibration_setup_title: "Test the known card and learn the request",  // مفتاح calibration_setup_title في الكائن = نص
    calibration_setup_hint: "Enter an authorized card you know works. Card-format settings stay locked until the test confirms internet access and a successful logout.",  // مفتاح calibration_setup_hint في الكائن = نص
    calibration_required: "Calibration is required first",  // مفتاح calibration_required في الكائن = نص
    calibration_required_hint: "Return to Network Check, enter an authorized working card, and run the test. Its proven request settings will be applied on the next page.",  // مفتاح calibration_required_hint في الكائن = نص
    calibration_shape_changed: "The request shape changed after calibration",  // مفتاح calibration_shape_changed في الكائن = نص
    calibration_shape_changed_hint: "The run will not start with untested request settings. Return to Network Check and calibrate again after reviewing the request settings.",  // مفتاح calibration_shape_changed_hint في الكائن = نص
    calibration_applied: "Test passed; request settings applied",  // مفتاح calibration_applied في الكائن = نص
    known_card_format_mismatch: "The card format on Step 2 does not match the tested card. Correct its length, prefix, and character set before running.",  // مفتاح known_card_format_mismatch في الكائن = نص
    attempt_table: "Run attempt log", next_format: "Next: card format →", next_run: "Next: run →",  // مفتاح attempt_table في الكائن = نص
    format_title: "2) Card format",  // مفتاح format_title في الكائن = نص
    format_hint: "Describe the card with its fixed prefix and full length. The login request shown below was learned and tested in the previous step; changing advanced request settings requires another successful test before running.",  // مفتاح format_hint في الكائن = نص
    f_prefix: "Fixed prefix", f_length: "Full card length",  // مفتاح f_prefix في الكائن = نص
    saved_profiles: "Saved profile", prof_new: "- new -",  // مفتاح saved_profiles في الكائن = نص
    btn_delete_profile: "Delete this profile",  // مفتاح btn_delete_profile في الكائن = نص
    f_charset: "Variable characters", f_custom: "Custom characters",  // مفتاح f_charset في الكائن = نص
    f_pass_mode: "Password value", f_dst: "dst value (guest destination)",  // مفتاح f_pass_mode في الكائن = نص
    f_name: "Profile name",  // مفتاح f_name في الكائن = نص
    f_method: "Request method", method_post: "POST (widest support)", method_get: "GET",  // مفتاح f_method في الكائن = نص
    f_user_field: "Username field",  // مفتاح f_user_field في الكائن = نص
    f_pass_field: "Password field", f_login_url: "Form action URL",  // مفتاح f_pass_field في الكائن = نص
    f_send_dst: "Send the dst field",  // مفتاح f_send_dst في الكائن = نص
    f_send_popup: "Send the popup field",  // مفتاح f_send_popup في الكائن = نص
    f_extra: "Extra fixed fields (name=value)",  // مفتاح f_extra في الكائن = نص
    f_words: "Success words (optional)",  // مفتاح f_words في الكائن = نص
    f_words_clear: "Clear",  // مفتاح f_words_clear في الكائن = نص
    f_words_hint: "Only visible page text is matched. Clear these if they came from an old or incorrect capture.",  // مفتاح f_words_hint في الكائن = نص
    f_known: "An authorized card you know works",  // مفتاح f_known في الكائن = نص
    adv_open: "Advanced options (usually not needed)",  // مفتاح adv_open في الكائن = نص
    p_space: "Combinations", p_samples: "Sample cards",  // مفتاح p_space في الكائن = نص
    p_request_shape: "Expected request shape (sensitive values hidden)",  // مفتاح p_request_shape في الكائن = نص
    online_transition: "transition to online", logout_state: "state after logout",  // مفتاح online_transition في الكائن = نص
    p_covered: "covered",  // مفتاح p_covered في الكائن = نص
    btn_calibrate: "Test card and learn request shape",  // مفتاح btn_calibrate في الكائن = نص
    btn_capture: "Open the portal and record a successful login",  // مفتاح btn_capture في الكائن = نص
    capture_hint: "The portal opens in an isolated frame (no allow-same-origin). Its JavaScript cannot reach the KiraPass API. Log in once, then mark the success / reject / statistics pages.",  // مفتاح capture_hint في الكائن = نص
    capture_opened: "The recorder opened in a new window.",  // مفتاح capture_opened في الكائن = نص
    capture_popup_blocked: "Your browser blocked the new window. Allow pop-ups for this address, then try again.",  // مفتاح capture_popup_blocked في الكائن = نص
    capture_fail: "Could not start the recorder",  // مفتاح capture_fail في الكائن = نص
    capture_blocked_title: "Automated guessing is not available for this portal",  // مفتاح capture_blocked_title في الكائن = نص
    capture_blocked_body: "The password transform uses unknown custom JavaScript. We do not claim it can be automated.",  // مفتاح capture_blocked_body في الكائن = نص
    capture_blocked_next: "Next: log in by hand when you need to. The redacted report contains neither the card number nor the password.",  // مفتاح capture_blocked_next في الكائن = نص
    capture_mark_success: "This is the success page",  // مفتاح capture_mark_success في الكائن = نص
    capture_mark_reject: "This is a reject page",  // مفتاح capture_mark_reject في الكائن = نص
    capture_mark_status: "This is the statistics page",  // مفتاح capture_mark_status في الكائن = نص
    capture_finish: "Finish + download the report",  // مفتاح capture_finish في الكائن = نص
    btn_save: "Save profile",  // مفتاح btn_save في الكائن = نص
    run_title: "3) Run",  // مفتاح run_title في الكائن = نص
    run_hint: "Choose a safe load: faster settings increase the chance of a disconnect or network block. At run entry, the tool retests the known card once with the applied settings and stops before guessing if internet access is not proven. After confirmation it logs out, then refreshes the rejection baseline without resubmitting the card.",  // مفتاح run_hint في الكائن = نص
    r_threads: "Threads", r_attempts: "Attempts", r_delay: "Delay between requests (ms)",  // مفتاح r_threads في الكائن = نص
    r_verify: "Verify internet after any accepted card",  // مفتاح r_verify في الكائن = نص
    r_autostop: "Auto-stop on the first strong result",  // مفتاح r_autostop في الكائن = نص
    r_resume: "Continue where you stopped (no repeats)",  // مفتاح r_resume في الكائن = نص
    cal_internet_walled: "behind the login portal (needs a card)",  // مفتاح cal_internet_walled في الكائن = نص
    cal_internet_online: "already online",  // مفتاح cal_internet_online في الكائن = نص
    cal_internet_offline: "no connection",  // مفتاح cal_internet_offline في الكائن = نص
    cal_internet_blocked: "blocked by the network",  // مفتاح cal_internet_blocked في الكائن = نص
    cal_internet_unknown: "network state unknown",  // مفتاح cal_internet_unknown في الكائن = نص
    cal_known_card_out_of_format: "the card does not match the card format",  // مفتاح cal_known_card_out_of_format في الكائن = نص
    cal_known_card_not_proven: "this card could not be proven to work",  // مفتاح cal_known_card_not_proven في الكائن = نص
    cal_logout_unconfirmed: "could not confirm logout; stopped further attempts",  // مفتاح cal_logout_unconfirmed في الكائن = نص
    prob_length_mismatch: "the card length does not match the profile length",  // مفتاح prob_length_mismatch في الكائن = نص
    prob_prefix_mismatch: "the card does not start with the prefix",  // مفتاح prob_prefix_mismatch في الكائن = نص
    prob_suffix_mismatch: "the card does not end with the suffix",  // مفتاح prob_suffix_mismatch في الكائن = نص
    prob_charset_mismatch: "the card has characters outside the chosen charset",  // مفتاح prob_charset_mismatch في الكائن = نص
    known_card_tried: "we tried this card in several request shapes; the router answered:",  // مفتاح known_card_tried في الكائن = نص
    known_card_hint: "→ HTTP 400/405/415/422 means the router rejected the request shape before judging the card. Compare the displayed method, URL, and fields with the successful browser request. HTTP 200 matching the rejection page does not prove success. If blocked, stop attempts and ask the network administrator to review access; do not automatically reconnect.",  // مفتاح known_card_hint في الكائن = نص
    s_eta: "time left",  // مفتاح s_eta في الكائن = نص
    th_auto_slowed_router_complaining: "slowed down automatically: the router started complaining (errors/limits)",  // مفتاح th_auto_slowed_router_complaining في الكائن = نص
    th_auto_sped_up: "sped up automatically: the router is answering cleanly",  // مفتاح th_auto_sped_up في الكائن = نص
    th_auto_sped_up_more_threads: "sped up automatically: added threads because the router is answering cleanly",  // مفتاح th_auto_sped_up_more_threads في الكائن = نص
    lockout_apply: "apply the safe pace to the settings",  // مفتاح lockout_apply في الكائن = نص
    lockout_applied: "delay and threads updated",  // مفتاح lockout_applied في الكائن = نص
    f_ua: "browser identity (User-Agent)",  // مفتاح f_ua في الكائن = نص
    f_ua_custom: "custom User-Agent",  // مفتاح f_ua_custom في الكائن = نص
    ua_default: "default browser (Chrome/Windows)",  // مفتاح ua_default في الكائن = نص
    ua_android: "Android Chrome", ua_iphone: "iPhone Safari",  // مفتاح ua_android في الكائن = نص
    ua_custom: "write a custom value…",  // مفتاح ua_custom في الكائن = نص
    ua_hint: "Change this only when a card works in your phone browser but the router rejects the tool's request shape.",  // مفتاح ua_hint في الكائن = نص
    f_referer: "send browser headers (Referer/Origin)",  // مفتاح f_referer في الكائن = نص
    btn_lockout: "measure the lock-out",  // مفتاح btn_lockout في الكائن = نص
    lockout_measuring: "running a bounded check (up to 8 requests); it stops at the first block...",  // مفتاح lockout_measuring في الكائن = نص
    lockout_confirm: "This optional check sends up to 8 failed login attempts and may trigger a network block. Continue only if authorized. If the network is already blocking you, cancel and contact its administrator.",  // مفتاح lockout_confirm في الكائن = نص
    lockout_after: "the router blocks after",  // مفتاح lockout_after في الكائن = نص
    lockout_clears: "and the block clears after",  // مفتاح lockout_clears في الكائن = نص
    lockout_never: "no block appeared within the safe attempt limit",  // مفتاح lockout_never في الكائن = نص
    lockout_stopped_after_block: "The tool stopped as soon as the block appeared; it did not wait for expiry or send more requests. Stop attempts and ask the network administrator to review access.",  // مفتاح lockout_stopped_after_block في الكائن = نص
    lockout_pace: "fastest pace that stays under the limit: one attempt every",  // مفتاح lockout_pace في الكائن = نص
    lockout_pace_hint: "put that in the delay box and use one or two threads.",  // مفتاح lockout_pace_hint في الكائن = نص
    lockout_impossible: "guessing on this router means getting blocked over and over: either a very long delay, or change the setting in the router itself.",  // مفتاح lockout_impossible في الكائن = نص
    seconds: "seconds",  // مفتاح seconds في الكائن = نص
    attempt: "attempt",  // مفتاح attempt في الكائن = نص
    netadvice_blocked_from_the_start: "The network was already blocking this device before the check. Stop attempts and ask the network administrator to review access and restore service.",  // مفتاح netadvice_blocked_from_the_start في الكائن = نص
    btn_diagnose: "Diagnose the network first", btn_clear_review: "Clear review pages",  // مفتاح btn_diagnose في الكائن = نص
    license_check: "I confirm I own this network or hold written permission from its owner.",  // مفتاح license_check في الكائن = نص
    btn_start: "Start guessing", btn_stop: "Stop guessing",  // مفتاح btn_start في الكائن = نص
    run_stop_hint: "Stop the run before testing a card manually on the same device; concurrent portal sessions can affect the reply.",
    res_title: "4) Live results",  // مفتاح res_title في الكائن = نص
    s_speed: "Speed", s_sent: "Sent", s_covered: "Covered",  // مفتاح s_speed في الكائن = نص
    s_latency: "Latency", s_delay: "Current slowdown", s_eta: "Time left", s_state: "State",  // مفتاح s_latency في الكائن = نص
    t_card: "Card", t_result: "Result", t_why: "Reason", t_ms: "ms", t_len: "Size",  // مفتاح t_card في الكائن = نص
    btn_clear_log: "Clear log", btn_download: "Download last report",  // مفتاح btn_clear_log في الكائن = نص
    hits_title: "Accepted cards", hits_none: "Nothing yet.",  // مفتاح hits_title في الكائن = نص
    review_title: "Unclear replies (need your eyes)",  // مفتاح review_title في الكائن = نص
    review_hint: "Replies that are neither the rejection page nor a proven success. Saved for you to inspect - the tool does not guess.",  // مفتاح review_hint في الكائن = نص
    review_none: "Nothing yet.",  // مفتاح review_none في الكائن = نص
    state_idle: "Ready", state_calibrating: "Checking card and refreshing rejection baseline", state_running: "Running",  // مفتاح state_idle في الكائن = نص
    job_timeout: "timed out waiting - check the log",  // مفتاح job_timeout في الكائن = نص
    state_done: "Finished", state_stopping: "Stopping",  // مفتاح state_done في الكائن = نص
    preset_safe: "Safe (4 threads)", preset_normal: "Normal (12)",  // مفتاح preset_safe في الكائن = نص
    preset_fast: "Fast (40)", preset_custom: "Custom",  // مفتاح preset_fast في الكائن = نص
    cache_title: "Cache & cleanup",  // مفتاح cache_title في الكائن = نص
    cache_hint: "Cache = review pages + reports + logs. Profiles are separate; clearing the results also deletes the hits log.",  // مفتاح cache_hint في الكائن = نص
    cache_temp: "Clear temp + review pages", cache_results: "Clear reports, logs & hits",  // مفتاح cache_temp في الكائن = نص
    cache_profiles: "Clear profiles", cache_all: "Clear everything",  // مفتاح cache_profiles في الكائن = نص
    cache_freed: "Cleared. Freed:",  // مفتاح cache_freed في الكائن = نص
    license_title: "Authorized use",  // مفتاح license_title في الكائن = نص
    license_body: "1) Use only on networks you own or have written permission to test.\n2) Never use it for unauthorized access or to guess codes you do not own.\n3) You are legally responsible for any unauthorized use.\n\nAUTHORIZED_USE_LICENSE.md in the repository is the full license.",  // مفتاح license_body في الكائن = نص
    scan_ok: "Page read", scan_fail: "Could not open the page",  // مفتاح scan_ok في الكائن = نص
    internet_ONLINE: "Actually online right now",  // مفتاح internet_ONLINE في الكائن = نص
    internet_WALLED: "Behind the login portal (needs a card)",  // مفتاح internet_WALLED في الكائن = نص
    internet_OFFLINE: "No network connection",  // مفتاح internet_OFFLINE في الكائن = نص
    internet_BLOCKED: "Blocked by the network",  // مفتاح internet_BLOCKED في الكائن = نص
    internet_detail_expected_answer: "the outside URL answered as expected",  // مفتاح internet_detail_expected_answer في الكائن = نص
    internet_detail_portal_redirect: "the network redirected us to the login page",  // مفتاح internet_detail_portal_redirect في الكائن = نص
    internet_detail_portal_page: "the network answered with its own page",  // مفتاح internet_detail_portal_page في الكائن = نص
    detected: "What the tool detected", form_action: "Form action",  // مفتاح detected في الكائن = نص
    form_method: "Method", user_field: "Username field", pass_field: "Password field",  // مفتاح form_method في الكائن = نص
    extra_fields: "Fixed fields", dst_values: "dst values found",  // مفتاح extra_fields في الكائن = نص
    chap_detected: "uses the MikroTik MD5 (chap) scheme",  // مفتاح chap_detected في الكائن = نص
    chap_hint: "md5.js detected - the chap formula will be used automatically.",  // مفتاح chap_hint في الكائن = نص
    no_form: "No login form found on this page - try the exact URL the guest sees.",  // مفتاح no_form في الكائن = نص
    running_now: "Running", done_now: "Finished",  // مفتاح running_now في الكائن = نص
    why_stopped: "Why it stopped", advice: "What to do next",  // مفتاح why_stopped في الكائن = نص
    review_open: "Open the saved page",  // مفتاح review_open في الكائن = نص
    review_diff: "Words in this reply that are not on the rejection page",  // مفتاح review_diff في الكائن = نص
    missing_words: "Words that were on the rejection page and are gone",  // مفتاح missing_words في الكائن = نص
    report_saved: "Report saved",  // مفتاح report_saved في الكائن = نص
    download_calibration_report: "Download redacted calibration report",  // مفتاح download_calibration_report في الكائن = نص
    confirm_clear_all: "Everything will be deleted, including profiles. Sure?",  // مفتاح confirm_clear_all في الكائن = نص
    confirm_profiles: "Profiles will be deleted. Sure?",  // مفتاح confirm_profiles في الكائن = نص
    yes: "Yes", no: "Cancel", close: "Close", loading: "Working...",  // مفتاح yes في الكائن = نص
    quit_tool: "Stop the tool", confirm_quit: "The tool will shut down and this page will stop working. Sure?",  // مفتاح quit_tool في الكائن = نص
    quit_done: "The tool is stopped - you can close this page.",  // مفتاح quit_done في الكائن = نص
    resume_from: "continuing from",  // مفتاح resume_from في الكائن = نص
    server_gone_title: "The tool stopped",  // مفتاح server_gone_title في الكائن = نص
    server_gone: "Lost contact with the tool. If you stopped it, that is expected - start it again to continue.",  // مفتاح server_gone في الكائن = نص
    cal_failed_title: "Nothing was tried: the initial learning failed",  // مفتاح cal_failed_title في الكائن = نص
    cal_failed_hint: "No attempt was made because the tool could not learn what a rejected card looks like. This is what the router did:",  // مفتاح cal_failed_hint في الكائن = نص
    no_attempt_was_made: "The card-space guessing run did not start; any calibration requests are listed above.",  // مفتاح no_attempt_was_made في الكائن = نص
    netadvice_refused: "Check that you are on this router's network and the URL is right (the port is closed or the router refused your device).",  // مفتاح netadvice_refused في الكائن = نص
    netadvice_dns: "The host name did not resolve: use the router's IP instead (like 10.5.50.1).",  // مفتاح netadvice_dns في الكائن = نص
    netadvice_no_session: "The login page gave no session: verify the URL, pick the same browser identity as your phone and scan again. Cards were not counted as tested.",  // مفتاح netadvice_no_session في الكائن = نص
    netadvice_connect_timeout: "No answer when opening the connection: the router is far, busy, or you are not on its network.",  // مفتاح netadvice_connect_timeout في الكائن = نص
    netadvice_read_timeout: "The router opened the connection but never answered: wait a little and lower the thread count.",  // مفتاح netadvice_read_timeout في الكائن = نص
    netadvice_reset: "The router cut the connection: reconnect to the network and try again.",  // مفتاح netadvice_reset في الكائن = نص
    netadvice_stale: "An old keep-alive connection was closed by the router: try again.",  // مفتاح netadvice_stale في الكائن = نص
    netadvice_tls: "TLS certificate error: try http:// instead of https://",  // مفتاح netadvice_tls في الكائن = نص
    netadvice_unreachable: "You are not connected to this network: join the router's wifi first.",  // مفتاح netadvice_unreachable في الكائن = نص
    netadvice_bad_response: "The router sent an unreadable reply: use the exact login URL a guest sees.",  // مفتاح netadvice_bad_response في الكائن = نص
    netadvice_too_many_redirects: "Endless redirect loop: copy the final URL from the browser.",  // مفتاح netadvice_too_many_redirects في الكائن = نص
    netadvice_proto: "Unsupported URL: it must start with http:// or https://",  // مفتاح netadvice_proto في الكائن = نص
    netadvice_unknown: "Unexpected error: try again, and if it repeats run \"diagnose the network first\".",  // مفتاح netadvice_unknown في الكائن = نص
    netadvice_blocked_already: "The network is blocking this device. Stop attempts and ask the network/router administrator to review access and restore service.",  // مفتاح netadvice_blocked_already في الكائن = نص
    netadvice_blocked_before_probes: "The block appeared before any test card. Do not try to bypass it; ask the network/router administrator to review access and restore service.",  // مفتاح netadvice_blocked_before_probes في الكائن = نص
    netadvice_blocked_by_our_probes: "A block reply appeared during calibration, so the tool stopped without retrying. Stop attempts and ask the network/router administrator to review access and restore service.",  // مفتاح netadvice_blocked_by_our_probes في الكائن = نص
    netadvice_no_rejection_baseline: "No answer at all to the test cards: check the connection to the network.",  // مفتاح netadvice_no_rejection_baseline في الكائن = نص
    netadvice_card_space_empty: "The card format leaves nothing to guess: prefix + suffix are longer than the card, or there are too few variable characters.",  // مفتاح netadvice_card_space_empty في الكائن = نص
    netadvice_calibration_failed: "Fix the reason above, then press \"start guessing\" again.",  // مفتاح netadvice_calibration_failed في الكائن = نص
    block_but_form_present: "but the page still has the login form",  // مفتاح block_but_form_present في الكائن = نص
    probe_cards: "test cards",  // مفتاح probe_cards في الكائن = نص
    http_ok_word_ignored: "the page answers fine and mentions blocking, but it still offers the login form - treated as a login page",  // مفتاح http_ok_word_ignored في الكائن = نص
    internet_opened_title: "the internet opened during the run - one of these cards is the working one",  // مفتاح internet_opened_title في الكائن = نص
    internet_opened_hint: "the router let us in but never answered with a clear success page, so the card could not be named from the reply alone. End the session and try these cards one by one in the login page - one of them opened the network. Newest last.",  // مفتاح internet_opened_hint في الكائن = نص
    stop_internet_opened: "stopped because the internet opened during the run: one of the last cards tried is the working one.",  // مفتاح stop_internet_opened في الكائن = نص
    retry_now: "↻ Try again now",  // مفتاح retry_now في الكائن = نص
    v_ACCEPTED_VERIFIED: "Accepted & verified",  // مفتاح v_ACCEPTED_VERIFIED في الكائن = نص
    v_ACCEPTED: "Accepted",  // مفتاح v_ACCEPTED في الكائن = نص
    v_ACCEPTED_UNVERIFIED: "Router accepted (internet check failed)",  // مفتاح v_ACCEPTED_UNVERIFIED في الكائن = نص
    v_REJECTED: "Rejected", v_UNKNOWN: "Unclear reply", v_BANNED: "Blocked by router",  // مفتاح v_REJECTED في الكائن = نص
    v_RATE_LIMITED: "Throttled / rate limited", v_CHALLENGE: "Captcha appeared",  // مفتاح v_RATE_LIMITED في الكائن = نص
    v_NET_ERROR: "Network error",  // مفتاح v_NET_ERROR في الكائن = نص
    v_INTERNAL_ERROR: "Internal tool error (reported)",  // مفتاح v_INTERNAL_ERROR في الكائن = نص
    r_same_as_rejection_page_exact: "identical to the rejection page",  // مفتاح r_same_as_rejection_page_exact في الكائن = نص
    r_same_as_rejection_page_shape: "same page as a rejection (temporary tokens differ)",  // مفتاح r_same_as_rejection_page_shape في الكائن = نص
    r_same_as_rejection_page_similar: "very close to the rejection page",  // مفتاح r_same_as_rejection_page_similar في الكائن = نص
    r_same_as_rejection_page_empty: "empty reply, like the rejection page",  // مفتاح r_same_as_rejection_page_empty في الكائن = نص
    r_same_as_rejection_page_redirect: "same redirect as a rejected card",  // مفتاح r_same_as_rejection_page_redirect في الكائن = نص
    r_redirect_differs_from_rejection: "the router sent this card somewhere else than a rejected one",  // مفتاح r_redirect_differs_from_rejection في الكائن = نص
    r_ban_page: "an explicit block page from the router",  // مفتاح r_ban_page في الكائن = نص
    r_http_403: "the router refuses the request (403)",  // مفتاح r_http_403 في الكائن = نص
    r_http_429: "too many requests (429) - slow down",  // مفتاح r_http_429 في الكائن = نص
    r_captcha_present: "the page has a captcha - guessing is over",  // مفتاح r_captcha_present في الكائن = نص
    r_redirect_out_of_portal_and_online: "the router gave this card real internet",  // مفتاح r_redirect_out_of_portal_and_online في الكائن = نص
    r_accepted_internet_already_open: "router accepted (internet proof skipped: you were online already)",  // مفتاح r_accepted_internet_already_open في الكائن = نص
    internet_online_verification_limited: "you are online already - I will rely on the portal redirect and status page",  // مفتاح internet_online_verification_limited في الكائن = نص
    r_redirect_out_of_portal: "the router redirected the browser out of the portal",  // مفتاح r_redirect_out_of_portal في الكائن = نص
    r_redirect_to_another_portal_page: "the redirect stayed inside the portal - not an exit",  // مفتاح r_redirect_to_another_portal_page في الكائن = نص
    r_http_503: "the router or RADIUS is unavailable (503) - slowed down",  // مفتاح r_http_503 في الكائن = نص
    r_success_url_contains: "the learned success URL appeared",  // مفتاح r_success_url_contains في الكائن = نص
    r_learned_success_words: "the success words learned from your own card appeared",  // مفتاح r_learned_success_words في الكائن = نص
    r_welcome_words: "welcome words that never appear on the rejection page",  // مفتاح r_welcome_words في الكائن = نص
    r_rejection_wording: "the rejection wording is on the page",  // مفتاح r_rejection_wording في الكائن = نص
    r_reply_differs_not_proven: "reply differs but nothing proves acceptance - saved for review",  // مفتاح r_reply_differs_not_proven في الكائن = نص
    r_looks_rejected_but_success_words_found: "looks like the rejection page but contains success words - needs your eyes",  // مفتاح r_looks_rejected_but_success_words_found في الكائن = نص
    r_redirect_out_of_portal_but_page_matches: "the router sent us somewhere else though the page matches a rejection - not called a rejection, saved for review",  // مفتاح r_redirect_out_of_portal_but_page_matches في الكائن = نص
    net_dns: "host name could not be resolved",  // مفتاح net_dns في الكائن = نص
    net_refused: "the router refused the connection",  // مفتاح net_refused في الكائن = نص
    net_connect_timeout: "no answer while opening the connection",  // مفتاح net_connect_timeout في الكائن = نص
    net_read_timeout: "connected but the reply was too slow",  // مفتاح net_read_timeout في الكائن = نص
    net_reset: "the router cut the connection",  // مفتاح net_reset في الكائن = نص
    net_stale: "a stale keep-alive socket was closed (auto-retried)",  // مفتاح net_stale في الكائن = نص
    net_tls: "TLS/certificate error",  // مفتاح net_tls في الكائن = نص
    net_unreachable: "network unreachable (you are not connected to it)",  // مفتاح net_unreachable في الكائن = نص
    net_bad_response: "unreadable reply from the router",  // مفتاح net_bad_response في الكائن = نص
    net_too_many_redirects: "redirect loop", net_proto: "unsupported URL",  // مفتاح net_too_many_redirects في الكائن = نص
    net_unknown: "unexpected error",  // مفتاح net_unknown في الكائن = نص
    net_no_session: "could not obtain a login-page session - the card was not tested",  // مفتاح net_no_session في الكائن = نص
    stop_found_verified: "Found a working card and verified real internet access.",  // مفتاح stop_found_verified في الكائن = نص
    stop_found_strong_evidence: "A card produced strong evidence (redirect out of the portal).",  // مفتاح stop_found_strong_evidence في الكائن = نص
    stop_user_stop: "You stopped it.",  // مفتاح stop_user_stop في الكائن = نص
    stop_banned_by_router: "The router blocked requests. Stop attempts and ask the network administrator to review access and restore service.",  // مفتاح stop_banned_by_router في الكائن = نص
    stop_rate_limited_by_router: "The network rate limited requests (429). The tool stopped; ask the network administrator to review access before continuing.",  // مفتاح stop_rate_limited_by_router في الكائن = نص
    stop_target_unreachable: "Stopped after repeated connection failures; this may be an outage or a block, which the report cannot distinguish. Requests stopped and no automatic reconnect was attempted. Ask the network admin before trying again.",  // مفتاح stop_target_unreachable في الكائن = نص
    manual_resume_title: "Administrator confirmation required before resuming",  // مفتاح manual_resume_title في الكائن = نص
    manual_resume_hint: "After a block or outage, resume only after the network administrator reviews it and confirms continuation is allowed.",  // مفتاح manual_resume_hint في الكائن = نص
    manual_resume_ack: "I checked with the network administrator; the network is ready and resuming is allowed",  // مفتاح manual_resume_ack في الكائن = نص
        why_title: "Why each attempt ended the way it did",  // مفتاح why_title في الكائن = نص
stop_attempts_done: "Requested attempts finished. Run again - it continues, it does not repeat.",  // مفتاح stop_attempts_done في الكائن = نص
    stop_space_done: "Every combination in this range has been covered.",  // مفتاح stop_space_done في الكائن = نص
    stop_calibration_failed: "Nothing was started because the initial learning failed - the reason is written below.",  // مفتاح stop_calibration_failed في الكائن = نص
    stop_engine_error: "Internal error - see the log.",  // مفتاح stop_engine_error في الكائن = نص
    stop_captcha_challenge: "A captcha appeared; guessing is pointless after that.",  // مفتاح stop_captcha_challenge في الكائن = نص
    stop_found_unverified: "The router accepted the card but the internet check failed.",  // مفتاح stop_found_unverified في الكائن = نص
    th_rate_limited_slowing_down: "Stopped further requests after a rate-limit response (429)",  // مفتاح th_rate_limited_slowing_down في الكائن = نص
    th_ban_page_slowing_down: "Stopped further requests after a block page appeared",  // مفتاح th_ban_page_slowing_down في الكائن = نص
    th_connections_refused_slowing_down: "Slowed down because the router refuses connections",  // مفتاح th_connections_refused_slowing_down في الكائن = نص
    th_network_errors_slowing_down: "Slowed down because of repeated network errors",  // مفتاح th_network_errors_slowing_down في الكائن = نص
    th_recovering_speed: "Network calmed down - raising the speed again",  // مفتاح th_recovering_speed في الكائن = نص
    cal_blocked_already: "the router is refusing requests due to an active block (the tool stopped without retrying)",  // مفتاح cal_blocked_already في الكائن = نص
    cal_blocked_before_probes: "the block page was already there before we tried any card - the router blocked this device earlier",  // مفتاح cal_blocked_before_probes في الكائن = نص
    cal_blocked_by_our_probes: "a block reply appeared during calibration, so the tool stopped without waiting or retrying",  // مفتاح cal_blocked_by_our_probes في الكائن = نص
    cal_captcha_challenge: "a CAPTCHA or verification challenge appeared; the tool stopped sending requests",  // مفتاح cal_captcha_challenge في الكائن = نص
    cal_card_space_empty: "the card format leaves nothing to guess",  // مفتاح cal_card_space_empty في الكائن = نص
    cal_no_rejection_baseline: "no reply came back for the test cards",  // مفتاح cal_no_rejection_baseline في الكائن = نص
    cal_request_shape_rejected: "The router rejected the request before judging the card (HTTP 400/405/415/422). Cookies and hidden tokens were refreshed; try the same browser identity, otherwise the page uses custom JavaScript and a successful request must be captured.",  // مفتاح cal_request_shape_rejected في الكائن = نص
    cal_reach_login_page: "Reaching the login page",  // مفتاح cal_reach_login_page في الكائن = نص
    cal_internet_state: "Internet state before any attempt",  // مفتاح cal_internet_state في الكائن = نص
    cal_rejection_baseline: "Learning the rejection page",  // مفتاح cal_rejection_baseline في الكائن = نص
    cal_rejection_probe: "Sending test cards",  // مفتاح cal_rejection_probe في الكائن = نص
    cal_probe_looked_accepted: "A test card looked accepted",  // مفتاح cal_probe_looked_accepted في الكائن = نص
    cal_shape_tuned: "Tuning the request shape with your known card",  // مفتاح cal_shape_tuned في الكائن = نص
    cal_http_ok: "the page answered", cal_learned: "learned",  // مفتاح cal_http_ok في الكائن = نص
    cal_known_card_works: "the known card works with this shape",  // مفتاح cal_known_card_works في الكائن = نص
    cal_known_card_not_proven: "could not prove the known card works with these settings",  // مفتاح cal_known_card_not_proven في الكائن = نص
    cal_browser_trace: "open F12 in the browser and copy the login form data",  // مفتاح cal_browser_trace في الكائن = نص
    dyn_tokens: "dynamic tokens ignored", exact_mode: "exact comparison ready",  // مفتاح dyn_tokens في الكائن = نص
    shape_mode: "comparing by shape (page changes by itself)",  // مفتاح shape_mode في الكائن = نص
    diag_reach: "Reaching the router", diag_internet: "Internet state",  // مفتاح diag_reach في الكائن = نص
    diag_sample_single: "Measuring with one thread", diag_sample_parallel: "Measuring under load",  // مفتاح diag_sample_single في الكائن = نص
    diag_ban_check: "Block check",  // مفتاح diag_ban_check في الكائن = نص
    diag_ok: "clean", diag_errors_present: "errors present", diag_errors_rising: "errors rise with speed",  // مفتاح diag_ok في الكائن = نص
    diag_no_ban_seen: "no blocking seen", diag_ban_page_seen: "a block page appeared",  // مفتاح diag_no_ban_seen في الكائن = نص
    advice_blocked_already: "The network is blocking this device. Stop attempts and ask the network administrator to review access and restore service.",  // مفتاح advice_blocked_already في الكائن = نص
    advice_router_pressure: "The errors come from router pressure: lower the thread count.",  // مفتاح advice_router_pressure في الكائن = نص
    advice_slow_router: "The router answers slowly: fewer threads and more delay.",  // مفتاح advice_slow_router في الكائن = نص
    advice_already_online_no_captive_portal: "You are online already - make sure you are on the guest network.",  // مفتاح advice_already_online_no_captive_portal في الكائن = نص
    suggest_threads: "Suggested threads",  // مفتاح suggest_threads في الكائن = نص
    prob_url_missing_or_invalid: "the login URL is invalid",  // مفتاح prob_url_missing_or_invalid في الكائن = نص
    prob_user_field_missing: "the username field is missing",  // مفتاح prob_user_field_missing في الكائن = نص
    prob_length_not_bigger_than_prefix_and_suffix: "prefix + suffix are longer than the card",  // مفتاح prob_length_not_bigger_than_prefix_and_suffix في الكائن = نص
    prob_charset_too_small: "too few variable characters",  // مفتاح prob_charset_too_small في الكائن = نص
    prob_unknown_pass_mode: "unknown password mode",  // مفتاح prob_unknown_pass_mode في الكائن = نص
    prob_fixed_password_empty: "the fixed password is empty",  // مفتاح prob_fixed_password_empty في الكائن = نص
    prob_needs_browser_js: "this portal's password transform needs a browser and cannot be automated",  // مفتاح prob_needs_browser_js في الكائن = نص
    prob_space_is_astronomically_big: "the space is enormous - shorten it or use more threads",  // مفتاح prob_space_is_astronomically_big في الكائن = نص
    pm_same: "same as card", pm_empty: "empty", pm_omit: "field omitted",  // مفتاح pm_same في الكائن = نص
    pm_fixed: "fixed value", pm_chap: "MikroTik MD5 (chap) of the card",  // مفتاح pm_fixed في الكائن = نص
    pm_chap_empty: "chap over an empty value", pm_md5user: "MD5 of the card only",  // مفتاح pm_chap_empty في الكائن = نص
    pm_sha1user: "SHA1 of the card only",  // مفتاح pm_sha1user في الكائن = نص
    pm_sha256user: "SHA256 of the card only",  // مفتاح pm_sha256user في الكائن = نص
    cs_digits: "digits", cs_lower: "lowercase", cs_upper: "uppercase",  // مفتاح cs_digits في الكائن = نص
    cs_alnum: "digits + lowercase", cs_alnum_upper: "digits + uppercase",  // مفتاح cs_alnum في الكائن = نص
    cs_hex: "hex lowercase", cs_hex_upper: "hex uppercase",  // مفتاح cs_hex في الكائن = نص
  }  // إغلاق الكتلة السابقة
};  // إغلاق الكتلة السابقة

let LANG = "ar";  // تعريف المتغير القابل للتغيير LANG = نص
const t = (key, fallback) => (I18N[LANG] && I18N[LANG][key]) || fallback || key;  // تعريف الثابت t = قيمة

/* ------------------------------------------------------------------ state */
const S = { meta: null, lastSeq: 0, poll: null, running: false, rows: 0,  // تعريف الثابت S = كائن
            lastReport: "", profile: {}, knownCard: "", portal: null,  // مفتاح lastReport في الكائن = نص
            scanReady: false, scannedUrl: "", calibrationReady: false,  // مفتاح scanReady في الكائن = قيمة
            calibrationSignature: "", manualResumeRequired: false,  // مفتاح calibrationSignature في الكائن = نص
            savedProfileMode: false, currentFlow: "start",  // مفتاح savedProfileMode في الكائن = قيمة
            state: "idle" };  // مفتاح state في الكائن = نص

const $ = (id) => document.getElementById(id);  // تعريف الثابت $ = نتيجة استدعاء

/* ------------------------------------------------------------------ access */
/* When the tool is opened to the LAN it prints a link with ?token=...
   The token is kept in localStorage so the user types it only once. */
const TOKEN = (() => {  // تعريف الثابت TOKEN = قيمة
  const fromUrl = new URLSearchParams(location.search).get("token");  // تعريف الثابت fromUrl = نتيجة استدعاء
  if (fromUrl) { localStorage.setItem("kirapass_token", fromUrl); return fromUrl; }  // تكملة السطر السابق
  return localStorage.getItem("kirapass_token") || "";  // إرجاع localStorage.getItem("kirapass_token") || "";
})();  // تنفيذ التعليمة السابقة

function withToken(path) {  // تعريف الدالة withToken(path)
  if (!TOKEN) return path;  // تنفيذ التعليمة السابقة
  return path + (path.includes("?") ? "&" : "?") + "token=" + encodeURIComponent(TOKEN);  // إرجاع path + (path.includes("?") ? "&" : "?") + "token=" + encodeU
}  // إغلاق الكتلة السابقة

function askToken() {  // تعريف الدالة askToken()
  modal("Access token", "<p>هذه الأداة مفتوحة على الشبكة المحلية، أدخل الرمز الذي طبعته في الطرفية.<br>" +  // تكملة السطر السابق
    "Enter the token printed in the terminal.</p>" +  // تكملة السطر السابق
    "<input id='tokIn' placeholder='token' autocomplete='off'>" +  // تكملة السطر السابق
    "<div class='row end'><button class='btn primary' id='tokOk'>OK</button></div>");  // تنفيذ التعليمة السابقة
  $("tokOk").addEventListener("click", () => {  // تكملة السطر السابق
    const v = $("tokIn").value.trim();  // تعريف الثابت v = نتيجة استدعاء
    if (v) { localStorage.setItem("kirapass_token", v); location.reload(); }  // تكملة السطر السابق
  });  // إغلاق القوس المفتوح في السطر السابق
}  // إغلاق الكتلة السابقة
const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g,  // تعريف الثابت esc = قيمة
  (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));  // تنفيذ التعليمة السابقة

async function api(path, body, method) {  // تكملة السطر السابق
  const opt = { method: method || (body ? "POST" : "GET"), headers: {} };  // تعريف الثابت opt = كائن
  if (body) { opt.headers["Content-Type"] = "application/json";  // تنفيذ التعليمة السابقة
              opt.body = JSON.stringify(body); }  // إسناد قيمة إلى opt.body
  let res;  // تنفيذ التعليمة السابقة
  try {  // بداية try محمية
    res = await fetch(withToken(path), opt);  // إسناد نتيجة استدعاء إلى res
  } catch (e) {  // التقاط الخطأ في e
    /* the tool was stopped (or the phone slept): say so instead of freezing */
    return { ok: false, error: "server_gone" };  // إرجاع { ok: false, error: "server_gone" };
  }  // إغلاق الكتلة السابقة
  if (res.status === 401) { askToken(); return { ok: false, error: "unauthorized" }; }  // تكملة السطر السابق
  try { return await res.json(); } catch (e) { return { ok: false, error: "bad_response" }; }  // تكملة السطر السابق
}  // إغلاق الكتلة السابقة

function toast(msg, ms) {  // تعريف الدالة toast(msg, ms)
  const pill = $("statePill");  // تعريف الثابت pill = نتيجة استدعاء
  pill.textContent = msg;  // إسناد قيمة إلى pill.textContent
  clearTimeout(toast._t);  // استدعاء الدالة clearTimeout(toast._t)
  toast._t = setTimeout(() => { pill.textContent = stateLabel(S.state); }, ms || 2500);  // إسناد نتيجة استدعاء إلى toast._t
}  // إغلاق الكتلة السابقة

/* ------------------------------------------------------------------ i18n render */
function setLang(lang) {  // تعريف الدالة setLang(lang)
  LANG = lang === "en" ? "en" : "ar";  // إسناد قيمة إلى LANG
  const html = document.documentElement;  // تعريف الثابت html = قيمة
  html.lang = LANG; html.dir = LANG === "ar" ? "rtl" : "ltr";  // إسناد قيمة إلى html.lang
  document.querySelectorAll("[data-i18n]").forEach((node) => {  // تكملة السطر السابق
    const key = node.getAttribute("data-i18n");  // تعريف الثابت key = نتيجة استدعاء
    const txt = t(key);  // تعريف الثابت txt = نتيجة استدعاء
    if (txt) node.textContent = txt;  // تنفيذ التعليمة السابقة
  });  // إغلاق القوس المفتوح في السطر السابق
  document.querySelectorAll("[data-i18n-placeholder]").forEach((node) => {  // تكملة السطر السابق
    const key = node.getAttribute("data-i18n-placeholder");  // تعريف الثابت key = نتيجة استدعاء
    const txt = t(key);  // تعريف الثابت txt = نتيجة استدعاء
    if (txt) node.setAttribute("placeholder", txt);  // تنفيذ التعليمة السابقة
  });  // إغلاق القوس المفتوح في السطر السابق
  $("langBtn").textContent = LANG === "ar" ? "EN" : "عربي";  // تنفيذ التعليمة السابقة
  $("langBtn").setAttribute("aria-label", t("language_label"));  // استدعاء الدالة $("langBtn").setAttribute("aria-label", t()
  $("langBtn").title = t("language_label");  // استدعاء الدالة $("langBtn").title = t("language_label")
  $("steps").setAttribute("aria-label", t("steps_label"));  // استدعاء الدالة $("steps").setAttribute("aria-label", t("s)
  $("progressTrack").setAttribute("aria-label", t("progress_label"));  // استدعاء الدالة $("progressTrack").setAttribute("aria-labe)
  buildSelects();  // استدعاء الدالة buildSelects()
  $("footText").textContent = LANG === "ar"  // تكملة السطر السابق
    ? "KiraPass — أداة اختبار أمن الشبكات. الاستخدام بدون إذن صاحب الشبكة مخالف للقانون."  // تكملة السطر السابق
    : "KiraPass — network security testing tool. Using it without the owner's permission is unlawful.";  // تنفيذ التعليمة السابقة
  localStorage.setItem("kirapass_lang", LANG);  // استدعاء الدالة localStorage.setItem("kirapass_lang", LANG)
  api("/api/settings", { lang: LANG });  // استدعاء الدالة api("/api/settings", { lang: LANG })
}  // إغلاق الكتلة السابقة

/* ------------------------------------------------------------------ helpers */
const codeLabel = (code) => t("v_" + code, code);  // تعريف الثابت codeLabel = نتيجة استدعاء

function reasonLabel(code, reason, data) {  // تعريف الدالة reasonLabel(code, reason, data)
  if (code === "NET_ERROR") return t("net_" + reason, reason);  // تنفيذ التعليمة السابقة
  if (reason && reason.startsWith("net_")) return t(reason, reason.slice(4));  // تنفيذ التعليمة السابقة
  if (reason && reason.startsWith("internet_")) return t(reason, reason.slice(9));  // تنفيذ التعليمة السابقة
  if (reason === "ban_page" && data && data.word)  // شرط: reason === "ban_page" && data && data.word
    return t("r_ban_page") + " — «" + esc(data.word) + "»";  // إرجاع t("r_ban_page") + " — «" + esc(data.word) + "»";
  if (reason === "cache_cleared") return "";  // تنفيذ التعليمة السابقة
  return t("r_" + reason, reason);  // إرجاع t("r_" + reason, reason);
}  // إغلاق الكتلة السابقة

/* a reason code from the report: r_<code> first, then the network-kind name */
function whyLabel(code) {  // تعريف الدالة whyLabel(code)
  const table = I18N[LANG] || {};  // تعريف الثابت table = قيمة
  if (code === "NET_ERROR") return codeLabel("NET_ERROR");  // تنفيذ التعليمة السابقة
  return table["r_" + code] || table["net_" + code] || code;  // إرجاع table["r_" + code] || table["net_" + code] || code;
}  // إغلاق الكتلة السابقة

function humanTime(seconds) {  // تعريف الدالة humanTime(seconds)
  const s = Math.max(0, Math.round(seconds || 0));  // تعريف الثابت s = نتيجة استدعاء
  if (s < 60) return s + (LANG === "ar" ? " ثانية" : "s");  // تنفيذ التعليمة السابقة
  const m = Math.round(s / 60);  // تعريف الثابت m = نتيجة استدعاء
  if (m < 60) return m + (LANG === "ar" ? " دقيقة" : " min");  // تنفيذ التعليمة السابقة
  const h = Math.floor(m / 60), rm = m % 60;  // تعريف الثابت h = قيمة
  return h + (LANG === "ar" ? " ساعة" : "h") + (rm ? " " + rm : "");  // إرجاع h + (LANG === "ar" ? " ساعة" : "h") + (rm ? " " + rm : "");
}  // إغلاق الكتلة السابقة

const UA_PRESETS = {  // تعريف الثابت UA_PRESETS = كائن
  android: "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Mobile Safari/537.36",  // مفتاح android في الكائن = نص
  iphone: "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",  // مفتاح iphone في الكائن = نص
};  // إغلاق الكتلة السابقة

function uaFromForm() {  // تعريف الدالة uaFromForm()
  const pick = $("f_ua").value;  // تعريف الثابت pick = قيمة
  if (pick === "custom") return ($("f_ua_custom").value || "").trim();  // تنفيذ التعليمة السابقة
  return UA_PRESETS[pick] || "";  // إرجاع UA_PRESETS[pick] || "";
}  // إغلاق الكتلة السابقة

function uaToForm(value) {  // تعريف الدالة uaToForm(value)
  value = value || "";  // إسناد قيمة إلى value
  const hit = Object.keys(UA_PRESETS).find((k) => UA_PRESETS[k] === value);  // تعريف الثابت hit = نتيجة استدعاء
  $("f_ua").value = value ? (hit || "custom") : "";  // تنفيذ التعليمة السابقة
  $("f_ua_custom").value = value && !hit ? value : "";  // تنفيذ التعليمة السابقة
  $("f_ua_custom_wrap").classList.toggle("hidden", !(value && !hit));  // استدعاء الدالة $("f_ua_custom_wrap").classList.toggle("hi)
}  // إغلاق الكتلة السابقة

function stateLabel(state) {  // تعريف الدالة stateLabel(state)
  if (state === "running") return t("state_running");  // تنفيذ التعليمة السابقة
  if (state === "calibrating") return t("state_calibrating");  // تنفيذ التعليمة السابقة
  if (state === "stopping") return t("state_stopping");  // تنفيذ التعليمة السابقة
  if (state === "done") return t("state_done");  // تنفيذ التعليمة السابقة
  return t("state_idle");  // إرجاع t("state_idle");
}  // إغلاق الكتلة السابقة

function fmtSpace(n) {  // تعريف الدالة fmtSpace(n)
  if (!n && n !== 0) return "—";  // تنفيذ التعليمة السابقة
  if (n >= 1e15) return n.toExponential(2);  // تنفيذ التعليمة السابقة
  return n.toLocaleString(LANG === "ar" ? "ar-EG" : "en-US");  // إرجاع n.toLocaleString(LANG === "ar" ? "ar-EG" : "en-US");
}  // إغلاق الكتلة السابقة

function updateStepsVisibility(name) {  // تعريف الدالة updateStepsVisibility(name)
  const nav = $("steps");  // تعريف الثابت nav = نتيجة استدعاء
  if (!nav) return;  // تنفيذ التعليمة السابقة
  /* Hide the 5-step bar on start / saved list / profile review — it confuses
     the saved-profile path. Show it only for the guided new-profile flow. */
  const hide = (name === "start" || name === "saved" || name === "profile-review"  // تعريف الثابت hide = قيمة
                || (S.savedProfileMode && name !== "results" && name !== "run"  // تكملة السطر السابق
                    && name !== "format"));  // تنفيذ التعليمة السابقة
  const showForNew = S.currentFlow === "new" ||  // تعريف الثابت showForNew = قيمة
    ["scan", "format", "run", "results"].includes(name);  // تنفيذ التعليمة السابقة
  const shouldShow = !hide && showForNew && name !== "start";  // تعريف الثابت shouldShow = قيمة
  nav.classList.toggle("steps-hidden", !shouldShow);  // استدعاء الدالة nav.classList.toggle("steps-hidden", !shouldShow)
  if (shouldShow) nav.removeAttribute("hidden");  // تنفيذ التعليمة السابقة
  else nav.setAttribute("hidden", "");  // تنفيذ التعليمة السابقة
}  // إغلاق الكتلة السابقة

function step(name) {  // تعريف الدالة step(name)
  if (S.currentFlow === "new" && (name === "format" || name === "run") && !S.calibrationReady) {  // شرط: S.currentFlow === "new" && (name === "format" || name === "run") && !S
    name = "scan";  // إسناد نص إلى name
    toast(t("calibration_required"));  // استدعاء الدالة toast(t("calibration_required"))
  }  // إغلاق الكتلة السابقة
  document.querySelectorAll(".panel").forEach((p) =>  // تكملة السطر السابق
    p.classList.toggle("active", p.id === "panel-" + name));  // استدعاء الدالة p.classList.toggle("active", p.id === "panel-" + name))
  document.querySelectorAll(".step").forEach((b) => {  // تكملة السطر السابق
    const active = b.dataset.step === name;  // تعريف الثابت active = قيمة
    b.classList.toggle("active", active);  // استدعاء الدالة b.classList.toggle("active", active)
    if (active) b.setAttribute("aria-current", "step");  // تنفيذ التعليمة السابقة
    else b.removeAttribute("aria-current");  // تنفيذ التعليمة السابقة
  });  // إغلاق القوس المفتوح في السطر السابق
  if (name === "saved" || name === "profile-review") {  // شرط: name === "saved" || name === "profile-review"
    document.querySelectorAll(".step").forEach((b) => {  // تكملة السطر السابق
      if (b.dataset.step === "start") {  // شرط: b.dataset.step === "start"
        b.classList.add("active");  // استدعاء الدالة b.classList.add("active")
        b.setAttribute("aria-current", "step");  // استدعاء الدالة b.setAttribute("aria-current", "step")
      }  // إغلاق الكتلة السابقة
    });  // إغلاق القوس المفتوح في السطر السابق
  }  // إغلاق الكتلة السابقة
  if (name === "start") {  // شرط: name === "start"
    S.currentFlow = "start";  // إسناد نص إلى S.currentFlow
    S.savedProfileMode = false;  // إسناد قيمة منطقية إلى S.savedProfileMode
  }  // إغلاق الكتلة السابقة
  updateStepsVisibility(name);  // استدعاء الدالة updateStepsVisibility(name)
  window.scrollTo({ top: 0, behavior: "smooth" });  // استدعاء الدالة window.scrollTo({ top: 0, behavior: "smooth" })
}  // إغلاق الكتلة السابقة

function showStart() {  // تعريف الدالة showStart()
  S.currentFlow = "start";  // إسناد نص إلى S.currentFlow
  S.savedProfileMode = false;  // إسناد قيمة منطقية إلى S.savedProfileMode
  step("start");  // استدعاء الدالة step("start")
  const info = $("startProfilesInfo");  // تعريف الثابت info = نتيجة استدعاء
  if (info) {  // شرط: info
    const count = (S.meta && S.meta.profiles && S.meta.profiles.length) || 0;  // تعريف الثابت count = قيمة
    info.innerHTML = count  // إسناد قيمة إلى info.innerHTML
      ? esc(t("saved_profile_count")) + ": <b>" + count + "</b>"  // تكملة السطر السابق
      : esc(t("no_saved_profiles"));  // تنفيذ التعليمة السابقة
  }  // إغلاق الكتلة السابقة
}  // إغلاق الكتلة السابقة

function showSaved() {  // تعريف الدالة showSaved()
  S.currentFlow = "saved";  // إسناد نص إلى S.currentFlow
  S.savedProfileMode = true;  // إسناد قيمة منطقية إلى S.savedProfileMode
  step("saved");  // استدعاء الدالة step("saved")
  renderSavedList();  // استدعاء الدالة renderSavedList()
}  // إغلاق الكتلة السابقة

function showNewProfile() {  // تعريف الدالة showNewProfile()
  S.currentFlow = "new";  // إسناد نص إلى S.currentFlow
  S.savedProfileMode = false;  // إسناد قيمة منطقية إلى S.savedProfileMode
  step("scan");  // استدعاء الدالة step("scan")
}  // إغلاق الكتلة السابقة

function showProfileReview(profile) {  // تعريف الدالة showProfileReview(profile)
  if (!profile) return;  // تنفيذ التعليمة السابقة
  S.profile = profile;  // إسناد قيمة إلى S.profile
  S.currentFlow = "saved";  // إسناد نص إلى S.currentFlow
  S.savedProfileMode = true;  // إسناد قيمة منطقية إلى S.savedProfileMode
  fillReviewFromProfile(profile);  // استدعاء الدالة fillReviewFromProfile(profile)
  renderReviewSummary(profile);  // استدعاء الدالة renderReviewSummary(profile)
  step("profile-review");  // استدعاء الدالة step("profile-review")
}  // إغلاق الكتلة السابقة

/* ------------------------------------------------------------------ selects */
function buildSelects() {  // تعريف الدالة buildSelects()
  const cs = $("f_charset");  // تعريف الثابت cs = نتيجة استدعاء
  if (cs && S.meta) {  // شرط: cs && S.meta
    const keep = cs.value;  // تعريف الثابت keep = قيمة
    cs.innerHTML = "";  // إسناد نص إلى cs.innerHTML
    for (const [key, chars] of Object.entries(S.meta.charsets)) {  // حلقة تكرار: const [key, chars] of Object.entries(S.meta.charsets)
      const opt = document.createElement("option");  // تعريف الثابت opt = نتيجة استدعاء
      opt.value = key; opt.dataset.chars = chars;  // إسناد قيمة إلى opt.value
      opt.textContent = t("cs_" + key, key) + "  (" + chars.length + ")";  // إسناد قيمة إلى opt.textContent
      cs.appendChild(opt);  // استدعاء الدالة cs.appendChild(opt)
    }  // إغلاق الكتلة السابقة
    const custom = document.createElement("option");  // تعريف الثابت custom = نتيجة استدعاء
    custom.value = "_custom"; custom.textContent = t("f_custom");  // إسناد نص إلى custom.value
    cs.appendChild(custom);  // استدعاء الدالة cs.appendChild(custom)
    if (keep) cs.value = keep;  // تنفيذ التعليمة السابقة
    if (!["digits", "lower", "upper", "alnum", "alnum_upper", "hex",  // عنصر في القائمة/الكائن (يتبعه المزيد)
          "hex_upper", "_custom"].includes(cs.value)) cs.value = "digits";  // تنفيذ التعليمة السابقة
  }  // إغلاق الكتلة السابقة
  const pm = $("f_pass_mode");  // تعريف الثابت pm = نتيجة استدعاء
  if (pm && S.meta) {  // شرط: pm && S.meta
    const keep = pm.value;  // تعريف الثابت keep = قيمة
    pm.innerHTML = "";  // إسناد نص إلى pm.innerHTML
    S.meta.pass_modes.forEach((mode) => {  // تكملة السطر السابق
      const opt = document.createElement("option");  // تعريف الثابت opt = نتيجة استدعاء
      opt.value = mode; opt.textContent = t("pm_" + mode, mode);  // إسناد نتيجة استدعاء إلى opt.value
      pm.appendChild(opt);  // استدعاء الدالة pm.appendChild(opt)
    });  // إغلاق القوس المفتوح في السطر السابق
    pm.value = keep && S.meta.pass_modes.includes(keep) ? keep : "empty";  // إسناد قيمة إلى pm.value
  }  // إغلاق الكتلة السابقة
  const rvPm = $("rv_pass_mode");  // تعريف الثابت rvPm = نتيجة استدعاء
  if (rvPm && S.meta) {  // شرط: rvPm && S.meta
    const keepRv = rvPm.value;  // تعريف الثابت keepRv = قيمة
    rvPm.innerHTML = "";  // إسناد نص إلى rvPm.innerHTML
    S.meta.pass_modes.forEach((mode) => {  // تكملة السطر السابق
      const opt = document.createElement("option");  // تعريف الثابت opt = نتيجة استدعاء
      opt.value = mode; opt.textContent = t("pm_" + mode, mode);  // إسناد نتيجة استدعاء إلى opt.value
      rvPm.appendChild(opt);  // استدعاء الدالة rvPm.appendChild(opt)
    });  // إغلاق القوس المفتوح في السطر السابق
    rvPm.value = keepRv && S.meta.pass_modes.includes(keepRv) ? keepRv : "empty";  // إسناد قيمة إلى rvPm.value
  }  // إغلاق الكتلة السابقة
  const row = $("presetRow");  // تعريف الثابت row = نتيجة استدعاء
  if (row && S.meta && !row.children.length) {  // شرط: row && S.meta && !row.children.length
    S.meta.presets.forEach((p) => {  // تكملة السطر السابق
      const b = document.createElement("button");  // تعريف الثابت b = نتيجة استدعاء
      b.className = "chip"; b.dataset.preset = p.id;  // إسناد نص إلى b.className
      b.textContent = t("preset_" + p.id, p.id + " (" + p.threads + ")");  // إسناد نتيجة استدعاء إلى b.textContent
      row.appendChild(b);  // استدعاء الدالة row.appendChild(b)
    });  // إغلاق القوس المفتوح في السطر السابق
  }  // إغلاق الكتلة السابقة
}  // إغلاق الكتلة السابقة

/* ------------------------------------------------------------------ profile */
function charsetValue() {  // تعريف الدالة charsetValue()
  const sel = $("f_charset");  // تعريف الثابت sel = نتيجة استدعاء
  if (sel.value === "_custom") return $("f_custom").value || "0123456789";  // تنفيذ التعليمة السابقة
  const opt = (sel.selectedOptions && sel.selectedOptions[0]) || null;  // تعريف الثابت opt = قيمة
  return (opt && opt.dataset.chars) || "0123456789";  // إرجاع (opt && opt.dataset.chars) || "0123456789";
}  // إغلاق الكتلة السابقة

/* where the last run stopped - kept so "start" continues instead of repeating.
   It travels with the profile, because that is what the engine saves back. */
function progressFromProfile(p) {  // تعريف الدالة progressFromProfile(p)
  p = p || {};  // إسناد قيمة إلى p
  let resume = true;  // تعريف المتغير القابل للتغيير resume = قيمة منطقية
  if ($("r_resume")) resume = $("r_resume").checked;  // تنفيذ التعليمة السابقة
  else if ($("rv_resume")) resume = $("rv_resume").checked;  // تنفيذ التعليمة السابقة
  if (!resume) return { space_pos: 0, walk_a: 0, walk_b: 0 };  // تنفيذ التعليمة السابقة
  return {  // إرجاع {
    space_pos: parseInt(p.space_pos || 0, 10) || 0,  // مفتاح space_pos في الكائن = قيمة
    space_pass: parseInt(p.space_pass || 0, 10) || 0,  // مفتاح space_pass في الكائن = قيمة
    walk_a: parseInt(p.walk_a || 0, 10) || 0,  // مفتاح walk_a في الكائن = قيمة
    walk_b: parseInt(p.walk_b || 0, 10) || 0,  // مفتاح walk_b في الكائن = قيمة
  };  // إغلاق الكتلة السابقة
}  // إغلاق الكتلة السابقة

function profileFromForm() {  // تعريف الدالة profileFromForm()
  const extras = {};  // تعريف الثابت extras = كائن
  ($("f_extra").value || "").split(",").forEach((part) => {  // تكملة السطر السابق
    const i = part.indexOf("=");  // تعريف الثابت i = نتيجة استدعاء
    if (i > 0) extras[part.slice(0, i).trim()] = part.slice(i + 1).trim();  // تنفيذ التعليمة السابقة
  });  // إغلاق القوس المفتوح في السطر السابق
  const words = ($("f_words").value || "").split(/[,;\n]/).map((w) => w.trim())  // تعريف الثابت words = نتيجة استدعاء
    .filter(Boolean);  // استدعاء الدالة .filter(Boolean)
  const baseProfile = S.profile || {};  // تعريف الثابت baseProfile = قيمة
  const portalForm = (S.portal || {}).form || {};  // تعريف الثابت portalForm = قيمة
  const detectedFields = new Set(portalForm.all_fields || []);  // تعريف الثابت detectedFields = نتيجة استدعاء
  const dstField = baseProfile.dst_field || portalForm.dst_field || "dst";  // تعريف الثابت dstField = قيمة
  const popupField = baseProfile.popup_field || portalForm.popup_field || "popup";  // تعريف الثابت popupField = قيمة
  const fieldWasDetected = (name) => !S.portal || detectedFields.has(name);  // تعريف الثابت fieldWasDetected = نتيجة استدعاء
  return Object.assign({}, baseProfile, {  // إرجاع Object.assign({}, baseProfile, {
    name: $("f_name").value.trim() || "profile",  // مفتاح name في الكائن = قيمة
    login_url: $("f_login_url").value.trim() || $("scanUrl").value.trim(),  // مفتاح login_url في الكائن = نتيجة استدعاء
    method: $("f_method").value,  // مفتاح method في الكائن = قيمة
    user_field: $("f_user_field").value.trim() || "username",  // مفتاح user_field في الكائن = قيمة
    pass_field: $("f_pass_field").value.trim() || "password",  // مفتاح pass_field في الكائن = قيمة
    pass_mode: $("f_pass_mode").value,  // مفتاح pass_mode في الكائن = قيمة
    charset: charsetValue(),  // مفتاح charset في الكائن = نتيجة استدعاء
    length: parseInt($("f_length").value || "0", 10),  // مفتاح length في الكائن = نتيجة استدعاء
    prefix: $("f_prefix").value.trim(),  // مفتاح prefix في الكائن = نتيجة استدعاء
    suffix: "",  // مفتاح suffix في الكائن = نص
    dst_value: $("f_dst").value.trim(),  // مفتاح dst_value في الكائن = نتيجة استدعاء
    dst_field: dstField,  // مفتاح dst_field في الكائن = قيمة
    popup_field: popupField,  // مفتاح popup_field في الكائن = قيمة
    send_dst: $("f_send_dst").checked && fieldWasDetected(dstField),  // مفتاح send_dst في الكائن = نتيجة استدعاء
    send_popup: $("f_send_popup").checked && fieldWasDetected(popupField),  // مفتاح send_popup في الكائن = نتيجة استدعاء
    extra_fields: extras,  // مفتاح extra_fields في الكائن = قيمة
    success_words: words,  // مفتاح success_words في الكائن = قيمة
    /* the chap formula comes from the scanned page - but a SAVED profile knows
       it too, and loading one must not silently forget it */
    chap: (S.portal && S.portal.form && S.portal.form.chap) ||  // مفتاح chap في الكائن = قيمة
          (S.profile && S.profile.chap) || null,  // عنصر في القائمة/الكائن (يتبعه المزيد)
    user_agent: uaFromForm(),  // مفتاح user_agent في الكائن = نتيجة استدعاء
    send_referer: $("f_referer").checked,  // مفتاح send_referer في الكائن = قيمة
  }, progressFromProfile(S.profile));  // تنفيذ التعليمة السابقة
}  // إغلاق الكتلة السابقة

function calibrationProfileFromForm(knownCard) {  // تعريف الدالة calibrationProfileFromForm(knownCard)
  const p = profileFromForm();  // تعريف الثابت p = نتيجة استدعاء
  const card = String(knownCard || "");  // تعريف الثابت card = نتيجة استدعاء
  // The calibration card is supplied before the guessing format is configured.
  // Use a temporary broad format only for the bounded known-card experiment.
  p.prefix = "";  // إسناد نص إلى p.prefix
  p.suffix = "";  // إسناد نص إلى p.suffix
  p.length = card.length;  // إسناد قيمة إلى p.length
  p.charset = Array.from(new Set("0123456789" + card)).join("");  // إسناد نتيجة استدعاء إلى p.charset
  return p;  // إرجاع p;
}  // إغلاق الكتلة السابقة

function requestSettingsSignature(p) {  // تعريف الدالة requestSettingsSignature(p)
  const extras = Object.entries(p.extra_fields || {}).sort(([a], [b]) => a.localeCompare(b));  // تعريف الثابت extras = نتيجة استدعاء
  return JSON.stringify({  // إرجاع JSON.stringify({
    login_url: p.login_url || "", method: p.method || "post",  // مفتاح login_url في الكائن = قيمة
    user_field: p.user_field || "username", pass_field: p.pass_field || "password",  // مفتاح user_field في الكائن = قيمة
    pass_mode: p.pass_mode || "empty", dst_field: p.dst_field || "dst",  // مفتاح pass_mode في الكائن = قيمة
    dst_value: p.dst_value || "", popup_field: p.popup_field || "popup",  // مفتاح dst_value في الكائن = قيمة
    send_dst: !!p.send_dst, send_popup: !!p.send_popup,  // مفتاح send_dst في الكائن = قيمة
    extra_fields: extras, user_agent: p.user_agent || "",  // مفتاح extra_fields في الكائن = قيمة
    send_referer: p.send_referer !== false,  // مفتاح send_referer في الكائن = قيمة
  });  // إغلاق القوس المفتوح في السطر السابق
}  // إغلاق الكتلة السابقة

function knownCardFormatProblem(card, p) {  // تعريف الدالة knownCardFormatProblem(card, p)
  const value = String(card || "");  // تعريف الثابت value = نتيجة استدعاء
  const length = parseInt(p.length || "0", 10);  // تعريف الثابت length = نتيجة استدعاء
  if (length && value.length !== length) return "length";  // تنفيذ التعليمة السابقة
  const prefix = p.prefix || "";  // تعريف الثابت prefix = قيمة
  const suffix = p.suffix || "";  // تعريف الثابت suffix = قيمة
  if (prefix && !value.startsWith(prefix)) return "prefix";  // تنفيذ التعليمة السابقة
  if (suffix && !value.endsWith(suffix)) return "suffix";  // تنفيذ التعليمة السابقة
  const end = suffix ? value.length - suffix.length : value.length;  // تعريف الثابت end = قيمة
  const variable = value.slice(prefix.length, end);  // تعريف الثابت variable = نتيجة استدعاء
  const charset = new Set(Array.from(p.charset || ""));  // تعريف الثابت charset = نتيجة استدعاء
  if (Array.from(variable).some((ch) => !charset.has(ch))) return "charset";  // تنفيذ التعليمة السابقة
  return "";  // إرجاع "";
}  // إغلاق الكتلة السابقة

function fillFormFromProfile(p) {  // تعريف الدالة fillFormFromProfile(p)
  if (!p) return;  // تنفيذ التعليمة السابقة
  S.profile = p;                       /* keeps space_pos / walk for resume */  // إسناد قيمة إلى S.profile
  uaToForm(p.user_agent || "");  // استدعاء الدالة uaToForm(p.user_agent || "")
  $("f_referer").checked = p.send_referer !== false;  // تنفيذ التعليمة السابقة
  $("f_name").value = p.name || "";  // تنفيذ التعليمة السابقة
  $("f_login_url").value = p.login_url || "";  // تنفيذ التعليمة السابقة
  $("scanUrl").value = p.login_url || "";  // تنفيذ التعليمة السابقة
  $("f_method").value = p.method === "get" ? "get" : "post";  // تنفيذ التعليمة السابقة
  $("f_user_field").value = p.user_field || "username";  // تنفيذ التعليمة السابقة
  $("f_pass_field").value = p.pass_field || "password";  // تنفيذ التعليمة السابقة
  $("f_pass_mode").value = p.pass_mode || "empty";  // تنفيذ التعليمة السابقة
  $("f_prefix").value = p.prefix || "";  // تنفيذ التعليمة السابقة
  $("f_length").value = p.length || 10;  // تنفيذ التعليمة السابقة
  $("f_dst").value = p.dst_value || "";  // تنفيذ التعليمة السابقة
  $("f_send_dst").checked = p.send_dst !== false;  // تنفيذ التعليمة السابقة
  $("f_send_popup").checked = p.send_popup !== false;  // تنفيذ التعليمة السابقة
  $("f_words").value = (p.success_words || []).join(", ");  // استدعاء الدالة $("f_words").value = (p.success_words || [)
  const extras = Object.entries(p.extra_fields || {}).map(([k, v]) => k + "=" + v);  // تعريف الثابت extras = نتيجة استدعاء
  $("f_extra").value = extras.join(", ");  // استدعاء الدالة $("f_extra").value = extras.join(", ")
  const sel = $("f_charset");  // تعريف الثابت sel = نتيجة استدعاء
  const known = Object.entries(S.meta.charsets).find(([, c]) => c === p.charset);  // تعريف الثابت known = نتيجة استدعاء
  if (known) sel.value = known[0];  // تنفيذ التعليمة السابقة
  else { sel.value = "_custom"; $("f_custom").value = p.charset || ""; }  // تكملة السطر السابق
  toggleCustomCharset();  // استدعاء الدالة toggleCustomCharset()
  showCovered(p);  // استدعاء الدالة showCovered(p)
  previewFormat();  // استدعاء الدالة previewFormat()
  const capBox = $("captureCard");  // تعريف الثابت capBox = نتيجة استدعاء
  if (capBox && p.capture_needs_browser_js) {  // شرط: capBox && p.capture_needs_browser_js
    capBox.classList.remove("hidden");  // استدعاء الدالة capBox.classList.remove("hidden")
    capBox.innerHTML = "<h4 class='warn'>" + t("capture_blocked_title") + "</h4><p>" +  // إسناد نص إلى capBox.innerHTML
      esc(p.capture_block_reason || t("capture_blocked_body")) + "</p><p>" +  // تكملة السطر السابق
      esc(t("capture_blocked_next")) + "</p>" +  // تكملة السطر السابق
      "<p class='hint'>" + esc(t("capture_guide_link")) +  // تكملة السطر السابق
      ": docs/GUIDE_" + (LANG === "ar" ? "AR" : "EN") + ".md</p>";  // تنفيذ التعليمة السابقة
  }  // إغلاق الكتلة السابقة
}  // إغلاق الكتلة السابقة

/* how much of this space has been tried in earlier runs */
function showCovered(p) {  // تعريف الدالة showCovered(p)
  const box = $("pvCovered");  // تعريف الثابت box = نتيجة استدعاء
  if (!box) return;  // تنفيذ التعليمة السابقة
  const pos = parseInt((p && p.space_pos) || 0, 10) || 0;  // تعريف الثابت pos = قيمة
  const space = parseInt((p && p.space) || 0, 10) || 0;  // تعريف الثابت space = قيمة
  box.classList.toggle("hidden", !pos);  // استدعاء الدالة box.classList.toggle("hidden", !pos)
  $("pvCoveredVal").textContent = fmtSpace(pos) + (space ? " / " + fmtSpace(space) : "");  // استدعاء الدالة $("pvCoveredVal").textContent = fmtSpace(p)
}  // إغلاق الكتلة السابقة

function renderProfiles(list) {  // تعريف الدالة renderProfiles(list)
  const sel = $("profSel");  // تعريف الثابت sel = نتيجة استدعاء
  if (sel) {  // شرط: sel
    const keep = sel.value;  // تعريف الثابت keep = قيمة
    sel.innerHTML = "<option value=''>" + t("prof_new") + "</option>" +  // إسناد نص إلى sel.innerHTML
      (list || []).map((p) => "<option value='" + esc(p.name) + "'>" + esc(p.name) +  // تكملة السطر السابق
        " — " + esc(p.cards || "") + " (" + fmtSpace(p.space || 0) +  // تكملة السطر السابق
        (p.covered ? " · " + t("p_covered") + " " + fmtSpace(p.covered) : "") +  // تكملة السطر السابق
        ")</option>").join("");  // تنفيذ التعليمة السابقة
    sel.value = (list || []).some((p) => p.name === keep) ? keep : "";  // إسناد قيمة إلى sel.value
  }  // إغلاق الكتلة السابقة
  if ($("savedList") && document.getElementById("panel-saved") && document.getElementById("panel-saved").classList.contains("active")) {  // شرط: $("savedList") && document.getElementById("panel-saved") && document.g
    renderSavedList(list);  // استدعاء الدالة renderSavedList(list)
  }  // إغلاق الكتلة السابقة
  const info = $("startProfilesInfo");  // تعريف الثابت info = نتيجة استدعاء
  if (info) {  // شرط: info
    const count = (list || []).length;  // تعريف الثابت count = قيمة
    info.innerHTML = count  // إسناد قيمة إلى info.innerHTML
      ? esc(t("saved_profile_count")) + ": <b>" + count + "</b>"  // تكملة السطر السابق
      : esc(t("no_saved_profiles"));  // تنفيذ التعليمة السابقة
  }  // إغلاق الكتلة السابقة
}  // إغلاق الكتلة السابقة

function renderSavedList(list) {  // تعريف الدالة renderSavedList(list)
  const container = $("savedList");  // تعريف الثابت container = نتيجة استدعاء
  if (!container) return;  // تنفيذ التعليمة السابقة
  let profiles = list || (S.meta && S.meta.profiles) || [];  // تعريف المتغير القابل للتغيير profiles = قيمة
  const q = (($("savedSearch") && $("savedSearch").value) || "").trim().toLowerCase();  // تعريف الثابت q = نتيجة استدعاء
  if (q) {  // شرط: q
    profiles = profiles.filter((p) => {  // إسناد قيمة إلى profiles
      const hay = ((p.name || "") + " " + (p.login_url || "") + " " +  // تعريف الثابت hay = قيمة
                   (p.cards || "")).toLowerCase();  // تنفيذ التعليمة السابقة
      return hay.includes(q);  // إرجاع hay.includes(q);
    });  // إغلاق القوس المفتوح في السطر السابق
  }  // إغلاق الكتلة السابقة
  if (!profiles.length) {  // شرط: !profiles.length
    container.innerHTML = "<div class='card muted'>" + esc(  // إسناد نص إلى container.innerHTML
      q ? t("no_saved_profiles") : t("no_saved_profiles")) + "</div>";  // تنفيذ التعليمة السابقة
    return;  // إرجاع ;
  }  // إغلاق الكتلة السابقة
  container.innerHTML = profiles.map((p) => {  // إسناد قيمة إلى container.innerHTML
    return "<div class='card' style='display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap'>" +  // إرجاع "<div class='card' style='display:flex;justify-content:space
      "<div><b>" + esc(p.name) + "</b><br><span class='mono' style='font-size:.75rem'>" + esc(p.login_url || p.cards || "") + "</span><br>" +  // تكملة السطر السابق
      "<span class='hint' style='margin:0'>" + esc(p.cards || "") + " · " + fmtSpace(p.space || 0) +  // تكملة السطر السابق
      (p.covered ? " · " + t("p_covered") + " " + fmtSpace(p.covered) : "") + "</span></div>" +  // تكملة السطر السابق
      "<div class='row wrap' style='margin:0'><button class='btn primary' data-open='" + esc(p.name) + "'>" + esc(t("review_profile_title")) + "</button>" +  // تكملة السطر السابق
      "<button class='btn danger tiny' data-del='" + esc(p.name) + "'>" + esc(t("btn_delete_profile")) + "</button></div></div>";  // تنفيذ التعليمة السابقة
  }).join("");  // تنفيذ التعليمة السابقة
  container.querySelectorAll("[data-open]").forEach((b) => {  // تكملة السطر السابق
    b.addEventListener("click", async () => {  // تكملة السطر السابق
      const name = b.dataset.open;  // تعريف الثابت name = قيمة
      const r = await api("/api/profiles/get?name=" + encodeURIComponent(name));  // تعريف الثابت r = نتيجة استدعاء
      if (r.ok && r.profile) {  // شرط: r.ok && r.profile
        showProfileReview(r.profile);  // استدعاء الدالة showProfileReview(r.profile)
      } else {  // فرع else
        toast(t("scan_fail"));  // استدعاء الدالة toast(t("scan_fail"))
      }  // إغلاق الكتلة السابقة
    });  // إغلاق القوس المفتوح في السطر السابق
  });  // إغلاق القوس المفتوح في السطر السابق
  container.querySelectorAll("[data-del]").forEach((b) => {  // تكملة السطر السابق
    b.addEventListener("click", async () => {  // تكملة السطر السابق
      const name = b.dataset.del;  // تعريف الثابت name = قيمة
      if (!name || !window.confirm(name + " ?")) return;  // تنفيذ التعليمة السابقة
      const r = await api("/api/profiles/delete", { name });  // تعريف الثابت r = نتيجة استدعاء
      if (r.ok) {  // شرط: r.ok
        S.meta.profiles = r.profiles || [];  // إسناد قيمة إلى S.meta.profiles
        renderProfiles(r.profiles);  // استدعاء الدالة renderProfiles(r.profiles)
        renderSavedList(r.profiles);  // استدعاء الدالة renderSavedList(r.profiles)
        toast("🗑 " + name);  // استدعاء الدالة toast("🗑 " + name)
      }  // إغلاق الكتلة السابقة
    });  // إغلاق القوس المفتوح في السطر السابق
  });  // إغلاق القوس المفتوح في السطر السابق
}  // إغلاق الكتلة السابقة

function localValidateProfile(p) {  // تعريف الدالة localValidateProfile(p)
  const problems = [];  // تعريف الثابت problems = مصفوفة
  if (!p || typeof p !== "object") return ["url_missing_or_invalid"];  // تنفيذ التعليمة السابقة
  const url = (p.login_url || "").trim();  // تعريف الثابت url = نتيجة استدعاء
  if (!url || !(url.startsWith("http://") || url.startsWith("https://"))) problems.push("url_missing_or_invalid");  // تنفيذ التعليمة السابقة
  if (!p.user_field) problems.push("user_field_missing");  // تنفيذ التعليمة السابقة
  const vlen = (parseInt(p.length || 0, 10) - (p.prefix || "").length - (p.suffix || "").length);  // تعريف الثابت vlen = نتيجة استدعاء
  if (vlen <= 0) problems.push("length_not_bigger_than_prefix_and_suffix");  // تنفيذ التعليمة السابقة
  const charsetSize = new Set((p.charset || "").split("")).size;  // تعريف الثابت charsetSize = قيمة
  if (charsetSize < 2) problems.push("charset_too_small");  // تنفيذ التعليمة السابقة
  if (p.capture_needs_browser_js) problems.push("needs_browser_js");  // تنفيذ التعليمة السابقة
  return problems;  // إرجاع problems;
}  // إغلاق الكتلة السابقة

function fillReviewFromProfile(p) {  // تعريف الدالة fillReviewFromProfile(p)
  if (!p) return;  // تنفيذ التعليمة السابقة
  const rv = (id) => $(id);  // تعريف الثابت rv = نتيجة استدعاء
  if (rv("rv_login_url")) rv("rv_login_url").value = p.login_url || "";  // تنفيذ التعليمة السابقة
  if (rv("rv_method")) rv("rv_method").value = (p.method === "get" ? "get" : "post");  // تنفيذ التعليمة السابقة
  if (rv("rv_user_field")) rv("rv_user_field").value = p.user_field || "username";  // تنفيذ التعليمة السابقة
  if (rv("rv_pass_field")) rv("rv_pass_field").value = p.pass_field || "password";  // تنفيذ التعليمة السابقة
  if (rv("rv_pass_mode")) {  // شرط: rv("rv_pass_mode")
    const keep = p.pass_mode || "empty";  // تعريف الثابت keep = قيمة
    if (S.meta && S.meta.pass_modes) {  // شرط: S.meta && S.meta.pass_modes
      rv("rv_pass_mode").innerHTML = S.meta.pass_modes.map((m) => "<option value='" + esc(m) + "'>" + esc(t("pm_" + m, m)) + "</option>").join("");  // استدعاء الدالة rv("rv_pass_mode").innerHTML = S.meta.pass_)
      rv("rv_pass_mode").value = S.meta.pass_modes.includes(keep) ? keep : "empty";  // تنفيذ التعليمة السابقة
    } else {  // فرع else
      rv("rv_pass_mode").value = keep;  // تنفيذ التعليمة السابقة
    }  // إغلاق الكتلة السابقة
  }  // إغلاق الكتلة السابقة
  if (rv("rv_dst")) rv("rv_dst").value = p.dst_value || "";  // تنفيذ التعليمة السابقة
  if (rv("rv_prefix")) rv("rv_prefix").value = p.prefix || "";  // تنفيذ التعليمة السابقة
  if (rv("rv_length")) rv("rv_length").value = p.length || 10;  // تنفيذ التعليمة السابقة
  if (rv("rv_charset")) rv("rv_charset").value = p.charset || "0123456789";  // تنفيذ التعليمة السابقة
  if (rv("rv_delay")) rv("rv_delay").value = parseInt(p.safe_delay_ms || 0, 10) || 0;  // تنفيذ التعليمة السابقة
  if (rv("rv_threads")) rv("rv_threads").value = 12;  // تنفيذ التعليمة السابقة
  if (rv("rv_attempts")) rv("rv_attempts").value = 2000;  // تنفيذ التعليمة السابقة
  if (rv("rv_resume")) rv("rv_resume").checked = true;  // تنفيذ التعليمة السابقة
  fillFormFromProfile(p);  // استدعاء الدالة fillFormFromProfile(p)
}  // إغلاق الكتلة السابقة

function profileFromReview() {  // تعريف الدالة profileFromReview()
  const get = (id) => ($(id) ? $(id).value : "");  // تعريف الثابت get = نتيجة استدعاء
  const base = S.profile || {};  // تعريف الثابت base = قيمة
  const p = Object.assign({}, base, {  // تعريف الثابت p = قيمة
    login_url: get("rv_login_url").trim(),  // مفتاح login_url في الكائن = نتيجة استدعاء
    method: get("rv_method") || "post",  // مفتاح method في الكائن = قيمة
    user_field: get("rv_user_field").trim() || "username",  // مفتاح user_field في الكائن = قيمة
    pass_field: get("rv_pass_field").trim() || "password",  // مفتاح pass_field في الكائن = قيمة
    pass_mode: get("rv_pass_mode") || base.pass_mode || "empty",  // مفتاح pass_mode في الكائن = قيمة
    dst_value: get("rv_dst").trim(),  // مفتاح dst_value في الكائن = نتيجة استدعاء
    prefix: get("rv_prefix").trim(),  // مفتاح prefix في الكائن = نتيجة استدعاء
    length: parseInt(get("rv_length") || "10", 10),  // مفتاح length في الكائن = نتيجة استدعاء
    charset: get("rv_charset").trim() || "0123456789",  // مفتاح charset في الكائن = قيمة
    suffix: base.suffix || "",  // مفتاح suffix في الكائن = قيمة
    send_dst: base.send_dst !== false,  // مفتاح send_dst في الكائن = قيمة
    send_popup: base.send_popup !== false,  // مفتاح send_popup في الكائن = قيمة
    extra_fields: base.extra_fields || {},  // مفتاح extra_fields في الكائن = قيمة
    success_words: base.success_words || [],  // مفتاح success_words في الكائن = قيمة
  });  // إغلاق القوس المفتوح في السطر السابق
  return p;  // إرجاع p;
}  // إغلاق الكتلة السابقة

function renderReviewSummary(p) {  // تعريف الدالة renderReviewSummary(p)
  const summary = $("reviewSummaryCard");  // تعريف الثابت summary = نتيجة استدعاء
  const probBox = $("reviewProblemsCard");  // تعريف الثابت probBox = نتيجة استدعاء
  if (!summary) return;  // تنفيذ التعليمة السابقة
  const space = (() => {  // تعريف الثابت space = قيمة
    try {  // بداية try محمية
      const vlen = (p.length || 0) - (p.prefix || "").length - (p.suffix || "").length;  // تعريف الثابت vlen = قيمة
      const cs = new Set((p.charset || "").split("")).size;  // تعريف الثابت cs = قيمة
      if (vlen <= 0 || cs < 2) return 0;  // تنفيذ التعليمة السابقة
      return Math.pow(cs, vlen);  // إرجاع Math.pow(cs, vlen);
    } catch (e) { return 0; }  // تكملة السطر السابق
  })();  // تنفيذ التعليمة السابقة
  const covered = parseInt(p.space_pos || 0, 10) || 0;  // تعريف الثابت covered = قيمة
  const remaining = Math.max(0, space - covered);  // تعريف الثابت remaining = نتيجة استدعاء
  summary.innerHTML = "<h4>" + esc(t("profile_summary")) + " — " + esc(p.name || "") + "</h4>" +  // إسناد نص إلى summary.innerHTML
    "<dl class='kv'>" +  // تكملة السطر السابق
    "<dt>" + esc(t("f_login_url")) + "</dt><dd>" + esc(p.login_url || "—") + "</dd>" +  // تكملة السطر السابق
    "<dt>" + esc(t("f_method")) + "</dt><dd>" + esc((p.method || "post").toUpperCase()) + "</dd>" +  // تكملة السطر السابق
    "<dt>" + esc(t("f_user_field")) + "</dt><dd>" + esc(p.user_field || "—") + "</dd>" +  // تكملة السطر السابق
    "<dt>" + esc(t("f_pass_field")) + "</dt><dd>" + esc(p.pass_field || "—") + "</dd>" +  // تكملة السطر السابق
    "<dt>" + esc(t("f_pass_mode")) + "</dt><dd>" + esc(t("pm_" + (p.pass_mode || "empty"), p.pass_mode || "empty")) + "</dd>" +  // تكملة السطر السابق
    "<dt>" + esc(t("f_dst")) + "</dt><dd>" + esc(p.dst_value || "—") + "</dd>" +  // تكملة السطر السابق
    "<dt>" + esc(t("f_prefix")) + "</dt><dd>" + esc(p.prefix || "—") + "</dd>" +  // تكملة السطر السابق
    "<dt>" + esc(t("f_length")) + "</dt><dd>" + esc(String(p.length || "—")) + "</dd>" +  // تكملة السطر السابق
    "<dt>" + esc(t("f_charset")) + "</dt><dd>" + esc((p.charset || "").slice(0, 80)) + " (" + (new Set((p.charset || "").split("")).size) + ")</dd>" +  // تكملة السطر السابق
    "<dt>" + esc(t("p_space")) + "</dt><dd>" + fmtSpace(space) + "</dd>" +  // تكملة السطر السابق
    "<dt>" + esc(t("p_covered")) + "</dt><dd>" + fmtSpace(covered) + (space ? " / " + fmtSpace(space) : "") +  // تكملة السطر السابق
      (space ? " · left " + fmtSpace(remaining) : "") + "</dd>" +  // تكملة السطر السابق
    "</dl>";  // تنفيذ التعليمة السابقة
  const problems = localValidateProfile(p);  // تعريف الثابت problems = نتيجة استدعاء
  if (problems.length) {  // شرط: problems.length
    probBox.classList.remove("hidden");  // استدعاء الدالة probBox.classList.remove("hidden")
    probBox.innerHTML = "<h4 class='bad'>" + esc(t("profile_invalid")) + "</h4><p class='warn'>" + esc(t("profile_invalid_hint")) + "</p><div>" + problems.map((pr) => "• " + esc(t("prob_" + pr, pr))).join("<br>") + "</div>";  // إسناد نص إلى probBox.innerHTML
  } else {  // فرع else
    probBox.classList.remove("hidden");  // استدعاء الدالة probBox.classList.remove("hidden")
    probBox.innerHTML = "<h4 class='ok'>" + esc(t("profile_valid")) + "</h4>";  // إسناد نص إلى probBox.innerHTML
  }  // إغلاق الكتلة السابقة
  previewReviewFormat();  // استدعاء الدالة previewReviewFormat()
  updateLoadWarnings(p, $("rv_threads") ? parseInt($("rv_threads").value || "12", 10) : 12,  // عنصر في القائمة/الكائن (يتبعه المزيد)
                     $("rvLoadWarn"));  // استدعاء الدالة $("rvLoadWarn"))
}  // إغلاق الكتلة السابقة

let reviewPreviewTimer = null;  // تعريف المتغير القابل للتغيير reviewPreviewTimer = null
function previewReviewFormat() {  // تعريف الدالة previewReviewFormat()
  clearTimeout(reviewPreviewTimer);  // استدعاء الدالة clearTimeout(reviewPreviewTimer)
  reviewPreviewTimer = setTimeout(async () => {  // إسناد قيمة إلى reviewPreviewTimer
    if (!$("rvPvSpace")) return;  // تنفيذ التعليمة السابقة
    const p = profileFromReview();  // تعريف الثابت p = نتيجة استدعاء
    const res = await api("/api/format/preview", { profile: p });  // تعريف الثابت res = نتيجة استدعاء
    if (!res.ok) return;  // تنفيذ التعليمة السابقة
    $("rvPvSpace").textContent = fmtSpace(res.space);  // استدعاء الدالة $("rvPvSpace").textContent = fmtSpace(res.)
    $("rvPvSamples").innerHTML = (res.samples || [])  // استدعاء الدالة $("rvPvSamples").innerHTML = (res.samples )
      .map((c) => "<span class='sample'>" + esc(c) + "</span>").join("") || "—";  // تنفيذ التعليمة السابقة
    const box = $("rvPvProblems");  // تعريف الثابت box = نتيجة استدعاء
    if (box) {  // شرط: box
      const hard = (res.problems || []).filter((x) => x !== "space_is_astronomically_big");  // تعريف الثابت hard = نتيجة استدعاء
      box.classList.toggle("hidden", !hard.length);  // استدعاء الدالة box.classList.toggle("hidden", !hard.length)
      box.innerHTML = hard.map((x) => "• " + t("prob_" + x, x)).join("<br>");  // إسناد نتيجة استدعاء إلى box.innerHTML
    }  // إغلاق الكتلة السابقة
    updateLoadWarnings(p, parseInt(($("rv_threads") || {}).value || "12", 10),  // عنصر في القائمة/الكائن (يتبعه المزيد)
                       $("rvLoadWarn"), res.space);  // استدعاء الدالة $("rvLoadWarn"), res.space)
  }, 350);  // تنفيذ التعليمة السابقة
}  // إغلاق الكتلة السابقة

function updateLoadWarnings(profile, threads, node, space) {  // تعريف الدالة updateLoadWarnings(profile, threads, node, space)
  if (!node) return;  // تنفيذ التعليمة السابقة
  const warnSpace = (S.meta && S.meta.defaults && S.meta.defaults.warn_space) || 1e9;  // تعريف الثابت warnSpace = قيمة
  const warnThreads = (S.meta && S.meta.defaults && S.meta.defaults.warn_threads) || 50;  // تعريف الثابت warnThreads = قيمة
  let spaceVal = space;  // تعريف المتغير القابل للتغيير spaceVal = قيمة
  if (spaceVal == null && profile) {  // شرط: spaceVal == null && profile
    try {  // بداية try محمية
      const vlen = (profile.length || 0) - (profile.prefix || "").length -  // تعريف الثابت vlen = قيمة
                   (profile.suffix || "").length;  // تنفيذ التعليمة السابقة
      const cs = new Set((profile.charset || "").split("")).size;  // تعريف الثابت cs = قيمة
      spaceVal = (vlen > 0 && cs >= 2) ? Math.pow(cs, vlen) : 0;  // إسناد قيمة إلى spaceVal
    } catch (e) { spaceVal = 0; }  // تكملة السطر السابق
  }  // إغلاق الكتلة السابقة
  const msgs = [];  // تعريف الثابت msgs = مصفوفة
  if (spaceVal > warnSpace) msgs.push(t("warn_big_space"));  // تنفيذ التعليمة السابقة
  if ((threads || 0) > warnThreads) msgs.push(t("warn_many_threads"));  // تنفيذ التعليمة السابقة
  node.classList.toggle("hidden", !msgs.length);  // استدعاء الدالة node.classList.toggle("hidden", !msgs.length)
  node.innerHTML = msgs.map((m) => "⚠ " + esc(m)).join("<br>");  // إسناد نتيجة استدعاء إلى node.innerHTML
}  // إغلاق الكتلة السابقة


/* after a run the engine has saved how far it got - pull it back so the
   "continue where you stopped" checkbox has something to continue from */
async function refreshProfiles() {  // تكملة السطر السابق
  const r = await api("/api/profiles");  // تعريف الثابت r = نتيجة استدعاء
  if (!r.ok) return;  // تنفيذ التعليمة السابقة
  renderProfiles(r.profiles || []);  // استدعاء الدالة renderProfiles(r.profiles || [])
  const name = (S.profile || {}).name;  // تعريف الثابت name = قيمة
  if (!name) return;  // تنفيذ التعليمة السابقة
  const fresh = (r.profiles || []).find((p) => p.name === name);  // تعريف الثابت fresh = نتيجة استدعاء
  if (fresh) {  // شرط: fresh
    S.profile = Object.assign({}, S.profile,  // إسناد قيمة إلى S.profile
      { space_pos: fresh.covered || 0, space: fresh.space || 0 });  // تنفيذ التعليمة السابقة
    showCovered(S.profile);  // استدعاء الدالة showCovered(S.profile)
  }  // إغلاق الكتلة السابقة
}  // إغلاق الكتلة السابقة

async function loadProfile(name) {  // تكملة السطر السابق
  if (!name) return;  // تنفيذ التعليمة السابقة
  const r = await api("/api/profiles/get?name=" + encodeURIComponent(name));  // تعريف الثابت r = نتيجة استدعاء
  if (r.ok && r.profile) {  // شرط: r.ok && r.profile
    fillFormFromProfile(r.profile);  // استدعاء الدالة fillFormFromProfile(r.profile)
    toast("📂 " + name);  // استدعاء الدالة toast("📂 " + name)
  } else { toast(t("scan_fail")); }  // تكملة السطر السابق
}  // إغلاق الكتلة السابقة

function toggleCustomCharset() {  // تعريف الدالة toggleCustomCharset()
  $("f_customWrap").classList.toggle("hidden", $("f_charset").value !== "_custom");  // استدعاء الدالة $("f_customWrap").classList.toggle("hidden)
}  // إغلاق الكتلة السابقة

/* ------------------------------------------------------------------ scan */
async function doScan() {  // تكملة السطر السابق
  const url = $("scanUrl").value.trim();  // تعريف الثابت url = نتيجة استدعاء
  if (!url) return;  // تنفيذ التعليمة السابقة
  S.scanReady = false;  // إسناد قيمة منطقية إلى S.scanReady
  S.calibrationReady = false;  // إسناد قيمة منطقية إلى S.calibrationReady
  S.calibrationSignature = "";  // إسناد نص إلى S.calibrationSignature
  $("calibrateBtn").disabled = true;  // تنفيذ التعليمة السابقة
  $("toFormat").disabled = true;  // تنفيذ التعليمة السابقة
  $("calibCard").classList.add("hidden");  // استدعاء الدالة $("calibCard").classList.add("hidden")
  $("scanBtn").disabled = true; $("scanBtn").textContent = t("loading");  // استدعاء الدالة $("scanBtn").disabled = true; $("scanBtn"))
  const res = await api("/api/scan", { url });  // تعريف الثابت res = نتيجة استدعاء
  $("scanBtn").disabled = false; $("scanBtn").textContent = t("scan_button");  // استدعاء الدالة $("scanBtn").disabled = false; $("scanBtn")
  const card = $("portalCard"); const net = $("internetCard");  // تعريف الثابت card = نتيجة استدعاء
  card.classList.remove("hidden"); net.classList.remove("hidden");  // استدعاء الدالة card.classList.remove("hidden"); net.classList.remove("hidden")

  if (!res.ok) {  // شرط: !res.ok
    card.innerHTML = '<h4 class="bad">' + t("scan_fail") + "</h4>" +  // إسناد نص إلى card.innerHTML
      '<div class="kv"><dt>' + (res.hint || "") + "</dt><dd>" + esc(res.detail || res.error) + "</dd></div>";  // تنفيذ التعليمة السابقة
    net.classList.add("hidden");  // استدعاء الدالة net.classList.add("hidden")
    $("toFormat").disabled = true;  // تنفيذ التعليمة السابقة
    return;  // إرجاع ;
  }  // إغلاق الكتلة السابقة
  S.portal = res.portal;  // إسناد قيمة إلى S.portal
  S.scannedUrl = url;  // إسناد قيمة إلى S.scannedUrl
  S.scanReady = true;  // إسناد قيمة منطقية إلى S.scanReady
  $("calibrateBtn").disabled = !$("f_known").value.trim();  // استدعاء الدالة $("calibrateBtn").disabled = !$("f_known"))
  renderInternet(res.internet, net);  // استدعاء الدالة renderInternet(res.internet, net)

  const f = res.portal.form || {};  // تعريف الثابت f = قيمة
  card.innerHTML =  // تكملة السطر السابق
    "<h4>" + t("detected") + "</h4><dl class='kv'>" +  // تكملة السطر السابق
    "<dt>" + t("form_action") + "</dt><dd>" + esc(f.action) + "</dd>" +  // تكملة السطر السابق
    "<dt>" + t("form_method") + "</dt><dd>" + esc((f.method || "").toUpperCase()) +  // تكملة السطر السابق
      " · " + res.ms + " ms · HTTP " + res.portal.status + "</dd>" +  // تكملة السطر السابق
    "<dt>" + t("user_field") + "</dt><dd>" + esc(f.user_field || "—") + "</dd>" +  // تكملة السطر السابق
    "<dt>" + t("pass_field") + "</dt><dd>" + esc(f.pass_field || "—") + "</dd>" +  // تكملة السطر السابق
    "<dt>" + t("extra_fields") + "</dt><dd>" +  // تكملة السطر السابق
      esc(Object.entries(f.extra_fields || {}).map(([k, v]) => k + "=" + v).join("  ") || "—") +  // تكملة السطر السابق
    "</dd><dt>" + t("dst_values") + "</dt><dd>" +  // تكملة السطر السابق
      esc((res.portal.dst_candidates || []).join("  |  ") || "—") + "</dd>" +  // تكملة السطر السابق
    (f.chap ? "<dt class='ok'>" + t("chap_detected") + "</dt><dd>" + t("chap_hint") + "</dd>" : "") +  // تكملة السطر السابق
    "</dl>" +  // تكملة السطر السابق
    (f.all_fields && f.all_fields.length ? "" :  // تكملة السطر السابق
      "<div class='warn'>" + t("no_form") + "</div>");  // تنفيذ التعليمة السابقة

  /* auto-fill the format step with what the page told us */
  $("f_login_url").value = f.action || res.portal.url;  // تنفيذ التعليمة السابقة
  $("f_method").value = (f.method || "post").toLowerCase() === "get" ? "get" : "post";  // تنفيذ التعليمة السابقة
  $("f_user_field").value = f.user_field || "username";  // تنفيذ التعليمة السابقة
  $("f_pass_field").value = f.pass_field || "password";  // تنفيذ التعليمة السابقة
  const detectedFields = new Set(f.all_fields || []);  // تعريف الثابت detectedFields = نتيجة استدعاء
  $("f_send_dst").checked = detectedFields.has(f.dst_field);  // استدعاء الدالة $("f_send_dst").checked = detectedFields.h)
  $("f_send_popup").checked = detectedFields.has(f.popup_field);  // استدعاء الدالة $("f_send_popup").checked = detectedFields)
  const dsts = res.portal.dst_candidates || [];  // تعريف الثابت dsts = قيمة
  $("f_dst").value = dsts.find((d) => d) || "";  // تنفيذ التعليمة السابقة
  if (f.chap) $("f_pass_mode").value = "chap";  // تنفيذ التعليمة السابقة
  if (!($("f_extra").value)) {  // شرط: !($("f_extra").value)
    $("f_extra").value = Object.entries(f.extra_fields || {})  // استدعاء الدالة $("f_extra").value = Object.entries(f.extr)
      .map(([k, v]) => k + "=" + v).join(", ");  // استدعاء الدالة .map(([k, v]) => k + "=" + v).join(", ")
  }  // إغلاق الكتلة السابقة
  if (!($("f_name").value)) {  // شرط: !($("f_name").value)
    try { $("f_name").value = new URL(res.portal.url).hostname; }  // تكملة السطر السابق
    catch (e) { $("f_name").value = "profile"; }  // تكملة السطر السابق
  }  // إغلاق الكتلة السابقة
  /* a network we scanned before: load its saved profile, so a run can
     continue where it stopped instead of starting over */
  const same = ((S.meta || {}).profiles || []).find((p) => p.name === $("f_name").value);  // تعريف الثابت same = نتيجة استدعاء
  if (same) await loadProfile(same.name);  // تنفيذ التعليمة السابقة
  else { S.profile = null; showCovered(null); }  // تكملة السطر السابق
  $("toFormat").disabled = true;  // تنفيذ التعليمة السابقة
  $("calibrateBtn").disabled = !$("f_known").value.trim();  // استدعاء الدالة $("calibrateBtn").disabled = !$("f_known"))
  previewFormat();  // استدعاء الدالة previewFormat()
}  // إغلاق الكتلة السابقة

function renderInternet(info, node) {  // تعريف الدالة renderInternet(info, node)
  if (!info) { node.classList.add("hidden"); return; }  // تكملة السطر السابق
  const state = info.state || "OFFLINE";  // تعريف الثابت state = قيمة
  const cls = state === "ONLINE" ? "ok" : (state === "WALLED" ? "warn" : "bad");  // تعريف الثابت cls = نتيجة استدعاء
  node.classList.remove("hidden");  // استدعاء الدالة node.classList.remove("hidden")
  node.innerHTML = "<h4 class='" + cls + "'>" + t("internet_" + state) + "</h4>" +  // إسناد نص إلى node.innerHTML
    "<div class='kv'><dt>" + t("internet_detail_" + (info.detail || ""),  // عنصر في القائمة/الكائن (يتبعه المزيد)
                               t("net_" + (info.detail || ""), info.detail || "")) +  // تكملة السطر السابق
    "</dt><dd>" + esc(info.url || "") + (info.location ? " → " + esc(info.location) : "") +  // تكملة السطر السابق
    "</dd></div>";  // تنفيذ التعليمة السابقة
  const banner = $("onlineAlreadyWarn");  // تعريف الثابت banner = نتيجة استدعاء
  if (banner) {  // شرط: banner
    if (state === "ONLINE") {  // شرط: state === "ONLINE"
      banner.classList.remove("hidden");  // استدعاء الدالة banner.classList.remove("hidden")
      banner.innerHTML = "⚠ " + esc(t("online_already_banner"));  // إسناد نص إلى banner.innerHTML
    } else {  // فرع else
      banner.classList.add("hidden");  // استدعاء الدالة banner.classList.add("hidden")
    }  // إغلاق الكتلة السابقة
  }  // إغلاق الكتلة السابقة
}  // إغلاق الكتلة السابقة

/* ------------------------------------------------------------------ preview */
let previewTimer = null;  // تعريف المتغير القابل للتغيير previewTimer = null
function previewFormat() {  // تعريف الدالة previewFormat()
  clearTimeout(previewTimer);  // استدعاء الدالة clearTimeout(previewTimer)
  previewTimer = setTimeout(async () => {  // إسناد قيمة إلى previewTimer
    const res = await api("/api/format/preview", { profile: profileFromForm() });  // تعريف الثابت res = نتيجة استدعاء
    if (!res.ok) return;  // تنفيذ التعليمة السابقة
    $("pvSpace").textContent = fmtSpace(res.space);  // استدعاء الدالة $("pvSpace").textContent = fmtSpace(res.sp)
    $("pvSamples").innerHTML = (res.samples || [])  // استدعاء الدالة $("pvSamples").innerHTML = (res.samples ||)
      .map((c) => "<span class='sample'>" + esc(c) + "</span>").join("");  // استدعاء الدالة .map((c) => "<span class='sample'>" + esc(c) )
    const shape = res.request_shape;  // تعريف الثابت shape = قيمة
    if (shape) {  // شرط: shape
      const body = (shape.body_field_names || []).length  // تعريف الثابت body = قيمة
        ? " · body fields: " + shape.body_field_names.join(", ") : "";  // تنفيذ التعليمة السابقة
      $("pvRequest").textContent = shape.method + " " + shape.url + body;  // تنفيذ التعليمة السابقة
    } else {  // فرع else
      $("pvRequest").textContent = "—";  // تنفيذ التعليمة السابقة
    }  // إغلاق الكتلة السابقة
    const box = $("pvProblems");  // تعريف الثابت box = نتيجة استدعاء
    const hard = (res.problems || []).filter((p) => p !== "space_is_astronomically_big");  // تعريف الثابت hard = نتيجة استدعاء
    box.classList.toggle("hidden", !hard.length);  // استدعاء الدالة box.classList.toggle("hidden", !hard.length)
    box.innerHTML = hard.map((p) => "• " + t("prob_" + p, p)).join("<br>");  // إسناد نتيجة استدعاء إلى box.innerHTML
  }, 350);  // تنفيذ التعليمة السابقة
}  // إغلاق الكتلة السابقة

/* ------------------------------------------------------------------ jobs */
async function waitJob(jobId, onTick) {  // تكملة السطر السابق
  /* never spin forever: 240 x 0.7s ~ 2.8 minutes is well past every job we run */
  for (let i = 0; i < 240; i++) {  // حلقة تكرار: let i = 0; i < 240; i++
    await new Promise((r) => setTimeout(r, 700));  // تنفيذ التعليمة السابقة
    const res = await api("/api/job?id=" + encodeURIComponent(jobId));  // تعريف الثابت res = نتيجة استدعاء
    if (!res.ok) return null;  // تنفيذ التعليمة السابقة
    if (onTick) onTick(res.job);  // تنفيذ التعليمة السابقة
    if (res.job.state !== "running") return res.job;  // تنفيذ التعليمة السابقة
  }  // إغلاق الكتلة السابقة
  return { state: "error", error: t("job_timeout"), result: {} };  // إرجاع { state: "error", error: t("job_timeout"), result: {} };
}  // إغلاق الكتلة السابقة

async function startCapture() {  // تكملة السطر السابق
  const url = ($("f_login_url").value.trim() || $("scanUrl").value.trim());  // تعريف الثابت url = نتيجة استدعاء
  if (!url) { toast(t("scan_fail")); return; }  // تكملة السطر السابق
  /* Open synchronously inside the click gesture. Opening only after awaiting
     the API is blocked by many mobile browsers' popup protections. */
  const popup = window.open("about:blank", "kp-capture");  // تعريف الثابت popup = نتيجة استدعاء
  if (!popup) {  // شرط: !popup
    modal(t("capture_fail"), "<p>" + esc(t("capture_popup_blocked")) + "</p>");  // استدعاء الدالة modal(t("capture_fail"), "<p>" + esc(t("captur)
    return;  // إرجاع ;
  }  // إغلاق الكتلة السابقة
  try {  // بداية try محمية
    popup.document.title = "KiraPass — " + t("loading");  // إسناد نص إلى popup.document.title
    popup.document.body.textContent = t("loading");  // إسناد نتيجة استدعاء إلى popup.document.body.textContent
  } catch (e) { /* navigating below still works if the browser isolates it */ }  // تكملة السطر السابق
  const box = $("captureCard");  // تعريف الثابت box = نتيجة استدعاء
  if (box) {  // شرط: box
    box.classList.remove("hidden");  // استدعاء الدالة box.classList.remove("hidden")
    box.innerHTML = "<p>" + esc(t("capture_hint")) + "</p>";  // إسناد نص إلى box.innerHTML
  }  // إغلاق الكتلة السابقة
  const res = await api("/api/capture/start", { url });  // تعريف الثابت res = نتيجة استدعاء
  if (!res.ok) {  // شرط: !res.ok
    popup.close();  // استدعاء الدالة popup.close()
    modal(t("capture_fail"), "<pre>" + esc(JSON.stringify(res, null, 2)) + "</pre>");  // استدعاء الدالة modal(t("capture_fail"), "<pre>" + esc(JSON.st)
    return;  // إرجاع ;
  }  // إغلاق الكتلة السابقة
  const view = res.view || ("/capture/view?id=" + encodeURIComponent(res.id));  // تعريف الثابت view = نتيجة استدعاء
  popup.location.replace(withToken(view));  // استدعاء الدالة popup.location.replace(withToken(view))
  toast(t("capture_opened"));  // استدعاء الدالة toast(t("capture_opened"))
}  // إغلاق الكتلة السابقة

async function runCalibration() {  // تكملة السطر السابق
  const btn = $("calibrateBtn");  // تعريف الثابت btn = نتيجة استدعاء
  const card = $("calibCard");  // تعريف الثابت card = نتيجة استدعاء
  const known = $("f_known").value.trim();  // تعريف الثابت known = نتيجة استدعاء
  if (!S.scanReady || !known) {  // شرط: !S.scanReady || !known
    toast(t("calibration_required"));  // استدعاء الدالة toast(t("calibration_required"))
    return;  // إرجاع ;
  }  // إغلاق الكتلة السابقة
  btn.disabled = true;  // إسناد قيمة منطقية إلى btn.disabled
  S.calibrationReady = false;  // إسناد قيمة منطقية إلى S.calibrationReady
  S.calibrationSignature = "";  // إسناد نص إلى S.calibrationSignature
  $("toFormat").disabled = true;  // تنفيذ التعليمة السابقة
  card.classList.remove("hidden");  // استدعاء الدالة card.classList.remove("hidden")
  card.innerHTML = "<h4>" + t("loading") + "</h4>";  // إسناد نص إلى card.innerHTML
  const res = await api("/api/calibrate", {  // تعريف الثابت res = قيمة
    profile: calibrationProfileFromForm(known), known_card: known,  // مفتاح profile في الكائن = قيمة
  });  // إغلاق القوس المفتوح في السطر السابق
  if (!res.ok) {  // شرط: !res.ok
    card.innerHTML = "<div class='bad'>" + esc(res.error) + "</div>";  // إسناد نص إلى card.innerHTML
    btn.disabled = !S.scanReady || !known;  // إسناد قيمة إلى btn.disabled
    return;  // إرجاع ;
  }  // إغلاق الكتلة السابقة
  const job = await waitJob(res.job.id);  // تعريف الثابت job = نتيجة استدعاء
  if (!job) {  // شرط: !job
    card.innerHTML = "<div class='bad'>job lost</div>";  // إسناد نص إلى card.innerHTML
    btn.disabled = !S.scanReady || !known;  // إسناد قيمة إلى btn.disabled
    return;  // إرجاع ;
  }  // إغلاق الكتلة السابقة
  renderCalibration(job, card);  // استدعاء الدالة renderCalibration(job, card)
  const result = job.result || {};  // تعريف الثابت result = قيمة
  if (job.state !== "error" && result.ok && result.applied_settings &&  // تكملة السطر السابق
      result.tuned && result.tuned.verified) {  // تكملة السطر السابق
    applyCalibrationSettings(result.applied_settings, known);  // استدعاء الدالة applyCalibrationSettings(result.applied_settings, known)
    S.calibrationReady = true;  // إسناد قيمة منطقية إلى S.calibrationReady
    S.calibrationSignature = requestSettingsSignature(profileFromForm());  // إسناد نتيجة استدعاء إلى S.calibrationSignature
    $("toFormat").disabled = false;  // تنفيذ التعليمة السابقة
    S.knownCard = known;  // إسناد قيمة إلى S.knownCard
    toast(t("calibration_applied"));  // استدعاء الدالة toast(t("calibration_applied"))
  } else {  // فرع else
    S.calibrationReady = false;  // إسناد قيمة منطقية إلى S.calibrationReady
    $("toFormat").disabled = true;  // تنفيذ التعليمة السابقة
  }  // إغلاق الكتلة السابقة
  btn.disabled = !S.scanReady || !known;  // إسناد قيمة إلى btn.disabled
}  // إغلاق الكتلة السابقة

function applyCalibrationSettings(settings, knownCard) {  // تعريف الدالة applyCalibrationSettings(settings, knownCard)
  if ((!S.profile || !S.profile.length) && knownCard)  // شرط: (!S.profile || !S.profile.length) && knownCard
    $("f_length").value = String(knownCard.length);  // استدعاء الدالة $("f_length").value = String(knownCard.len)
  if (settings.login_url) $("f_login_url").value = settings.login_url;  // تنفيذ التعليمة السابقة
  if (settings.method) $("f_method").value = settings.method.toLowerCase();  // تنفيذ التعليمة السابقة
  if (settings.user_field) $("f_user_field").value = settings.user_field;  // تنفيذ التعليمة السابقة
  if (settings.pass_field) $("f_pass_field").value = settings.pass_field;  // تنفيذ التعليمة السابقة
  if (settings.pass_mode && $("f_pass_mode").querySelector(  // تكملة السطر السابق
      "option[value='" + settings.pass_mode + "']"))  // تكملة السطر السابق
    $("f_pass_mode").value = settings.pass_mode;  // تنفيذ التعليمة السابقة
  if (settings.dst_value != null) $("f_dst").value = settings.dst_value;  // تنفيذ التعليمة السابقة
  $("f_send_dst").checked = !!settings.send_dst;  // تنفيذ التعليمة السابقة
  $("f_send_popup").checked = !!settings.send_popup;  // تنفيذ التعليمة السابقة
  if (settings.extra_field_names && settings.extra_field_names.length) {  // شرط: settings.extra_field_names && settings.extra_field_names.length
    const extras = {};  // تعريف الثابت extras = كائن
    ($("f_extra").value || "").split(",").forEach((part) => {  // تكملة السطر السابق
      const i = part.indexOf("=");  // تعريف الثابت i = نتيجة استدعاء
      if (i > 0) extras[part.slice(0, i).trim()] = part.slice(i + 1).trim();  // تنفيذ التعليمة السابقة
    });  // إغلاق القوس المفتوح في السطر السابق
    settings.extra_field_names.forEach((name) => {  // تكملة السطر السابق
      if (!(name in extras)) extras[name] = "";  // تنفيذ التعليمة السابقة
    });  // إغلاق القوس المفتوح في السطر السابق
    $("f_extra").value = Object.entries(extras)  // استدعاء الدالة $("f_extra").value = Object.entries(extras)
      .map(([key, value]) => key + "=" + value).join(", ");  // استدعاء الدالة .map(([key, value]) => key + "=" + value).joi)
  }  // إغلاق الكتلة السابقة
  if (S.portal && settings.field_names) {  // شرط: S.portal && settings.field_names
    S.portal.form = Object.assign({}, S.portal.form || {}, {  // إسناد قيمة إلى S.portal.form
      action: settings.login_url || S.portal.form.action,  // مفتاح action في الكائن = قيمة
      method: settings.method || S.portal.form.method,  // مفتاح method في الكائن = قيمة
      user_field: settings.user_field || S.portal.form.user_field,  // مفتاح user_field في الكائن = قيمة
      pass_field: settings.pass_field || S.portal.form.pass_field,  // مفتاح pass_field في الكائن = قيمة
      dst_field: settings.dst_field || S.portal.form.dst_field,  // مفتاح dst_field في الكائن = قيمة
      popup_field: settings.popup_field || S.portal.form.popup_field,  // مفتاح popup_field في الكائن = قيمة
      all_fields: settings.field_names.slice(),  // مفتاح all_fields في الكائن = نتيجة استدعاء
    });  // إغلاق القوس المفتوح في السطر السابق
  }  // إغلاق الكتلة السابقة
  const profileSettings = Object.assign({}, settings);  // تعريف الثابت profileSettings = نتيجة استدعاء
  delete profileSettings.extra_field_names;  // تنفيذ التعليمة السابقة
  delete profileSettings.field_names;  // تنفيذ التعليمة السابقة
  S.profile = Object.assign({}, S.profile || {}, profileSettings);  // إسناد نتيجة استدعاء إلى S.profile
  previewFormat();  // استدعاء الدالة previewFormat()
}  // إغلاق الكتلة السابقة

function renderCalibration(job, node) {  // تعريف الدالة renderCalibration(job, node)
  if (job.state === "error") {  // شرط: job.state === "error"
    node.innerHTML = "<h4 class='bad'>" + esc(job.error) + "</h4>";  // إسناد نص إلى node.innerHTML
    return;  // إرجاع ;
  }  // إغلاق الكتلة السابقة
  const r = job.result || {};  // تعريف الثابت r = قيمة
  let html = "<h4>" + (r.ok ? t("cal_known_card_works") : t("scan_fail")) + "</h4>";  // تعريف المتغير القابل للتغيير html = نص

  const fp = r.fingerprint;  // تعريف الثابت fp = قيمة
  if (fp) {  // شرط: fp
    html += "<div class='kv'><dt>" + t("cal_rejection_baseline") + "</dt><dd>" +  // تكملة السطر السابق
      (fp.exact ? t("exact_mode") : t("shape_mode")) + " · " +  // تكملة السطر السابق
      t("dyn_tokens") + ": " + fp.dynamic_tokens + " · HTTP " + fp.reject_status +  // تكملة السطر السابق
      " · " + fp.reject_length + " bytes</dd></div>";  // تنفيذ التعليمة السابقة
  }  // إغلاق الكتلة السابقة
  html += "<ul style='margin:.4rem 0 0;padding-inline-start:1.1rem'>";  // تنفيذ التعليمة السابقة
  (r.steps || []).forEach((s) => {  // تكملة السطر السابق
    const mark = s.ok ? "✔" : "✖";  // تعريف الثابت mark = قيمة
    const cls = s.ok ? "ok" : "warn";  // تعريف الثابت cls = قيمة
    let extra = "";  // تعريف المتغير القابل للتغيير extra = نص
    const d = s.detail || {};  // تعريف الثابت d = قيمة
    if (s.id === "internet_state" && d.state) extra = " — " + t("internet_" + d.state);  // تنفيذ التعليمة السابقة
    if (s.id === "reach_login_page" && d.ms) extra = " — HTTP " + d.status + " · " + d.ms + " ms";  // تنفيذ التعليمة السابقة
    if (s.id === "shape_tuned" && d.tuned) {  // شرط: s.id === "shape_tuned" && d.tuned
      const trial = d.tuned.trial || {};  // تعريف الثابت trial = قيمة
      extra = " — " + t("pm_" + d.tuned.mode, d.tuned.mode) +  // إسناد نص إلى extra
              (d.tuned.method ? " · " + d.tuned.method : "") +  // تكملة السطر السابق
              (trial.url ? " · " + trial.url : "") +  // تكملة السطر السابق
              (d.tuned.dst ? " · dst=" + d.tuned.dst : "");  // تنفيذ التعليمة السابقة
    }  // إغلاق الكتلة السابقة
    if (s.id === "shape_tuned" && d.wrong) extra = " — " + esc(t("prob_" + d.wrong, d.wrong));  // تنفيذ التعليمة السابقة
    html += "<li class='" + cls + "'>" + mark + " " + t("cal_" + s.id, s.id) + ": " +  // تكملة السطر السابق
            t("cal_" + s.reason, s.reason) + esc(extra) + "</li>";  // تنفيذ التعليمة السابقة
  });  // إغلاق القوس المفتوح في السطر السابق
  html += "</ul>";  // تنفيذ التعليمة السابقة
  /* "could not prove the known card" is worthless without what came back */
  (r.steps || []).forEach((s) => {  // تكملة السطر السابق
    const d = s.detail || {};  // تعريف الثابت d = قيمة
    if (s.id !== "shape_tuned" || !d.trials || !d.trials.length) return;  // تنفيذ التعليمة السابقة
    html += "<div class='hint'>" + esc(t("known_card_tried")) + " " + d.tried +  // تكملة السطر السابق
            "</div><table class='why' style='margin-top:4px'><tbody>";  // تنفيذ التعليمة السابقة
    d.trials.forEach((tr) => {  // تكملة السطر السابق
      const net = tr.internet_before || tr.internet_after  // تعريف الثابت net = قيمة
        ? (tr.internet_before || "?") + " → " + (tr.internet_after || "?") +  // تكملة السطر السابق
          (tr.online_transition ? " · " + t("online_transition") : "") : "";  // تنفيذ التعليمة السابقة
      const logout = tr.logout && tr.logout.internet_after  // تعريف الثابت logout = قيمة
        ? " · " + t("logout_state") + " → " + tr.logout.internet_after : "";  // تنفيذ التعليمة السابقة
      const bodyFields = (tr.body_field_names || []).length  // تعريف الثابت bodyFields = قيمة
        ? "<br>body: " + esc(tr.body_field_names.join(", ")) : "";  // تنفيذ التعليمة السابقة
      html += "<tr><td class='mono'>" + esc((tr.method || "") + " " + (tr.mode || "")) +  // تكملة السطر السابق
              (tr.url ? "<br>" + esc(tr.url) : "") + bodyFields + "</td><td>" +  // تكملة السطر السابق
              (tr.status || "—") + (tr.response_bytes ? " · " + tr.response_bytes + " B" : "") +  // تكملة السطر السابق
              "</td><td>" + esc(codeLabel(tr.code)) + "</td><td class='why'>" +  // تكملة السطر السابق
              esc(reasonLabel(tr.code, tr.reason, {})) +  // تكملة السطر السابق
              (tr.word ? " «" + esc(tr.word) + "»" : "") +  // تكملة السطر السابق
              (net ? "<br>" + esc(net) : "") + esc(logout) + "</td></tr>";  // تنفيذ التعليمة السابقة
    });  // إغلاق القوس المفتوح في السطر السابق
    html += "</tbody></table><div class='warn'>" + esc(t("known_card_hint")) + "</div>";  // تنفيذ التعليمة السابقة
  });  // إغلاق القوس المفتوح في السطر السابق
  if (r.success_words && r.success_words.length)  // شرط: r.success_words && r.success_words.length
    html += "<div class='kv'><dt>" + t("f_words") + "</dt><dd>" +  // تكملة السطر السابق
            esc(r.success_words.join(", ")) + "</dd></div>";  // تنفيذ التعليمة السابقة
  if (r.report_file)  // شرط: r.report_file
    html += "<div class='hint'><a target='_blank' rel='noopener' href='" +  // تكملة السطر السابق
      esc(withToken("/api/report?name=" + encodeURIComponent(r.report_file))) + "'>" +  // تكملة السطر السابق
      esc(t("download_calibration_report")) + "</a></div>";  // تنفيذ التعليمة السابقة
  if (r.error) html += "<div class='bad'>" + esc(t("cal_" + r.error, r.error)) + "</div>";  // تنفيذ التعليمة السابقة
  node.innerHTML = html;  // إسناد قيمة إلى node.innerHTML
}  // إغلاق الكتلة السابقة

async function runDiagnose() {  // تكملة السطر السابق
  const btn = $("diagnoseBtn"); btn.disabled = true;  // تعريف الثابت btn = قيمة
  const card = $("diagCard"); card.classList.remove("hidden");  // تعريف الثابت card = نتيجة استدعاء
  card.innerHTML = "<h4>" + t("loading") + "</h4>";  // إسناد نص إلى card.innerHTML
  const res = await api("/api/diagnose", { profile: profileFromForm(),  // تعريف الثابت res = قيمة
                                           threads: parseInt($("r_threads").value || "12", 10) });  // مفتاح threads في الكائن = نتيجة استدعاء
  if (!res.ok) { card.innerHTML = "<div class='bad'>" + esc(res.error) + "</div>"; btn.disabled = false; return; }  // تكملة السطر السابق
  const job = await waitJob(res.job.id);  // تعريف الثابت job = نتيجة استدعاء
  btn.disabled = false;  // إسناد قيمة منطقية إلى btn.disabled
  if (!job) return;  // تنفيذ التعليمة السابقة
  renderDiagnose(job, card);  // استدعاء الدالة renderDiagnose(job, card)
}  // إغلاق الكتلة السابقة

async function runLockoutProbe() {  // تكملة السطر السابق
  if (!window.confirm(t("lockout_confirm"))) return;  // تنفيذ التعليمة السابقة
  const btn = $("lockoutBtn"); btn.disabled = true;  // تعريف الثابت btn = قيمة
  const card = $("lockoutCard"); card.classList.remove("hidden");  // تعريف الثابت card = نتيجة استدعاء
  card.innerHTML = "<h4>" + t("lockout_measuring") + "</h4>";  // إسناد نص إلى card.innerHTML
  const res = await api("/api/lockout", { profile: profileFromForm(),  // تعريف الثابت res = قيمة
                                          max_failures: 8 });  // مفتاح max_failures في الكائن = رقم
  if (!res.ok) {  // شرط: !res.ok
    card.innerHTML = "<div class='bad'>" + esc(res.error) + "</div>";  // إسناد نص إلى card.innerHTML
    btn.disabled = false; return;  // إسناد قيمة إلى btn.disabled
  }  // إغلاق الكتلة السابقة
  const job = await waitJob(res.job.id);  // تعريف الثابت job = نتيجة استدعاء
  btn.disabled = false;  // إسناد قيمة منطقية إلى btn.disabled
  if (!job) return;  // تنفيذ التعليمة السابقة
  renderLockout(job, card);  // استدعاء الدالة renderLockout(job, card)
}  // إغلاق الكتلة السابقة

function renderLockout(job, node) {  // تعريف الدالة renderLockout(job, node)
  if (job.state === "error") {  // شرط: job.state === "error"
    node.innerHTML = "<div class='bad'>" + esc(job.error) + "</div>";  // إسناد نص إلى node.innerHTML
    return;  // إرجاع ;
  }  // إغلاق الكتلة السابقة
  const r = job.result || {};  // تعريف الثابت r = قيمة
  let html = "<h4>" + t("btn_lockout") + "</h4>";  // تعريف المتغير القابل للتغيير html = نص
  if (r.error) {  // شرط: r.error
    html += "<div class='bad mono'>" + esc(r.error) + "</div>" +  // تكملة السطر السابق
            "<div class='warn'>" + esc(t("netadvice_" + r.error, "")) + "</div>";  // تنفيذ التعليمة السابقة
    node.innerHTML = html;  // إسناد قيمة إلى node.innerHTML
    return;  // إرجاع ;
  }  // إغلاق الكتلة السابقة
  if (r.ban_after == null) {  // شرط: r.ban_after == null
    html += "<div class='ok'>" + t("lockout_never", "") + " " +  // تكملة السطر السابق
            esc(String(r.tried || 0)) + "</div>";  // تنفيذ التعليمة السابقة
  } else {  // فرع else
    html += "<div class='bad'>" + t("lockout_after") + ": <b>" + r.ban_after +  // تكملة السطر السابق
            "</b></div>";  // تنفيذ التعليمة السابقة
    html += "<div class='warn'>" + t("lockout_stopped_after_block") + "</div>";  // تنفيذ التعليمة السابقة
  }  // إغلاق الكتلة السابقة
  node.innerHTML = html;  // إسناد قيمة إلى node.innerHTML
}  // إغلاق الكتلة السابقة

function renderDiagnose(job, node) {  // تعريف الدالة renderDiagnose(job, node)
  if (job.state === "error") { node.innerHTML = "<div class='bad'>" + esc(job.error) + "</div>"; return; }  // تكملة السطر السابق
  const r = job.result || {};  // تعريف الثابت r = قيمة
  let html = "<h4>" + t("btn_diagnose") + "</h4><ul style='margin:.2rem 0 0;padding-inline-start:1.1rem'>";  // تعريف المتغير القابل للتغيير html = نص
  (r.steps || []).forEach((s) => {  // تكملة السطر السابق
    let extra = "";  // تعريف المتغير القابل للتغيير extra = نص
    const d = s.detail || {};  // تعريف الثابت d = قيمة
    if (s.id === "internet") extra = " — " + t("internet_" + (d.state || ""));  // تنفيذ التعليمة السابقة
    if (s.id === "sample_single" || s.id === "sample_parallel")  // شرط: s.id === "sample_single" || s.id === "sample_parallel"
      extra = " — " + (d.sent || 0) + " req · " + (d.avg_ms || 0) + " ms · " +  // إسناد نص إلى extra
              (d.error_rate || 0) + "% " + (LANG === "ar" ? "أخطاء" : "errors");  // تنفيذ التعليمة السابقة
    if (s.id === "ban_check") extra = " — " + (d.ban_pages || 0);  // تنفيذ التعليمة السابقة
    html += "<li class='" + (s.ok ? "ok" : "warn") + "'>" +  // تكملة السطر السابق
            (s.ok ? "✔" : "✖") + " " + t("diag_" + s.id, s.id) + ": " +  // تكملة السطر السابق
            t("diag_" + s.reason, t("cal_" + s.reason, s.reason)) + esc(extra) + "</li>";  // تنفيذ التعليمة السابقة
  });  // إغلاق القوس المفتوح في السطر السابق
  html += "</ul>";  // تنفيذ التعليمة السابقة
  (r.advice || []).forEach((a) => {  // تكملة السطر السابق
    html += "<div class='warn'>→ " + t("advice_" + a.reason, a.reason) +  // تكملة السطر السابق
      (a.suggest_threads ? " (" + t("suggest_threads") + ": " + a.suggest_threads + ")" : "") +  // تكملة السطر السابق
      "</div>";  // تنفيذ التعليمة السابقة
  });  // إغلاق القوس المفتوح في السطر السابق
  node.innerHTML = html;  // إسناد قيمة إلى node.innerHTML
}  // إغلاق الكتلة السابقة

/* ------------------------------------------------------------------ run */
async function startRun() {  // تكملة السطر السابق
  if (S.manualResumeRequired) {  // شرط: S.manualResumeRequired
    modal(t("manual_resume_title"), "<p>" +  // تكملة السطر السابق
      esc(t("manual_resume_hint")) + "</p><p>" + esc(t("manual_resume_confirm_body")) + "</p>");  // استدعاء الدالة esc(t("manual_resume_hint")) + "</p><p>" + e)
    return;  // إرجاع ;
  }  // إغلاق الكتلة السابقة
  if (S.currentFlow !== "saved" && !S.savedProfileMode && !S.calibrationReady) {  // شرط: S.currentFlow !== "saved" && !S.savedProfileMode && !S.calibrationRead
    step("scan");  // استدعاء الدالة step("scan")
    modal(t("calibration_required"), "<p>" + esc(t("calibration_required_hint")) + "</p>");  // استدعاء الدالة modal(t("calibration_required"), "<p>" + esc(t)
    return;  // إرجاع ;
  }  // إغلاق الكتلة السابقة
  const profile = profileFromForm();  // تعريف الثابت profile = نتيجة استدعاء
  if (!S.savedProfileMode && S.currentFlow !== "saved") {  // شرط: !S.savedProfileMode && S.currentFlow !== "saved"
    const formatProblem = knownCardFormatProblem($("f_known").value.trim(), profile);  // تعريف الثابت formatProblem = نتيجة استدعاء
    if (formatProblem) {  // شرط: formatProblem
      step("format");  // استدعاء الدالة step("format")
      modal(t("known_card_format_mismatch"), "<p>" +  // تكملة السطر السابق
        esc(t("prob_" + formatProblem + "_mismatch", formatProblem)) + "</p>");  // استدعاء الدالة esc(t("prob_" + formatProblem + "_mismatch",)
      return;  // إرجاع ;
    }  // إغلاق الكتلة السابقة
  }  // إغلاق الكتلة السابقة
  if (!S.savedProfileMode && S.currentFlow !== "saved" && requestSettingsSignature(profile) !== S.calibrationSignature) {  // شرط: !S.savedProfileMode && S.currentFlow !== "saved" && requestSettingsSig
    S.calibrationReady = false;  // إسناد قيمة منطقية إلى S.calibrationReady
    $("toFormat").disabled = true;  // تنفيذ التعليمة السابقة
    step("scan");  // استدعاء الدالة step("scan")
    modal(t("calibration_shape_changed"), "<p>" +  // تكملة السطر السابق
      esc(t("calibration_shape_changed_hint")) + "</p>");  // استدعاء الدالة esc(t("calibration_shape_changed_hint")) + ")
    return;  // إرجاع ;
  }  // إغلاق الكتلة السابقة
  if (profile.capture_needs_browser_js) {  // شرط: profile.capture_needs_browser_js
    modal(t("capture_blocked_title"),  // عنصر في القائمة/الكائن (يتبعه المزيد)
      "<p>" + esc(t("capture_blocked_body")) + "</p><p>" +  // تكملة السطر السابق
      esc(profile.capture_block_reason || t("capture_blocked_next")) + "</p>" +  // تكملة السطر السابق
      "<p class='hint'>" + esc(t("capture_guide_link")) +  // تكملة السطر السابق
      ": docs/GUIDE_" + (LANG === "ar" ? "AR" : "EN") + ".md</p>");  // تنفيذ التعليمة السابقة
    return;  // إرجاع ;
  }  // إغلاق الكتلة السابقة
  const payload = {  // تعريف الثابت payload = كائن
    profile,  // عنصر في القائمة/الكائن (يتبعه المزيد)
    // Reconfirm the proven shape once at run entry; do not tune around failure.
    // preflight_only: true is required for new-profile calibration flow (kept for integrity check)
    known_card: (S.savedProfileMode || S.currentFlow === "saved") ? "" : $("f_known").value.trim(),  // مفتاح known_card في الكائن = نتيجة استدعاء
    preflight_only: true,  // مفتاح preflight_only في الكائن = قيمة منطقية
    attempts: parseInt($("r_attempts").value || "2000", 10),  // مفتاح attempts في الكائن = نتيجة استدعاء
    threads: parseInt($("r_threads").value || "12", 10),  // مفتاح threads في الكائن = نتيجة استدعاء
    delay_ms: parseInt($("r_delay").value || "0", 10),  // مفتاح delay_ms في الكائن = نتيجة استدعاء
    verify: $("r_verify").checked, auto_stop: $("r_autostop").checked,  // مفتاح verify في الكائن = قيمة
    resume: $("r_resume").checked,  // مفتاح resume في الكائن = قيمة
  };  // إغلاق الكتلة السابقة
  if (S.savedProfileMode || S.currentFlow === "saved") {  // شرط: S.savedProfileMode || S.currentFlow === "saved"
    payload.known_card = "";  // إسناد نص إلى payload.known_card
    payload.preflight_only = false;  // إسناد قيمة منطقية إلى payload.preflight_only
  }  // إغلاق الكتلة السابقة
  S.lastStart = payload;  // إسناد قيمة إلى S.lastStart
  const clearanceUsed = S.manualResumeRequired;  // تعريف الثابت clearanceUsed = قيمة
  S.manualResumeRequired = false;  // إسناد قيمة منطقية إلى S.manualResumeRequired
  const res = await api("/api/run/start", payload);  // تعريف الثابت res = نتيجة استدعاء
  if (!res.ok) {  // شرط: !res.ok
    S.manualResumeRequired = clearanceUsed;  // إسناد قيمة إلى S.manualResumeRequired
    modal(t("scan_fail"), "<pre>" + esc(JSON.stringify(res, null, 2)) + "</pre>");  // استدعاء الدالة modal(t("scan_fail"), "<pre>" + esc(JSON.strin)
    return;  // إرجاع ;
  }  // إغلاق الكتلة السابقة
  S.lastSeq = 0; S.rows = 0;  // إسناد رقم إلى S.lastSeq
  $("logBody").innerHTML = ""; $("hitsBox").innerHTML = t("hits_none");  // استدعاء الدالة $("logBody").innerHTML = ""; $("hitsBox").)
  $("reviewBox").innerHTML = t("review_none");  // استدعاء الدالة $("reviewBox").innerHTML = t("review_none")
  $("startBtn").classList.add("hidden");
  setRunStopVisible(true);
  S.running = true;  // إسناد قيمة منطقية إلى S.running
  step("results");  // استدعاء الدالة step("results")
  pollStatus();  // استدعاء الدالة pollStatus()
}  // إغلاق الكتلة السابقة

async function startFromReview() {  // تكملة السطر السابق
  const profile = profileFromReview();  // تعريف الثابت profile = نتيجة استدعاء
  const problems = localValidateProfile(profile);  // تعريف الثابت problems = نتيجة استدعاء
  if (problems.length) {  // شرط: problems.length
    const probBox = $("reviewProblemsCard");  // تعريف الثابت probBox = نتيجة استدعاء
    if (probBox) {  // شرط: probBox
      probBox.classList.remove("hidden");  // استدعاء الدالة probBox.classList.remove("hidden")
      probBox.innerHTML = "<h4 class='bad'>" + esc(t("profile_invalid")) + "</h4><p class='warn'>" + esc(t("profile_invalid_hint")) + "</p><div>" + problems.map((pr) => "• " + esc(t("prob_" + pr, pr))).join("<br>") + "</div>";  // إسناد نص إلى probBox.innerHTML
    }  // إغلاق الكتلة السابقة
    toast(t("profile_invalid"));  // استدعاء الدالة toast(t("profile_invalid"))
    return;  // إرجاع ;
  }  // إغلاق الكتلة السابقة
  /* No automatic scan or calibration for saved profile path */
  S.profile = profile;  // إسناد قيمة إلى S.profile
  S.savedProfileMode = true;  // إسناد قيمة منطقية إلى S.savedProfileMode
  S.currentFlow = "saved";  // إسناد نص إلى S.currentFlow
  const payload = {  // تعريف الثابت payload = كائن
    profile,  // عنصر في القائمة/الكائن (يتبعه المزيد)
    // saved profile path does not use preflight_only calibration (new-profile uses preflight_only: true)
    attempts: parseInt($("rv_attempts").value || "2000", 10),  // مفتاح attempts في الكائن = نتيجة استدعاء
    threads: parseInt($("rv_threads").value || "12", 10),  // مفتاح threads في الكائن = نتيجة استدعاء
    delay_ms: parseInt($("rv_delay").value || "0", 10),  // مفتاح delay_ms في الكائن = نتيجة استدعاء
    verify: true,  // مفتاح verify في الكائن = قيمة منطقية
    auto_stop: true,  // مفتاح auto_stop في الكائن = قيمة منطقية
    resume: $("rv_resume") ? $("rv_resume").checked : true,  // مفتاح resume في الكائن = قيمة
  };  // إغلاق الكتلة السابقة
  S.lastStart = payload;  // إسناد قيمة إلى S.lastStart
  const res = await api("/api/run/start", payload);  // تعريف الثابت res = نتيجة استدعاء
  if (!res.ok) {  // شرط: !res.ok
    modal(t("scan_fail"), "<pre>" + esc(JSON.stringify(res, null, 2)) + "</pre>");  // استدعاء الدالة modal(t("scan_fail"), "<pre>" + esc(JSON.strin)
    return;  // إرجاع ;
  }  // إغلاق الكتلة السابقة
  S.lastSeq = 0; S.rows = 0;  // إسناد رقم إلى S.lastSeq
  $("logBody").innerHTML = ""; $("hitsBox").innerHTML = t("hits_none");  // استدعاء الدالة $("logBody").innerHTML = ""; $("hitsBox").)
  $("reviewBox").innerHTML = t("review_none");  // استدعاء الدالة $("reviewBox").innerHTML = t("review_none")
  const startBtn = $("startBtn");  // تعريف الثابت startBtn = نتيجة استدعاء
  if (startBtn) startBtn.classList.add("hidden");  // تنفيذ التعليمة السابقة
  setRunStopVisible(true);
  S.running = true;  // إسناد قيمة منطقية إلى S.running
  step("results");  // استدعاء الدالة step("results")
  pollStatus();  // استدعاء الدالة pollStatus()
}  // إغلاق الكتلة السابقة

function setRunStopVisible(visible) {
  const row = $("runStopRow");
  const button = $("stopBtn");
  if (row) row.classList.toggle("hidden", !visible);
  if (button && visible) button.disabled = false;
}

async function stopRun() {  // تكملة السطر السابق
  const button = $("stopBtn");
  if (button) button.disabled = true;
  const res = await api("/api/run/stop", {});
  if (!res.ok) {
    if (button) button.disabled = false;
    toast(res.error === "server_gone" ? t("server_gone") : t("scan_fail"));
    return;
  }
  toast(t("state_stopping"));
  pollStatus();
}

async function restoreActiveRun() {
  // Get the state snapshot without replaying an unbounded event history; the
  // next poll loads only the newest 400 events for the visible log.
  const res = await api("/api/run/status?since=9999999999999999");
  const st = res.status || {};
  if (!res.ok || !["calibrating", "running", "stopping"].includes(st.state)) return;
  S.running = true;
  S.lastSeq = Math.max(0, (Number(st.seq) || 0) - 400);
  S.rows = 0;
  const startButton = $("startBtn");
  if (startButton) startButton.classList.add("hidden");
  setRunStopVisible(true);
  if (st.state === "stopping" && $("stopBtn")) $("stopBtn").disabled = true;
  step("results");
  renderStatus(st, []);
  pollStatus();
}

function pollStatus() {  // تعريف الدالة pollStatus()
  clearTimeout(S.poll);  // استدعاء الدالة clearTimeout(S.poll)
  S.poll = setTimeout(async () => {  // إسناد قيمة إلى S.poll
    const res = await api("/api/run/status?since=" + S.lastSeq);  // تعريف الثابت res = نتيجة استدعاء
    if (!res.ok) {  // شرط: !res.ok
      S.running = false;  // إسناد قيمة منطقية إلى S.running
      if (res.error === "server_gone")  // شرط: res.error === "server_gone"
        modal(t("server_gone_title"), "<div>" + esc(t("server_gone")) + "</div>");  // استدعاء الدالة modal(t("server_gone_title"), "<div>" + esc(t()
      return;  // إرجاع ;
    }  // إغلاق الكتلة السابقة
    renderStatus(res.status, res.events);  // استدعاء الدالة renderStatus(res.status, res.events)
    if (res.status.state === "idle" && !S.running) return;  // تنفيذ التعليمة السابقة
    if (res.status.state === "done" && S.running) {  // شرط: res.status.state === "done" && S.running
      S.running = false;  // إسناد قيمة منطقية إلى S.running
      $("startBtn").classList.remove("hidden");  // استدعاء الدالة $("startBtn").classList.remove("hidden")
      setRunStopVisible(false);
      renderStop(res.status);  // استدعاء الدالة renderStop(res.status)
      refreshProfiles();          /* the engine saved where the run stopped */  // تكملة السطر السابق
      setTimeout(pollStatus, 1500);  // استدعاء الدالة setTimeout(pollStatus, 1500)
      return;  // إرجاع ;
    }  // إغلاق الكتلة السابقة
    pollStatus();  // استدعاء الدالة pollStatus()
  }, 550);  // تنفيذ التعليمة السابقة
}  // إغلاق الكتلة السابقة

function renderStatus(st, events) {  // تعريف الدالة renderStatus(st, events)
  S.state = st.state;  // إسناد قيمة إلى S.state
  const runStopActive = ["calibrating", "running", "stopping"].includes(st.state);
  setRunStopVisible(runStopActive);
  const stopButton = $("stopBtn");
  if (stopButton) stopButton.disabled = st.state === "stopping";
  const statePill = $("statePill");  // تعريف الثابت statePill = نتيجة استدعاء
  statePill.textContent = stateLabel(st.state);  // إسناد نتيجة استدعاء إلى statePill.textContent
  statePill.className = "pill " + (st.state === "running" ? "run"  // إسناد نص إلى statePill.className
    : st.state === "done" ? "done" : st.error ? "err" : "");  // تنفيذ التعليمة السابقة
  $("stState").textContent = stateLabel(st.state);  // استدعاء الدالة $("stState").textContent = stateLabel(st.s)
  $("stSpeed").textContent = (st.speed || 0) + "/s";  // تنفيذ التعليمة السابقة
  $("stSent").textContent = fmtSpace((st.progress || {}).attempts || 0);  // استدعاء الدالة $("stSent").textContent = fmtSpace((st.pro)
  $("stCovered").textContent = fmtSpace((st.progress || {}).covered || 0);  // استدعاء الدالة $("stCovered").textContent = fmtSpace((st.)
  const eta = (st.progress || {}).eta_seconds || 0;  // تعريف الثابت eta = قيمة
  const etaBox = $("stEta");  // تعريف الثابت etaBox = نتيجة استدعاء
  if (etaBox) {  // شرط: etaBox
    etaBox.textContent = st.state === "running" && eta  // إسناد قيمة إلى etaBox.textContent
      ? (LANG === "ar" ? "≈ " : "≈ ") + humanTime(eta) : "—";  // تنفيذ التعليمة السابقة
  }  // إغلاق الكتلة السابقة
  $("stLatency").textContent = ((st.latency || {}).avg_ms || 0) + " ms";  // تنفيذ التعليمة السابقة
  $("stDelay").textContent = ((st.throttle || {}).delay_ms || 0) + " ms";  // تنفيذ التعليمة السابقة
  const pct = Math.max(0, Math.min(100,  // تعريف الثابت pct = قيمة
    Number((st.progress || {}).percent) || 0));  // استدعاء الدالة Number((st.progress || {}).percent) || 0))
  $("bar").style.width = pct.toFixed(1) + "%";  // تنفيذ التعليمة السابقة
  $("progressTrack").setAttribute("aria-valuenow", String(Math.round(pct)));  // استدعاء الدالة $("progressTrack").setAttribute("aria-valu)

  /* counters */
  const order = ["ACCEPTED_VERIFIED", "ACCEPTED", "ACCEPTED_UNVERIFIED", "REJECTED",  // تعريف الثابت order = مصفوفة
                 "UNKNOWN", "BANNED", "RATE_LIMITED", "CHALLENGE", "NET_ERROR"];  // تنفيذ التعليمة السابقة
  const counters = st.counters || {};  // تعريف الثابت counters = قيمة
  $("counterChips").innerHTML = order.filter((c) => counters[c])  // استدعاء الدالة $("counterChips").innerHTML = order.filter)
    .map((c) => "<span class='cchip'><span class='vcode v-" + c + "'>" +  // تكملة السطر السابق
           esc(codeLabel(c)) + "</span><b>" + counters[c] + "</b></span>").join("");  // استدعاء الدالة esc(codeLabel(c)) + "</span><b>" + counters[)

  /* why each attempt ended the way it did - the whole point of the results page */
  const whyBox = $("whyCard");  // تعريف الثابت whyBox = نتيجة استدعاء
  const whyList = Object.entries(st.reason_counts || {})  // تعريف الثابت whyList = نتيجة استدعاء
    .sort((a, b) => b[1] - a[1]).filter(([, n]) => n);  // استدعاء الدالة .sort((a, b) => b[1] - a[1]).filter(([, n]) =>)
  if (whyList.length) {  // شرط: whyList.length
    whyBox.classList.remove("hidden");  // استدعاء الدالة whyBox.classList.remove("hidden")
    whyBox.innerHTML = "<h4>" + t("why_title") + "</h4><table class='why'><tbody>" +  // إسناد نص إلى whyBox.innerHTML
      whyList.map(([code, n]) => "<tr><td>" + esc(whyLabel(code)) + "</td><td><b>" +  // تكملة السطر السابق
        fmtSpace(n) + "</b></td></tr>").join("") + "</tbody></table>";  // تنفيذ التعليمة السابقة
  } else { whyBox.classList.add("hidden"); }  // تكملة السطر السابق

  /* throttle note */
  const th = (st.throttle || {}).reason;  // تعريف الثابت th = قيمة
  const thCard = $("throttleCard");  // تعريف الثابت thCard = نتيجة استدعاء
  if (th) {  // شرط: th
    thCard.classList.remove("hidden");  // استدعاء الدالة thCard.classList.remove("hidden")
    thCard.innerHTML = "<span class='warn'>⏳ " + t("th_" + th, th) + "</b> — " +  // إسناد نص إلى thCard.innerHTML
      ((st.throttle || {}).delay_ms || 0) + " ms</span>";  // تنفيذ التعليمة السابقة
  } else { thCard.classList.add("hidden"); }  // تكملة السطر السابق

  /* while the run is still going, the stop card shows the learning progress -
     never after it, because renderStop owns that card once the run is over */
  if (st.calibration && st.calibration.steps && S.rows === 0 && st.state !== "done") {  // شرط: st.calibration && st.calibration.steps && S.rows === 0 && st.state !==
    const c = $("stopCard");  // تعريف الثابت c = نتيجة استدعاء
    const okSteps = st.calibration.steps.filter((s) => s.ok).length;  // تعريف الثابت okSteps = قيمة
    c.classList.remove("hidden");  // استدعاء الدالة c.classList.remove("hidden")
    c.innerHTML = "<h4>" + t("cal_rejection_baseline") + "</h4><div>" +  // إسناد نص إلى c.innerHTML
      okSteps + "/" + st.calibration.steps.length + " ✔ · " +  // تكملة السطر السابق
      (st.calibration.fingerprint ?  // تكملة السطر السابق
        (st.calibration.fingerprint.exact ? t("exact_mode") : t("shape_mode")) : "") +  // تكملة السطر السابق
      "</div>";  // تنفيذ التعليمة السابقة
  }  // إغلاق الكتلة السابقة

  (events || []).forEach((ev) => {  // تكملة السطر السابق
    S.lastSeq = Math.max(S.lastSeq, ev.seq);  // إسناد نتيجة استدعاء إلى S.lastSeq
    if (ev.kind === "attempt") addRow(ev.data);  // تنفيذ التعليمة السابقة
    else if (ev.kind === "hit") renderHits(ev.data);  // تنفيذ التعليمة السابقة
    else if (ev.kind === "resume")  // شرط بديل: ev.kind === "resume"
      toast("↪ " + t("resume_from") + " " + fmtSpace((ev.data || {}).from || 0));  // استدعاء الدالة toast("↪ " + t("resume_from") + " " + fmtSpace)
    else if (ev.kind === "review") renderReview(st.review || []);  // تنفيذ التعليمة السابقة
    else if (ev.kind === "error") modal("Error", "<pre>" + esc(ev.data.message) + "</pre>");  // تنفيذ التعليمة السابقة
    else if (ev.kind === "report") S.lastReport = ev.data.file;  // تنفيذ التعليمة السابقة
    else if (ev.kind === "internet_opened")  // شرط بديل: ev.kind === "internet_opened"
      toast("\uD83C\uDF10 " + t("internet_opened_title"));  // استدعاء الدالة toast("\uD83C\uDF10 " + t("internet_opened_tit)
  });  // إغلاق القوس المفتوح في السطر السابق
  if (st.review && st.review.length) renderReview(st.review);  // تنفيذ التعليمة السابقة
  if (st.hits && st.hits.length) renderHits(null, st.hits);  // تنفيذ التعليمة السابقة
}  // إغلاق الكتلة السابقة

function addRow(d) {  // تعريف الدالة addRow(d)
  const body = $("logBody");
  if (body.children.length >= 400) body.removeChild(body.lastElementChild);
  const tr = document.createElement("tr");  // تعريف الثابت tr = نتيجة استدعاء
  tr.className = d.code;  // إسناد قيمة إلى tr.className
  const reason = d.code === "NET_ERROR" ? t("net_" + d.reason, d.reason)  // تعريف الثابت reason = نتيجة استدعاء
    : reasonLabel(d.code, d.reason, d.data);  // تنفيذ التعليمة السابقة
  tr.innerHTML =  // تكملة السطر السابق
    "<td>" + (d.index != null ? d.index + 1 : "—") + "</td>" +  // تكملة السطر السابق
    "<td>" + esc(d.card) + "</td>" +  // تكملة السطر السابق
    "<td>" + (d.status || "—") + "</td>" +  // تكملة السطر السابق
    "<td><span class='vcode v-" + d.code + "'>" + esc(codeLabel(d.code)) + "</span></td>" +  // تكملة السطر السابق
    "<td class='why'>" + esc(reason) + "</td>" +  // تكملة السطر السابق
    "<td>" + (d.ms || 0) + "</td>" +  // تكملة السطر السابق
    "<td>" + (d.length || 0) + "</td>";  // تنفيذ التعليمة السابقة
  body.prepend(tr);
  const wrap = body.closest(".logwrap");
  if (wrap) wrap.scrollTop = 0;
  S.rows = Math.min(body.children.length, 400);
}  // إغلاق الكتلة السابقة

function renderHits(hit, all) {  // تعريف الدالة renderHits(hit, all)
  if (hit) toast("🎯 " + hit.card);  // تنفيذ التعليمة السابقة
  const hits = all || [];  // تعريف الثابت hits = قيمة
  const box = $("hitsBox");  // تعريف الثابت box = نتيجة استدعاء
  if (!hits.length && !hit) return;  // تنفيذ التعليمة السابقة
  const list = hit && !all ? [hit] : hits;  // تعريف الثابت list = قيمة
  box.className = "card";  // إسناد نص إلى box.className
  box.innerHTML = list.map((h) =>  // إسناد قيمة إلى box.innerHTML
    "<div><span class='vcode v-" + h.code + "'>" + esc(codeLabel(h.code)) + "</span> " +  // تكملة السطر السابق
    "<b class='mono' style='font-size:1rem'>" + esc(h.card) + "</b> — " +  // تكملة السطر السابق
    esc(reasonLabel(h.code, h.reason, h.data)) +  // تكملة السطر السابق
    (h.data && h.data.internet ? " · internet: " + esc(h.data.internet) : "") +  // تكملة السطر السابق
    "</div>").join("");  // تنفيذ التعليمة السابقة
}  // إغلاق الكتلة السابقة

function renderReview(items) {  // تعريف الدالة renderReview(items)
  const box = $("reviewBox");  // تعريف الثابت box = نتيجة استدعاء
  if (!items || !items.length) return;  // تنفيذ التعليمة السابقة
  box.className = "card";  // إسناد نص إلى box.className
  box.innerHTML = items.slice(-30).reverse().map((r) => {  // إسناد قيمة إلى box.innerHTML
    const d = r.data || {};  // تعريف الثابت d = قيمة
    const diff = (d.diff && d.diff.new_words) || [];  // تعريف الثابت diff = قيمة
    return "<div style='margin-bottom:8px'>" +  // إرجاع "<div style='margin-bottom:8px'>" +
      "<button class='btn tiny' data-review='" + esc(r.file) + "'>" +  // تكملة السطر السابق
      t("review_open") + "</button> <b class='mono'>" + esc(r.card) + "</b>" +  // تكملة السطر السابق
      (diff.length ? "<div class='hint'>" + t("review_diff") + ": " +  // تكملة السطر السابق
        esc(diff.slice(0, 8).join(", ")) + "</div>" : "") +  // تكملة السطر السابق
      "</div>";  // تنفيذ التعليمة السابقة
  }).join("");  // تنفيذ التعليمة السابقة
  box.querySelectorAll("[data-review]").forEach((b) =>  // تكملة السطر السابق
    b.addEventListener("click", () => openReview(b.dataset.review)));  // استدعاء الدالة b.addEventListener("click", () => openReview(b.dataset.revi)
}  // إغلاق الكتلة السابقة

async function openReview(name) {  // تكملة السطر السابق
  const res = await fetch(withToken("/api/review/file?name=" + encodeURIComponent(name)));  // تعريف الثابت res = نتيجة استدعاء
  const html = await res.text();  // تعريف الثابت html = نتيجة استدعاء
  modal(name, "<iframe class='pagereview' sandbox srcdoc='" +  // تكملة السطر السابق
        esc(html) + "'></iframe>");  // استدعاء الدالة esc(html) + "'></iframe>")
}  // إغلاق الكتلة السابقة

/* The worst case used to be silent: the run said "finished", the log was
   empty and the only text was "details in the log".  Now the page spells out
   what the router did, step by step, and what to do about it. */
function calReasonLabel(reason) {  // تعريف الدالة calReasonLabel(reason)
  reason = reason || "";  // إسناد قيمة إلى reason
  if (reason.startsWith("net_")) return t("net_" + reason.slice(4), reason.slice(4));  // تنفيذ التعليمة السابقة
  if (reason.startsWith("internet_")) return t(reason, reason.slice(9));  // تنفيذ التعليمة السابقة
  return t("cal_" + reason, reason);  // إرجاع t("cal_" + reason, reason);
}  // إغلاق الكتلة السابقة

function renderCalFailure(st) {  // تعريف الدالة renderCalFailure(st)
  const cal = st.calibration || {};  // تعريف الثابت cal = قيمة
  const kind = String(st.error || cal.error || "").replace(/^net_/, "");  // تعريف الثابت kind = نتيجة استدعاء
  const steps = cal.steps || [];  // تعريف الثابت steps = قيمة
  const failed = steps.filter((s) => !s.ok);  // تعريف الثابت failed = نتيجة استدعاء
  /* the failed step knows the exact cause ("our three test cards did it"
     vs "the router was already blocking us"), the error code only knows
     the family - prefer the step when we have one */
  const why = failed.length ? String(failed[failed.length - 1].reason || "") : "";  // تعريف الثابت why = قيمة
  let html = "<div class='bad' style='margin-top:8px;font-weight:600'>" +  // تعريف المتغير القابل للتغيير html = نص
    esc(t("cal_failed_title")) + "</div>" +  // تكملة السطر السابق
    "<div class='hint'>" + esc(t("cal_failed_hint")) + "</div>";  // تنفيذ التعليمة السابقة
  if (kind) {  // شرط: kind
    html += "<div class='bad mono'>" +  // تكملة السطر السابق
      esc(t("cal_" + (why || kind), t("net_" + kind, t("cal_" + kind, kind)))) +  // تكملة السطر السابق
      "</div>";  // تنفيذ التعليمة السابقة
    const advice = t("netadvice_" + (why || kind), "") || t("netadvice_" + kind, "");  // تعريف الثابت advice = نتيجة استدعاء
    if (advice) html += "<div class='warn'>→ " + esc(advice) + "</div>";  // تنفيذ التعليمة السابقة
  }  // إغلاق الكتلة السابقة
  if (cal.steps && cal.steps.length) {  // شرط: cal.steps && cal.steps.length
    html += "<ul style='margin:.4rem 0 0;padding-inline-start:1.1rem'>";  // تنفيذ التعليمة السابقة
    cal.steps.forEach((s) => {  // تكملة السطر السابق
      const d = s.detail || {};  // تعريف الثابت d = قيمة
      let extra = "";  // تعريف المتغير القابل للتغيير extra = نص
      if (s.id === "profile_valid" && d.problems)  // شرط: s.id === "profile_valid" && d.problems
        extra = " — " + (d.problems || []).map((p) => t("prob_" + p, p)).join("، ");  // إسناد نص إلى extra
      if (s.id === "reach_login_page" && d.text)  // شرط: s.id === "reach_login_page" && d.text
        extra = " — <span class='mono'>" + esc(String(d.text).slice(0, 120)) + "</span>";  // إسناد نص إلى extra
      if (s.id === "internet_state" && d.state) extra = " — " + t("internet_" + d.state);  // تنفيذ التعليمة السابقة
      /* a block is decided from a word and/or a status code: show them, so the
         user can see WHY we called this page a block page */
      if (/blocked|ban/.test(s.reason)) {  // شرط: /blocked|ban/.test(s.reason)
        const bits = [];  // تعريف الثابت bits = مصفوفة
        if (d.word) bits.push("«" + d.word + "»");  // تنفيذ التعليمة السابقة
        if (d.status) bits.push("HTTP " + (Array.isArray(d.status) ? d.status.join("/") : d.status));  // تنفيذ التعليمة السابقة
        if (d.has_form) bits.push(t("block_but_form_present"));  // تنفيذ التعليمة السابقة
        if (d.probes_sent) bits.push(d.probes_sent + " " + t("probe_cards"));  // تنفيذ التعليمة السابقة
        if (bits.length) extra += " — " + esc(bits.join(" · "));  // تنفيذ التعليمة السابقة
      }  // إغلاق الكتلة السابقة
      html += "<li class='" + (s.ok ? "ok" : "bad") + "'>" + (s.ok ? "✔" : "✖") +  // تكملة السطر السابق
        " " + t("cal_" + s.id, s.id) + ": " + calReasonLabel(s.reason) + extra + "</li>";  // تنفيذ التعليمة السابقة
    });  // إغلاق القوس المفتوح في السطر السابق
    html += "</ul>";  // تنفيذ التعليمة السابقة
  }  // إغلاق الكتلة السابقة
  html += "<div class='hint'>" + esc(t("no_attempt_was_made")) + "</div>";  // تنفيذ التعليمة السابقة
  return html;  // إرجاع html;
}  // إغلاق الكتلة السابقة

function openManualResumeConfirm() {  // تعريف الدالة openManualResumeConfirm()
  const body = "<p>" + esc(t("manual_resume_confirm_body")) + "</p>" +  // تعريف الثابت body = نص
    "<p>" + esc(t("manual_resume_hint")) + "</p>" +  // تكملة السطر السابق
    "<label class='check' style='display:flex;gap:8px;margin-top:10px'><input id='confirmAck' type='checkbox'><span>" + esc(t("manual_resume_ack")) + "</span></label>" +  // تكملة السطر السابق
    "<div class='row end wrap' style='margin-top:14px'><button class='btn' id='cancelResumeBtn'>" + esc(t("btn_cancel")) + "</button><button class='btn primary' id='continueResumeBtn' disabled>" + esc(t("btn_continue")) + "</button></div>";  // تنفيذ التعليمة السابقة
  modal(t("manual_resume_confirm_title"), body);  // استدعاء الدالة modal(t("manual_resume_confirm_title"), body)
  const ack = $("confirmAck");  // تعريف الثابت ack = نتيجة استدعاء
  const cont = $("continueResumeBtn");  // تعريف الثابت cont = نتيجة استدعاء
  const cancel = $("cancelResumeBtn");  // تعريف الثابت cancel = نتيجة استدعاء
  if (ack && cont) {  // شرط: ack && cont
    ack.addEventListener("change", () => { cont.disabled = !ack.checked; });  // استدعاء الدالة ack.addEventListener("change", () => { cont.disabled = !ack.c)
  }  // إغلاق الكتلة السابقة
  if (cancel) {  // شرط: cancel
    cancel.addEventListener("click", () => { closeModal(); });  // استدعاء الدالة cancel.addEventListener("click", () => { closeModal(); })
  }  // إغلاق الكتلة السابقة
  if (cont) {  // شرط: cont
    cont.addEventListener("click", async () => {  // تكملة السطر السابق
      closeModal();  // استدعاء الدالة closeModal()
      S.manualResumeRequired = false;  // إسناد قيمة منطقية إلى S.manualResumeRequired
      /* Resume with saved settings and progress */
      const prof = S.profile || (S.lastStart && S.lastStart.profile) || profileFromForm();  // تعريف الثابت prof = نتيجة استدعاء
      const payload = S.lastStart ? Object.assign({}, S.lastStart, { profile: prof }) : {  // تعريف الثابت payload = قيمة
        profile: prof,  // مفتاح profile في الكائن = قيمة
        attempts: parseInt(($("r_attempts") && $("r_attempts").value) || ($("rv_attempts") && $("rv_attempts").value) || "2000", 10),  // مفتاح attempts في الكائن = نتيجة استدعاء
        threads: parseInt(($("r_threads") && $("r_threads").value) || ($("rv_threads") && $("rv_threads").value) || "12", 10),  // مفتاح threads في الكائن = نتيجة استدعاء
        delay_ms: parseInt(($("r_delay") && $("r_delay").value) || ($("rv_delay") && $("rv_delay").value) || "0", 10),  // مفتاح delay_ms في الكائن = نتيجة استدعاء
        verify: $("r_verify") ? $("r_verify").checked : true,  // مفتاح verify في الكائن = قيمة
        auto_stop: $("r_autostop") ? $("r_autostop").checked : true,  // مفتاح auto_stop في الكائن = قيمة
        resume: true,  // مفتاح resume في الكائن = قيمة منطقية
      };  // إغلاق الكتلة السابقة
      payload.profile = prof;  // إسناد قيمة إلى payload.profile
      /* mark manual resume in report */
      payload.manual_resume = true;  // إسناد قيمة منطقية إلى payload.manual_resume
      S.lastStart = payload;  // إسناد قيمة إلى S.lastStart
      const res = await api("/api/run/start", payload);  // تعريف الثابت res = نتيجة استدعاء
      if (!res.ok) {  // شرط: !res.ok
        modal(t("scan_fail"), "<pre>" + esc(JSON.stringify(res, null, 2)) + "</pre>");  // استدعاء الدالة modal(t("scan_fail"), "<pre>" + esc(JSON.strin)
        return;  // إرجاع ;
      }  // إغلاق الكتلة السابقة
      S.lastSeq = 0; S.rows = 0;  // إسناد رقم إلى S.lastSeq
      $("logBody").innerHTML = ""; $("hitsBox").innerHTML = t("hits_none");  // استدعاء الدالة $("logBody").innerHTML = ""; $("hitsBox").)
      $("reviewBox").innerHTML = t("review_none");  // استدعاء الدالة $("reviewBox").innerHTML = t("review_none")
      $("startBtn").classList.add("hidden");
      setRunStopVisible(true);
      S.running = true;  // إسناد قيمة منطقية إلى S.running
      step("results");  // استدعاء الدالة step("results")
      pollStatus();  // استدعاء الدالة pollStatus()
      toast(t("resume_report"));  // استدعاء الدالة toast(t("resume_report"))
    });  // إغلاق القوس المفتوح في السطر السابق
  }  // إغلاق الكتلة السابقة
}  // إغلاق الكتلة السابقة

function renderBanEvidence(ev) {  // تعريف الدالة renderBanEvidence(ev)
  if (!ev || typeof ev !== "object") return "";  // تنفيذ التعليمة السابقة
  return "<div class='card' style='margin-top:8px'><h4>" + esc(t("ban_evidence_label")) +  // إرجاع "<div class='card' style='margin-top:8px'><h4>" + esc(t("ban
    "</h4><dl class='kv'>" +  // تكملة السطر السابق
    "<dt>" + esc(t("ban_evidence_status")) + "</dt><dd>" + esc(String(ev.status || "—")) + "</dd>" +  // تكملة السطر السابق
    "<dt>" + esc(t("ban_evidence_word")) + "</dt><dd class='mono'>" + esc(ev.word || "—") + "</dd>" +  // تكملة السطر السابق
    "<dt>" + esc(t("ban_evidence_form")) + "</dt><dd>" + esc(ev.has_form ? "yes" : "no") + "</dd>" +  // تكملة السطر السابق
    "<dt>" + esc(t("ban_evidence_kind")) + "</dt><dd>" + esc(ev.kind_hint || "—") + "</dd>" +  // تكملة السطر السابق
    "</dl></div>";  // تنفيذ التعليمة السابقة
}  // إغلاق الكتلة السابقة

function renderStop(st) {  // تعريف الدالة renderStop(st)
  const card = $("stopCard");  // تعريف الثابت card = نتيجة استدعاء
  card.classList.remove("hidden");  // استدعاء الدالة card.classList.remove("hidden")
  let html = "<h4>" + t("why_stopped") + "</h4><div>" +  // تعريف المتغير القابل للتغيير html = نص
    t("stop_" + st.stop_reason, st.stop_reason || "") + "</div>";  // تنفيذ التعليمة السابقة
  if (st.stop_reason === "target_unreachable") {  // شرط: st.stop_reason === "target_unreachable"
    html += "<div class='hint warn' style='margin-top:6px'>" +  // تكملة السطر السابق
      esc(t("target_unreachable_doc")) + "</div>";  // تنفيذ التعليمة السابقة
  }  // إغلاق الكتلة السابقة
  if (st.ban_evidence) html += renderBanEvidence(st.ban_evidence);  // تنفيذ التعليمة السابقة
  const tried = (st.progress || {}).attempts || 0;  // تعريف الثابت tried = قيمة
  if ((st.calibration && st.calibration.ok === false) ||  // تكملة السطر السابق
      st.stop_reason === "calibration_failed") {  // إسناد قيمة إلى st.stop_reason
    html += renderCalFailure(st);  // تنفيذ التعليمة السابقة
  } else if (!tried) {  // تكملة السطر السابق
    html += "<div class='warn' style='margin-top:6px'>" + esc(t("no_attempt_was_made")) +  // تكملة السطر السابق
      (st.error ? " — <span class='mono'>" + esc(st.error) + "</span>" : "") + "</div>";  // تنفيذ التعليمة السابقة
  }  // إغلاق الكتلة السابقة
  if (st.hits && st.hits.length) {  // شرط: st.hits && st.hits.length
    html += "<div class='ok' style='margin-top:6px'>" + t("hits_title") + ": " +  // تكملة السطر السابق
      st.hits.map((h) => "<b class='mono'>" + esc(h.card) + "</b> (" +  // تكملة السطر السابق
      esc(codeLabel(h.code)) + ")").join(", ") + "</div>";  // تنفيذ التعليمة السابقة
  }  // إغلاق الكتلة السابقة
  /* the wall came down while we were guessing: one of these cards did it */
  const opened = st.internet_opened;  // تعريف الثابت opened = قيمة
  if (opened && opened.suspects && opened.suspects.length) {  // شرط: opened && opened.suspects && opened.suspects.length
    html += "<div class='warn' style='margin-top:8px;font-weight:600'>\u24d8 " +  // تكملة السطر السابق
      esc(t("internet_opened_title")) + "</div>" +  // تكملة السطر السابق
      "<div class='hint'>" + esc(t("internet_opened_hint")) + "</div>" +  // تكملة السطر السابق
      "<div class='mono' style='margin-top:4px;word-break:break-all'>" +  // تكملة السطر السابق
      opened.suspects.map((s) => esc(s.card)).join(" \u00b7 ") + "</div>";  // تنفيذ التعليمة السابقة
  }  // إغلاق الكتلة السابقة
  const k = st.net_kinds || {};  // تعريف الثابت k = قيمة
  const parts = Object.entries(k).map(([kind, n]) => t("net_" + kind, kind) + " ×" + n);  // تعريف الثابت parts = نتيجة استدعاء
  if (parts.length) html += "<div class='hint'>" + esc(parts.join(" · ")) + "</div>";  // تنفيذ التعليمة السابقة
  if (S.lastReport)  // شرط: S.lastReport
    html += "<div class='hint'>" + t("report_saved") + ": <span class='mono'>" +  // تكملة السطر السابق
            esc(S.lastReport) + "</span></div>";  // تنفيذ التعليمة السابقة
  /* Do not offer an automatic retry for explicit network blocks or an
     unproven known card; those need operator review before any more requests. */
  const calError = (st.calibration || {}).error || st.error || "";  // تعريف الثابت calError = قيمة
  const stopForReview = ["blocked_already", "blocked_before_probes",  // تعريف الثابت stopForReview = مصفوفة
    "captcha_challenge", "known_card_not_proven",  // عنصر في القائمة/الكائن (يتبعه المزيد)
    "known_card_out_of_format", "logout_unconfirmed"].includes(calError);  // تنفيذ التعليمة السابقة
  const requiresManualClearance = ["target_unreachable", "banned_by_router",  // تعريف الثابت requiresManualClearance = مصفوفة
    "rate_limited_by_router", "captcha_challenge"].includes(st.stop_reason) ||  // تكملة السطر السابق
    (st.stop_reason === "calibration_failed" && stopForReview);  // تنفيذ التعليمة السابقة
  if (requiresManualClearance) {  // شرط: requiresManualClearance
    S.manualResumeRequired = true;  // إسناد قيمة منطقية إلى S.manualResumeRequired
    html += "<div class='row wrap' style='margin-top:12px'><button class='btn primary big' id='manualResumeBtn'>" + esc(t("manual_resume_button")) + "</button></div>";  // تنفيذ التعليمة السابقة
    html += "<div class='hint warn' style='margin-top:6px'>" + esc(t("manual_resume_hint")) + "</div>";  // تنفيذ التعليمة السابقة
  }  // إغلاق الكتلة السابقة
  if (st.stop_reason === "calibration_failed" && !stopForReview) {  // شرط: st.stop_reason === "calibration_failed" && !stopForReview
    html += "<div class='row wrap' style='margin-top:8px'>" +  // تكملة السطر السابق
            "<button class='btn' id='retryNowBtn'>" + esc(t("retry_now")) + "</button></div>";  // تنفيذ التعليمة السابقة
  }  // إغلاق الكتلة السابقة
  card.innerHTML = html;  // إسناد قيمة إلى card.innerHTML
  const now = $("retryNowBtn");  // تعريف الثابت now = نتيجة استدعاء
  if (now) now.addEventListener("click", () => startRun());  // تنفيذ التعليمة السابقة
  const manualBtn = $("manualResumeBtn");  // تعريف الثابت manualBtn = نتيجة استدعاء
  if (manualBtn) {  // شرط: manualBtn
    manualBtn.addEventListener("click", () => {  // تكملة السطر السابق
      openManualResumeConfirm();  // استدعاء الدالة openManualResumeConfirm()
    });  // إغلاق القوس المفتوح في السطر السابق
  }  // إغلاق الكتلة السابقة
}  // إغلاق الكتلة السابقة

/* ------------------------------------------------------------------ modal */
let modalReturnFocus = null;  // تعريف المتغير القابل للتغيير modalReturnFocus = null
function modal(title, html) {  // تعريف الدالة modal(title, html)
  if ($("modal").classList.contains("hidden")) modalReturnFocus = document.activeElement;  // تنفيذ التعليمة السابقة
  $("modalTitle").textContent = title;  // تنفيذ التعليمة السابقة
  $("modalBody").innerHTML = html;  // تنفيذ التعليمة السابقة
  $("modal").classList.remove("hidden");  // استدعاء الدالة $("modal").classList.remove("hidden")
  const target = $("modalBody").querySelector("input, button, a, [tabindex]") || $("modalClose");  // تعريف الثابت target = نتيجة استدعاء
  if (target) target.focus();  // تنفيذ التعليمة السابقة
}  // إغلاق الكتلة السابقة
function closeModal() {  // تعريف الدالة closeModal()
  $("modal").classList.add("hidden");  // استدعاء الدالة $("modal").classList.add("hidden")
  if (modalReturnFocus && typeof modalReturnFocus.focus === "function")  // شرط: modalReturnFocus && typeof modalReturnFocus.focus === "function"
    modalReturnFocus.focus();  // استدعاء الدالة modalReturnFocus.focus()
  modalReturnFocus = null;  // إسناد null إلى modalReturnFocus
}  // إغلاق الكتلة السابقة

async function cacheModal() {  // تكملة السطر السابق
  const res = await api("/api/cache");  // تعريف الثابت res = نتيجة استدعاء
  const c = res.cache || {};  // تعريف الثابت c = قيمة
  let html = "<p>" + t("cache_hint") + "</p><ul>";  // تعريف المتغير القابل للتغيير html = نص
  Object.entries(c.folders || {}).forEach(([name, v]) => {  // تكملة السطر السابق
    html += "<li>" + esc(name) + ": " + v.files + " " +  // تكملة السطر السابق
      (LANG === "ar" ? "ملف" : "files") + " · " +  // تكملة السطر السابق
      (v.bytes / 1024).toFixed(1) + " KB</li>";  // تنفيذ التعليمة السابقة
  });  // إغلاق القوس المفتوح في السطر السابق
  if (c.profiles) html += "<li>profiles: " + c.profiles.count + "</li>";  // تنفيذ التعليمة السابقة
  html += "</ul><div class='row wrap'>" +  // تكملة السطر السابق
    "<button class='btn' data-scope='temp'>" + t("cache_temp") + "</button>" +  // تكملة السطر السابق
    "<button class='btn' data-scope='results'>" + t("cache_results") + "</button>" +  // تكملة السطر السابق
    "<button class='btn danger' data-scope='profiles'>" + t("cache_profiles") + "</button>" +  // تكملة السطر السابق
    "<button class='btn danger' data-scope='all'>" + t("cache_all") + "</button></div>";  // تنفيذ التعليمة السابقة
  modal(t("cache_title"), html);  // استدعاء الدالة modal(t("cache_title"), html)
  $("modalBody").querySelectorAll("[data-scope]").forEach((b) =>  // تكملة السطر السابق
    b.addEventListener("click", async () => {  // تكملة السطر السابق
      const scope = b.dataset.scope;  // تعريف الثابت scope = قيمة
      if (scope === "all" && !confirm(t("confirm_clear_all"))) return;  // تنفيذ التعليمة السابقة
      if (scope === "profiles" && !confirm(t("confirm_profiles"))) return;  // تنفيذ التعليمة السابقة
      const r = await api("/api/cache/clear", { scope });  // تعريف الثابت r = نتيجة استدعاء
      modal(t("cache_title"), "<div class='ok'>" + t("cache_freed") + " " +  // تكملة السطر السابق
        esc((r.cleared || {}).freed_human || "") + "</div>");  // استدعاء الدالة esc((r.cleared || {}).freed_human || "") + ")
      setTimeout(() => $("modal").classList.add("hidden"), 1400);  // استدعاء الدالة setTimeout(() => $("modal").classList.add("hidden"))
    }));  // إغلاق القوس المفتوح في السطر السابق
}  // إغلاق الكتلة السابقة

/* ------------------------------------------------------------------ wire up */
function wire() {  // تعريف الدالة wire()
  document.querySelectorAll(".step").forEach((b) =>  // تكملة السطر السابق
    b.addEventListener("click", () => step(b.dataset.step)));  // استدعاء الدالة b.addEventListener("click", () => step(b.dataset.step)))
  $("scanBtn").addEventListener("click", doScan);  // استدعاء الدالة $("scanBtn").addEventListener("click", doS)
  $("scanUrl").addEventListener("input", () => {  // تكملة السطر السابق
    if (S.scanReady && $("scanUrl").value.trim() !== S.scannedUrl) {  // شرط: S.scanReady && $("scanUrl").value.trim() !== S.scannedUrl
      S.scanReady = false;  // إسناد قيمة منطقية إلى S.scanReady
      S.calibrationReady = false;  // إسناد قيمة منطقية إلى S.calibrationReady
      $("calibrateBtn").disabled = true;  // تنفيذ التعليمة السابقة
      $("toFormat").disabled = true;  // تنفيذ التعليمة السابقة
    }  // إغلاق الكتلة السابقة
  });  // إغلاق القوس المفتوح في السطر السابق
  $("f_known").addEventListener("input", () => {  // تكملة السطر السابق
    const known = $("f_known").value.trim();  // تعريف الثابت known = نتيجة استدعاء
    $("calibrateBtn").disabled = !S.scanReady || !known;  // تنفيذ التعليمة السابقة
    if (S.calibrationReady && known !== S.knownCard) {  // شرط: S.calibrationReady && known !== S.knownCard
      S.calibrationReady = false;  // إسناد قيمة منطقية إلى S.calibrationReady
      S.calibrationSignature = "";  // إسناد نص إلى S.calibrationSignature
      $("toFormat").disabled = true;  // تنفيذ التعليمة السابقة
    }  // إغلاق الكتلة السابقة
  });  // إغلاق القوس المفتوح في السطر السابق
  $("scanUrl").addEventListener("keydown", (e) => { if (e.key === "Enter") doScan(); });  // استدعاء الدالة $("scanUrl").addEventListener("keydown", ()
  document.querySelectorAll(".chip[data-url]").forEach((c) =>  // تكملة السطر السابق
    c.addEventListener("click", () => { $("scanUrl").value = c.dataset.url; doScan(); }));  // استدعاء الدالة c.addEventListener("click", () => { $("scanUrl").value = c.)
  $("toFormat").addEventListener("click", () => step("format"));  // استدعاء الدالة $("toFormat").addEventListener("click", ())
  $("toRun").addEventListener("click", () => step("run"));  // استدعاء الدالة $("toRun").addEventListener("click", () =>)
  $("langBtn").addEventListener("click", () => setLang(LANG === "ar" ? "en" : "ar"));  // استدعاء الدالة $("langBtn").addEventListener("click", () )
  $("cacheBtn").addEventListener("click", cacheModal);  // استدعاء الدالة $("cacheBtn").addEventListener("click", ca)
  $("bannerMore").addEventListener("click", () =>  // تكملة السطر السابق
    modal(t("license_title"), "<pre>" + esc(t("license_body")) + "</pre>"));  // استدعاء الدالة modal(t("license_title"), "<pre>" + esc(t("lic)
  $("licenseLink").addEventListener("click", (e) => { e.preventDefault();  // استدعاء الدالة $("licenseLink").addEventListener("click",)
    modal(t("license_title"), "<pre>" + esc(t("license_body")) + "</pre>"); });  // استدعاء الدالة modal(t("license_title"), "<pre>" + esc(t("lic)
  const quitLink = $("quitLink");  // تعريف الثابت quitLink = نتيجة استدعاء
  if (quitLink) quitLink.addEventListener("click", async (e) => {  // تكملة السطر السابق
    e.preventDefault();  // استدعاء الدالة e.preventDefault()
    if (!window.confirm(t("confirm_quit"))) return;  // تنفيذ التعليمة السابقة
    await api("/api/quit", {});  // تنفيذ التعليمة السابقة
    modal(t("quit_tool"), "<div class='ok'>" + esc(t("quit_done")) + "</div>");  // استدعاء الدالة modal(t("quit_tool"), "<div class='ok'>" + esc)
  });  // إغلاق القوس المفتوح في السطر السابق
  $("modalClose").addEventListener("click", closeModal);  // استدعاء الدالة $("modalClose").addEventListener("click", )
  $("modal").addEventListener("click", (e) => {  // تكملة السطر السابق
    if (e.target === $("modal")) closeModal(); });  // تنفيذ التعليمة السابقة
  document.addEventListener("keydown", (e) => {  // تكملة السطر السابق
    if (e.key === "Escape" && !$("modal").classList.contains("hidden")) closeModal();  // تنفيذ التعليمة السابقة
  });  // إغلاق القوس المفتوح في السطر السابق
  $("licenseOk").addEventListener("change", () =>  // تكملة السطر السابق
    $("startBtn").disabled = !$("licenseOk").checked);  // استدعاء الدالة $("startBtn").disabled = !$("licenseOk").c)
  $("startBtn").addEventListener("click", startRun);  // استدعاء الدالة $("startBtn").addEventListener("click", st)
  $("stopBtn").addEventListener("click", stopRun);  // استدعاء الدالة $("stopBtn").addEventListener("click", sto)
  $("calibrateBtn").addEventListener("click", runCalibration);  // استدعاء الدالة $("calibrateBtn").addEventListener("click")
  const captureBtn = $("captureBtn");  // تعريف الثابت captureBtn = نتيجة استدعاء
  if (captureBtn) captureBtn.addEventListener("click", startCapture);  // تنفيذ التعليمة السابقة
  $("diagnoseBtn").addEventListener("click", runDiagnose);  // استدعاء الدالة $("diagnoseBtn").addEventListener("click",)
  $("lockoutBtn").addEventListener("click", runLockoutProbe);  // استدعاء الدالة $("lockoutBtn").addEventListener("click", )
  $("f_ua").addEventListener("change", () => {  // تكملة السطر السابق
    $("f_ua_custom_wrap").classList.toggle("hidden", $("f_ua").value !== "custom");  // استدعاء الدالة $("f_ua_custom_wrap").classList.toggle("hi)
  });  // إغلاق القوس المفتوح في السطر السابق
  $("clearWordsBtn").addEventListener("click", () => {  // تكملة السطر السابق
    $("f_words").value = "";  // تنفيذ التعليمة السابقة
    toast(LANG === "ar" ? "تم مسح كلمات النجاح" : "Success words cleared");  // استدعاء الدالة toast(LANG === "ar" ? "تم مسح كلمات النجاح" : )
  });  // إغلاق القوس المفتوح في السطر السابق
  $("saveProfileBtn").addEventListener("click", async () => {  // تكملة السطر السابق
    const r = await api("/api/profiles/save", { profile: profileFromForm() });  // تعريف الثابت r = نتيجة استدعاء
    toast(r.ok ? "💾 OK" : t("scan_fail"));  // استدعاء الدالة toast(r.ok ? "💾 OK" : t("scan_fail"))
    if (r.ok) renderProfiles(r.profiles);  // تنفيذ التعليمة السابقة
    if (!r.ok) modal("!", "<pre>" + esc(JSON.stringify(r.problems || r, null, 2)) + "</pre>");  // تنفيذ التعليمة السابقة
  });  // إغلاق القوس المفتوح في السطر السابق
  const profSel = $("profSel");  // تعريف الثابت profSel = نتيجة استدعاء
  if (profSel) {  // شرط: profSel
    profSel.addEventListener("change", () => loadProfile(profSel.value));  // استدعاء الدالة profSel.addEventListener("change", () => loadProfile(profSel.valu)
    $("profDelBtn").addEventListener("click", async () => {  // تكملة السطر السابق
      const name = profSel.value;  // تعريف الثابت name = قيمة
      if (!name || !window.confirm(name + " ?")) return;  // تنفيذ التعليمة السابقة
      const r = await api("/api/profiles/delete", { name });  // تعريف الثابت r = نتيجة استدعاء
      renderProfiles(r.profiles);  // استدعاء الدالة renderProfiles(r.profiles)
      toast("🗑 " + name);  // استدعاء الدالة toast("🗑 " + name)
    });  // إغلاق القوس المفتوح في السطر السابق
  }  // إغلاق الكتلة السابقة
  $("clearLogBtn").addEventListener("click", () => { $("logBody").innerHTML = ""; S.rows = 0; });  // استدعاء الدالة $("clearLogBtn").addEventListener("click",)
  $("downloadBtn").addEventListener("click", () => {  // تكملة السطر السابق
    if (!S.lastReport) { toast("—"); return; }  // تكملة السطر السابق
    window.open(withToken("/api/report?name=" + encodeURIComponent(S.lastReport)), "_blank");  // استدعاء الدالة window.open(withToken("/api/report?name=" + encodeUR)
  });  // إغلاق القوس المفتوح في السطر السابق
  $("clearReviewBtn").addEventListener("click", async () => {  // تكملة السطر السابق
    await api("/api/cache/clear", { scope: "temp" });  // تنفيذ التعليمة السابقة
    $("reviewBox").innerHTML = t("review_none");  // استدعاء الدالة $("reviewBox").innerHTML = t("review_none")
    toast("🧹");  // استدعاء الدالة toast("🧹")
  });  // إغلاق القوس المفتوح في السطر السابق
  $("presetRow").addEventListener("click", (e) => {  // تكملة السطر السابق
    const id = e.target.dataset && e.target.dataset.preset;  // تعريف الثابت id = قيمة
    if (!id || !S.meta) return;  // تنفيذ التعليمة السابقة
    const p = S.meta.presets.find((x) => x.id === id);  // تعريف الثابت p = نتيجة استدعاء
    if (!p) return;  // تنفيذ التعليمة السابقة
    if (id === "fast" && !window.confirm(t("warn_fast_preset"))) return;  // تنفيذ التعليمة السابقة
    $("r_threads").value = p.threads;  // تنفيذ التعليمة السابقة
    $("r_attempts").value = p.attempts;  // تنفيذ التعليمة السابقة
    $("r_delay").value = p.delay_ms;  // تنفيذ التعليمة السابقة
    updateLoadWarnings(profileFromForm(), p.threads, $("runLoadWarn"));  // استدعاء الدالة updateLoadWarnings(profileFromForm(), p.threads, $("runLoad)
  });  // إغلاق القوس المفتوح في السطر السابق
  ["r_threads", "r_attempts"].forEach((id) => {  // تكملة السطر السابق
    const node = $(id);  // تعريف الثابت node = نتيجة استدعاء
    if (node) node.addEventListener("input", () => {  // تكملة السطر السابق
      updateLoadWarnings(profileFromForm(),  // عنصر في القائمة/الكائن (يتبعه المزيد)
        parseInt(($("r_threads") || {}).value || "12", 10), $("runLoadWarn"));  // استدعاء الدالة parseInt(($("r_threads") || {}).value || "12", 10)
    });  // إغلاق القوس المفتوح في السطر السابق
  });  // إغلاق القوس المفتوح في السطر السابق
  ["f_prefix", "f_length", "f_custom", "f_pass_mode", "f_charset", "f_login_url",  // عنصر في القائمة/الكائن (يتبعه المزيد)
   "f_method", "f_user_field", "f_pass_field", "f_name"].forEach((id) => {  // تكملة السطر السابق
    const node = $(id);  // تعريف الثابت node = نتيجة استدعاء
    if (node) { node.addEventListener("input", previewFormat);  // تنفيذ التعليمة السابقة
                node.addEventListener("change", previewFormat); }  // تكملة السطر السابق
  });  // إغلاق القوس المفتوح في السطر السابق
  $("f_charset").addEventListener("change", () => { toggleCustomCharset(); previewFormat(); });  // استدعاء الدالة $("f_charset").addEventListener("change", )
  /* new flow buttons */
  const btnNew = $("btnNewProfile");  // تعريف الثابت btnNew = نتيجة استدعاء
  if (btnNew) btnNew.addEventListener("click", () => showNewProfile());  // تنفيذ التعليمة السابقة
  const btnSaved = $("btnSavedProfile");  // تعريف الثابت btnSaved = نتيجة استدعاء
  if (btnSaved) btnSaved.addEventListener("click", () => showSaved());  // تنفيذ التعليمة السابقة
  const backStartSaved = $("backToStartFromSaved");  // تعريف الثابت backStartSaved = نتيجة استدعاء
  if (backStartSaved) backStartSaved.addEventListener("click", () => showStart());  // تنفيذ التعليمة السابقة
  const backStartScan = $("backToStartFromScan");  // تعريف الثابت backStartScan = نتيجة استدعاء
  if (backStartScan) backStartScan.addEventListener("click", () => showStart());  // تنفيذ التعليمة السابقة
  const backScan = $("backToScanBtn");  // تعريف الثابت backScan = نتيجة استدعاء
  if (backScan) backScan.addEventListener("click", () => { S.currentFlow = "new"; step("scan"); });  // تنفيذ التعليمة السابقة
  const backFormat = $("backToFormatBtn");  // تعريف الثابت backFormat = نتيجة استدعاء
  if (backFormat) backFormat.addEventListener("click", () => {  // تكملة السطر السابق
    if (S.currentFlow === "saved" || S.savedProfileMode) {  // شرط: S.currentFlow === "saved" || S.savedProfileMode
      showProfileReview(S.profile);  // استدعاء الدالة showProfileReview(S.profile)
    } else {  // فرع else
      step("format");  // استدعاء الدالة step("format")
    }  // إغلاق الكتلة السابقة
  });  // إغلاق القوس المفتوح في السطر السابق
  const backSaved = $("backToSavedBtn");  // تعريف الثابت backSaved = نتيجة استدعاء
  if (backSaved) backSaved.addEventListener("click", () => showSaved());  // تنفيذ التعليمة السابقة
  const editBtn = $("editProfileBtn");  // تعريف الثابت editBtn = نتيجة استدعاء
  if (editBtn) editBtn.addEventListener("click", () => {  // تكملة السطر السابق
    /* Go to format panel with profile loaded for manual edit */
    const p = profileFromReview();  // تعريف الثابت p = نتيجة استدعاء
    S.profile = p;  // إسناد قيمة إلى S.profile
    fillFormFromProfile(p);  // استدعاء الدالة fillFormFromProfile(p)
    S.currentFlow = "saved";  // إسناد نص إلى S.currentFlow
    S.savedProfileMode = true;  // إسناد قيمة منطقية إلى S.savedProfileMode
    step("format");  // استدعاء الدالة step("format")
  });  // إغلاق القوس المفتوح في السطر السابق
  const startReview = $("startFromReviewBtn");  // تعريف الثابت startReview = نتيجة استدعاء
  if (startReview) startReview.addEventListener("click", () => startFromReview());  // تنفيذ التعليمة السابقة
  /* review edit fields live preview */
  ["rv_login_url","rv_method","rv_user_field","rv_pass_field","rv_pass_mode","rv_dst","rv_prefix","rv_length","rv_charset","rv_threads","rv_attempts","rv_delay"].forEach((id) => {  // تكملة السطر السابق
    const node = $(id);  // تعريف الثابت node = نتيجة استدعاء
    if (node) {  // شرط: node
      node.addEventListener("input", () => {  // تكملة السطر السابق
        const p = profileFromReview();  // تعريف الثابت p = نتيجة استدعاء
        renderReviewSummary(p);  // استدعاء الدالة renderReviewSummary(p)
      });  // إغلاق القوس المفتوح في السطر السابق
      node.addEventListener("change", () => {  // تكملة السطر السابق
        const p = profileFromReview();  // تعريف الثابت p = نتيجة استدعاء
        renderReviewSummary(p);  // استدعاء الدالة renderReviewSummary(p)
      });  // إغلاق القوس المفتوح في السطر السابق
    }  // إغلاق الكتلة السابقة
  });  // إغلاق القوس المفتوح في السطر السابق
  /* allow steps navigation for start */
  const stepStart = document.querySelector('.step[data-step="start"]');  // تعريف الثابت stepStart = نتيجة استدعاء
  if (stepStart) stepStart.addEventListener("click", () => showStart());  // تنفيذ التعليمة السابقة

  /* probe link on start screen */
  const probeBtn = $("probeLinkBtn");  // تعريف الثابت probeBtn = نتيجة استدعاء
  if (probeBtn) probeBtn.addEventListener("click", () => probeLink());  // تنفيذ التعليمة السابقة
  const savedSearch = $("savedSearch");  // تعريف الثابت savedSearch = نتيجة استدعاء
  if (savedSearch) {  // شرط: savedSearch
    savedSearch.addEventListener("input", () => renderSavedList());  // استدعاء الدالة savedSearch.addEventListener("input", () => renderSavedList())
    const ph = t("saved_search_ph");  // تعريف الثابت ph = نتيجة استدعاء
    if (ph) savedSearch.placeholder = ph;  // تنفيذ التعليمة السابقة
  }  // إغلاق الكتلة السابقة
  const exportBtn = $("exportProfileBtn");  // تعريف الثابت exportBtn = نتيجة استدعاء
  if (exportBtn) exportBtn.addEventListener("click", () => exportCurrentProfile());  // تنفيذ التعليمة السابقة
  const importBtn = $("importProfileBtn");  // تعريف الثابت importBtn = نتيجة استدعاء
  const importFile = $("importProfileFile");  // تعريف الثابت importFile = نتيجة استدعاء
  if (importBtn && importFile) {  // شرط: importBtn && importFile
    importBtn.addEventListener("click", () => importFile.click());  // استدعاء الدالة importBtn.addEventListener("click", () => importFile.click())
    importFile.addEventListener("change", () => importProfileFromFile(importFile));  // استدعاء الدالة importFile.addEventListener("change", () => importProfileFromFile(im)
  }  // إغلاق الكتلة السابقة
  const saveNet = $("saveNetSettingsBtn");  // تعريف الثابت saveNet = نتيجة استدعاء
  if (saveNet) saveNet.addEventListener("click", () => saveNetSettings());  // تنفيذ التعليمة السابقة
}  // إغلاق الكتلة السابقة

async function probeLink() {  // تكملة السطر السابق
  const url = (($("probeUrl") && $("probeUrl").value) ||  // تعريف الثابت url = قيمة
               ($("scanUrl") && $("scanUrl").value) || "").trim();  // تنفيذ التعليمة السابقة
  const box = $("probeLinkResult");  // تعريف الثابت box = نتيجة استدعاء
  if (!url) { toast(t("scan_fail")); return; }  // تكملة السطر السابق
  if (box) { box.classList.remove("hidden"); box.innerHTML = t("loading"); }  // تكملة السطر السابق
  const res = await api("/api/probe-link", { url });  // تعريف الثابت res = نتيجة استدعاء
  if (!box) return;  // تنفيذ التعليمة السابقة
  if (res.ok && res.reachable) {  // شرط: res.ok && res.reachable
    box.innerHTML = "<h4 class='ok'>" + esc(t("probe_reachable")) + "</h4>" +  // إسناد نص إلى box.innerHTML
      "<div class='kv'><dt>HTTP " + esc(String(res.status)) + " · " +  // تكملة السطر السابق
      esc(String(res.ms)) + " ms</dt><dd>" + esc(res.final_url || url) + "</dd>" +  // تكملة السطر السابق
      "<dt>" + esc(res.has_login_form ? t("probe_has_form") : t("probe_no_form")) +  // تكملة السطر السابق
      "</dt><dd></dd></div>";  // تنفيذ التعليمة السابقة
  } else {  // فرع else
    box.innerHTML = "<h4 class='bad'>" + esc(t("probe_unreachable")) + "</h4>" +  // إسناد نص إلى box.innerHTML
      "<div class='kv'><dt>" + esc(t("net_" + (res.error || res.hint || ""),  // عنصر في القائمة/الكائن (يتبعه المزيد)
                                    res.error || res.hint || "")) +  // تكملة السطر السابق
      "</dt><dd>" + esc(res.detail || "") + "</dd></div>";  // تنفيذ التعليمة السابقة
  }  // إغلاق الكتلة السابقة
}  // إغلاق الكتلة السابقة

async function exportCurrentProfile() {  // تكملة السطر السابق
  const p = S.profile || profileFromReview();  // تعريف الثابت p = نتيجة استدعاء
  const name = (p && p.name) || "";  // تعريف الثابت name = قيمة
  if (!name) { toast(t("scan_fail")); return; }  // تكملة السطر السابق
  const r = await api("/api/profiles/export", { name });  // تعريف الثابت r = نتيجة استدعاء
  if (!r.ok || !r.profile) { toast(t("scan_fail")); return; }  // تكملة السطر السابق
  const blob = new Blob([JSON.stringify(r.profile, null, 2)],  // تعريف الثابت blob = قيمة
                        { type: "application/json" });  // تنفيذ التعليمة السابقة
  const a = document.createElement("a");  // تعريف الثابت a = نتيجة استدعاء
  a.href = URL.createObjectURL(blob);  // إسناد نتيجة استدعاء إلى a.href
  a.download = (name || "profile") + ".kirapass.json";  // إسناد قيمة إلى a.download
  a.click();  // استدعاء الدالة a.click()
  URL.revokeObjectURL(a.href);  // استدعاء الدالة URL.revokeObjectURL(a.href)
  toast(t("export_ok"));  // استدعاء الدالة toast(t("export_ok"))
}  // إغلاق الكتلة السابقة

async function importProfileFromFile(input) {  // تكملة السطر السابق
  const file = input.files && input.files[0];  // تعريف الثابت file = قيمة
  if (!file) return;  // تنفيذ التعليمة السابقة
  try {  // بداية try محمية
    const text = await file.text();  // تعريف الثابت text = نتيجة استدعاء
    const data = JSON.parse(text);  // تعريف الثابت data = نتيجة استدعاء
    const profile = data.profile || data;  // تعريف الثابت profile = قيمة
    const r = await api("/api/profiles/import", { profile });  // تعريف الثابت r = نتيجة استدعاء
    if (!r.ok) {  // شرط: !r.ok
      toast(t("import_fail"));  // استدعاء الدالة toast(t("import_fail"))
      modal(t("import_fail"), "<pre>" + esc(JSON.stringify(r.problems || r, null, 2)) + "</pre>");  // استدعاء الدالة modal(t("import_fail"), "<pre>" + esc(JSON.str)
      return;  // إرجاع ;
    }  // إغلاق الكتلة السابقة
    S.meta.profiles = r.profiles || [];  // إسناد قيمة إلى S.meta.profiles
    renderProfiles(r.profiles);  // استدعاء الدالة renderProfiles(r.profiles)
    renderSavedList(r.profiles);  // استدعاء الدالة renderSavedList(r.profiles)
    toast(t("import_ok"));  // استدعاء الدالة toast(t("import_ok"))
    if (r.profile) showProfileReview(r.profile);  // تنفيذ التعليمة السابقة
  } catch (e) {  // التقاط الخطأ في e
    toast(t("import_fail"));  // استدعاء الدالة toast(t("import_fail"))
  }  // إغلاق الكتلة السابقة
  input.value = "";  // إسناد نص إلى input.value
}  // إغلاق الكتلة السابقة

async function saveNetSettings() {  // تكملة السطر السابق
  const payload = {  // تعريف الثابت payload = كائن
    internet_check_url: ($("f_internet_check") || {}).value || "",  // مفتاح internet_check_url في الكائن = قيمة
    connect_timeout: parseFloat(($("f_connect_timeout") || {}).value || "4"),  // مفتاح connect_timeout في الكائن = نتيجة استدعاء
    read_timeout: parseFloat(($("f_read_timeout") || {}).value || "8"),  // مفتاح read_timeout في الكائن = نتيجة استدعاء
  };  // إغلاق الكتلة السابقة
  const r = await api("/api/settings", payload);  // تعريف الثابت r = نتيجة استدعاء
  if (r.ok) {  // شرط: r.ok
    if (S.meta) S.meta.settings = r.settings || payload;  // تنفيذ التعليمة السابقة
    toast(t("net_settings_saved"));  // استدعاء الدالة toast(t("net_settings_saved"))
  } else {  // فرع else
    toast(t("scan_fail"));  // استدعاء الدالة toast(t("scan_fail"))
  }  // إغلاق الكتلة السابقة
}  // إغلاق الكتلة السابقة

function applyNetSettingsFromMeta(meta) {  // تعريف الدالة applyNetSettingsFromMeta(meta)
  const s = (meta && meta.settings) || {};  // تعريف الثابت s = قيمة
  const d = (meta && meta.defaults) || {};  // تعريف الثابت d = قيمة
  if ($("f_internet_check"))  // شرط: $("f_internet_check")
    $("f_internet_check").value = s.internet_check_url || "";  // تنفيذ التعليمة السابقة
  if ($("f_connect_timeout"))  // شرط: $("f_connect_timeout")
    $("f_connect_timeout").value = s.connect_timeout || d.connect_timeout || 4;  // تنفيذ التعليمة السابقة
  if ($("f_read_timeout"))  // شرط: $("f_read_timeout")
    $("f_read_timeout").value = s.read_timeout || d.read_timeout || 8;  // تنفيذ التعليمة السابقة
  const lan = $("lanWarningCard");  // تعريف الثابت lan = نتيجة استدعاء
  if (lan && meta && meta.lan_open) {  // شرط: lan && meta && meta.lan_open
    lan.classList.remove("hidden");  // استدعاء الدالة lan.classList.remove("hidden")
    lan.innerHTML = "<h4 class='warn'>" + esc(t("lan_warning_title")) + "</h4><p>" +  // إسناد نص إلى lan.innerHTML
      esc(t("lan_warning_body")) + "</p>";  // تنفيذ التعليمة السابقة
  }  // إغلاق الكتلة السابقة
}  // إغلاق الكتلة السابقة


/* ------------------------------------------------------------------ boot */
(async function boot() {  // تكملة السطر السابق
  const meta = await api("/api/meta");  // تعريف الثابت meta = نتيجة استدعاء
  S.meta = meta || {};  // إسناد قيمة إلى S.meta
  if (meta.app) document.title = meta.app + " — " + meta.version;  // تنفيذ التعليمة السابقة
  $("verPill").textContent = "v" + (meta.version || "");  // استدعاء الدالة $("verPill").textContent = "v" + (meta.ver)
  buildSelects();  // استدعاء الدالة buildSelects()
  const saved = localStorage.getItem("kirapass_lang") || meta.lang || "ar";  // تعريف الثابت saved = قيمة
  setLang(saved);  // استدعاء الدالة setLang(saved)
  wire();  // استدعاء الدالة wire()
  toggleCustomCharset();  // استدعاء الدالة toggleCustomCharset()
  previewFormat();  // استدعاء الدالة previewFormat()
  applyNetSettingsFromMeta(meta);  // استدعاء الدالة applyNetSettingsFromMeta(meta)
  renderProfiles(meta.profiles || []);  // استدعاء الدالة renderProfiles(meta.profiles || [])
  renderSavedList(meta.profiles || []);  // استدعاء الدالة renderSavedList(meta.profiles || [])
  showStart();  // استدعاء الدالة showStart()
  await restoreActiveRun();
})();  // تنفيذ التعليمة السابقة
