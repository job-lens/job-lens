#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p verification/ci-results
adb wait-for-device
adb shell wm size 390x844
adb shell wm density 160
adb shell settings put system font_scale 1.0
adb shell settings put secure show_ime_with_hard_keyboard 1
adb shell setprop debug.hwui.drawing_enabled true
adb install -r app/build/outputs/apk/debug/app-debug.apk
adb install -r app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk
adb shell cmd package compile -m speed -f xyz.qunxue.joblens
adb shell cmd package compile -m speed -f xyz.qunxue.joblens.test
result=0
timeout 600 adb shell am instrument -w -e class xyz.qunxue.joblens.NativeUiTest xyz.qunxue.joblens.test/androidx.test.runner.AndroidJUnitRunner > verification/ci-results/instrumentation.log 2>&1 || result=1
cat verification/ci-results/instrumentation.log
grep -F 'OK (14 tests)' verification/ci-results/instrumentation.log || result=1
adb pull /sdcard/Android/data/xyz.qunxue.joblens/files/qa verification/ci-results/screenshots || result=1
adb shell am force-stop xyz.qunxue.joblens
timeout 45 adb shell am start -W -n xyz.qunxue.joblens/.MainActivity || result=1
# Activity launch completion can precede its first rendered frame. Read real login
# controls, then verify the actual screenshot instead of guessing a sleep duration.
if ! python3 - <<'PY'
import pathlib, struct, subprocess, time, xml.etree.ElementTree as ET, zlib

out = pathlib.Path("verification/ci-results")

def visible_frame(png):
    if png[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("Screenshot is not a PNG")
    offset, compressed = 8, bytearray()
    while offset < len(png):
        length = struct.unpack(">I", png[offset:offset + 4])[0]
        kind = png[offset + 4:offset + 8]
        data = png[offset + 8:offset + 8 + length]
        if kind == b"IHDR":
            width, height, depth, color, _, _, interlace = struct.unpack(">IIBBBBB", data)
        elif kind == b"IDAT":
            compressed.extend(data)
        offset += length + 12
    if depth != 8 or color not in (2, 6) or interlace or width < 100 or height < 100:
        raise ValueError("Unsupported screenshot format or dimensions")
    channels = 3 if color == 2 else 4
    stride, raw = width * channels, zlib.decompress(compressed)
    previous, bright, sampled = bytearray(stride), 0, 0
    for y in range(height):
        start = y * (stride + 1)
        mode, row = raw[start], bytearray(raw[start + 1:start + 1 + stride])
        for i in range(stride):
            left = row[i - channels] if i >= channels else 0
            above = previous[i]
            corner = previous[i - channels] if i >= channels else 0
            if mode == 1:
                row[i] = (row[i] + left) & 255
            elif mode == 2:
                row[i] = (row[i] + above) & 255
            elif mode == 3:
                row[i] = (row[i] + ((left + above) // 2)) & 255
            elif mode == 4:
                prediction = left + above - corner
                distances = [abs(prediction - v) for v in (left, above, corner)]
                row[i] = (row[i] + (left, above, corner)[distances.index(min(distances))]) & 255
            elif mode != 0:
                raise ValueError("Unsupported PNG row filter")
        # Exclude status/navigation bars: their bright pixels do not prove app drawing.
        if height // 10 <= y < height * 9 // 10:
            for x in range(0, stride, channels):
                bright += max(row[x:x + 3]) > 24
                sampled += 1
        previous = row
    return bright > sampled // 100

def login_visible(xml):
    nodes = list(ET.fromstring(xml).iter("node"))
    nodes = [n for n in nodes if n.get("package") == "xyz.qunxue.joblens"
             and n.get("bounds") not in (None, "[0,0][0,0]")]
    fields = [n for n in nodes if n.get("class") == "android.widget.EditText"
              and n.get("enabled") == "true"]
    def labelled(node, label):
        return any(child.get("content-desc") == label for child in node.iter("node"))
    return (any(labelled(n, "账号") and n.get("password") == "false" for n in fields)
            and any(labelled(n, "密码") and n.get("password") == "true" for n in fields)
            and any(n.get("clickable") == "true" and n.get("enabled") == "true"
                    and any(child.get("text") == "登录" for child in n.iter("node"))
                    for n in nodes))

def main():
    deadline = time.monotonic() + 60
    reason = "Login controls were not visible"
    def adb(*args):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Login screenshot deadline reached")
        return subprocess.run(["adb", *args], check=True, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, timeout=min(10, remaining)).stdout
    while time.monotonic() < deadline:
        try:
            adb("shell", "uiautomator", "dump", "--compressed", "/sdcard/joblens-login.xml")
            xml = adb("exec-out", "cat", "/sdcard/joblens-login.xml")
            (out / "production-login-hierarchy.xml").write_bytes(xml)
            if not login_visible(xml):
                reason = "Actual account, password and login controls are not visible"
                continue
            png = adb("exec-out", "screencap", "-p")
            (out / "00-production-login.png").write_bytes(png)
            if not visible_frame(png):
                reason = "Actual login screenshot is black despite visible controls"
                continue
            print("Actual login controls and non-black rendered frame verified")
            return
        except (subprocess.SubprocessError, ET.ParseError, ValueError, TimeoutError) as error:
            reason = str(error)
    raise SystemExit("Login screenshot failed within 60 seconds: " + reason)

if __name__ == "__main__":
    main()
PY
then
  result=1
fi
adb logcat -d > verification/ci-results/logcat.txt || true
sha256sum app/build/outputs/apk/debug/app-debug.apk > verification/ci-results/APK-SHA256.txt
exit "$result"
