#!/data/data/com.termux/files/usr/bin/bash
set -e

PROJ="$HOME/Kael_ia/android_assist"
TOOLS="$HOME/android-tools"
BUILD="$PROJ/build_termux"
ANDROID_JAR="$TOOLS/android.jar"
KOTLINC="$TOOLS/kotlinc/bin/kotlinc"
STDLIB_JAR="$TOOLS/kotlinc/lib/kotlin-stdlib.jar"

export PATH="$TOOLS/kotlinc/bin:$PATH"

rm -rf "$BUILD"
mkdir -p "$BUILD/res_flat" "$BUILD/gen" "$BUILD/classes" "$BUILD/dex" "$BUILD/apk"

echo "[1/5] Compilando recursos (aapt2)..."
aapt2 compile --dir "$PROJ/res" -o "$BUILD/res_flat/res.zip"
aapt2 link -o "$BUILD/apk/unsigned.apk" -I "$ANDROID_JAR" --manifest "$PROJ/AndroidManifest.xml" --java "$BUILD/gen" "$BUILD/res_flat/res.zip"

echo "[2/5] Compilando Kotlin + Java (kotlinc)..."
"$KOTLINC" -classpath "$ANDROID_JAR" -d "$BUILD/classes" "$PROJ/src/main/kotlin/com/kael/assist/KaelAssistService.kt" "$PROJ/src/main/kotlin/com/kael/assist/KaelAssistSession.kt" "$PROJ/src/main/kotlin/com/kael/assist/KaelAssistActivity.kt" "$PROJ/src/main/kotlin/com/kael/assist/KaelRecognitionService.kt" "$BUILD/gen"

echo "[3/5] Convertendo bytecode para DEX (d8)..."
d8 --lib "$ANDROID_JAR" --output "$BUILD/dex" $(find "$BUILD/classes" -name "*.class") "$STDLIB_JAR"

echo "[4/5] Empacotando classes.dex no APK..."
cp "$BUILD/dex/classes.dex" "$BUILD/apk/classes.dex"
(cd "$BUILD/apk" && zip -q -u unsigned.apk classes.dex)

echo "[5/5] Assinando APK (apksigner)..."
KEYSTORE="$TOOLS/kael-release.keystore"
if [ ! -f "$KEYSTORE" ]; then
  keytool -genkeypair -v -keystore "$KEYSTORE" -storepass android -keypass android -alias kaelkey -keyalg RSA -keysize 2048 -validity 10000 -dname "CN=KaelAssist,O=Kael,C=BR" >/dev/null 2>&1
fi
apksigner sign --ks "$KEYSTORE" --ks-pass pass:android --key-pass pass:android --out "$PROJ/KaelAssist.apk" "$BUILD/apk/unsigned.apk"

echo "APK GERADO COM SUCESSO: $PROJ/KaelAssist.apk"
