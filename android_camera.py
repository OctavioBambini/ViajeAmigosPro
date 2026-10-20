"""Android Camera intent for a private, local JPEG without exposing file:// URIs.

The ACTION_IMAGE_CAPTURE thumbnail is intentionally used: it avoids the
FileProvider configuration required when requesting full-resolution images.
It may be lower resolution than a normal camera app photo.
"""
from pathlib import Path


def take_picture(destination, callback):
    """Open the Android camera app and call callback(path or '') on return.

    This module should only be invoked on Android, after CAMERA permission.
    """
    from jnius import autoclass
    from android import activity
    from kivy.clock import Clock

    JavaActivity = autoclass('android.app.Activity')
    PythonActivity = autoclass('org.kivy.android.PythonActivity')
    Intent = autoclass('android.content.Intent')
    MediaStore = autoclass('android.provider.MediaStore')
    FileOutputStream = autoclass('java.io.FileOutputStream')
    Format = autoclass('android.graphics.Bitmap$CompressFormat')
    request_code = 0x6A42
    Path(destination).parent.mkdir(parents=True, exist_ok=True)

    def on_result(req, result, intent):
        if req != request_code:
            return
        activity.unbind(on_activity_result=on_result)
        stored = ''
        try:
            if result == JavaActivity.RESULT_OK and intent is not None:
                bundle = intent.getExtras()
                bitmap = bundle.get('data') if bundle is not None else None
                if bitmap is not None:
                    stream = FileOutputStream(str(destination))
                    try:
                        if bitmap.compress(Format.JPEG, 88, stream):
                            stream.flush()
                            stored = str(destination)
                    finally:
                        stream.close()
        except Exception:
            stored = ''
        Clock.schedule_once(lambda _: callback(stored), 0)

    activity.bind(on_activity_result=on_result)
    try:
        intent = Intent(MediaStore.ACTION_IMAGE_CAPTURE)
        PythonActivity.mActivity.startActivityForResult(intent, request_code)
    except Exception:
        activity.unbind(on_activity_result=on_result)
        raise
