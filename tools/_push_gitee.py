"""把源码推到 Gitee（dulwich，无需系统 git）。"""
from __future__ import annotations

import os
import shutil
import time

from dulwich import porcelain
from dulwich.repo import Repo

ROOT = r"C:\Users\渡渡\Documents\deepseek-harness\default-workspace\halo-desktop"
STAGE = os.path.join(ROOT, ".push_stage")
TOKEN = "1242b25886a0546fdb14f05e3ee18a84"
URL = f"https://guo-wenlong:{TOKEN}@gitee.com/guo-wenlong/halo-desk.git"

SKIP_DIRS = {".venv", "build", "dist", "data", "__pycache__", ".git", ".verify",
             ".verify_data", ".sim_data", ".uitest", "docs/shots", ".push_stage"}
SKIP_EXT = {".log", ".jpg", ".jpeg", ".pyc"}


def copy_tree(src: str, dst: str) -> None:
    os.makedirs(dst, exist_ok=True)
    for name in os.listdir(src):
        if name in SKIP_DIRS or name.startswith(".verify") or name.startswith(".uitest"):
            continue
        s = os.path.join(src, name)
        d = os.path.join(dst, name)
        if os.path.isdir(s):
            os.makedirs(d, exist_ok=True)
            copy_tree(s, d)
        else:
            if os.path.splitext(name)[1].lower() in SKIP_EXT:
                continue
            if src.endswith("docs") and name.lower().endswith(".png"):
                continue
            shutil.copy2(s, d)


def main() -> None:
    if os.path.exists(STAGE):
        shutil.rmtree(STAGE, ignore_errors=True)
    os.makedirs(STAGE)
    for item in ("main.py", "README.md", "HaloDesk.spec"):
        shutil.copy2(os.path.join(ROOT, item), os.path.join(STAGE, item))
    for item in ("app", "assets", "tools", "docs"):
        copy_tree(os.path.join(ROOT, item), os.path.join(STAGE, item))

    gi = os.path.join(STAGE, ".gitignore")
    with open(gi, "w", encoding="utf-8") as f:
        f.write("data/\ndist/\nbuild/\n.venv/\n__pycache__/\n*.pyc\n*.log\n"
                "*.png\n._MEI*\n.verify*/\n.uitest*/\n")

    repo = Repo.init(STAGE)
    porcelain.add(repo, paths=["."])
    porcelain.commit(
        repo,
        message="大肥鱼桌面版 v3.0：记忆可视化、记忆压缩、生图模型轮换、两套表情",
        author=b"guo-wenlong <guo-wenlong@users.noreply.gitee.com>",
        committer=b"guo-wenlong <guo-wenlong@users.noreply.gitee.com>",
    )
    print("commit ok")
    porcelain.push(repo, URL, refspecs=["refs/heads/master:refs/heads/master"])
    print("push ok", time.strftime("%H:%M:%S"))


if __name__ == "__main__":
    main()
