import random
import string


def generate_otp() -> str:
    return "".join(random.choices(string.digits, k=6))
