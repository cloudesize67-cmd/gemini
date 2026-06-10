"""
AEGIS.NET — Secure Key Setup
=============================
Run this ONCE to securely add API keys to .env.

Keys are entered with hidden input (like a password prompt) —
they never appear on screen and are never stored in chat history.

Usage:
    python setup_keys.py
"""
import getpass, os, sys

ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "aegis-net", ".env")

KEYS = [
    ("ANTHROPIC_API_KEY",  "Anthropic API key (console.anthropic.com/settings/keys)"),
    ("GROQ_API_KEY",       "Groq API key — free (console.groq.com) — press Enter to skip"),
    ("GEMINI_API_KEY",     "Gemini API key — free (aistudio.google.com) — press Enter to skip"),
    ("YOUTUBE_API_KEY",    "YouTube Data API key — free (console.cloud.google.com) — press Enter to skip"),
]

def read_env(path):
    if not os.path.exists(path):
        return {}
    lines = open(path).readlines()
    env = {}
    for line in lines:
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip()
    return env

def write_env(path, env):
    # Read original file to preserve comments and structure
    if os.path.exists(path):
        lines = open(path).readlines()
    else:
        lines = []

    # Update lines that have matching keys
    updated = set()
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if "=" in stripped and not stripped.startswith("#"):
            k = stripped.split("=")[0].strip()
            if k in env:
                new_lines.append(f"{k}={env[k]}\n")
                updated.add(k)
                continue
        new_lines.append(line)

    # Append any keys not already in file
    for k, v in env.items():
        if k not in updated:
            new_lines.append(f"{k}={v}\n")

    with open(path, "w") as f:
        f.writelines(new_lines)

def main():
    print("\n" + "="*55)
    print("  AEGIS.NET — Secure API Key Setup")
    print("  Keys are hidden as you type. Nothing shown in chat.")
    print("="*55 + "\n")

    current = read_env(ENV_FILE)
    new_values = {}

    for key, description in KEYS:
        existing = current.get(key, "")
        already_set = existing and not existing.startswith("your_") and existing != ""

        if already_set:
            print(f"  {key}: already set — press Enter to keep, or type new value")
        else:
            print(f"  {description}")

        try:
            value = getpass.getpass(f"  {key}: ")
        except (KeyboardInterrupt, EOFError):
            print("\n  Cancelled.")
            sys.exit(0)

        if value.strip():
            new_values[key] = value.strip()
        elif already_set:
            print(f"  Keeping existing {key}")
        else:
            print(f"  Skipping {key}")
        print()

    if new_values:
        write_env(ENV_FILE, new_values)
        print(f"  Keys saved to {ENV_FILE}")
        print("  File is git-ignored — keys never leave this machine.\n")
    else:
        print("  No changes made.\n")

if __name__ == "__main__":
    main()
