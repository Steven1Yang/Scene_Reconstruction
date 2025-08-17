import bpy
import sys
import os
import argparse
import mathutils
import math

def import_glb_files(input_dir):
    """
    导入所有 .glb 文件到场景
    """
    glb_files = [f for f in os.listdir(input_dir) if f.lower().endswith('.glb')]
    imported_objects = []
    for glb_file in glb_files:
        file_path = os.path.join(input_dir, glb_file)
        bpy.ops.import_scene.gltf(filepath=file_path)
        # 获取新导入的对象
        for obj in bpy.context.selected_objects:
            if obj.type == 'MESH':
                imported_objects.append(obj)
    return imported_objects

def merge_mesh_objects(mesh_objects):
    """
    合并所有网格对象为一个
    """
    if not mesh_objects:
        print("没有找到任何网格对象。")
        return None
    # 取消所有选择
    bpy.ops.object.select_all(action='DESELECT')
    # 选择所有要合并的对象
    for obj in mesh_objects:
        obj.select_set(True)
    # 设置活动对象为第一个
    bpy.context.view_layer.objects.active = mesh_objects[0]
    # 合并
    bpy.ops.object.join()
    return bpy.context.view_layer.objects.active
def is_empty_object(obj):
    """
    递归判断一个对象是否是“空节点”：
    - 非 mesh
    - 所有子对象也都是空节点
    """
    if obj.type == 'MESH':
        return False
    # 如果没有子对象，则是空节点
    if not obj.children:
        return True
    # 递归检查所有子对象
    for child in obj.children:
        if not is_empty_object(child):
            return False
    return True

def cleanup_scene():
    """
    递归遍历并删除所有空节点，只保留 mesh 对象，直到场景树中没有可删对象。
    并在提取 mesh 时，将其世界位移集成到自身，保持场景位置不变。
    """
    for obj in bpy.context.scene.objects:
        if obj.type == 'MESH' and obj.parent is not None:
            # 记录 mesh 的世界变换
            mw = obj.matrix_world.copy()
            # 解除父子关系
            obj.parent = None
            # 恢复世界变换（包括位置、旋转、缩放）
            obj.matrix_world = mw
    bpy.ops.object.select_all(action='DESELECT')
    for obj in bpy.context.scene.objects:
        if obj.type == 'MESH':
            obj.select_set(True)
    bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)
    bpy.ops.object.select_all(action='DESELECT')
    while True:
        bpy.ops.object.select_all(action='DESELECT')
        to_delete = [obj for obj in bpy.context.scene.objects if is_empty_object(obj)]
        for obj in to_delete:
            obj.select_set(True)
        if to_delete:
            bpy.ops.object.delete()
            print(f"已递归删除 {len(to_delete)} 个空节点。")
        else:
            break
    # 提取mesh并集成父节点的世界平移
    print("递归删除完成，只保留 mesh 对象，并集成父节点平移。")

def main():
    if "--" not in sys.argv:
        pass
    else:
        sys.argv = [""] + sys.argv[sys.argv.index("--") + 1:]

    parser = argparse.ArgumentParser(description="Merge all .glb files in a directory into one .blend file using Blender")
    parser.add_argument('--input_dir', required=True, help='Directory containing all .glb files to merge')
    parser.add_argument('--output_file', required=True, help='Path to save the output .blend file')
    args = parser.parse_args()

    input_dir = args.input_dir
    output_file = args.output_file

    # 清空场景
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)

    print(f"导入 {input_dir} 目录下的所有 .glb 文件并合并...")
    mesh_objects = import_glb_files(input_dir)
    merged_obj = merge_mesh_objects(mesh_objects)

    cleanup_scene()

    # 遍历所有 mesh 对象
    for obj in bpy.data.objects:
        if obj.type == 'MESH':
            # 进入对象数据模式，处理网格数据
            mesh = obj.data
            for v in mesh.vertices:
                x, y, z = v.co
                v.co = mathutils.Vector((x, z, -y))  # 重新映射坐标轴

            # 重置 rotation_euler 为原来的 -90 度（保留你的原始旋转）
            obj.rotation_euler = (math.radians(-90), 0, 0)
    if merged_obj:
        print(f"成功合并为对象: {merged_obj.name}")
        # 只保存合并后的对象
        bpy.ops.object.select_all(action='DESELECT')
        merged_obj.select_set(True)
        bpy.context.view_layer.objects.active = merged_obj
        # 保存为 .blend 文件
        bpy.ops.wm.save_as_mainfile(filepath=output_file)
        print(f"已保存为 {output_file}")
    else:
        print("无对象可保存。")

if __name__ == "__main__":
    main()