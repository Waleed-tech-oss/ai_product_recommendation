# from fastapi import APIRouter, Query
# from database.postgres import get_search_suggestions

# router = APIRouter()

# @router.get("/search-suggestions")
# def search_suggestions(q: str = Query(..., min_length=1)):
#     suggestions = get_search_suggestions(q)

#     return {
#         "success": True,
#         "suggestions": suggestions
#     }