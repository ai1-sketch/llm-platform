# Security Policy

## الإبلاغ عن ثغرة
هذه منصّة **داخلية**. أبلغ عن أي ثغرة أمنية **مباشرةً لمالك المستودع** — لا تفتح Issue/PR عاماً بالتفاصيل.

## نموذج الأمان (Phase 1)
- البوّابة والمحرّكان (`llamacpp`/`embeddings`) والذاكرة وpostgres **غير مكشوفة**؛ المنفذ العام الوحيد = Open WebUI (R-ARCH-24).
- **كل مرور موديل عبر بوّابة LiteLLM** بمفاتيح virtual keys مُنطاقة least-privilege (ADR-023؛ مفتاح `memory` يصل `embed-default` فقط — مُتحقَّق: 403 على موديل الدردشة).
- الأسرار من `.env` (git-ignored)؛ لا أسرار في الكود/الصور (R-ARCH-20، gitleaks في CI). الصورة تعمل **غير-جذر**.
- عزل الذاكرة per-user بـ `WHERE user_id` على كل استعلام (مُختبَر على Postgres حقيقي، بوّابة CI).

## معروف ومؤجَّل — **إلزامي قبل أي تعريض خارجي** (v2)
هوية `X-OpenWebUI-User-Id` **قابلة للانتحال** (مفتاح OWUI مشترك)؛ الحدّ الأمني الحالي = البوّابة الداخلية. قبل أي فتح خارجي تجب: RLS كامل (role split + FORCE + WITH CHECK) + virtual keys per-user + تجريد الهوية من الـ header (المواصفة §9، [docs/DECISIONS.md](../docs/DECISIONS.md) ADR-012).
