"""테마의 동아시아 글꼴 칸(ea)과 한글(Hang) 글꼴을 지정해 한글이 어느 프로그램에서나 같은 글꼴로 나오게 한다."""
import sys, zipfile, shutil, re, os
path, font = sys.argv[1], sys.argv[2]
tmp = path + ".tmp"
with zipfile.ZipFile(path) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
    for it in zin.infolist():
        data = zin.read(it.filename)
        if it.filename.startswith("ppt/theme/theme") and it.filename.endswith(".xml"):
            s = data.decode("utf-8")
            s = s.replace('<a:ea typeface=""/>', f'<a:ea typeface="{font}"/>')
            s = re.sub(r'<a:font script="Hang" typeface="[^"]*"/>', f'<a:font script="Hang" typeface="{font}"/>', s)
            data = s.encode("utf-8")
        zout.writestr(it, data)
shutil.move(tmp, path)
print("ea font ->", font, os.path.basename(path))
