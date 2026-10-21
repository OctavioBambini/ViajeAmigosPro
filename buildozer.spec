[app]
title = ViajeAmigos Pro Local
package.name = viajeamigosprolocal
package.domain = org.proyectoescuela
source.dir = .
source.include_exts = py,kv,png,jpg,jpeg,atlas,txt,json
source.exclude_dirs = tests,.github,.venv,venv,__pycache__,bin,.buildozer
version = 1.0.0
requirements = python3,kivy==2.3.1,plyer,pyjnius,kivy_garden.mapview,requests,certifi,charset-normalizer==3.4.2
orientation = portrait
fullscreen = 0
icon.filename = %(source.dir)s/assets/icon.png
android.permissions = INTERNET,ACCESS_FINE_LOCATION,ACCESS_COARSE_LOCATION,CAMERA
android.minapi = 24
android.api = 35
android.accept_sdk_license = True
android.archs = arm64-v8a
android.debug_artifact = apk
android.allow_backup = False

[buildozer]
log_level = 2
warn_on_root = 1
