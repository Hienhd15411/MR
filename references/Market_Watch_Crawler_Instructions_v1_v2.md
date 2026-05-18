# Market Watch – Crawler Instructions v1

**Phiên bản:** v1 (Crawl + Filter + Basic Scoring)
**Tần suất:** 1 lần/tuần
**Output:** Excel với 22 cột theo W19 template + Sheet "Discarded" log lý do loại
**Scope automation:** Mức 1 — Crawl + Filter đúng scope, scoring sơ bộ. Classification và scoring chính xác do human review.

---

## SECTION 1 — SOURCE CONFIGURATION

### Danh sách 36 nguồn cần crawl

| No | Priority | Source | Chuyên mục | URL |
|----|----------|--------|------------|-----|
| 1 | 0 | Grab Merchant | Blog | https://merchant.grab.com/vn-vn/blog |
| 2 | 0 | Grab Passenger | Blog | https://www.grab.com/vn/blog/ |
| 3 | 0 | Grab Passenger | Inside Grab | https://www.grab.com/inside-grab/ |
| 4 | 0 | MoMo | Tin tức | https://www.momo.vn/tin-tuc |
| 5 | 0 | Shopee | Blog | https://banhang.shopee.vn/edu/category?sub_cat_id=1006 |
| 6 | 0 | Telegram | Blog | https://telegram.org/blog |
| 7 | 0 | TikTokShop | Blog | https://seller-vn.tiktok.com/university/essay?knowledge_id=8858869405370113 |
| 8 | 0 | WhatsApp | Blog | https://blog.whatsapp.com/ |
| 9 | 0 | ZaloOA | Tin tức | https://oa.zalo.me/home/resources/news |
| 10 | 0 | ZaloPay | Tin tức | https://zalopay.vn/tin-tuc |
| 11 | 0 | ZaloPay | Khuyến mãi | https://zalopay.vn/khuyen-mai |
| 12 | 1 | OpenAI | News | https://openai.com/news/ |
| 13 | 1 | Bloomberg | Consumer tech | https://www.bloomberg.com/technology/consumer-tech |
| 14 | 1 | Dân Trí | AI - Internet | https://dantri.com.vn/cong-nghe/ai-internet/ |
| 15 | 1 | Dân Trí | An ninh mạng | https://dantri.com.vn/cong-nghe/an-ninh-mang.htm |
| 16 | 1 | Luật Việt Nam | Điểm tin chính sách | https://luatvietnam.vn/ban-tin-luatvietnam/diem-tin-chinh-sach-moi-c559-article.html |
| 17 | 1 | Luật Việt Nam | Văn bản mới | https://luatvietnam.vn/ban-tin-luatvietnam/diem-tin-van-ban-moi-c220-article.html |
| 18 | 1 | Meta | Newsroom | https://about.fb.com/news/ |
| 19 | 1 | Meta | Product news | https://about.fb.com/news/category/product-news/ |
| 20 | 1 | SCMP | WeChat | https://www.scmp.com/topics/wechat |
| 21 | 1 | SCMP | Tech | https://www.scmp.com/tech |
| 22 | 1 | TechCrunch | Apps | https://techcrunch.com/category/apps/ |
| 23 | 1 | TechCrunch | AI | https://techcrunch.com/category/artificial-intelligence/ |
| 24 | 1 | Tech in Asia | Fintech | https://www.techinasia.com/category/fintech |
| 25 | 1 | Tech in Asia | Consumer tech | https://www.techinasia.com/category/consumer-tech |
| 26 | 1 | Tech in Asia | E-commerce | https://www.techinasia.com/category/e-commerce-social-commerce |
| 27 | 1 | Sensor Tower | Blog | https://sensortower.com/blog |
| 28 | 1 | VNEconomy | Tech Talk | https://vneconomy.vn/techconnect/tech-talk.htm |
| 29 | 1 | VnExpress | Khoa học công nghệ | https://vnexpress.net/khoa-hoc-cong-nghe |
| 30 | 1 | VnExpress | Kinh doanh | https://vnexpress.net/kinh-doanh |
| 31 | 2 | Báo Tin Tức | Thị trường tiền tệ | https://baotintuc.vn/thi-truong-tien-te-587ct128.htm |
| 32 | 2 | VNEconomy | TechConnect | https://vneconomy.vn/techconnect/ |
| 33 | 2 | VNEconomy | Tech Lifestyle | https://vneconomy.vn/techconnect/tech-lifestyle.htm |
| 34 | 3 | GenK | AI | https://genk.vn/ai.chn |
| 35 | 3 | GenK | Tin ICT | https://genk.vn/tin-ict.chn |
| 36 | 3 | The Information | Technology | https://www.theinformation.com/technology?view=recent |

### Quy tắc kỹ thuật

- **Crawl method:** HTML scraping cho article listing pages, fetch từng article URL để lấy nội dung đầy đủ
- **Recency filter:** Chỉ giữ bài có `publish_date` trong 7 ngày qua tính từ ngày crawl
- **Required fields per article:** `url`, `title_raw`, `publish_date`, `source_name`, `short_description` (cho phần filter Section 2)
- **Retry policy:** 3 lần với exponential backoff; nếu fail → ghi vào log
- **Rate limiting:** 1-2 request/second per domain để tránh bị block

### Priority để dedupe (Section 4)
- **Priority 0:** Official blog/news của player → cao nhất, luôn giữ
- **Priority 1:** Tier 1 tech media (Bloomberg, TechCrunch, SCMP, Tech in Asia, VnExpress, VNEconomy Tech Talk, Dân Trí, OpenAI, Meta, Sensor Tower)
- **Priority 2:** Báo Tin Tức, VNEconomy general
- **Priority 3:** GenK, The Information (đôi khi clickbait, ưu tiên thấp)

---

## SECTION 2 — ARTICLE FILTERING RULES

### Nguyên tắc tổng quát

Bài "hợp lệ" = thuộc scope **HST super-app 7 vertical B2C**: AI, Chat, TMĐT, Travel/khách sạn/vui chơi giải trí, Ride/food delivery, E-wallet, Ticket (sự kiện, concert).

**Logic filter:**
```
IF source_priority == 0:
    → KEEP all (player blog luôn hợp lệ vì đó là Players Movement)
ELSE:
    IF article matches TIER 3 EXCLUDE:
        → DISCARD, log reason
    ELSE IF article matches TIER 1 INCLUDE:
        → KEEP
    ELSE IF article matches TIER 2 INCLUDE with ≥2 keywords:
        → KEEP
    ELSE IF article matches TIER 4 AMBIGUOUS:
        → KEEP with flag "HUMAN_REVIEW"
    ELSE:
        → DISCARD, log reason "no relevant keywords"
```

### 2.1 TIER 1 — STRONG INCLUDE
*Bài có ít nhất 1 keyword Tier 1 → KEEP*

#### 2.1.1 AI models & vendors (vertical AI)

**AI models:**
ChatGPT, GPT-5, GPT-5.5, GPT-5.4, GPT-5.3, GPT-4, GPT-4o, GPT-3, GPT-3.5, Claude, Claude Opus, Claude Sonnet, Claude Haiku, Claude Code, Gemini, Gemini Pro, Gemini Ultra, Gemini Flash, Gemini Nano, DeepSeek, DeepSeek V4, DeepSeek R1, Llama, Mistral, Qwen, Ernie, Doubao, Grok, Perplexity, Mythos, Copilot, Codex, Sora, Nano Banana, Veo, Apple Intelligence, Siri, Personal Intelligence

**AI vendors:**
OpenAI, Anthropic, xAI, Meta AI, Google AI, Microsoft AI, DeepMind, Mistral AI, Cohere, Hugging Face, Stability AI, Midjourney

**AI concepts:**
LLM, large language model, generative AI, Gen AI, AI agent, agentic AI, agentic, AI search, AI assistant, AI coding, AI chatbot, AI image, AI voice, AI dictation, AI translation, AI customer service, OpenClaw, MCP, multi-modal, foundation model, AI Subscription, AI pricing change, AI Revenue stream, AI business model, Sản phẩm AI thương mại mới

#### 2.1.2 Super-app players (vertical Chat, TMĐT, Ride/Food, E-wallet, Travel)

**VN super-app player core (Players Movement primary):**
MoMo, Zalo, ZaloPay, Grab, Traveloka, WhatsApp, Telegram, Shopee, TikTok Shop, TikTokShop

**Sub-services:**
GrabCar, GrabBike, GrabFood, GrabPay, GrabMart, GrabExpress, GrabKitchen, GrabAds, GrabClub, Ví Trả Sau, MoMo Pay, ZaloPay QR, Zalo OA, Zalo Mini App, TikTok Shop Vietnam

**Competitor/adjacent players:**
- Ride/Food: Gojek, GoTo, Gocar, Gosend, Gopay, Uber, Lyft, DoorDash, Meituan, Xanh SM, Be, GSM, Tada, Lalamove, Ahamove
- TMĐT: Lazada, Amazon, Etsy, Alibaba, Pinduoduo, Taobao, Tmall, JD.com, Xiaohongshu, RedNote, Sendo, VnShop, Tokopedia, Bukalapak, Sea Group, eBay, Coupang
- Travel: Booking.com, Booking Holdings, Expedia, Vrbo, Airbnb, Trip.com, Klook, Agoda, Traveloka, Vinpearl
- E-wallet/Fintech: PayPal, Stripe, Apple Pay, Google Pay, Alipay, AlipayHK, WeChat Pay, Ant Group, Ant International, PhonePe, Airwallex, Robinhood, RedotPay, Klarna, Affirm, Square, Cash App, Razorpay, Paytm
- Streaming/Ticket: Disney, Disney+, Netflix, Spotify, Prime Video, YouTube Premium, Apple TV, HBO Max, Ticketbox, Ticketmaster
- Messaging/Social: Snapchat, Snap, Threads, Instagram, Facebook, Discord, X (Twitter), Reddit, WeChat, Line, KakaoTalk, WhatsApp, Zalo, Viber, Messenger

#### 2.1.3 Fintech / E-wallet keywords (vertical E-wallet)

ví điện tử, e-wallet, mobile wallet, digital wallet, fintech, payment, thanh toán, QR payment, QR code thanh toán, BNPL, buy now pay later, mua trước trả sau, eKYC, KYC, biometric, sinh trắc học, nhận diện khuôn mặt, vân tay, cross-border payment, thanh toán xuyên biên giới, remittance, kiều hối, open banking, banking API, neobank, digital bank, ngân hàng số, mobile banking, internet banking, stablecoin, CBDC, tiền số ngân hàng, embedded finance, lending app, insurance tech, insurtech, bảo hiểm số, micro-loan, credit score

#### 2.1.4 TMĐT / E-commerce keywords (vertical TMĐT)

ecommerce, TMĐT, thương mại điện tử, marketplace, sàn TMĐT, livestream commerce, livestream bán hàng, social commerce, GMV, merchant, người bán, seller, dropshipping, fulfillment, last-mile, agentic commerce, agentic storefront, discover-and-buy, AI search shopping, voice commerce, conversational commerce, omnichannel, headless commerce, headless cms

#### 2.1.5 Ride-hailing / Food Delivery keywords

ride-hailing, gọi xe, xe ôm công nghệ, gọi xe công nghệ, food delivery, giao đồ ăn, giao hàng, delivery, last-mile delivery, courier, tài xế công nghệ, gig worker, gig economy, taxi công nghệ, xe điện gọi xe, drone delivery, autonomous delivery

#### 2.1.6 Travel / Ticket PLATFORM keywords (chỉ giữ platform moves, không giữ tips)

**Platform-level signals:**
OTA, online travel agent, travel platform, booking platform, super app travel, travel aggregator, travel super-app, hotel booking integration, flight booking integration, vé máy bay tích hợp, đặt phòng qua app, vacation rental platform, cruise booking, concert ticketing, event ticketing, vé concert qua app

**Industry/business:**
travel industry, OTA market, travel commerce, vé máy bay GMV, hotel GMV, RevPAR, ADR (average daily rate), travel tech investment

#### 2.1.7 Chat / Messaging / Social PLATFORM keywords

messaging app, chat app, social media platform, mini app, mini program, super app chat, group chat, direct message, DM, voice message, video call, WhatsApp Pay, Zalo OA, Telegram Bot, Telegram Stars, Zalo Mini App, social commerce

#### 2.1.8 Regulation / Legal keywords

**VN regulation/ International regulation:**
Luật AI, AI policy, AI act, Luật TMĐT, eCommerce regulation, Luật fintech, luật thanh toán, luật tiền điện tử, Chính sách gig economy, chính sách ride-hailing , chính sách food-delivery, data privacy/ child safety/ age verification (super app), social media regulation, chat regulation

### 2.2 TIER 2 — WEAK INCLUDE (cần combo)

*Bài có ≥2 keyword Tier 2 hoặc 1 Tier 2 + 1 Tier 1 → KEEP*

**Earnings/Corporate:**
earnings, revenue, doanh thu, GMV, EBITDA, profit, lợi nhuận, valuation, định giá, IPO, M&A, sáp nhập, acquisition, mua lại, funding round, gọi vốn, Series A/B/C/D, unicorn

**Infrastructure:**
chip AI, AI chip, semiconductor, semiconductor manufacturing, data center, AI infrastructure, hạ tầng AI, cloud computing, edge computing, 5G, internet bandwidth

**Cybersecurity (related to super-app):**
data breach, vi phạm dữ liệu, hack, phishing, deepfake, account takeover, ransomware, vulnerability, lỗ hổng bảo mật, OTP fraud

**Consumer behavior research:**
khảo sát người dùng, consumer survey, user adoption report, sensor tower data, app analytics, market share report, GMV report, digital adoption report, payment behavior report

**Tech giants (include when mentioned + keywords):**
Apple, Google, Microsoft, Meta, Amazon, Samsung, Xiaomi, ByteDance, Baidu, Tencent, Alibaba, Sony, Huawei, Qualcomm, NVIDIA, TSMC, Intel, AMD
Tech giant + AI keyword (AI chip, Apple Intelligence, AI feature) → KEEP
Tech giant + super-app keyword → KEEP
Tech giant + regulation → KEEP
Tech giant alone (review, earnings thông thường) → DISCARD

#### Banking/ Tech corp (include when mentioned + keywords)
VN banks: Vietcombank, VCB, BIDV, HDBank, Techcombank, VietinBank, Agribank, VPBank, MB Bank, Sacombank, ACB, TPBank, OCB, MSB, SHB, LPBank, Eximbank, VietBank, Public Bank, Saigonbank, Bac A Bank
VN tech corp: VNPT, Viettel, FPT, VNG, Garena, VinFast, Vingroup, Masan, VnPay, NAPAS, Misa, KiotViet
Keywords: liên quan đến hợp tác với VN super-app player core , xây dựng super-app, triển khai super-app -> KEEP
Keywords: sản phẩm banking thuần (lãi suất, gói vay) -> DISCARD


### 2.3 TIER 3 — STRONG EXCLUDE

*Bài CHỈ match Tier 3 và KHÔNG match Tier 1 → DISCARD*

#### 2.3.1 Pure travel tips/content (không có platform angle)

cẩm nang du lịch, top X địa điểm du lịch, top X resort, top X khách sạn, review điểm đến, khám phá ẩm thực, must-visit, best places to visit, ăn gì ở [địa danh], chơi gì ở [địa danh], lễ X đi đâu, du lịch hè, du lịch tết, kinh nghiệm du lịch, tips du lịch, lưu trú nhà nghỉ, homestay review, food blog, review nhà hàng cá nhân

**Loại trừ exception:** Nếu bài có mention nền tảng đặt phòng/vé (Booking, Expedia, Traveloka, Klook, Agoda, MoMo, ZaloPay) → KEEP

#### 2.3.2 Pure entertainment (không có platform/streaming angle)

concert tour BTS, tour diễn Taylor, concert review, idol comeback, fan meeting, kpop news, drama Hàn Quốc, review phim, top phim hè/tết, phim hot tuần, bóc tách phim, review series, idol show, music video debut, album debut

**Loại trừ exception:** Nếu bài về streaming platform (Netflix, Disney+, Prime Video, Spotify), ticket platform (Ticketbox), hoặc tích hợp với super-app → KEEP

#### 2.3.3 Pure hardware review (không có AI/super-app angle)

review iPhone X, review Samsung Galaxy, review laptop, review MacBook, benchmark CPU/GPU, test hiệu năng, unboxing, hands-on, đập hộp, RAM upgrade, SSD comparison, screen comparison, camera comparison, gaming laptop review

**Loại trừ exception:** Nếu có "AI", "Apple Intelligence", "on-device AI", "AI chip", "Apple Silicon", "Snapdragon AI", hoặc smartphone có ý nghĩa với payment (NFC, ApplePay) → KEEP

#### 2.3.4 Sports (không có streaming/ticket/sponsorship angle)

U23 Việt Nam, World Cup, Premier League, EPL, NBA, MLB, NHL, NFL, F1, MotoGP, Tour de France, Olympic medal, World Athletics, Wimbledon, Roland Garros, AFC Asian Cup, SEA Games, ASIAD, esports tournament, LoL Worlds, Dota 2 The International, CS:GO Major

**Loại trừ exception:** Nếu bài về streaming platform broadcast, ticket platform, sponsorship deal với super-app, hoặc esports investment/M&A → KEEP

#### 2.3.5 Crypto speculation (chỉ về giá, không về fintech)

Bitcoin giá, BTC price, ETH price, altcoin pump, memecoin, token X giá tăng/giảm, crypto trading signal, bullish/bearish crypto, whale alert, on-chain analysis, NFT floor price, NFT minting

**Loại trừ exception:** Nếu bài về stablecoin, CBDC, crypto payment, crypto wallet partnership với fintech, crypto regulation, blockchain infrastructure → KEEP

#### 2.3.6 Pure politics (không có tech/economy angle)

Bầu cử, đại hội Đảng, kỳ họp Quốc hội thường niên, ngoại giao quốc tế, hội nghị thượng đỉnh không-tech, chính trị Mỹ tổng thống, NATO summit, G7 G20 (trừ khi bàn về tech/AI policy)

**Loại trừ exception:** Nếu bài về AI/tech policy, payment regulation, eCommerce regulation, data privacy law, antitrust action → KEEP

#### 2.3.7 Personal anecdotal / lifestyle

Phàn nàn cá nhân về AI, than phiền dịch vụ, blog cá nhân chia sẻ, vlog trải nghiệm, story người dùng cá nhân, "tôi đã dùng X và..." khi không có data, beauty review cá nhân, fashion personal style

**Loại trừ exception:** Nếu là báo cáo có số liệu / khảo sát quy mô → KEEP

#### 2.3.8 Pure healthcare/medical (không có super-app angle)

Phẫu thuật, bệnh nhân, lâm sàng, clinical trial, drug development, vaccine clinical, medical breakthrough không-AI, dược phẩm điều trị

**Loại trừ exception:** Nếu bài về AI healthcare app B2C, health AI subscription (Google AI Health Coach), telemedicine platform → KEEP

#### 2.3.9 Government/B2B/B2G AI thuần túy

AI cho cơ quan nhà nước, AI cho công an, AI quân sự, AI cho chính phủ, AI government, civil service AI, enterprise AI tool (B2B-only), AI HR enterprise

**Loại trừ exception:** Nếu policy/precedent có thể lan sang B2C VN → KEEP (Tier 2)

#### 2.3.10 Workforce/Talent (only AI-related):
AI workforce, AI engineer demand, data engineer, AI talent, reskilling AI

#### 2.3.11 Not-related Regulation (out of scope **HST super-app 7 vertical):
Luật chung chung: luật doanh nghiệp, luật thuế thuần
Quy định ngành khác: xây dựng, y tế, giáo dục

### 2.4 TIER 4 — AMBIGUOUS (human review)

*Bài có Tier 1 + Tier 3 keywords cùng lúc, hoặc context không rõ → FLAG human review*

**Trigger conditions:**
- Có ≥1 keyword Tier 1 VÀ ≥1 keyword Tier 3 trong cùng article
- Source là Priority 3 (GenK, The Information) — content có thể clickbait
- Title có pattern lifestyle/anecdotal nhưng có brand name super-app
- Article quá ngắn (<200 từ summary) — không đủ context để judge
- Article có nhiều entity nhưng không có vertical core nào nổi bật

**Examples từ W17-W19:**
- "BTS dùng AI tạo MV trên YouTube" → Có "BTS"+"YouTube" (entertainment + platform); flag review
- "Người Việt mất ngủ vì ChatGPT" → "ChatGPT" (Tier 1) + "phàn nàn" sentiment (Tier 3); flag
- "Esports VN hội nhập" → Có "esports" (Tier 3) nhưng có "VN B2C ecosystem" (Tier 1); flag
- "Apple iPhone nghiên cứu tốc độ đi bộ" → "Apple" (Tier 1) + "research" (B2B-ish); flag

### 2.5 GEOGRAPHIC MAPPING (cho sub_topic_group sơ bộ)

**Quy tắc:** Detect geography từ title + summary, gán theo độ ưu tiên:

```
IF có VN keyword ("Việt Nam", "VN", "Hà Nội", "TP.HCM", "Saigon", tên ngân hàng VN, tên player VN):
    → "Trong nước"
ELIF có SEA keyword ("Indonesia", "Thailand", "Singapore", "Malaysia", "Philippines", "SEA", "ASEAN", "Đông Nam Á"):
    → "SEA"
ELIF có TQ keyword ("Trung Quốc", "China", "TQ", "Beijing", "Shanghai", "Shenzhen", "Hong Kong"):
    → "Trung quốc"
ELSE:
    → "Quốc tế"
```

**Lưu ý:** Nếu bài chạm nhiều region, ưu tiên VN > SEA > TQ > Quốc tế. Ví dụ: "TikTok đầu tư $25B Thái Lan" → SEA (không phải Quốc tế dù TikTok là TQ).

### 2.6 PLAYER MOVEMENT DETECTION (cho topic_group sơ bộ)

```
IF source_priority == 0 (player blog chính thức):
    → topic_group = "Players Movement"
    → sub_topic_group = tên player tương ứng (MoMo, Zalo, ZaloPay, Grab, Shopee, TikTokShop, WhatsApp, Telegram)
ELIF title mention rõ ràng player VN + hành động (ra mắt, cập nhật, hợp tác, khuyến mãi):
    → topic_group = "Players Movement"
    → flag HUMAN_REVIEW để xác nhận
ELSE:
    → topic_group = "Market Pulse"
```

### 2.7 LOG DISCARDED

Mọi bài bị loại phải ghi vào sheet "Discarded" với fields:
- `url`, `title_raw`, `source_name`, `publish_date`
- `discard_reason`: code (e.g. "T3_TRAVEL_TIPS", "T3_SPORTS", "NO_KEYWORD", "DUPLICATE")
- `matched_tier3_keywords`: list keyword đã trigger exclude

---

## SECTION 3 — SCORING RULES

**Reference:** File `Market_Watch_Scoring_Framework.md` (full framework R1/R2 với modifiers và caps).

### Quick reference table

**Công thức:** `signal_score = R1 × 0.6 + R2 × 0.4`
**Định nghĩa:** `TA = (Target Audience) = Nhân sự nội bộ phòng ban Product / Strategy / Business / Marketing / Growth của doanh nghiệp super-app, đọc Market Watch để cập nhật về:
Đối thủ: action của các player trong ngành (MoMo, Zalo, Grab, ZaloPay, Traveloka, WhatsApp, Telegram, Shopee, TikTokShop) và competitor SEA/global
Thị trường: chuyển động cấu trúc thị trường (TMĐT, e-wallet, ride-hailing, AI, travel, ticket, chat)
Người dùng: thay đổi hành vi consumer trong 7 vertical của HST super-app
Regulation: chính sách/luật ảnh hưởng đến cách super-app vận hành`

**R1 — Impact (60%):** "TA có thể action được gì từ tin này không?"

| Score | Description |
|-------|-------------|
| 5 | Regulation đã ban hành áp lên vertical VN; Đối thủ direct launch product/pricing đụng vertical TA; Infrastructure/tool TA đang dùng có breaking change |
| 4 | Đối thủ peer update feature/pricing; Tool/infrastructure mới TA có thể adopt; Banking/fintech entry; Regulation precedent SEA/TQ sắp đến VN |
| 3 | AI tech advance không trực tiếp super-app (DeepSeek V4, GPT update); Corporate news ngành; Routine player promo; Regulation distant/proposed |
| 2 | Niche partnership; Vertical mới chưa scale; Trend gián tiếp |
| 1 | Dev tooling thuần (OpenAI Agents SDK); HR/AI hype không product implication; B2G/B2D không tạo precedent |

**Modifiers cho R1:**
- Vietnam → +0.6 đến +0.8
- TQ event với precedent rõ cho VN → +0.3 đến +0.5
- Quốc tế (US/EU) chỉ là "tin tham khảo" → −0.3 đến −0.5
- Tin đồn/leak chưa confirm → cap R1 ≤ 3
- B2B/enterprise solutions (dù có AI) → cap R1 ≤ 2
- Players Movement promo định kỳ → cap R1 ≤ 3.5
- Players Movement product launch/pricing/M&A/feature update → R1 ≥ 4

**R2 — Relevance (40%):** "Tin này có thuộc liên quan đến các vertical không?"

| Score | Description |
|-------|-------------|
| 5 | Liên quan 2+ vertical core + content actionable |
| 4 | Liên quan đến 1 vertical core + content actionable |
| 3 | Adjacent: banking partner, regulatory precedent, 1 vertical thin / cross-vertical |
| 2 | Background signal — xu hướng gián tiếp, chưa có actor cụ thể |
| 1 | Hoàn toàn ngoài HST scope |

**Modifiers cho R2:**
- Concrete signal: Bài có ≥1 số liệu kinh doanh/ performance cụ thể (GMV, %, $, user count, hiệu quả mô hình kinh doanh, etc) VÀ có tên actor (company/product) → +0.1 đến +0.3
- Pattern transferable: Bài về pattern có thể apply cho VN super-app context (ví dụ: SEA precedent, đối thủ peer move, copy-cat pattern)→ +0.3 đến +0.5
- Foreign context unfit: Bài về thị trường có cấu trúc khác hẳn VN (ví dụ Mỹ healthcare insurance) → -0.3
- Abstract/opinion: Bài là analysis chung, không có actor cụ thể, không có data → −0.3

**Signal Levels:**

| Score range | Level |
|-------------|-------|
| 4.21 – 5.00 | 5 – Industry disruption |
| 3.41 – 4.20 | 4 – Strategic shift |
| 2.51 – 3.40 | 3 – Market signal |
| 1.61 – 2.50 | 2 – Minor signal |
| ≤ 1.60 | 1 – Noise |

### Calibration anchors (cho crawler tham chiếu)

| Pattern | R1 | R2 | Score | Level | Example |
|---------|----|----|-------|-------|---------|
| Player VN product launch | 4-5 | 4-5 | 4.0-5.0 | L4-L5 | "MoMo ra mắt Ví Trả Sau 2.0" |
| Player VN promo định kỳ | 3 | 4 | 3.4 | L3 | "Grab x HD Bank hoàn tiền" |
| AI model VN launch trực tiếp | 5 | 5 | 5.0 | L5 | "Gemini Personal Intelligence VN" |
| AI model global update (no VN) | 3-4 | 3 | 3.0-3.6 | L3-L4 | "GPT-5.5 ra mắt global" |
| Regulation SEA precedent | 4-4.5 | 4 | 4.0-4.3 | L4 | "Indonesia 8% fee cap" |
| Regulation EU/US distant | 3 | 3 | 3.0 | L3 | "FTC điều tra Meta" |
| TQ event với VN precedent | 3.5-4 | 4 | 3.7-4.0 | L4 | "TQ siết livestream" |
| Tin đồn/leak | ≤3 | 3-4 | 3.0-3.4 | L3 | "Anthropic sắp ra design tool" |
| B2B enterprise tool | ≤2 | 2 | 2.0 | L2 | "Microsoft OpenClaw enterprise" |
| Platform structural shift | 4-4.5 | 4.5 | 4.2-4.4 | L5 | "Image AI drives app growth" |
| Pure hardware/research | 2 | 2 | 2.0 | L2 | "Apple iPhone gait research" |
| Niche app non-super-app | 2 | 2 | 2.0 | L2 | "Bumble dating overhaul" |

### Example
| Content | R2 base | Modifiers | R2 final |
|---------|----|----|-------|-------|
TikTok Shop $45.6B GMV SEA tăng gấp đôi | 4 | Concrete +0.3 + Pattern +0.3 | 4.6
AI và thấu cảm trong CS — bài học chung | 3 | Abstract -0.3 | 2.7
Indonesia 8% fee cap ride-hailing | 4 | Concrete +0.3 + Pattern +0.3 | 4.6
OpenAI Agents SDK update (dev tool) | 2 | Concrete +0.3 + Foreign -0.3 | 2.0

---

## SECTION 4 — DEDUPLICATION RULES

### 4.1 Same-event detection

**Logic:** Hai bài coi là "cùng event" nếu thoả mãn TẤT CẢ:

1. **Title similarity ≥ 70%** (dùng Jaccard similarity hoặc embedding cosine similarity)
   - Hoặc: chứa ≥3 entity giống nhau (player name, product name, số liệu cụ thể)
2. **publish_date cách nhau ≤ 48 giờ**
3. **Mention cùng entity chính** (player name, product launch, regulation name)

### 4.2 Keep rule

Khi 2+ bài là duplicate:
1. **Giữ bài có source priority CAO NHẤT** (0 > 1 > 2 > 3)
2. **Nếu cùng priority:** giữ bài có summary dài hơn/chi tiết hơn
3. **Nếu vẫn cùng:** giữ bài tiếng Việt > English (cho audience VN)
4. **Đánh dấu DUP:** các bài bị loại lưu trong sheet "Discarded" với reason="DUPLICATE_OF_ID_X"

### 4.3 Examples

- "TikTok $25B Thái Lan" có 2 nguồn (VNEconomy P2, SCMP P1) → giữ SCMP, dedupe VNEconomy
- "Gemini Personal Intelligence VN" có 2 nguồn (Dân Trí P1, VnExpress P1) → cùng priority, giữ bài chi tiết hơn

---

## SECTION 5 — OUTPUT SCHEMA

### Sheet 1: "Database"

22 cột theo W19 template, thứ tự cố định:

| Col | Name | Type | Auto / Human | Description |
|-----|------|------|--------------|-------------|
| 1 | id | int | Auto | Sequential ID, continue from last week |
| 2 | url | string | Auto (crawl) | Article URL |
| 3 | hyperlink | string | Auto | = title_normalized (clickable hyperlink to url) |
| 4 | source_name | string | Auto | Source name từ Section 1 |
| 5 | signal_level | string | Auto (compute) | "5 - Industry disruption" etc. theo signal_score |
| 6 | week | int | Auto | Week number (e.g., 19) |
| 7 | crawl_date | date | Auto | Date của crawl run |
| 8 | title_raw | string | Auto (crawl) | Tiêu đề gốc bài |
| 9 | publish_date | date | Auto (crawl) | Ngày bài xuất bản |
| 10 | topic_group | string | Auto (Sec 2.6) | "Market Pulse" / "Players Movement" |
| 11 | sub_topic_group | string | Auto (Sec 2.5) | Geography hoặc player name |
| 12 | category | string | **HUMAN** | Theo taxonomy v2 |
| 13 | subcategory | string | **HUMAN** | Theo taxonomy v2 |
| 14 | merged_category | string | Auto | = category + " \| " + subcategory |
| 15 | title_normalized | string | **HUMAN** | Có thể auto-gen rough từ title_raw, human edit |
| 16 | summary | string | **HUMAN** | Auto-gen từ first 3 paragraphs of article + flag for human edit |
| 17 | start_date | date | Optional | Cho promo: ngày bắt đầu |
| 18 | end_date | date | Optional | Cho promo: ngày kết thúc |
| 19 | R1 | float | Auto (basic) | Theo Section 3 rough scoring |
| 20 | R2 | float | Auto (basic) | Theo Section 3 rough scoring |
| 21 | signal_score | float | Auto (compute) | R1 × 0.6 + R2 × 0.4 |
| 22 | related_vertical | string | **HUMAN** | Theo B5 rule trong taxonomy |

### Sheet 2: "Discarded"

| Col | Name | Type | Description |
|-----|------|------|-------------|
| 1 | url | string | URL bài bị loại |
| 2 | source_name | string | Source |
| 3 | title_raw | string | Tiêu đề gốc |
| 4 | publish_date | date | Ngày xuất bản |
| 5 | discard_reason | string | Code (e.g., T3_TRAVEL_TIPS, T3_SPORTS, NO_KEYWORD, DUPLICATE_OF_ID_X) |
| 6 | matched_keywords | string | Keywords đã trigger exclude |
| 7 | review_flag | bool | TRUE nếu nên human spot-check |

### Sheet 3: "Audit_Log"

| Col | Name | Description |
|-----|------|-------------|
| 1 | crawl_start_time | Timestamp |
| 2 | crawl_end_time | Timestamp |
| 3 | source_name | Per-source crawl status |
| 4 | articles_fetched | Số bài fetch được |
| 5 | articles_kept | Số bài pass filter |
| 6 | articles_discarded | Số bài bị loại |
| 7 | articles_flagged | Số bài cần human review |
| 8 | errors | Lỗi nếu có |

---
