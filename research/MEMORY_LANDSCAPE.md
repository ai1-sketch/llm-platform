# خريطة مشهد ذاكرة الـ LLM — مرجع بحثي شامل

> **مالك المشروع (Project owner): Ali Odeh.**

> ⚠️ **تحديث ([ADR-025](../docs/DECISIONS.md), 2026-06-26):** اعتمد المالك لاحقاً **ذاكرة/RAG المدمجة في Open WebUI** كمسار أساسي (والمحرّك المخصّص متقاعد إلى فرع). توصيات هذا المسح (التي كانت تميل لمسار hook مخصّص وتُقلّل من OWUI Native Memory بحجّة "تحتاج موديلات frontier") **تجاوزها القرار** — والموديل المخطّط (Gemini) يعالج تحفّظ "موديل frontier". اقرأه كمرجع تاريخي/مستقبلي لا كتوصية حالية.
>
> ناتج مسح موسوعي (11 مساعد، بحث ويب) — مرجع لقرار ADR-012. ليس وثيقة حوكمة (معفى من حدّ 180 سطر).
> التاريخ: 2026-06-24.

## كتالوج موسوعي لذاكرة الـ LLM (منظّم بالفئات)

> رمز الملاءمة: ✅ واقعي لنا · 🟡 ممكن بتحفّظ · 📚 موسوعي للعلم (مستبعَد عملياً)

---

### الفئة 1 — أطر الذاكرة (Frameworks)

| العنصر | الآلية (سطر-سطران) | الحالة |
|---|---|---|
| **LangChain Memory الكلاسيكي** (Buffer/Window/Summary/SummaryBuffer/TokenBuffer/Entity/KG/VectorRetriever/Combined) | كلاسات ذاكرة تقليدية تحقن التاريخ خاماً/ملخّصاً/متجهياً. **كلها deprecated v0.3.1 وتُزال في v1.0** — تُؤخذ منها الأنماط لا الكود. | 📚 (الأنماط ✅) |
| **LangGraph Checkpointers** (PostgresSaver) | يحفظ لقطة حالة الغراف لكل خطوة مفهرسة بـ thread_id؛ ذاكرة قصيرة المدى داخل الجلسة. يستثمر Postgres مباشرة. لا يلخّص وحده. | 🟡 |
| **LangGraph BaseStore** (PostgresStore) | مخزن key-value بـ namespaces + بحث دلالي اختياري؛ ذاكرة طويلة عابرة للجلسات على pgvector. | 🟡 |
| **LangMem SDK** | طبقة "دماغ" فوق Store تقرّر ماذا يُحفظ/يُحدّث/يُحذف (دلالي/عرضي/إجرائي) + consolidation خلفي. استدعاءات LLM للإدارة. | 🟡 (ثقيل كبداية) |
| **LlamaIndex — Memory (الموحّد الجديد)** | صنف يدمج قصير (FIFO) + طويل (Blocks) بضبط توكنات دقيق (token_limit/ratio/flush) + tokenizer قابل للتخصيص. خفيف (llama-index-core). | ✅ |
| **LlamaIndex — Memory Blocks** (Static/FactExtraction/Vector) | كتل: ثابتة (priority=0)، استخراج حقائق (LLM)، متجهية (pgvector). تركيب قصير+طويل. | 🟡 |
| **LlamaIndex — ChatMemoryBuffer / SummaryBuffer / SimpleComposable** | عوازل قديمة (FIFO/ملخّص/تركيبي). **مهجورة** لصالح Memory+Blocks. | 📚 |
| **Haystack** (ConversationMemory/Summary, ChatMessageStore 2.x) | ذاكرة داخل خط أنابيب Haystack؛ 2.x تجريبي. إطار كامل خارج مكدّسنا. | 📚 |
| **Semantic Kernel** (SemanticTextMemory legacy + Vector Store connectors preview) | Save/Recall + موصّلات Postgres؛ القديم مهجور والجديد Preview متقلّب. إطار .NET/Python كامل. | 📚 |
| **AutoGen v0.4 / AG2** (Memory protocol, ListMemory, ChromaDB/Redis/Mem0, Teachability) | بروتوكول query/update_context نظيف + تطبيقات ذاكرة؛ لكنه إطار وكلاء كامل. Teachability = "علّمني مرة". | 📚 (البروتوكول مُلهِم) |
| **txtai** | مكتبة embeddings خفيفة (تضمين+بحث+RAG، SQLite/Postgres، embedded بلا خادم). أخف بديل للأطر الثقيلة. | 🟡 |
| **خيار "صفر-إطار"** (دوال Python في LiteLLM hook + EmbedChain) | لا إطار: دوال تستعلم pgvector وتحقن/تكتب مباشرة في الـ hook. خط الأساس anti-bloat. | ✅ |

---

### الفئة 2 — منتجات الذاكرة المخصّصة (Dedicated Products)

| العنصر | الآلية | الحالة |
|---|---|---|
| **Mem0 (self-hosted) / OpenMemory** | يستخرج "حقائق" بـ LLM لكل add()، dedup تكيّفي، يخزّن في pgvector + graph اختياري (Neo4j). OpenAI-compatible → /v1. | ✅ (مع تحفّظ VRAM) |
| **Letta (MemGPT)** | إطار وكلاء stateful بهرمية ذاكرة OS (core/recall/archival) + self-editing عبر tools. **صورة Docker لم تعد مدعومة بنشاط**. | 📚 |
| **Zep + Graphiti** | knowledge graph زمني ثنائي الزمن (valid_at/invalid_at) مع إبطال تلقائي للحقائق. **أعلى دقة (63.8% LongMemEval)** لكن يحتاج Neo4j/FalkorDB. | 🟡 (ترقية لاحقة) |
| **Cognee** | خط ECL (Extract→Cognify→Load)، hybrid vector+graph، 14 وضع استرجاع، multi-hop. ثقيل/معقّد. | 📚 |
| **Memary** | ذاكرة graph (Neo4j) للوكلاء المستقلّين، multi-hop. نضج/صيانة أقل. | 📚 |
| **MemoryScope (Alibaba)** | ذاكرة طويلة بـ 20+ worker + consolidation/reflection؛ ElasticSearch افتراضي، عربية غير مؤكّدة. | 📚 |
| **Redis Agent Memory Server** | working (short) + long-term دلالي، ترقية async non-blocking + تلخيص تلقائي. REST+MCP. يضيف Redis. | 🟡 |
| **MCP memory servers** (الرسمي KG + Graphiti/Mem0/Redis MCP) | الرسمي = KG بسيط بملف JSONL (للنماذج فقط)؛ MCP = بروتوكول دمج محايد. غير ناضج مع Open WebUI/LiteLLM. | 📚 |
| **Memvid** | ذاكرة كـ "Smart Frames" في ملف append-only واحد، serverless، محلي، محايد، خفيف جداً. ادعاءات أداء تحتاج تحقّق. | 🟡 (PoC) |
| **Hindsight** | 4 شبكات ذاكرة (World/Experience/Opinion/Entity) تفصل الحقائق عن المعتقدات. ثقيل لحجمنا. | 📚 |

---

### الفئة 3 — التقنيات البحثية (Research Techniques)

| العنصر | الآلية | الحالة |
|---|---|---|
| **RAG الكلاسيكي** (Lewis 2020) | تقطيع→تضمين→top-k→حقن. أبسط ذاكرة دلالية، يعمل على pgvector. | ✅ |
| **Generative Agents** (recency+importance+relevance) | استرجاع بمزج 3 إشارات مُطبّعة + reflection دوري. لا يحتاج tool-calling = يلائم النماذج الصغيرة. | ✅ |
| **MemGPT** (LLM-as-OS) | paging بين النافذة والأرشيف عبر function calls ذاتية. يعطي وهم سياق لا نهائي لكن يعتمد tool-calling قوي. | 🟡 |
| **CoALA** (Working/Episodic/Semantic/Procedural) | تصنيف معرفي مرجعي لما يُخزَّن أين. خريطة تصميم محايدة بحتة. | ✅ (كإطار) |
| **Consolidation / Decay / Forgetting** (Ebbinghaus, MemoryBank) | دمج الحلقي→دلالي + تلاشٍ للقديم. تنفيذ خفيف (حقول strength + cron). جوهري لـ anti-bloat. | ✅ |
| **استخراج الحقائق/الكيانات** (Mem0/A-MEM/MemLLM) | LLM يستخرج حقائق منظّمة بدل النص الخام + add/update/delete للتعارض. | 🟡 |
| **Self-RAG** | استرجاع انتقائي + نقد ذاتي عبر reflection tokens. النسخة الأصلية تتطلب fine-tuning (تكسر الحياد). المحاكاة بـ prompting ممكنة. | 🟡 (محاكاة) |
| **Corrective RAG (CRAG)** | مُقيّم استرجاع خفيف + إجراء تصحيحي/fallback. خطوة إضافية لكل استعلام. | 📚 |
| **GraphRAG (Microsoft)** | بناء KG + ملخّصات مجتمعات للأسئلة الشاملة. آلاف استدعاءات LLM = مكلف جداً. | 📚 |
| **HippoRAG** | KG موحّد + Personalized PageRank لـ multi-hop (training-free). أخف من GraphRAG. | 📚 |
| **RAPTOR** | شجرة تلخيص هرمية (clustering+summarize تصاعدي)، استرجاع coarse-to-fine. بناء offline. | 🟡 |
| **A-MEM** (Zettelkasten) | ملاحظات ذرّية مترابطة ذاتية التطور بروابط LLM. مكلف وقت الكتابة. | 📚 |
| **MemGen / Titans** (latent/neural memory) | ذاكرة كـ latent tokens / وزن عصبي يتعلّم وقت الاختبار. **يكسر حياد الموديل ويحتاج تدريب**. | 📚 |

---

### الفئة 4 — التخزين والاسترجاع (Storage & Retrieval)

| العنصر | الآلية | الحالة |
|---|---|---|
| **pgvector** | امتداد Postgres (HNSW/IVFFlat + halfvec/quantization). صفر خدمة جديدة، SQL+فلترة+ACID. | ✅ |
| **VectorChord / pgvectorscale** | امتدادات تسريع فوق pgvector (DiskANN/SBQ + BM25). ترقية بلا مغادرة Postgres. | 🟡 |
| **halfvec + تكميم (binary/scalar)** | float16 = نصف الذاكرة بلا خسارة recall؛ binary = ضغط شديد + rerank. **تمكيني حرج لـ 6GB**. | ✅ |
| **Matryoshka Adaptive Retrieval + binary→rerank funnel** | استرجاع coarse-to-fine: binary shortlist ثم halfvec rerank. خفض ذاكرة+كمون داخل pgvector. | ✅ |
| **Qdrant / Chroma / LanceDB / Milvus / Weaviate / Redis-vector** | قواعد متجهات متخصصة/embedded. كلها تضيف خدمة/ازدواج تخزين (LanceDB الأخف embedded). | 📚 (Qdrant/Milvus/Weaviate) · 🟡 (LanceDB) |
| **BGE-M3** | embedding متعدد لغات (عربي جيد)، dense+sparse+ColBERT، بُعد 1024، نافذة 8192. ~568M يزاحم VRAM. | 🟡 |
| **Qwen3-Embedding-0.6B** | محلي، Apache، خفيف جداً، عربي جيد، Matryoshka، يتسق مع ستاك Qwen المثبّت. | ✅ |
| **gte-multilingual-base** | 305M، نافذة 8192، Matryoshka، متعدد لغات. توازن خفّة/جودة. | ✅ |
| **multilingual-e5 (s/b/l)** | مستقر راسخ، أحجام متدرّجة (384–1024)، نافذة 512، عربي مقبول. | 🟡 |
| **النماذج العربية** (Swan/GATE/ATM-V2) | أعلى دقة عربية + Matryoshka، أحجام base خفيفة. ضعف متعدد اللغات/الكود. | 🟡 (لو عربي غالب) |
| **nomic / jina-v3** | nomic خفيف لكن عربي ضعيف؛ jina-v3 قوي متعدد لغات لكن رخصة CC-BY-NC وحجم كبير. | 📚 |
| **بحث هجين في Postgres** (tsvector / pg_search-BM25 / pg_textsearch + RRF) | دمج dense+lexical عبر RRF (k=60) باستعلام واحد بلا Elasticsearch. يحسّن العربية. | ✅ |
| **تجزئة/تطبيع عربي لـ BM25** (CAMeL/Farasa/Tashaphyne) | تطبيع همزات/تشكيل + stemming قبل الفهرسة. بدونها يُهدر نصف فائدة BM25 العربي. | ✅ |
| **Rerankers** (bge-reranker-v2-m3 / mxbai-v2 / jina-v2 / ColBERT) | cross-encoder يعيد ترتيب top-N (دقة أعلى). مكلف؛ يُشغّل على CPU أو يؤجَّل. | 🟡 (مؤجَّل) |
| **قواعد الرسوم** (Neo4j/Kuzu/FalkorDB) | عقد+علاقات لـ GraphRAG. خدمة/ذاكرة إضافية. Kuzu أُرشِف 2025. | 📚 |
| **Apache AGE + pg_trgm** | graph (openCypher) داخل Postgres نفسه + مطابقة ضبابية عربية. GraphRAG بلا خدمة جديدة. | 🟡 |

---

### الفئة 5 — أنماط الدمج والأبعاد التشغيلية (Integration & Ops)

| العنصر | الآلية | الحالة |
|---|---|---|
| **LiteLLM async_pre/post_call hook** | حقن/استخراج الذاكرة في طبقة /v1 المركزية. **يحفظ حياد الواجهة+الموديل معاً**، يستخدم Postgres، صفر خدمة. | ✅ (الأنسب) |
| **Open WebUI Filter (inlet/outlet/stream)** | حقن على مستوى الواجهة بوصول __user__/__metadata__. محايد للموديل لكن **مربوط بالواجهة**. | 🟡 |
| **Open WebUI Native Memory / Adaptive Memory** | ذاكرة مدمجة (tool-calling) في Postgres. تحتاج frontier models؛ Beta غير مستقرة (v4 معطوبة). | 🟡 (نقطة بداية) |
| **Standalone Middleware Proxy** (Headroom/openai-http-proxy) | اعتراض /v1 مستقل. حياد تام لكن خدمة/قفزة شبكية إضافية (يهزمه الـ hook على anti-bloat). | 🟡 |
| **Semantic cache (LiteLLM) + Prompt/KV cache (llama.cpp)** | "شبه-ذاكرة" رخيصة: تجنّب إعادة التوليد + إعادة استخدام البريفكس الثابت. يخفّف GPU مباشرة (ليست ذاكرة استمرارية). | ✅ |
| **Observability/Tracing** (Langfuse self-host/Phoenix/OpenLLMetry) | يقيس ماذا استُرجِع/حُقِن/كلّف. ضروري لقرار "هل rerank يستحق كلفته". Langfuse على Postgres. | 🟡 |
| **Multi-tenancy isolation** (partitioning/RLS/filtered-HNSW) | عزل per-user في pgvector. انتبه: filtered-HNSW قد يكسر recall. حرج لـ 1→10. | ✅ |
| **استراتيجية ترحيل embedding** (version + backfill ليلي + shadow index) | تحوّل قيد "تبديل التضمين قاتل" إلى مخاطرة مُدارة عبر backfill خلفي. | ✅ |
| **هندسة الحقن** (JSON vs نص، موضع system vs last-user، token budget ~1500) | تنسيق/موضع/ميزانية الحقن. حرج لموديل 4B ونافذة 8192. | ✅ |
| **User-confirmed memory (HITL) + Memory UI** | موافقة "هل أحفظ X؟" + لوحة "ذاكرتي". يحمي من حقائق خاطئة لموديل صغير + GDPR. | ✅ |
| **Sleep-time consolidation (cron)** | دمج/تقطير الذاكرة خارج زمن الرد عبر LiteLLM ليلاً. لا يضخّم نافذة 8192 وقت الاستجابة. | ✅ |
| **Contextual Retrieval (Anthropic) / Late Chunking (Jina)** | تحسين جودة القطع: سياق مولّد قبل التضمين (LLM، offline) / تقطيع بعد تضمين الوثيقة كاملة (بلا LLM). | 🟡 |
| **Spreading Activation / Graph-walk** | انتشار تنشيط عبر روابط موزونة (recursive CTE في Postgres) لاسترجاع سياقي مترابط. | 📚 |

---

### الفئة 6 — الأبعاد التصنيفية المرجعية (Design Dimensions — CoALA + survey)

أنواع الذاكرة · النطاق (session/user/org/global) · سياسات الكتابة (explicit/automatic) · سياسات القراءة (top-k/hybrid/rerank/recency) · الإخلاء/النسيان (TTL/decay/consolidation) · حلّ التعارض (bi-temporal/invalidation/source-attribution) · الخصوصية وحق الحذف (GDPR م.15/16/17) · الركيزة التخزينية · سلطة التحكم (heuristic/prompted/learned) · التقييم (L1 مهمة، L2 جودة ذاكرة، L3 كفاءة، L4 حوكمة؛ بنشمارك LoCoMo/LongMemEval).

**أمنياً:** Memory Poisoning = OWASP ASI06 (2026) — أي ذاكرة دائمة تحتاج provenance + حذف/rollback + sanitization.

---

## مصفوفة القرار

## مصفوفة القرار — الخيارات القابلة للتطبيق على منصّتنا

التقييم: ✅ ممتاز · 🟡 مقبول/مشروط · ❌ ضعيف/يكسر القيد. (VRAM = أثر على بطاقة 6GB المشتركة مع llama.cpp؛ الجهد = جهد البناء/الصيانة).

### أ) أنماط الدمج (نقطة الحقن)

| الخيار | حياد الموديل | حياد الواجهة | VRAM/6GB | نافذة 8192 | العربية | anti-bloat | الجهد |
|---|---|---|---|---|---|---|---|
| **LiteLLM hook + pgvector (صفر-إطار)** | ✅ | ✅ | ✅ | ✅ (تحكم توكنات كامل) | 🟡 (رهن التضمين) | ✅ | 🟡 (تكتب المنطق) |
| Open WebUI Filter (inlet/outlet) | ✅ | ❌ (مربوط بالواجهة) | ✅ | ✅ | 🟡 | ✅ | 🟢 منخفض |
| Open WebUI Native/Adaptive Memory | ❌ (يحتاج frontier) | ❌ | ✅ | 🟡 | 🟡 | ✅ | 🟢 (لكن Beta) |
| Standalone middleware proxy | ✅ | ✅ | ✅ | ✅ | 🟡 | 🟡 (خدمة+قفزة) | 🟡 |

### ب) الأطر / المنتجات

| الخيار | حياد الموديل | حياد الواجهة | VRAM/6GB | نافذة 8192 | العربية | anti-bloat | الجهد |
|---|---|---|---|---|---|---|---|
| **txtai على pgvector** | ✅ | ✅ | ✅ | 🟡 | 🟡 | ✅ | 🟢 |
| **LlamaIndex Memory + VectorMemoryBlock** | ✅ | 🟡 (طبقة برمجية) | 🟡 (Fact block=LLM) | ✅ (ضبط توكنات) | 🟡 | 🟡 | 🟡 |
| LangGraph Saver+Store (+LangMem) | ✅ | 🟡 | 🟡 (LangMem=LLM) | 🟡 | 🟡 | 🟡 (إطار) | 🟡–🔴 |
| **Mem0 self-hosted (vector، بلا graph)** | ✅ (/v1) | ✅ | 🟡 (LLM استخراج لكل add) | ✅ | 🟡 | 🟡 (خدمة) | 🟡 |
| Redis Agent Memory Server | 🟡 (تحقّق /v1) | ✅ (REST) | 🟡 (Redis RAM) | ✅ (تلخيص تلقائي) | 🟡 | 🟡 (+Redis) | 🟡 |
| Zep + Graphiti | ✅ | ✅ | ❌ (graph build=LLM) | ✅ | 🟡 | ❌ (+Neo4j) | 🔴 |
| Letta (MemGPT) | 🟡 | ❌ (إطار وكيل) | ❌ (self-edit tools) | ✅ | 🟡 | ❌ | 🔴 (Docker مهمل) |
| Memvid (PoC) | ✅ | ✅ | ✅ | 🟡 | 🟡 (تحقّق) | ✅ | 🟢 |

### ج) التقنيات (منطق فوق /v1)

| الخيار | حياد الموديل | حياد الواجهة | VRAM/6GB | نافذة 8192 | العربية | anti-bloat | الجهد |
|---|---|---|---|---|---|---|---|
| **RAG كلاسيكي (top-k على pgvector)** | ✅ | ✅ | ✅ | ✅ | 🟡 | ✅ | 🟢 |
| **Generative Agents (recency+importance+relevance)** | ✅ (لا tool-call) | ✅ | 🟡 (importance=LLM دوري) | ✅ | 🟡 | ✅ | 🟡 |
| **Consolidation/Decay (cron + strength)** | ✅ | ✅ | 🟡 (تلخيص دوري) | ✅ (يكثّف) | 🟡 | ✅ | 🟡 |
| استخراج حقائق Mem0-style | ✅ | ✅ | 🟡 (LLM/كتابة) | ✅ | 🟡 (تحقّق) | 🟡 | 🟡 |
| RAPTOR (تلخيص هرمي) | ✅ | ✅ | 🟡 (بناء offline) | ✅ (يوفّر نافذة) | 🟡 | 🟡 | 🟡 |
| MemGPT paging | 🟡 (يحتاج tool-call) | ✅ | 🟡 | ✅ | 🟡 | 🟡 | 🔴 |

### د) التخزين / التضمين / الاسترجاع

| الخيار | حياد الموديل | حياد الواجهة | VRAM/6GB | نافذة 8192 | العربية | anti-bloat | الجهد |
|---|---|---|---|---|---|---|---|
| **pgvector + halfvec** | ✅ | ✅ | ✅ (-50% ذاكرة) | ✅ | n/a | ✅ | 🟢 |
| **Qwen3-Embedding-0.6B** | ✅ | ✅ | ✅ (خفيف) | ✅ | ✅ (جيد) | ✅ | 🟢 |
| gte-multilingual-base | ✅ | ✅ | ✅ (305M) | ✅ | 🟡 | ✅ | 🟢 |
| BGE-M3 | ✅ | ✅ | 🟡 (568M) | ✅ | ✅ | 🟡 (CPU/خدمة) | 🟡 |
| نماذج عربية (ATM-V2/GATE) | ✅ | ✅ | ✅ (base) | 🟡 | ✅✅ | ✅ | 🟡 |
| **هجين BM25(pg_search)+dense+RRF** | ✅ | ✅ | ✅ | ✅ | ✅ (مع تطبيع عربي) | ✅ (بلا ES) | 🟡 |
| **تطبيع/جذع عربي (CAMeL/Tashaphyne)** | ✅ | ✅ | ✅ | ✅ | ✅✅ | ✅ | 🟡 |
| Reranker (bge-reranker-v2-m3 CPU) | ✅ | ✅ | 🟡 (CPU/كمون) | ✅ | ✅ | 🟡 | 🟡 (مؤجَّل) |
| Apache AGE (graph في Postgres) | ✅ | ✅ | 🟡 (build=LLM) | ✅ | 🟡 | 🟡 (امتداد) | 🔴 (مؤجَّل) |

### هـ) الحوكمة والكفاءة (إلزامية مهما كان الاختيار)

| الخيار | الأثر | الحالة |
|---|---|---|
| **Semantic cache (LiteLLM) + KV/prefix cache** | يخفّف 6GB بصفر-إطار؛ يسرّع البريفكس الثابت | ✅ فعّل فوراً |
| **Multi-tenant isolation (user_id + RLS)** | عزل ذاكرة المستخدمين أمناً (1→10) | ✅ من اليوم-1 |
| **مسارات حذف/عرض/تصحيح (GDPR + OWASP ASI06)** | provenance + حق النسيان | ✅ من اليوم-1 |
| **embedding versioning + backfill ليلي** | يزيل خوف "القرار النهائي" للتضمين | ✅ صمّمه مبكراً |
| **Langfuse self-host (Postgres)** | يقيس قرارات الذاكرة (L2/L3) | 🟡 عند الحاجة |
| **هندسة الحقن (budget ~1500 tok، موضع، تنسيق)** | حرج لـ Gemma 4B + 8192 | ✅ |

---

## الشورت-ليست

## الشورت-ليست (4 خيارات واقعية لمنصّتنا)

كل الخيارات تشترك في: **التخزين = pgvector على Postgres الموجود + halfvec**، **التضمين = Qwen3-Embedding-0.6B** (محلي/Apache/خفيف/عربي/يتسق مع ستاك Qwen)، **العزل = user_id + RLS**، **حياد الموديل/الواجهة محفوظ**. الفرق في **مكان المنطق ومستوى التعقيد**.

---

### الخيار A — "صفر-إطار": LiteLLM hook + pgvector (خط الأساس الموصى به) ✅
- **الآلية:** دوال Python في `async_pre_call_hook` (تسترجع وتحقن) و`async_post_call_success_hook` (تكتب). RAG كلاسيكي + recency/importance بسيط، بلا أي إطار خارجي.
- **لماذا:** أقصى حياد (طبقة /v1 المركزية تخدم أي واجهة/موديل)، أقصى anti-bloat (صفر خدمة جديدة)، تحكم كامل بميزانية التوكنات (حرج لـ 8192)، تثبيت التضمين بمعزل عن الموديل التوليدي.
- **العيب:** تكتب منطق consolidation/dedup بنفسك (لكنه بسيط لـ 1–10 مستخدمين).

### الخيار B — txtai كطبقة دلالية خفيفة فوق pgvector 🟡
- **الآلية:** نفس نقطة الحقن (LiteLLM hook) لكن يستدعي txtai لإدارة التضمين/البحث/RAG في حزمة واحدة بدل كتابتها يدوياً.
- **لماذا:** يقلّل كود الاسترجاع المكتوب يدوياً مع بقاء الخفّة والحياد. وسط بين A وإطار ثقيل.
- **العيب:** نظام بيئي أصغر؛ تبعية إطار إضافية (طفيفة).

### الخيار C — Mem0 self-hosted (vector فقط، بلا graph) عبر /v1 🟡
- **الآلية:** خدمة Mem0 تستخرج "حقائق" تلقائياً (LLM عبر /v1) وتخزّن في pgvector، scoping بـ user_id جاهز، استرجاع تلقائي محقون.
- **لماذا:** حل ذاكرة "ذكي" جاهز (استخراج+dedup+scoping) دون كتابة المنطق؛ OpenAI-compatible يحفظ الحياد.
- **العيب:** استخراج LLM لكل كتابة = **ضغط على 6GB** (خفّفه: استخراج async/ليلي أو موديل استخراج أصغر)؛ يضيف خدمة (bloat معتدل)؛ جودة الاستخراج العربي تحتاج تحقّقاً مع Gemma 4B.

### الخيار D — Zep + Graphiti (ترقية مستقبلية، ليس بداية) 🟡→📚
- **الآلية:** knowledge graph زمني ثنائي الزمن مع إبطال تلقائي للحقائق القديمة؛ استرجاع graph+BM25+embedding بلا LLM وقت القراءة.
- **لماذا:** **أعلى دقة موثّقة (63.8% LongMemEval)** وأفضل لتتبّع تغيّر التفضيلات عبر الزمن.
- **العيب:** يفرض قاعدة graph (Neo4j/FalkorDB) = **ضد anti-bloat وخارج Postgres**، وبناء الـ graph كثيف LLM على 6GB. **يُؤجَّل** حتى تظهر حاجة فعلية لذاكرة زمنية دقيقة. (بديل anti-bloat لو لزم: Apache AGE داخل Postgres).

---

**المُستبعدون عملياً (📚 للعلم):** Letta (إطار وكيل + Docker مهمل)، GraphRAG/Cognee/Memary (آلاف استدعاءات LLM/تعقيد)، Semantic Kernel/Haystack/AutoGen (أطر كاملة خارج مكدّسنا)، MemGen/Titans (يكسران حياد الموديل)، Open WebUI Native Memory (يحتاج frontier models)، قواعد المتجهات المنفصلة Qdrant/Milvus/Weaviate (ازدواج/خدمة).

---

## توصية المعماري

## توصية المعماري + خطة متدرّجة

### القرار الجوهري أولاً: "هندسة سياق" أم "نظام ذاكرة"؟
العدسة الأهم (slice emerging-and-gaps): **كثير مما نسمّيه "ذاكرة" يُحلّ بحقن سياق انتقائي بلا بنية ثقيلة**. مع نافذة 8192 الضيقة وبطاقة 6GB، نبدأ بأبسط ما يحقق التخصيص ونصعد فقط عند ظهور حاجة مقاسة. هذا يحترم anti-bloat بنيوياً.

### التوصية: ابدأ بالخيار A (صفر-إطار) مع قرارات مثبّتة من اليوم-1
**المنطق المعماري:** كل الأطر/المنتجات (B/C/D) تُقاس ضد خط الأساس "صفر-إطار". لا نتبنّى إطاراً إلا إذا أثبت Langfuse أن المنطع اليدوي عجز فعلاً. هذا يجعل القرار قابلاً للتراجع ومحايداً.

**قرارات مثبّتة (تنطبق على كل المراحل):**
- **التخزين:** pgvector على Postgres الموجود + **halfvec افتراضياً** (-50% ذاكرة، حرج لـ 6GB).
- **التضمين:** **Qwen3-Embedding-0.6B** (محلي/Apache/خفيف/عربي جيد/Matryoshka/يتسق مع Qwen). إن كان المحتوى عربياً غالباً، اختبره ضد ATM-V2/GATE عبر ArabicMTEB قبل التثبيت.
- **حياد:** كل المنطق في **LiteLLM hook** (طبقة /v1) لا في Open WebUI → التبديل بين Gemma/Qwen أو تغيير الواجهة بلا فقد ذاكرة.
- **العزل:** `user_id` + RLS على جداول المتجهات (تحقّق من filtered-HNSW على recall).
- **الحوكمة:** مسارات عرض/تصحيح/حذف per-user + provenance لكل ذاكرة (GDPR + OWASP ASI06) **من اليوم-1**.
- **التضمين كمخاطرة مُدارة:** عمود `embedding_model_version` + خطة backfill ليلي → التبديل ممكن لاحقاً بلا توقف.

---

### الخطة المتدرّجة

**المرحلة 0 — مكاسب صفر-ذاكرة فورية (أيام):**
- فعّل **semantic cache في LiteLLM** + **KV/prefix cache في llama.cpp** (يخفّفان 6GB فوراً بصفر بنية ذاكرة).
- ثبّت سقف توكنات صارم في الـ hook (token-window) لمنع فيضان 8192.

**المرحلة 1 — الأساس (أسبوعان، الخيار A):**
- LiteLLM hook: استرجاع RAG كلاسيكي top-k على pgvector + حقن في موضع system بميزانية ~1500 توكن (هندسة حقن صريحة).
- نطاق session + user؛ كتابة **explicit** ("تذكّر/انسَ") + **User-confirmed memory (HITL)** لحماية الجودة من استخراج Gemma 4B الهشّ.
- مسارات الحذف/العرض/التصحيح + provenance.

**المرحلة 2 — استرجاع أذكى (أسبوع):**
- أضف **بحث هجين BM25(pg_search)+dense+RRF** مع **تطبيع/جذع عربي (CAMeL/Tashaphyne)** — شرط لجودة البحث العربي.
- أضف تسجيل **recency+importance+relevance** (Generative Agents، لا يحتاج tool-calling).

**المرحلة 3 — صحّة الذاكرة (أسبوع):**
- **cron ليلي (sleep-time consolidation)** يستدعي Gemma عبر /v1: دمج/تكثيف + decay/TTL + معالجة التقادم + invalidation (bi-temporal: valid_from/to) — يبقي العبء خارج زمن الرد.
- استخراج حقائق خفيف **مجدول** (لا لكل دور) لتكثيف ذاكرة المستخدم.

**المرحلة 4 — قياس ثم ترقية (عند الحاجة فقط):**
- **Langfuse self-host** لقياس L2/L3 (دقة استرجاع/توكنات/كمون). بناء مجموعة تقييم **عربية+إنجليزية متعددة الجلسات** (LoCoMo-style + Ragas).
- أضف **reranker (bge-reranker-v2-m3 على CPU)** فقط إن أثبت القياس أن جودة الاسترجاع تستحق الكمون.
- **ترقية للخيار D (Zep+Graphiti أو Apache AGE)** فقط إن برهنت البيانات على حاجة لذاكرة زمنية/علائقية دقيقة لا يحلّها bi-temporal البسيط.

---

### تنبيهات صدق ("موسوعي" مقابل "واقعي لنا")
- **يكسر حياد الموديل (مستبعد):** MemGen/Titans (تدريب/latent)، Self-RAG المُدرَّب، Open WebUI Native (frontier-only).
- **يخالف anti-bloat على 6GB:** Zep/GraphRAG/Cognee/Letta وأي قاعدة graph منفصلة — موسوعياً مهمة، عملياً مؤجَّلة.
- **القيد الأخطر المُدار:** ثبات التضمين — حُلّ بـ versioning+backfill بدل "لا تبدّل أبداً".
- **فجوة عربية حقيقية:** كل البنشمارك إنجليزية + tool-calling/استخراج Gemma 4B بالعربية غير مضمون → اعتمد HITL + قياس عربي مبكر قبل أي أتمتة استخراج.
