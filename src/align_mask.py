import json
import os
import subprocess
import sys
import argparse
import bpy
import pickle
from datetime import datetime
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)
from stage2 import (
    export_glb,
    align_road,
    smooth_sampled_points,
    create_masks,
    cut_selected_mesh_xz
)

if __name__ == "__main__":
    if "--" not in sys.argv:
        pass
    else:
        sys.argv = [""] + sys.argv[sys.argv.index("--") + 1:]
    parser = argparse.ArgumentParser(description="Align and create masks for scene reconstruction")
    parser.add_argument("--input_blender_path", type=str, required=True, help="Path to the input .glb file")
    parser.add_argument("--mask_output_path", type=str, required=True, help="Path to save the mask output")
    parser.add_argument("--glb_output_path", type=str, required=True, help="Path to save the aligned .glb file")
    parser.add_argument("--lat", type=float, required=True, help="Latitude of the location")
    parser.add_argument("--lng", type=float, required=True, help="Longitude of the location")
    parser.add_argument("--rad", type=float, required=True, help="Radius around the location")
    parser.add_argument("--ref_ground_output_path", type=str, required=True, help="Pathto save the reference ground output")
    args = parser.parse_args()  
    bpy.ops.wm.open_mainfile(filepath=args.input_blender_path)
    meshes_dir = os.path.dirname(args.glb_output_path)
    if not os.path.exists(os.path.join(meshes_dir, "aligned.glb")):
        print("Start cutting the aligned glb...")
        cut_selected_mesh_xz(-400, 400, -400, 400,mesh_name="Mesh_0")
        export_glb(mesh_name="Mesh_0",output_path=os.path.join(meshes_dir, "aligned.glb"))
    print("Start aligning and creating masks...")
    all_valid_points, all_ground_points, ground_polygons = align_road(
            input_glb_path=os.path.join(meshes_dir, "aligned.glb"),
            lat=args.lat, lng=args.lng, rad=args.rad,
        )
    print("Start smoothing points and creating masks...")
    road_info_dict, street_view_loc_clean_smooth, street_view_loc_clean_all, ground_info_dict = smooth_sampled_points(
            all_road_data=all_valid_points,
            all_ground_data=all_ground_points,
            ground_polygons=ground_polygons,
        )
    pickle.dump(street_view_loc_clean_all, open(args.ref_ground_output_path, "wb"))
    create_masks(
            reference_points=street_view_loc_clean_all,
            road_type_list=road_info_dict,
            ground_info=ground_info_dict,
            output_path=args.mask_output_path,
        )
    print("All done. The masked blend file is saved at:", args.mask_output_path)