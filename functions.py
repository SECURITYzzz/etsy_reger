import os
import random
import string
import sys


def generate_password(length=12):
    letters = string.ascii_letters
    digits = string.digits
    special_chars = "!@#$%^&*()_+-="
    all_chars = letters + digits + special_chars
    password = [
        random.choice(string.ascii_lowercase),
        random.choice(string.ascii_uppercase),
        random.choice(digits),
        random.choice(special_chars)
    ]
    for _ in range(length - 4):
        password.append(random.choice(all_chars))
    random.shuffle(password)
    return ''.join(password)

def get_executable_dir():
    if getattr(sys, 'frozen', False):
        application_path = os.path.dirname(sys.executable)
    else:
        application_path = os.path.dirname(os.path.abspath(__file__))

    return application_path


def get_abspath(relative_path: str):
    return os.path.join(get_executable_dir(), relative_path)


def create_resource_in_executable_dir(resource_path: str, is_folder: bool = False):
    executable_dir = get_executable_dir()
    path = os.path.split(resource_path)

    created_path = executable_dir
    for folder in path[:-1]:
        created_path = os.path.join(created_path, folder)
        if not os.path.exists(created_path):
            os.makedirs(created_path)

    if not os.path.exists(os.path.join(created_path, path[-1])):
        if is_folder:
            os.makedirs(os.path.join(created_path, path[-1]))
        else:
            open(os.path.join(created_path, path[-1]), 'w').close()

    return get_abspath(resource_path)
