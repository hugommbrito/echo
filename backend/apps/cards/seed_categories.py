"""Global seed categories (docs/PLAN.md §9.4). Used by the data migration and by tests."""

SEED_CATEGORIES = [
    {
        "slug": "everyday-situations",
        "name": "Everyday situations",
        "description": (
            "Daily life in Canada: neighbours, appointments, the bank, the doctor, public "
            "transport, weather, small talk, housing."
        ),
        "generation_hint": (
            "Alternate between questions someone asks the learner and situations where the "
            "learner must explain or describe something."
        ),
        "sort_order": 1,
    },
    {
        "slug": "shopping",
        "name": "Shopping",
        "description": (
            "Stores, groceries, returns and exchanges, prices, comparing products, asking staff "
            "for help, online orders and deliveries."
        ),
        "generation_hint": (
            "Include both the learner as customer and the learner describing habits or preferences."
        ),
        "sort_order": 2,
    },
    {
        "slug": "job-interview",
        "name": "Job interview",
        "description": (
            "Interview questions for entry and mid-level jobs in Canada (customer service, "
            "administration, hospitality, retail, tech support): classic, behavioural "
            '("tell me about a time…") and situational.'
        ),
        "generation_hint": (
            "Phrase questions exactly as an interviewer would. Vary classic / behavioural / "
            "situational."
        ),
        "sort_order": 3,
    },
    {
        "slug": "travel",
        "name": "Travel",
        "description": (
            "Airports, border and immigration questions, hotels, directions, public transport, "
            "describing trips and plans."
        ),
        "generation_hint": (
            "Include realistic officer and staff questions as well as questions about the "
            "learner's own travel experiences."
        ),
        "sort_order": 4,
    },
]
