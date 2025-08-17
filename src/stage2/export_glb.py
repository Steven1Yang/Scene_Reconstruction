import bpy

def export_glb(mesh_name, output_path):
    bpy.ops.object.select_all(action='DESELECT')
    for obj in bpy.context.scene.objects:
        if obj.type == 'MESH' and obj.name == mesh_name:
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            bpy.ops.export_scene.gltf(
                filepath=output_path,
                export_format='GLB',
                export_materials='NONE',
                use_selection=True
            )