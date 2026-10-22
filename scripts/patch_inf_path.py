import os

inf_file = r"C:\Users\phuongpn\AI_Avatar_NextGen_V2\engines\soulx_flashhead\flash_head\inference.py"
with open(inf_file, "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if 'with open("flash_head/configs/infer_params.yaml", "r") as f:' in line:
        new_lines.append('import os\n')
        new_lines.append('CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "configs", "infer_params.yaml")\n')
        new_lines.append('with open(CONFIG_PATH, "r") as f:\n')
    else:
        new_lines.append(line)

with open(inf_file, "w", encoding="utf-8") as f:
    f.writelines(new_lines)

print("Inference config path patched!")
