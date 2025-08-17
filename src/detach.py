import os
import shutil
import argparse
import sys

if __name__ == "__main__":
    if "--" not in sys.argv:
        pass
    else:
        sys.argv = [""] + sys.argv[sys.argv.index("--") + 1:]
    parser = argparse.ArgumentParser("Detach streetview images into folders", add_help=True)
    parser.add_argument("--input_dir", type=str, required=True, help="Directory with original images") 
    parser.add_argument("--output_dir", type=str, required=True, help="Directory to save detached images")
    parser.add_argument("--tag_path", type=str, required=True, help="Path to tag file for completion")
    args = parser.parse_args()  

    input_dir = args.input_dir
    output_dir = args.output_dir
    tag_path = args.tag_path

    os.makedirs(output_dir, exist_ok=True)

    for fname in os.listdir(input_dir):
        if not fname.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.gif')):
            continue
    # 拆分文件名
    # 假设文件名格式为：panoid_heading_lng_lat.jpg
        name, ext = os.path.splitext(fname)
        parts = name.split('_')
        if len(parts) < 4:
            print(f"文件名格式异常: {fname}")
            continue
        panoid = parts[0]
        heading = parts[1]
    # 新文件夹和文件名
        panoid_dir = os.path.join(output_dir, panoid)
        os.makedirs(panoid_dir, exist_ok=True)
        new_fname = f"heading_{heading}{ext}"
        src_path = os.path.join(input_dir, fname)
        dst_path = os.path.join(panoid_dir, new_fname)
        shutil.copy2(src_path, dst_path)
        print(f"已复制: {src_path} -> {dst_path}")

    os.makedirs(os.path.dirname(tag_path), exist_ok=True)
    with open(tag_path, "w", encoding="utf-8") as f:
        f.write("Done\n")