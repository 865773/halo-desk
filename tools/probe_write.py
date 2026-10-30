import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "probe_out.txt"
lines = []
try:
    p = Path.home() / "AppData" / "Roaming" / "HaloDesk"
    (p / "pyprobe.txt").write_text("hello")
    lines.append("direct write ok: %s" % p)
except Exception as e:
    lines.append("direct write FAIL: %r" % e)

try:
    sys.path.insert(0, str(ROOT))
    from app.config import CFG, CONFIG_PATH
    lines.append("config path: %s" % CONFIG_PATH)
    CFG.set("general.page", "probe")
    CFG.save()
    lines.append("cfg save -> exists=%s" % CONFIG_PATH.exists())
    if CONFIG_PATH.exists():
        lines.append("size=%s" % CONFIG_PATH.stat().st_size)
except Exception:
    lines.append("cfg FAIL:\n" + traceback.format_exc())

OUT.write_text("\n".join(lines), encoding="utf-8")
