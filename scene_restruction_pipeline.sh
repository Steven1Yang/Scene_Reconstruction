# Pineline for Scene Reconstruction
# This script orchestrates the scene reconstruction process by calling various components in sequence.
#!/bin/bash
# Last updated:2025.7.25
# Usage exemple: bash scene_restruction_pipeline.sh 

# Parameters for tmp storage
tmproot=""
# Parameters for stage output
dataroot=""
# Parameters for stage tag
tagroot=""
# Parameters for scene name
scene_name=""
# parameters check
while [[ $# -gt 0 ]]; do
    case "$1" in
        --tmproot)
            tmproot="$2"
            shift 2
            ;;
        --dataroot)
            dataroot="$2"
            shift 2
            ;;
        --tagroot)
            tagroot="$2"
            shift 2
            ;;
        --scene_name)
            scene_name="$2"
            shift 2
            ;;
        *)
            echo "Unknown parameter: $1"
            exit 1
            ;;
    esac
done

# Create directories if they do not exist
add_suffix_to_filename() {
  local path="$1"
  local suffix="$2"
  local directory
  local filename_without_ext
  local extension
  directory=$(dirname "$path")
  filename_without_ext=$(basename "$path" | cut -f 1 -d '.')
  extension=$(basename "$path" | grep -o "\.[^.]*$")
  echo "${directory}/${filename_without_ext}${suffix}${extension}"
}

# set color
write_color_output() {
  local color="$1"  # The color name passed as the first argument
  shift  # Remove the first argument to handle the rest as the output message
  local color_code  # Variable to store the ANSI escape sequence for the color

  # Map color names to ANSI escape sequences
  case $color in
    green) color_code="\e[32m" ;;   # Green for success
    red) color_code="\e[31m" ;;     # Red for failure
    yellow) color_code="\e[33m" ;;  # Yellow for warning
    blue) color_code="\e[34m" ;;    # Blue for info
    *) color_code="\e[0m" ;;        # Default (reset to no color)
  esac

  # Print the message with the selected color
  echo -e "${color_code}$*${RESET}"
}

# Executables
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
  blender="/data/yangjingqing/apps/blender-4.4.3-linux-x64/blender" # change this to your blender path
#   upscayl="upscayl-ncnn/build/upscayl-bin" 
  dst_path="/data/yangjingqing/temp/scene_reconstruction/final"
elif [[ "$OSTYPE" == "darwin"* ]]; then
  blender="/Applications/Blender.app/Contents/MacOS/Blender"
  upscayl="upscayl"
else
  blender="blender"
  upscayl="upscayl"
fi
# make dirs
for dir in ${dataroot} ${tmproot} ${tagroot} ${tmproot}/${scene_name} ${dataroot}/${scene_name} ${tagroot}/${scene_name}
do
  mkdir -p ${dir}
done

# Tags
single_tag="${tagroot}/${scene_name}/single_glb_done.txt"
pano_download_tag="${tagroot}/${scene_name}/pano_download_done.txt"
inpaint_done_tag="${tagroot}/${scene_name}/inpaint_done.txt"
detached_tag="${tagroot}/${scene_name}/detached_done.txt"
# INPUT
tileset_json="${tmproot}/${scene_name}/original_data/tileset.json"
osm_blender_file="${tmproot}/${scene_name}/osm_buildings/clean_osm.blend"
pano_file="${dataroot}/${scene_name}/streetview_locs.pkl"
solved_csv_file="${dataroot}/${scene_name}/streetview_solved.csv"
glb_file="${dataroot}/${scene_name}/${scene_name}.glb"
# OUTPUT
merged_blend="${dataroot}/${scene_name}/${scene_name}_merged.blend"
masked_blend="${dataroot}/${scene_name}/${scene_name}_masked.blend"
ref_ground_file="${dataroot}/${scene_name}/street_view_loc_clean_all.pkl"
terrain_blender_file="${dataroot}/${scene_name}/${scene_name}_terrain.blend"
height_field_file="${dataroot}/${scene_name}/${scene_name}_height_field.npz"
baked_terrain_file="${dataroot}/${scene_name}/${scene_name}_baked_terrain.blend"
baked_osm_file="${dataroot}/${scene_name}/${scene_name}_baked_osm.blend"
pano_file_meta_data="${dataroot}/${scene_name}/${scene_name}_pano_meta_data.csv"
with_camera_blender_file="${dataroot}/${scene_name}/${scene_name}_with_camera.blend"
solve_result_file="${dataroot}/${scene_name}/camera_solve_result.pkl"
images="${dataroot}/${scene_name}/streetview_images"
images_cleaned="${dataroot}/${scene_name}/streetview_images_cleaned"
down_load_error_log="${dataroot}/${scene_name}/streetview_error_log.csv"
inpainted_images="${dataroot}/${scene_name}/streetview_inpainted_images"
inpainted_terrain="${dataroot}/${scene_name}/inpainted_terrain.blend"
inpainted_buildings="${dataroot}/${scene_name}/inpainted_buildings.blend"
projected_file="${dataroot}/${scene_name}/${scene_name}_projected.blend"
combined_blender_file="${dataroot}/${scene_name}/${scene_name}_combined.blend"
aabb_file="${dataroot}/${scene_name}/building_to_osm_tags.json"

echo "dataroot=$dataroot"
echo "scene_name=$scene_name"
echo "tileset_json=$tileset_json"
# stage0:fetch single glb
if [[ ! -f "$single_tag" ]]; then
  python ./src/fetch_single_glb.py \
    --tileset ${tileset_json} \
    --outdir ${tmproot}/${scene_name}/extracted_single_glbs \
    --tag ${single_tag} 

  status=$?
  if [[ $status -eq 0 ]]; then
    write_color_output green "    [OK ] Fetching Single Done."
    # 继续后续流程...
  else
    write_color_output red "    [ERR] Fetching Single Failed, stopping."
    exit 1
  fi
else
  write_color_output blue "    [Ign] Fetching Single Skip."
fi

# stage1:merge glbs to one and align to center
if [[ ! -f "$merged_blend" ]]; then
  "$blender" -b --python ./src/merge.py -- \
    --input_dir ${tmproot}/${scene_name}/extracted_single_glbs \
    --output_file ${merged_blend}

  if [[ -f "$merged_blend" ]]; then
    write_color_output green "    [OK ] Merging Done." 
    # 继续后续流程...
  else
    write_color_output red "    [ERR] Merging Failed, stopping."
    exit 1
  fi
else
  write_color_output blue "    [Ign] Merging Skip."
fi

# stage2:align and create masks,里面的经纬度参数后续需要变成自动化操作
if [[ ! -f "$masked_blend" ]]; then
  "$blender" -b --python ./src/align_mask.py -- \
    --input_blender_path ${merged_blend} \
    --mask_output_path ${masked_blend} \
    --glb_output_path ${tmproot}/${scene_name} \
    --lat 39.894954 \
    --lng 116.313162 \
    --rad 400\
    --ref_ground_output_path ${ref_ground_file}
  if [[ -f "$masked_blend" ]]; then
    write_color_output green "    [OK ] Mask Done." 
    # 继续后续流程...
  else
    write_color_output red "    [ERR] Mask Failed, stopping."
    exit 1
  fi
else
  write_color_output blue "    [Ign] Mask Skip."
fi

# stage3:build terrain
if [[ ! -f "$terrain_blender_file" ]]; then
  "$blender" -b --python ./src/export_terrain.py -- \
    --rad "400" \
    --ground_points_ref "$ref_ground_file" \
    --save_dir "$terrain_blender_file"
  if [[ -f "$terrain_blender_file" ]]; then
    write_color_output green "    [OK ] Build Terrain Done."
  else
    write_color_output red "    [ERR] Build Terrain Failed, stopping."
    exit 1
  fi
else
  write_color_output blue "    [Ign] Build Terrain Skip."
fi

# stage4:export height field
if [[ ! -f "$height_field_file" ]]; then
  "$blender" -b --python ./src/export_height_field.py -- \
    --ground_points_ref "$ref_ground_file" \
    --save_dir "$height_field_file"
  if [[ -f "$height_field_file" ]]; then
    write_color_output green "    [OK ] Export Height Field Done."
  else
    write_color_output red "    [ERR] Export Height Field Failed, stopping."
    exit 1
  fi
else
  write_color_output blue "    [Ign] Export Height Field Skip."
fi

# stage5:bake terrain
if [[ ! -f "$baked_terrain_file" ]]; then
  "$blender" -b --python ./src/bake_terrain.py -- \
    --terrain_file "$terrain_blender_file" \
    --tile_file "$masked_blend" \
    --save_dir "$baked_terrain_file"
  if [[ -f "$baked_terrain_file" ]]; then
    write_color_output green "    [OK ] Bake Terrain Done."
  else
    write_color_output red "    [ERR] Bake Terrain Failed, stopping."
    exit 1
  fi
else
  write_color_output blue "    [Ign] Bake Terrain Skip."
fi

# stage6:bake OSM buildings
if [[ ! -f "$baked_osm_file" ]]; then
  "$blender" -b --python ./src/bake_osm.py -- \
    --osm_file "$osm_blender_file" \
    --terrain_file "$terrain_blender_file" \
    --tile_file "$merged_blend" \
    --save_dir "$baked_osm_file"
  if [[ -f "$baked_osm_file" ]]; then
    write_color_output green "    [OK ] Bake OSM Done."
  else
    write_color_output red "    [ERR] Bake OSM Failed, stopping."
    exit 1
  fi
else
  write_color_output blue "    [Ign] Bake OSM Skip."
fi

# stage7:fetch and align streetview meta data
if [[ ! -f "$pano_file_meta_data" || ! -f "$pano_file" ]]; then
  "$blender" -b --python ./src/fetch_pano_meta_data.py -- \
    --work_dir $tmproot \
    --output_csv $pano_file_meta_data \
    --output_pkl "$pano_file" \
    --lat 39.894954 \
    --lng 116.313162 
  if [[ -f "$pano_file_meta_data" && -f "$pano_file" ]]; then
    write_color_output green "    [OK ] Fetching StreetView Meta Done."
  else
    write_color_output red "    [ERR] Fetching StreetView Meta Failed, stopping."
    exit 1
  fi
else
  write_color_output blue "    [Ign] Fetching StreetView Meta Skip."
fi

# stage8:solve streetview cameras
if [[ ! -f "$with_camera_blender_file" ]]; then
  "$blender" -b --python ./src/solve_camera.py -- \
    --input_blend_path "$baked_osm_file" \
    --output_pkl "$pano_file" \
    --output_solve_result_path "$solve_result_file" \
    --output_blend_path "$with_camera_blender_file" \
    --solved_csv "$solved_csv_file"
  if [[ -f "$with_camera_blender_file" ]]; then
    write_color_output green "    [OK] Solve Done."
  else
    write_color_output red "    [ERR] Solve Failed, stopping."
    exit 1
  fi
else
  write_color_output blue "    [Ign] Skip street view solving."
fi

# stage9:fetch streetview
if [[ ! -f "$pano_download_tag" ]]; then
  python ./src/fetch_streetview.py \
    --input_csv "$solved_csv_file" \
    --output_dir "$images" \
    --error_log "$down_load_error_log" \
    --tag_path "$pano_download_tag" 
  if [[ -f "$pano_download_tag" ]]; then 
    write_color_output green "    [OK] Download Done."
  else
    write_color_output red "    [ERR] Download Failed, stopping."
    exit 1
  fi
else
  write_color_output blue "    [Ign] Skip street view downloading."
fi

if [[ ! -f "$detached_tag" ]]; then
  python ./src/detach.py \
    --input_dir "$images" \
    --output_dir "$images_cleaned" \
    --tag_path "$detached_tag"
  if [[ -f "$detached_tag" ]]; then 
    write_color_output green "    [OK] Detach Done."
  else
    write_color_output red "    [ERR] Detach, stopping."
    exit 1
  fi
else
  write_color_output blue "    [Ign] Skip detaching."
fi


# stage10:inpait streetview
if [[ ! -f "$inpaint_done_tag" ]]; then
PYTHONPATH=${PWD}/inpainting/Inpaint_Anything/:${PYTHONPATH} python inpainting/test_DINO_SAM_LaMa.py \
  --input_dir /data/yangjingqing/temp/scene_reconstruction/data/BEIJING/streetview_images_cleaned  \
  --output_dir /data/yangjingqing/temp/scene_reconstruction/data/BEIJING/streetview_inpainted_images   \
  --config /data/yangjingqing/virtual_community/Virtual-Community/ViCo/scene-generation/inpainting/GroundingDINO/groundingdino/config/GroundingDINO_SwinT_OGC.py  \
  --checkpoint /data/yangjingqing/virtual_community/Virtual-Community/ViCo/scene-generation/inpainting/checkpoints/groundingdino_swint_ogc.pth  \
  --box_threshold 0.3   \
  --text_threshold 0.25  \
  --sam_model_type vit_h \
  --sam_ckpt /data/yangjingqing/virtual_community/Virtual-Community/ViCo/scene-generation/inpainting/Inpaint_Anything/pretrained_models/sam_vit_h_4b8939.pth   \
  --lama_config /data/yangjingqing/virtual_community/Virtual-Community/ViCo/scene-generation/inpainting/Inpaint_Anything/lama/configs/prediction/default.yaml   \
  --lama_ckpt /data/yangjingqing/virtual_community/Virtual-Community/ViCo/scene-generation/inpainting/Inpaint_Anything/pretrained_models/big-lama
  echo "Done" > $inpaint_done_tag
  write_color_output green "    [OK ] Inpaint Street Views Done."
else
  write_color_output yellow "    [Ign] Skip inpainting street views."
fi

# stage11:project streetview to osm
if [[ ! -f "$projected_file" ]]; then
  "$blender" -b --python ./src/stage3c.py -- \
    --input_blend_path "$with_camera_blender_file" \
    --streetview_locs_path "$pano_file" \
    --input_gsv_dir "$inpainted_images" \
    --solve_result_path "$solve_result_file" \
    --cache_root "$tmproot"/${scene_name} \
    --blender_save_path "$projected_file" \
    --boundary_mask_dir "$tmproot/${scene_name}/boundary_mask"
  write_color_output green "    [OK ] Projection Done."
else
  write_color_output yellow "    [Ign] Skip gsv projection."
fi

# stage12:inpaint textures of buildings and terrain
if [[ ! -f "$inpainted_terrain" || ! -f "$inpainted_buildings" ]]; then
  write_color_output green "    Emitting Texture Maps..."
  ./inpainting/Emit.sh "$scene_name" "${blender[0]}" "$dataroot"

  if [[ ! -f "${tagroot}/${scene_name}/ground_inpaint_done.txt" ]]; then
    # Inpaint Terrain
    ./inpainting/Inpaint.sh \
      "${dataroot}/${scene_name}/textures_${scene_name}" \
      remove_black_batch.py \
      "${dataroot}/${scene_name}/textures_${scene_name}_ground_inpaint"
    echo "done" > "${tagroot}/${scene_name}/ground_inpaint_done.txt"
    write_color_output green "    [OK ] Ground inpaint Done."
  else
    write_color_output yellow "    [Ign] Skip ground inpaint."
  fi

  if [[ ! -f "${tagroot}/${scene_name}/building_inpaint_done.txt" ]]; then
    # Inpaint Building
    ./inpainting/Inpaint.sh \
      "${dataroot}/${scene_name}/textures_${scene_name}_building" \
      remove_black_batch_building.py \
      "${dataroot}/${scene_name}/textures_${scene_name}_building_inpaint"
    echo "done" > "${tagroot}/${scene_name}/building_inpaint_done.txt"
    write_color_output green "    [OK ] Building inpaint Done."
  else
    write_color_output yellow "    [Ign] Skip building inpaint."
  fi

  echo DEBUG $inpainted_terrain $inpainted_buildings
  # Rebundle Texture Maps
  "$blender" -b --python ./inpainting/ground_rebundle.py -- \
    --blender_file "$baked_terrain_file" \
    --mesh Terrain \
    --image_dir "${dataroot}/${scene_name}/textures_${scene_name}_ground_inpaint" \
    --save_to "$inpainted_terrain"

  "$blender" -b --python ./inpainting/building_rebundle.py -- \
    --blender_file "$projected_file" \
    --mesh Terrain \
    --image_dir "${dataroot}/${scene_name}/textures_${scene_name}_building_inpaint" \
    --save_to "$inpainted_buildings"
else
  write_color_output yellow "    [Ign] Skip texture inpainting."
fi

## Stage 13: Combine Building and Terrain
if [[ ! -f "$combined_blender_file" && -f "$inpainted_terrain" && -f "$inpainted_buildings" ]]; then
  "$blender" -b --python ./src/combine_terrain_buildings.py -- \
    --terrain_blender "$inpainted_terrain" \
    --building_blender "$inpainted_buildings" \
    --terrain_name "Terrain" \
    --save_to "$combined_blender_file" \
    --glb_to "$glb_file" \
    --roof_blender "$baked_osm_file" \
    --roof_name "Roof"
  write_color_output green "    [OK ] Building placement done."
elif [[ ! -f "$inpainted_terrain" || ! -f "$inpainted_buildings" ]]; then
  write_color_output magenta "    [WRN] Early stop pipeline since required file is not received yet."
  exit 1
else
  write_color_output yellow "    [Ign] Skip building placement."
fi

# Stage 14: Create building name <=> 3D AABB JSON
if [[ ! -f "$aabb_file" ]]; then
  "$blender" -b --python ./src/stage6.py -- \
    --building_file "$combined_blender_file" \
    --exclude_names "Roof" "Terrain" \
    --save_as "$aabb_file" \
    --circle "39.894954" "116.313162" "400"
  write_color_output green "    [OK ] Building meta & AABB generation done."
else
  write_color_output yellow "    [Ign] Skip generating metadata & AABB."
fi

# Stage 15: Converting emissive to basics
if [[ ! -f "${dataroot}/${scene_name}/roof_basic.glb" ]]; then
  "$blender" -b --python ./src/stage7.py -- \
    --input_dir ${dataroot}/${scene_name}
  write_color_output green "    [OK ] Converting emissive to basic done."
else
  write_color_output yellow "    [Ign] Skip converting emissive to basic."
fi

write_color_output green "Pipeline completed successfully!"