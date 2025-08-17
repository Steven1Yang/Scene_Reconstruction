import trimesh
import numpy as np
import math
import csv
import re
import os
import time
import glob
import random
import requests
import sys
sys.path.append(os.path.dirname(__file__))
from stage7 import transform        # 你已有的坐标转换模块
from PIL import Image
import argparse
import pickle
from tqdm import tqdm

# ------------------------mesh范围转换到经纬度----------------------------- #
def xyz_to_latlng(x, z, origin_lat, origin_lng, radius=6371000):
    lat = origin_lat - math.degrees(z / radius)
    lng = origin_lng + math.degrees(x / (radius * math.cos(math.radians(origin_lat))))
    return lng, lat
# --------------------------对经纬度均匀采样------------------------------- #
def uniform_sample_points(x_min, x_max, y_min, y_max, num_points=50):
    """在指定范围内均匀采样点，返回(lng, lat)列表"""
    long_range = np.linspace(x_min, x_max, num_points)
    lat_range = np.linspace(y_min, y_max, num_points)
    coords = [(lng, lat) for lng in long_range for lat in lat_range]    
    return coords
# --------------------------导出有效经纬度到CSV----------------------------- #
def sample_and_export_streetview_points(x_min, x_max, y_min, y_max, num_points, output_csv, has_street_view):
    """
    均匀采样经纬度点，判断每个点是否有街景，有则写入CSV，无则打印提示
    """
    coords = uniform_sample_points(x_min, x_max, y_min, y_max, num_points)
    headings = [0, 45, 90, 135, 180, 225, 270, 315]  # 采样方向
    with open(output_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["OBJECTID", "longitude", "latitude", "panoid","heading"])
        idx = 0
        for lng, lat in coords:
            for heading in headings:
                panoids = has_view(lng, lat, heading)
                if panoids:
                    for panoid in panoids:
                        print("该点有效:", (lng, lat, heading, panoid))
                        writer.writerow([idx, lng, lat, panoid, heading])
                        idx += 1
                else:
                    print(f"这个坐标点{(lng, lat)}在方向{heading}°不含街景")

# ---------------------基础函数--------------------- #
def has_view(lng, lat, heading):
    # 坐标转换
    bdmc_x, bdmc_y = wgs2bd09mc(lng, lat)
    url = (f"https://mapsv0.bdimg.com/?qt=qsdata&x={bdmc_x}&y={bdmc_y}"
           f"&l=17.031000000000002&action=0&t={int(time.time()*1000)}&heading={heading}")
    resp, status, reason = open_url(url)
    if resp is None:
        return None

    try:
        pano_ids = re.findall(r'"id":"(.+?)",', resp.decode("utf-8"))
        return pano_ids if pano_ids else None
    except Exception as e:
        print(f"SVID 解析错误: {e}")
        return None

def safe_get(url, need_image=False, timeout=10):
    """
    统一 GET：返回 (content or None, status_code, reason)
    need_image=True 时同时检查 Content‑Type 是否包含 image
    """
    try:
        r = requests.get(url, headers=get_headers(), timeout=timeout)
        ok = r.status_code == 200 and (not need_image or "image" in r.headers.get("Content-Type", ""))
        return (r.content if ok else None, r.status_code, r.reason)
    except requests.RequestException as e:
        return None, 0, str(e)

# ---------------------百度接口函数--------------------- #
def open_url(url):
    content, status, reason = safe_get(url)
    if content is None:
        print(f"open_url 失败 [{status} {reason}] → {url}")
    return content, status, reason

def wgs2bd09mc(wgs_x, wgs_y):
    """WGS‑84 → BD09MC"""
    try:
        bd09ll = transform.wgs84_to_bd09(wgs_x, wgs_y)
        bd09mc = transform.bd09ll_to_bd09mc(*bd09ll)
        return bd09mc
    except Exception as e:
        print(f"坐标转换错误: {e}")
        return None, None

def get_headers():
    """随机 UA + Referer"""
    ua_pool = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/cd5.1.15",
        "Mozilla/5.0 (Linux; Android 12; SM-G9910) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36"
    ]
    return {
        "User-Agent": random.choice(ua_pool),
        "Connection": "close",
        "Referer": "https://map.baidu.com/"
    }
# 对齐操作
def get_street_view_meta_data(output_csv):
    """
    获取街景元数据，返回一个字典，包含经纬度、朝向等信息
    """
    meta_data_list = []
    with open(output_csv, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            if len(row) < 3:
                continue
            lat = float(row[2])
            lng = float(row[1])
            panoid = row[3]
            heading = row[4]
            meta_data_list.append([lat, lng, panoid, heading])
    if len(meta_data_list) == 0:
        print("没有有效的街景元数据")
        assert False 
    return meta_data_list

def find_mesh_upper_bound_y(input_mesh, x, y):
    """
    Find the y-axis upper bound of a mesh at a given x, z coordinate.

    Parameters:
    - mesh (trimesh.Trimesh): The mesh to query.
    - x (float): The x coordinate.
    - z (float): The z coordinate.

    Returns:
    - float or None: The upper bound on the y-axis if an upper bound is found, otherwise None.
    """
    ray_origins = np.array([[x, y, input_mesh.bounds[1][2] + 1]])
    ray_directions = np.array([[0, 0, -1]])

    locations, index_ray, index_tri = input_mesh.ray.intersects_location(
        ray_origins=ray_origins,
        ray_directions=ray_directions
    )

    if len(locations) > 0:
        z_upbound = np.max(locations[:, 2])
        return z_upbound, True
    else:
        return 0, False    

def lat_lng_to_xy_matrix(lat0, lng0):
    R = 6371.0 * 1000

    delta_lat = 1.0
    delta_lat_km = (np.pi / 180) * R * delta_lat

    delta_lng = 1.0
    delta_lng_km = (np.pi / 180) * R * np.cos(np.radians(lat0)) * delta_lng

    conversion_matrix = np.array([[0, -delta_lat_km],
                                  [delta_lng_km, 0]])

    return conversion_matrix

def find_pos(lat_lng_list, original_lat, original_lng, input_mesh, output_path):
    """
    Input
        lat_lng_list: latitude, longitude of street views
        pca_lat_lng_diff: top-2 3d tiles pca vectors in LLA coordinates
        pca_xyz_diff: top-2 3d tiles pca vectors in final xyz coordinates
        original_lat: latitude of 3d tiles center
        original_lng: longitude of 3d tiles center
        mesh: input mesh
        output_streeview_glb_dir: output glb of street view (use small spheres to represent them)
        car_height: height of Google street view car
    """
    transform_matrix = lat_lng_to_xy_matrix(original_lat, original_lng)
    street_view_locs = {}
    for lat_lng in tqdm(lat_lng_list):
        lat, lng, pano_id, heading = lat_lng
        x_trans, y_trans = np.dot(np.array([lat - original_lat, lng - original_lng]), transform_matrix)
        z_trans, find = find_mesh_upper_bound_y(input_mesh, x_trans, y_trans)
        if find:
            street_view_locs[pano_id] = [x_trans, -z_trans, y_trans, lat, lng]
    pickle.dump(street_view_locs, open(output_path, "wb"))




if __name__ == "__main__":
    if "--" not in sys.argv:
        pass
    else:
        sys.argv = [""] + sys.argv[sys.argv.index("--") + 1:]
    parser = argparse.ArgumentParser("Sample and export streetview meta data", add_help=True)
    parser.add_argument("--work_dir", type=str, required=True, help="Path to the input mesh folder")
    parser.add_argument("--output_csv", type=str, required=True, help="Path to the output CSV file") 
    parser.add_argument("--output_pkl", type=str, required=True, help="Path to the output pickle file for street view locations")
    parser.add_argument("--lat", type=float, required=True, help="Origin latitude for coordinate conversion")
    parser.add_argument("--lng", type=float, required=True, help="Origin longitude for coordinate conversion")
    parser.add_argument("--num_points", type=float, default=50, help="Number of points to sample along each axis")
    args = parser.parse_args()
    # fetch strret view meta data
    origin_lng, origin_lat = args.lng,args.lat
    output_csv = args.output_csv
    input_glb = os.path.join(args.work_dir, "aligned.glb")
    tmesh = trimesh.load_mesh(input_glb)
    if not os.path.exists(output_csv):
        print("csv is not exist, will sample street view meta data")
        bounds_west_min = tmesh.bounds[0][0]
        bounds_west_max = tmesh.bounds[1][0]
        bounds_north_min = tmesh.bounds[1][2]
        bounds_north_max = tmesh.bounds[0][2]
        west,south = xyz_to_latlng(bounds_west_min, bounds_north_min, origin_lat, origin_lng)
        east,north = xyz_to_latlng(bounds_west_max, bounds_north_max, origin_lat, origin_lng)
        print(f"Mesh bounds: west=({west}, {south}), east=({east}, {north})")
        num_points = args.num_points  # 采样点数量
        sample_and_export_streetview_points(west, east, south, north, num_points, output_csv, has_view)
        print(f"有效街景经纬度已导出到 {output_csv}")

    # align street view meta data
    street_view_list = get_street_view_meta_data(output_csv)
    find_pos(lat_lng_list=street_view_list, original_lat=origin_lat, original_lng=origin_lng, input_mesh=tmesh,
             output_path=args.output_pkl)
