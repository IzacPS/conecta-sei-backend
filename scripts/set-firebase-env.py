"""One-off: read Firebase JSON and set FIREBASE_CREDENTIALS in .env (inline)."""
import json
import os

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSON_PATH = os.path.join(REPO_ROOT, "conecta-sei-firebase-adminsdk-fbsvc-7d024e07fd.json")
ENV_PATH = os.path.join(REPO_ROOT, ".env")

def main():
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    json_one_line = json.dumps(data, separators=(",", ":"))
    escaped = json_one_line.replace("\\", "\\\\").replace('"', '\\"')
    cred_line = 'FIREBASE_CREDENTIALS="' + escaped + '"\n'

    lines = []
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("FIREBASE_CREDENTIALS="):
                    continue
                lines.append(line)
    lines.append(cred_line)
    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.writelines(lines)
    print("FIREBASE_CREDENTIALS written to .env (inline JSON)")


if __name__ == "__main__":
    main()
