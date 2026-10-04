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
adb shell am start -W -n xyz.qunxue.joblens/.MainActivity
adb exec-out screencap -p > verification/ci-results/00-production-login.png
adb logcat -d > verification/ci-results/logcat.txt || true
sha256sum app/build/outputs/apk/debug/app-debug.apk > verification/ci-results/APK-SHA256.txt
exit "$result"
