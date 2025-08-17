import bpy
import bmesh

def cut_selected_mesh_xz(x_min, x_max, z_min, z_max, mesh_name=None):
    # 如果有名字，主动选中
    if mesh_name:
        obj = bpy.data.objects.get(mesh_name)
        if obj is None or obj.type != 'MESH':
            raise Exception(f"找不到名为 '{mesh_name}' 的 mesh 对象！")
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
    else:
        obj = bpy.context.active_object
        if obj is None or obj.type != 'MESH':
            raise Exception("请选中一个 mesh 对象！")
    
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    bpy.ops.mesh.select_all(action='DESELECT')
    for v in bm.verts:
        world_coord = obj.matrix_world @ v.co
        if world_coord.x < x_min or world_coord.x > x_max or world_coord.z < z_min or world_coord.z > z_max:
            v.select = True
    bmesh.update_edit_mesh(obj.data)
    bpy.ops.mesh.delete(type='VERT')
    bpy.ops.object.mode_set(mode='OBJECT')
    print("已完成软裁边（顶点删除）！")

# 用法：
# cut_selected_mesh_xz(-400, 400, -400, 400, mesh_name='你的mesh名字')