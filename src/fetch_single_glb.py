import os
import json
import shutil
import argparse

def find_deepest_glb_boxes_in_file(json_path, output_dir):
    results = []
    base_dir = os.path.dirname(json_path)

    with open(json_path, 'r') as f:
        data = json.load(f)

    def recurse_node(node):
        children = node.get("children", [])
        content = node.get("content", {})
        uri = content.get("uri", "")

        if uri.lower().endswith(".glb") and not children:
            box = node.get("boundingVolume", {}).get("box")
            if box:
                glb_path = os.path.normpath(os.path.join(base_dir, uri))
                results.append((glb_path, box))
                print(f"找到最深层 GLB: {uri}")
                # 复制文件到目标文件夹
                if os.path.isfile(glb_path):
                    shutil.copy2(glb_path, os.path.join(output_dir, os.path.basename(glb_path)))
                    print(f"已提取到: {output_dir}")
                else:
                    print(f"文件不存在: {glb_path}")
        else:
            for child in children:
                child_content = child.get("content", {})
                child_uri = child_content.get("uri", "")
                if child_uri.lower().endswith(".json"):
                    child_json_path = os.path.normpath(os.path.join(base_dir, child_uri))
                    results.extend(find_deepest_glb_boxes_in_file(child_json_path, output_dir))
                else:
                    recurse_node(child)

    recurse_node(data["root"])
    return results

def main():
    parser = argparse.ArgumentParser(description="Extract deepest .glb files from Cesium 3D Tiles tileset.json")
    parser.add_argument("--tileset", "-t", required=True, help="Path to the top-level tileset.json file")
    parser.add_argument("--outdir", "-o", required=True, help="Directory to copy extracted .glb files")
    parser.add_argument("--tag", "-g", required=True, help="Tag the output with 'Done' in tag.txt")
    args = parser.parse_args()

    top_tileset_path = args.tileset
    output_dir = args.outdir
    tag_path = args.tag
    os.makedirs(output_dir, exist_ok=True)

    deepest_glbs = find_deepest_glb_boxes_in_file(top_tileset_path, output_dir)
    print(f"找到 {len(deepest_glbs)} 个最深层 .glb 文件并已提取到 {output_dir}")
    os.makedirs(os.path.dirname(tag_path), exist_ok=True)
    with open(tag_path, "w", encoding="utf-8") as f:
        f.write("Done\n")
    print(f"已在 {tag_path} 中标记完成状态。")
if __name__ == "__main__":
    main()