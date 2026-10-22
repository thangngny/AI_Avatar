import os

repo_dir = r"C:\Users\phuongpn\AI_Avatar_NextGen_V2\engines\soulx_flashhead"

# 1. Patch flash_head_model.py
model_file = os.path.join(repo_dir, "flash_head", "src", "modules", "flash_head_model.py")
with open(model_file, "r", encoding="utf-8") as f:
    content = f.read()

target = """from xfuser.core.distributed import (
    get_sequence_parallel_rank,
    get_sequence_parallel_world_size,
    get_sp_group,
)
from xfuser.core.long_ctx_attention import xFuserLongContextAttention"""

replacement = """try:
    from xfuser.core.distributed import (
        get_sequence_parallel_rank,
        get_sequence_parallel_world_size,
        get_sp_group,
    )
    from xfuser.core.long_ctx_attention import xFuserLongContextAttention
except ImportError:
    def get_sequence_parallel_rank(): return 0
    def get_sequence_parallel_world_size(): return 1
    def get_sp_group(): return None
    xFuserLongContextAttention = None"""

# normalize line endings
content = content.replace("\r\n", "\n")
target = target.replace("\r\n", "\n")
replacement = replacement.replace("\r\n", "\n")

if target in content:
    content = content.replace(target, replacement)
    with open(model_file, "w", encoding="utf-8") as f:
        f.write(content)
    print("Patched flash_head_model.py successfully!")
else:
    print("Target not found in flash_head_model.py")

# 2. Patch flash_head_pipeline.py (disable compile on Windows)
pipe_file = os.path.join(repo_dir, "flash_head", "src", "pipeline", "flash_head_pipeline.py")
with open(pipe_file, "r", encoding="utf-8") as f:
    pipe_content = f.read().replace("\r\n", "\n")

pipe_content = pipe_content.replace("COMPILE_MODEL = True", "COMPILE_MODEL = False")
pipe_content = pipe_content.replace("COMPILE_VAE = True", "COMPILE_VAE = False")
pipe_content = pipe_content.replace("USE_PARALLEL_VAE = True", "USE_PARALLEL_VAE = False")

with open(pipe_file, "w", encoding="utf-8") as f:
    f.write(pipe_content)
print("Patched flash_head_pipeline.py successfully!")
