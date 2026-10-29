import os
import shutil
from dulwich import porcelain

ROOT = r"C:\Users\渡渡\Documents\deepseek-harness\default-workspace\halo-desktop"
STAGE = os.path.join(ROOT, ".push_stage8")
TOKEN = "1242b25886a0546fdb14f05e3ee18a84"
URL = f"https://guo-wenlong:{TOKEN}@gitee.com/guo-wenlong/halo-desk.git"

SKIP_DIRS = {".venv", "build", "dist", "data", "__pycache__", ".git", "docs/shots",
             ".push_stage8"}
SKIP_EXT = {".log", ".jpg", ".jpeg", ".pyc"}


def copy_tree(src, dst):
    os.makedirs(dst, exist_ok=True)
    for name in os.listdir(src):
        if name in SKIP_DIRS or name.startswith(".verify") or name.startswith(".uitest"):
            continue
        s, d = os.path.join(src, name), os.path.join(dst, name)
        if os.path.isdir(s):
            copy_tree(s, d)
        else:
            if os.path.splitext(name)[1].lower() in SKIP_EXT:
                continue
            if src.endswith("docs") and name.lower().endswith(".png"):
                continue
            shutil.copy2(s, d)


if os.path.exists(STAGE):
    shutil.rmtree(STAGE, ignore_errors=True)
porcelain.clone(URL, STAGE)
for item in ("main.py", "README.md", "HaloDesk.spec"):
    shutil.copy2(os.path.join(ROOT, item), os.path.join(STAGE, item))
for item in ("app", "assets", "tools", "docs"):
    copy_tree(os.path.join(ROOT, item), os.path.join(STAGE, item))

repo = porcelain.open_repo(STAGE)
porcelain.add(repo, paths=["."])
porcelain.commit(
    repo,
    message="v4.0：发帖板块锁死、生活记忆启动检查、通用记忆记录社区行为、"
            "双平台 23:00 日记带图、形象自定义、测试日记",
    author=b"guo-wenlong <guo-wenlong@users.noreply.gitee.com>",
    committer=b"guo-wenlong <guo-wenlong@users.noreply.gitee.com>")
porcelain.push(repo, URL, refspecs=["refs/heads/master:refs/heads/master"])
print("pushed")
shutil.rmtree(STAGE, ignore_errors=True)
