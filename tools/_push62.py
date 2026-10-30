import os
import shutil
from dulwich import porcelain

ROOT = r"C:\Users\渡渡\Documents\deepseek-harness\default-workspace\halo-desktop"
STAGE = os.path.join(ROOT, ".push_stage62")
TOKEN = "1242b25886a0546fdb14f05e3ee18a84"
URL = f"https://guo-wenlong:{TOKEN}@gitee.com/guo-wenlong/halo-desk.git"
SKIP_DIRS = {".venv", "build", "dist", "data", "__pycache__", ".git", "docs/shots",
             ".push_stage62", ".checkrepo"}
SKIP_EXT = {".log", ".jpeg", ".pyc"}
DOC_IMAGES = {"preview-home.png", "wallpaper_glass.png", "splash.png",
              "preview-pet.png", "preview-auto.png", "memcard.png"}


def copy_tree(src, dst, is_docs=False):
    os.makedirs(dst, exist_ok=True)
    for name in os.listdir(src):
        if name in SKIP_DIRS or name.startswith(".verify") or name.startswith(".uitest"):
            continue
        s, d = os.path.join(src, name), os.path.join(dst, name)
        if os.path.isdir(s):
            copy_tree(s, d, is_docs)
        else:
            if os.path.splitext(name)[1].lower() in SKIP_EXT:
                continue
            if is_docs and name.lower().endswith(".png") and name not in DOC_IMAGES:
                continue
            shutil.copy2(s, d)


if os.path.exists(STAGE):
    shutil.rmtree(STAGE, ignore_errors=True)
porcelain.clone(URL, STAGE)
for item in ("main.py", "README.md", "HaloDesk.spec", ".gitignore", "version.txt"):
    shutil.copy2(os.path.join(ROOT, item), os.path.join(STAGE, item))
for item in ("app", "assets", "tools"):
    copy_tree(os.path.join(ROOT, item), os.path.join(STAGE, item))
copy_tree(os.path.join(ROOT, "docs"), os.path.join(STAGE, "docs"), is_docs=True)
repo = porcelain.open_repo(STAGE)
porcelain.add(repo, paths=["."])
porcelain.commit(
    repo,
    message="v10.6：匿名安装统计、更新/公告/强制更新、后台管理提示词与下载直链",
    author=b"guo-wenlong <guo-wenlong@users.noreply.gitee.com>",
    committer=b"guo-wenlong <guo-wenlong@users.noreply.gitee.com>")
porcelain.push(repo, URL, refspecs=["refs/heads/master:refs/heads/master"])
print("pushed")
shutil.rmtree(STAGE, ignore_errors=True)
