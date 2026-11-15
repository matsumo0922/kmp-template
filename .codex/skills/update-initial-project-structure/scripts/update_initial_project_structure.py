#!/usr/bin/env python3
"""kmp-template-impl の内容で InitialProjectStructure.json を差分更新する。

収録済みの path は impl の作業ツリーと比較して更新・削除する。
新規ファイルは `--since` 以降に impl へ追加されたものだけを収録する。
`--all` を指定すると、impl の全ファイルを収録対象にする。
"""

import argparse
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

RAW_URL = "https://raw.githubusercontent.com/matsumo0922/kmp-template-impl/HEAD"


def git(impl, *args):
    result = subprocess.run(["git", "-C", str(impl), *args], capture_output=True, check=True)
    return result.stdout


def git_lines(impl, *args):
    return [line for line in git(impl, *args).decode("utf-8").split("\0") if line]


def decode(data):
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def estimate_tokens(text):
    """正規の tokenizer は使わず、文字数から 100 単位の概算値を返す。"""
    return max(100, math.ceil(len(text) / 4.2 / 100) * 100)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def tree_parent(tree, key, create=False):
    parts = key.strip("/").split("/")
    node = tree
    for part in parts[:-1]:
        node = node.setdefault(part, {}) if create else node[part]
    return node, parts[-1]


def prune_empty(tree):
    for name in list(tree):
        if isinstance(tree[name], dict):
            prune_empty(tree[name])
            if not tree[name]:
                del tree[name]


def build_entry(key, data):
    text = decode(data)
    if text is None:
        return {"type": "binary", "hash": sha256(data), "size": len(data), "url": RAW_URL + key}, 100
    return {"type": "content", "content": text, "hash": sha256(data), "size": len(data)}, estimate_tokens(text)


def main():
    repo_root = Path(__file__).resolve().parents[4]
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--impl", type=Path, default=repo_root.parent / "kmp-template-impl", help="kmp-template-impl の checkout")
    parser.add_argument("--json", type=Path, default=repo_root / "InitialProjectStructure.json", help="更新する JSON")
    parser.add_argument("--since", default="HEAD", help="JSON が最後に同期した impl の commit。これ以降の追加ファイルを収録する")
    parser.add_argument("--all", action="store_true", help="impl の全ファイルを収録対象にする")
    args = parser.parse_args()

    impl = args.impl.resolve()
    data = json.loads(args.json.read_text(encoding="utf-8"))
    files, tree, size = data["files"], data["tree"], data["size"]

    present = ["/" + path for path in git_lines(impl, "ls-files", "-z", "-co", "--exclude-standard") if (impl / path).is_file()]
    untracked = ["/" + path for path in git_lines(impl, "ls-files", "-z", "-o", "--exclude-standard")]
    touched = ["/" + path for path in git_lines(impl, "diff", "--name-only", "--no-renames", "-z", args.since)] + untracked
    added = ["/" + path for path in git_lines(impl, "diff", "--name-only", "--no-renames", "--diff-filter=A", "-z", args.since)] + untracked

    updated, removed, new = [], [], []
    token_delta = 0

    for key in list(files):
        entry = files[key]
        parent, name = tree_parent(tree, key)

        if key not in present:
            token_delta -= parent.pop(name)
            del files[key]
            removed.append(key)
            continue

        content = (impl / key.lstrip("/")).read_bytes()
        if entry["type"] == "binary":
            if entry["size"] != len(content):
                entry["size"] = len(content)
                entry["hash"] = sha256(content) if entry["hash"] else ""
                updated.append(key)
            continue

        if content.decode("utf-8") == entry["content"]:
            continue

        files[key], tokens = build_entry(key, content)
        token_delta += tokens - parent[name]
        parent[name] = tokens
        updated.append(key)

    candidates = present if args.all else added
    for key in sorted(set(candidates) & set(present) - set(files)):
        files[key], tokens = build_entry(key, (impl / key.lstrip("/")).read_bytes())
        parent, name = tree_parent(tree, key, create=True)
        parent[name] = tokens
        token_delta += tokens
        new.append(key)

    prune_empty(tree)

    # size の totalTokens / characters / lines は JSON 未収録のファイルも含むリポジトリ全体の値
    char_delta = line_delta = 0
    for key in sorted(set(touched)):
        path = key.lstrip("/")
        before = subprocess.run(["git", "-C", str(impl), "show", f"{args.since}:{path}"], capture_output=True)
        old_text = decode(before.stdout) if before.returncode == 0 else ""
        new_text = decode((impl / path).read_bytes()) if (impl / path).is_file() else ""
        if old_text is None or new_text is None:
            continue
        char_delta += len(new_text) - len(old_text)
        line_delta += new_text.count("\n") - old_text.count("\n")

    size["tokens"] += token_delta
    size["totalTokens"] += round(char_delta / 4.2)
    size["characters"] += char_delta
    size["lines"] += line_delta

    args.json.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    for label, keys in (("updated", updated), ("removed", removed), ("added", new)):
        print(f"{label}: {len(keys)}")
        for key in keys:
            print(f"  {key}")

    missing = sorted(set(present) - set(files))
    if missing:
        print(f"not included: {len(missing)} (--all で収録)", file=sys.stderr)
        for key in missing:
            print(f"  {key}", file=sys.stderr)


if __name__ == "__main__":
    main()
