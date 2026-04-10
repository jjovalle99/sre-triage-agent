def wrap_user_input(title: str, description: str) -> str:
    return f"Title: {title}\n\n[USER_INPUT_START]\n{description}\n[USER_INPUT_END]"
