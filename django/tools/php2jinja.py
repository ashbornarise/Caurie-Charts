"""Conversion mécanique des gabarits PHP simples (pages légales) vers Jinja2 ; relecture manuelle ensuite."""
import re, sys
from pathlib import Path

def expr(x: str) -> str:
    x = x.strip()
    x = re.sub(r"Config::get\(", "config(", x)
    x = re.sub(r"\(int\)\s*", "", x)
    x = re.sub(r"\$(\w+)\['(\w+)'\]", r"\1.\2", x)
    x = re.sub(r"\[\s*'(\w+)'\s*=>\s*", r"{'\1': ", x).replace("])", "})")
    x = x.replace(" . ", " ~ ").replace("!==", "!=").replace("===", "==").replace("||", " or ").replace("&&", " and ")
    x = re.sub(r"\$(\w+)", r"\1", x)
    return x

def convert(src: str) -> str:
    src = re.sub(r"<\?php\s+use [^;]+;\s*(\$\w+ = [^;]+;)?\s*\?>\n?", lambda m: ("{%- set " + expr(m.group(1)).rstrip(";").replace(" = ", " = ", 1) + " -%}\n") if m.group(1) else "", src)
    src = re.sub(r"<\?= e\((.+?)\) \?>", lambda m: "{{ " + expr(m.group(1)) + " }}", src)
    src = re.sub(r"<\?= (legal|path)\((.+?)\) \?>", lambda m: "{{ " + m.group(1) + "(" + expr(m.group(2)) + ") }}", src)
    src = re.sub(r"<\?= \(int\) (.+?) \?>", lambda m: "{{ " + expr(m.group(1)) + "|int }}", src)
    src = re.sub(r"<\?php if \((.+?)\): \?>", lambda m: "{% if " + expr(m.group(1)) + " %}", src)
    src = re.sub(r"<\?php elseif \((.+?)\): \?>", lambda m: "{% elif " + expr(m.group(1)) + " %}", src)
    src = src.replace("<?php else: ?>", "{% else %}").replace("<?php endif; ?>", "{% endif %}")
    return src

for f in sys.argv[1:]:
    out = Path("templates/legal") / (Path(f).stem + ".html")
    out.write_text(convert(Path(f).read_text(encoding="utf-8")), encoding="utf-8")
    print(out)
