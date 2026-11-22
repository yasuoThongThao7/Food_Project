# Stack
Monorepo: /server (Python 3.11+, FastAPI, SQLAlchemy 2.0 sync + Alembic, SQLite dev but Postgres-ready, Pydantic v2 + pydantic-settings, PyJWT, bcrypt, python-multipart, httpx, pytest), /client (React 18, Vite, TypeScript strict, Tailwind, React Router, TanStack Query, Leaflet + react-leaflet + OSM tiles), /docs.
No Google APIs anywhere. Maps = Leaflet + OSM tiles only. Geocoding = Nominatim (admin-side only).

# Conventions
- Endpoints are plain `def` (sync) using a SQLAlchemy Session dependency.
- JSON is camelCase on the wire (Pydantic alias_generator=to_camel, populate_by_name, response by_alias).
- Success: {ok:true,data,meta?}  Error: {ok:false,error:{code,message}}. Register exception handlers so HTTPException, RequestValidationError (-> 400 VALIDATION, NOT 422) and unexpected errors ALL return the envelope.
- Codes: VALIDATION(400) UNAUTHORIZED(401) FORBIDDEN(403) BANNED(403) NOT_FOUND(404) CONFLICT(409) RATE_LIMIT(429) AI_UNAVAILABLE(503)
- Pagination: ?page=1&limit=12 (limit<=50) -> meta:{page,limit,total}
- Auth: Authorization: Bearer <JWT 7d>. Roles USER|ADMIN. The auth dependency re-checks DB on every request: banned user -> 403 BANNED (message includes banReason). Optional-auth dependency for public routes that personalize.
- IDs are integers. Dates ISO strings. UI language Vietnamese; API messages Vietnamese, codes English.
- API prefix: none (routes exactly as listed). OpenAPI at /openapi.json is used by the sync checker, so every route must declare its path exactly as below and use tags.

# Database (SQLAlchemy models, table names plural snake_case)
User(id, email unique, password_hash, name, role[USER|ADMIN] default USER, is_banned false, ban_reason?, created_at)
Food(id, slug unique, name, ai_label unique (label returned by our AI model), description, category[noodle|seafood|snack|dessert|drink|other], image_url, price_min, price_max, is_active true)
Restaurant(id, slug unique, name, address, district, lat, lng, phone?, open_time "HH:mm", close_time "HH:mm", price_level 1-3, image_url, description, meal_slots csv of breakfast|lunch|snack|dinner, rating_avg 0, rating_count 0, is_active true)  // delete = soft (is_active=false)
RestaurantFood(restaurant_id, food_id, price?, is_signature) PK(restaurant_id,food_id)
Review(id, user_id, restaurant_id, rating 1-5, comment, created_at) unique(user_id,restaurant_id) -> POST upserts; recompute Restaurant.rating_avg/rating_count in the same transaction
Favorite(id, user_id, target_type[FOOD|RESTAURANT], target_id, created_at) unique(user_id,target_type,target_id)
SearchHistory(id, user_id, detected_food_ids JSON, created_at)  // never store images
Article(id, slug unique, title, summary, content(markdown), cover_url, author_id, is_published, published_at?)
Itinerary(id, user_id, date "YYYY-MM-DD", plan_json, source[AI|FALLBACK], input_hash, created_at)
Indexes: Restaurant(is_active,district), Food(ai_label), Review(restaurant_id), Favorite(user_id), SearchHistory(user_id,created_at), Itinerary(user_id,created_at), Itinerary(input_hash).

# Endpoints (one per line: METHOD /path  [auth] -> notes) — parsed by scripts/check_contract.py
POST /auth/register -> {email,password>=8,name} => {token,user}
POST /auth/login -> {email,password} => {token,user}
GET /auth/me [auth] => user
POST /search/image [optional auth] multipart field "image" (jpeg/png/webp <=5MB) => {foods:[{food,confidence,restaurants:[Restaurant+price+isSignature (top 10 by ratingAvg)]}],unmatched:[string]}; if logged in, save SearchHistory
GET /search/history [auth] => last 20 [{id,createdAt,foods:[Food]}]
DELETE /search/history [auth] => clear
GET /foods -> ?q&category&page&limit
GET /foods/{id} => Food + restaurants[] (with price)
GET /restaurants -> ?q&district&foodId&priceLevel&sort[rating|new]&page&limit
GET /restaurants/{id} => Restaurant + foods[] + isFavorite(if auth)
GET /restaurants/{id}/reviews -> paginated [{id,rating,comment,createdAt,user:{id,name}}]
POST /restaurants/{id}/reviews [auth] -> {rating,comment<=500}
GET /favorites [auth] => {foods:[Food],restaurants:[Restaurant]}
POST /favorites [auth] -> {targetType,targetId}
DELETE /favorites/{targetType}/{targetId} [auth]
POST /itinerary/generate [auth] -> {date?:"YYYY-MM-DD"} => Itinerary {id,date,source,plan:[{slot,restaurant:Restaurant,food?:Food,reason}]}
GET /itinerary [auth] => last 10 itineraries
GET /itinerary/{id} [auth] => Itinerary (owner only)
GET /articles -> paginated published
GET /articles/{slug}
GET /admin/stats [admin] => {users,restaurants,foods,reviews,searches7d}
GET /admin/users [admin] -> ?q&page
PATCH /admin/users/{id}/ban [admin] -> {banned:boolean,reason?} (cannot ban self or other ADMIN)
POST /admin/restaurants [admin]  (server geocodes address via Nominatim if lat/lng missing; lat/lng must be inside Da Nang bbox lat 15.9-16.2, lng 107.9-108.35; else VALIDATION)
PUT /admin/restaurants/{id} [admin]
DELETE /admin/restaurants/{id} [admin] (soft)
POST /admin/foods [admin]
PUT /admin/foods/{id} [admin]
DELETE /admin/foods/{id} [admin] (soft)
POST /admin/articles [admin]
PUT /admin/articles/{id} [admin]
DELETE /admin/articles/{id} [admin]
GET /health => {status:"ok"}

# External AI adapters (the ONLY files that touch our AI; owner plugs real URLs into .env)
ENV: AI_SEARCH_URL, AI_SEARCH_KEY, AI_ITINERARY_URL, AI_ITINERARY_KEY, AI_TIMEOUT_MS=15000, AI_MIN_CONF=0.4, MOCK_AI=true
1) server/app/adapters/ai_search.py
   Request: POST AI_SEARCH_URL multipart "image", header Authorization: Bearer AI_SEARCH_KEY
   Expected response: {predictions:[{label:string,confidence:number 0..1}]}
   Expose ONE function detect_foods(data:bytes, mime:str) -> list[{label,confidence}] and a clearly marked map_response() so the owner adapts other response shapes in one place.
   Logic: filter confidence>=AI_MIN_CONF, dedupe, top 5, map label->Food.ai_label; unknown labels go to unmatched. Timeout/error -> AI_UNAVAILABLE (503).
2) server/app/adapters/ai_itinerary.py
   Request JSON: {date, slots:["breakfast","lunch","snack","dinner"],
     profile:{favFoods:[{id,name}],favRestaurantIds:[],topRatedRestaurantIds:[] (user rating>=4),recentSearchFoodIds:[] (last 20,deduped),avgPriceLevel},
     candidates:[{id,name,district,priceLevel,open,close,mealSlots:[],foods:[name x<=3],rating}]}  // candidates <=40, pre-filtered by backend
   Expected response: {plan:[{slot,restaurantId,foodId?,reason}]}
   Expose generate_plan(payload) with a marked map_response().
   Backend validation of AI output (mandatory): restaurantId in candidates; each slot exactly once; no duplicate restaurant; open hours cover slot time (breakfast 06-09, lunch 11-13, snack 15-17, dinner 18-21); reason<=120 chars. Invalid/timeout/AI_UNAVAILABLE -> FALLBACK.
   FALLBACK (pure code, in services/itinerary_fallback.py): score = 3*isFav + 2*(userRated>=4) + 1*matchesSearchedFood + ratingAvg/5; per slot choose top candidate whose meal_slots includes slot and not yet used. Cold-start user -> top rating_avg per slot. reason from template.
   Candidate building: active restaurants only; prioritize favorites, rated, restaurants serving searched foods, fill by rating_avg up to 40.
   Cost control: input_hash=sha1(userId+date+payload); same hash -> return stored Itinerary, no AI call. Rate limit: max 5 NEW itineraries per hour per user, counted from the itineraries table (cache hits do not count) -> 429 RATE_LIMIT.
   MOCK_AI=true: both adapters return deterministic fake data (search: first 2 seeded foods; itinerary: fallback logic) so everything works without the real AI.
