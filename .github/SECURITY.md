# Security Policy

## الإبلاغ عن ثغرة
هذه منصّة **داخلية**. أبلغ عن أي ثغرة أمنية **مباشرةً لمالك المستودع** — لا تفتح Issue/PR عاماً بالتفاصيل.

## نموذج الأمان (Phase 1)
- البوّابة والمحرّك (`vllm`) وpostgres **غير مكشوفة**؛ المنفذ العام الوحيد = Open WebUI (R-ARCH-24). *(ملاحظة ADR-028: مصادقة vLLM تغطي `/v1` فقط — بقاء منفذه داخلياً شرط أمني لا اختياري.)*
- **كل مرور موديل عبر بوّابة LiteLLM** بمفاتيح virtual keys مُنطاقة least-privilege (ADR-023؛ `OPENWEBUI_LITELLM_KEY` للدردشة).
- الذاكرة/الملفات عبر ميزات Open WebUI المدمجة (RAG + Memory، [ADR-025](../docs/DECISIONS.md))؛ عزل per-user يديره OWUI. محرّك السياق المخصّص (وعزله `WHERE user_id` المُختبَر) متقاعد إلى فرع `future/context-engine`.
- الأسرار من `.env` (git-ignored)؛ لا أسرار في الكود/الصور (R-ARCH-20، gitleaks في CI). الصور الأربع جاهزة بأوضاعها الافتراضية — **حاوية المحرّك (`vllm`) تعمل جذراً** (افتراض الصورة الرسمية؛ مقبول لأنها على الشبكة الداخلية فقط — ADR-028)؛ non-root يعود شرطاً مع أي صورة نبنيها بأنفسنا.
- **قاعدة البيانات least-privilege ([ADR-029](../docs/DECISIONS.md)):** الـ superuser (`postgres`) للإدارة فقط — **لا يتصل به أي تطبيق**؛ كل تطبيق بدور عادي يملك قاعدته فقط + `REVOKE CONNECT FROM PUBLIC` (عزل CONNECT بالاتجاهين، مُثبَت باختبار سلبي). هذا يزرع "role split" المطلوب لـ RLS المستقبلي (v2 أدناه).

## معروف ومؤجَّل — **إلزامي قبل أي تعريض خارجي** (v2)
هوية `X-OpenWebUI-User-Id` **قابلة للانتحال** (مفتاح OWUI مشترك)؛ الحدّ الأمني الحالي = البوّابة الداخلية. قبل أي فتح خارجي تجب: RLS كامل (role split + FORCE + WITH CHECK) + virtual keys per-user + تجريد الهوية من الـ header (المواصفة §9، [docs/DECISIONS.md](../docs/DECISIONS.md) ADR-012).
