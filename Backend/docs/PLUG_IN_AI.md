# Plug in real AI

1. Edit only `server/app/adapters/ai_search.py` and `server/app/adapters/ai_itinerary.py`.
2. Set `AI_SEARCH_URL`, `AI_SEARCH_KEY`, `AI_ITINERARY_URL`, `AI_ITINERARY_KEY`, `AI_TIMEOUT_MS`, `AI_MIN_CONF`, and `MOCK_AI=false`.
3. Keep the backend contract validation unchanged.

## Search adapter
- Request: `POST AI_SEARCH_URL`
- Multipart field: `image`
- Header: `Authorization: Bearer AI_SEARCH_KEY`
- Response: `{"predictions":[{"label":"mi-quang","confidence":0.91}]}`
- Adapt alternate upstream fields only in `map_response()`.

## Itinerary adapter
- Request: `POST AI_ITINERARY_URL`
- JSON: `{"date":"2026-11-21","slots":["breakfast","lunch","snack","dinner"],"profile":{"favFoods":[],"favRestaurantIds":[],"topRatedRestaurantIds":[],"recentSearchFoodIds":[],"avgPriceLevel":2},"candidates":[{"id":1,"name":"Quán Ngon","district":"Hải Châu","priceLevel":2,"open":"06:00","close":"22:00","mealSlots":["breakfast","lunch","snack","dinner"],"foods":["Mì Quảng"],"rating":4.5}]}`
- Response: `{"plan":[{"slot":"breakfast","restaurantId":1,"foodId":1,"reason":"Phù hợp buổi sáng"}]}`
- Adapt alternate upstream fields only in `map_response()`.

Start real mode:
```powershell
$env:MOCK_AI="false"; $env:JWT_SECRET="<long-random-secret>"
```

Test search: `curl -X POST -H "Authorization: Bearer $AI_SEARCH_KEY" -F "image=@fixture.jpg" "$AI_SEARCH_URL"`
Test itinerary: `curl -X POST -H "Authorization: Bearer $AI_ITINERARY_KEY" -H "Content-Type: application/json" -d '{"date":"2026-11-21","slots":["breakfast","lunch","snack","dinner"],"profile":{},"candidates":[]}' "$AI_ITINERARY_URL"`
