import os
import shutil
from dulwich import porcelain

ROOT = r"C:\Users\渡渡\Documents\deepseek-harness\default-workspace\halo-desktop"
STAGE = os.path.join(ROOT, ".push_stage15")
TOKEN = "1242b25886a0546fdb14f05e3ee18a84"
URL = f"https://guo-wenlong:{TOKEN}@gitee.com/guo-wenlong/halo-desk.git"
SKIP_DIRS = {".venv", "build", "dist", "data", "__pycache__", ".git", "docs/shots",
             ".push_stage15"}
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
    message="v5.2：浅色主题+黑夜开关、账号隔离数据目录、登录失效检测、清空数据、生活记忆每小时",
    author=b"guo-wenlong <guo-wenlong@users.noreply.gitee.com>",
    committer=b"guo-wenlong <guo-wenlong@users.noreply.gitee.com>")
porcelain.push(repo, URL, refspecs=["refs/heads/master:refs/heads/master"])
print("pushed")
shutil.rmtree(STAGE, ignore_errors=True)
