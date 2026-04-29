"""Market research tools. Mock data for training — swap for google-play-scraper in production."""


_MOCK_REVIEWS_BY_CATEGORY = {
    'expense': [
        {'rating': 2, 'text': 'Splitting bills is complicated, needs more options'},
        {'rating': 4, 'text': 'Great for tracking shared expenses with roommates'},
        {'rating': 1, 'text': 'App crashes when I try to add a receipt photo'},
        {'rating': 5, 'text': 'Love the automatic category detection'},
        {'rating': 3, 'text': 'UI looks outdated, needs dark mode'},
    ],
    'fitness': [
        {'rating': 5, 'text': 'Step counter is very accurate'},
        {'rating': 2, 'text': 'Battery drain is terrible'},
        {'rating': 4, 'text': 'Would love GPS route tracking for walks'},
        {'rating': 1, 'text': 'Null pointer exception on startup after update'},
        {'rating': 3, 'text': 'Onboarding is too long, 7 screens before use'},
    ],
    'generic': [
        {'rating': 3, 'text': 'Decent app but slow on older phones'},
        {'rating': 5, 'text': 'Clean interface and easy to use'},
        {'rating': 2, 'text': 'Login screen freezes after entering password'},
        {'rating': 4, 'text': 'Please add offline mode and dark theme'},
        {'rating': 1, 'text': 'Data disappeared after last update'},
    ],
}


def get_play_store_reviews(app_id: str, limit: int = 5) -> dict:
    """Fetch recent Play Store reviews. Returns structured list."""
    key = 'generic'
    lowered = app_id.lower()
    if any(w in lowered for w in ('expense', 'split', 'finance', 'money', 'receipt')):
        key = 'expense'
    elif any(w in lowered for w in ('step', 'fit', 'health', 'walk', 'run')):
        key = 'fitness'

    reviews = _MOCK_REVIEWS_BY_CATEGORY[key][:limit]
    return {
        'status': 'ok',
        'app_id': app_id,
        'category': key,
        'count': len(reviews),
        'reviews': reviews,
    }


MARKET_TOOL_SCHEMAS = [
    {
        'type': 'function',
        'function': {
            'name': 'get_play_store_reviews',
            'description': 'Fetch recent Play Store reviews for a category-hinted app id.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'app_id': {'type': 'string', 'description': 'Package name or category hint'},
                    'limit': {'type': 'integer', 'description': 'Max reviews. Default 5.'},
                },
                'required': ['app_id'],
            },
        },
    },
]

MARKET_TOOL_MAP = {
    'get_play_store_reviews': get_play_store_reviews,
}
