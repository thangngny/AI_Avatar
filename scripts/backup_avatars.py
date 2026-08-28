#!/usr/bin/env python3
"""Prepared-Avatar file backup + strong-checksum manifest (V1.4.1 §5-6).

Copies prepared avatar folders (structure + metadata + images + mask + coords +
latents) to a destination and writes a per-file SHA-256 manifest so a receiving
engineer can verify completeness/corruption. Excludes temp/render/cache.

Usage:
    python scripts/backup_avatars.py --avatars doTrang_closeup,mc_hamai_mid --dest <DIR>
    python scripts/backup_avatars.py --all --dest <DIR>
    python scripts/backup_avatars.py --manifest-only --dest <DIR>   # no copy
"""
import os, sys, hashlib, json, shutil, time
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from studio import config

def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()

def manifest_avatar(aid, src_root):
    """Return list of {relpath, size, sha256} for every file under src_root/<aid>."""
    base = os.path.join(src_root, aid)
    out = []
    if not os.path.isdir(base):
        return out, False
    for dirpath, dirs, files in os.walk(base):
        for fn in files:
            fp = os.path.join(dirpath, fn)
            rel = os.path.relpath(fp, src_root).replace("\\", "/")
            try:
                out.append({"relpath": rel, "size": os.path.getsize(fp), "sha256": sha256_file(fp)})
            except OSError as e:
                out.append({"relpath": rel, "size": 0, "sha256": "", "error": str(e)})
    return out, True

def main():
    args = sys.argv[1:]
    if "--all" in args:
        aids = [d for d in os.listdir(config.AVATARS_ROOT)
                if os.path.isdir(os.path.join(config.AVATARS_ROOT, d)) and not d.startswith(".")]
    else:
        for i, a in enumerate(args):
            if a == "--avatars" and i+1 < len(args):
                aids = [x.strip() for x in args[i+1].split(",") if x.strip()]
                break
        else:
            print("Usage: --avatars id1,id2 | --all  --dest DIR [--manifest-only]")
            sys.exit(2)
    dest = None
    for i, a in enumerate(args):
        if a == "--dest" and i+1 < len(args):
            dest = args[i+1]; break
    if not dest:
        dest = r"D:\CongThang_AI_Avatar\backup_avatars"
    manifest_only = "--manifest-only" in args
    os.makedirs(dest, exist_ok=True)

    manifest = {"generated": time.strftime("%Y-%m-%d %H:%M"), "source": config.AVATARS_ROOT,
                "dest": dest, "manifest_only": manifest_only, "avatars": []}
    for aid in aids:
        files, exists = manifest_avatar(aid, config.AVATARS_ROOT)
        entry = {"avatar_id": aid, "exists": exists, "file_count": len(files),
                 "total_bytes": sum(f["size"] for f in files), "files": files}
        if exists and not manifest_only:
            dst = os.path.join(dest, aid)
            if os.path.exists(dst):
                shutil.rmtree(dst, ignore_errors=True)
            shutil.copytree(os.path.join(config.AVATARS_ROOT, aid), dst)
            print(f"  copied {aid}: {entry['file_count']} files, {entry['total_bytes']/1e6:.1f} MB")
        else:
            print(f"  manifest {aid}: {entry['file_count']} files, {entry['total_bytes']/1e6:.1f} MB")
        manifest["avatars"].append(entry)

    mp = os.path.join(dest, "avatar_manifest.json")
    json.dump(manifest, open(mp, "w", encoding="utf-8"), indent=2)
    print(f"\nManifest -> {mp}")
    print(f"Avatars: {len(aids)} | Total: {sum(a['total_bytes'] for a in manifest['avatars'])/1e9:.2f} GB")

if __name__ == "__main__":
    main()