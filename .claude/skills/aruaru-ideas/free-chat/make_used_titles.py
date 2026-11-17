"""stock/ から使用済みタイトルを抜き出し、無料プランのチャットに添付する一覧を作る。"""
import pathlib
import re

base = pathlib.Path(__file__).resolve().parent.parent / "stock"
out = pathlib.Path(__file__).resolve().parent / "used_titles.txt"

lines = ["使用済みタイトル一覧（このテーマ・オチは使わない）", ""]
for name, label in [("engineer.md", "エンジニア"), ("it.md", "IT業界"), ("shakaijin.md", "社会人")]:
    seen = []
    for raw in (base / name).read_text().splitlines():
        m = re.match(r"- ([^：]{1,40})：", raw)
        if m and m.group(1) not in seen:
            seen.append(m.group(1))
    lines.append(f"【{label}】{len(seen)}件")
    lines.append("／".join(seen))
    lines.append("")
out.write_text("\n".join(lines))
print(out, out.stat().st_size, "bytes")
