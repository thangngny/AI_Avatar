"""AI Avatar Studio — operator UI/controller for the validated MuseTalk v1.5
production pipeline.

This package is a CONTROLLER, not a second rendering system. It never imports
torch or MuseTalk; it drives the existing production entrypoints as
subprocesses:

  * tools/avatar_source_quality/validator.py  (avatar source quality gate)
  * avatars/musetalk/genavatar.py              (avatar preparation, v15)
  * generate_video_from_script.py             (production renderer)

The locked lip-sync truth lives ONLY in config/render_truth.json and is read
read-only. The controller has NO independent lip-sync truth and exposes NO
editable gain/ctx/offset/fps/resolution controls.
"""
__version__ = "1.0.0"