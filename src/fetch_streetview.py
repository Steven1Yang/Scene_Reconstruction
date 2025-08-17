import re
import os
import csv
import time
import glob
import random
import requests
from stage7 import transform          # 你已有的坐标转换模块
from PIL import Image
import argparse

# ———————————————————— 通用工具 ———————————————————— #
def write_csv(filepath, data, head=None):
    """保存 CSV；支持追加表头"""
    if head:
        data = [head] + data
    with open(filepath, "w", encoding="utf-8-sig", newline="") as f:
        csv.writer(f).writerows(data)


def read_csv(filepath):
    """按行读取 CSV → list[list[str]]"""
    if not os.path.exists(filepath):
        print(f"文件路径错误: {filepath}")
        return []
    with open(filepath, "r", encoding="utf-8") as f:
        return list(csv.reader(f))


def get_headers():
    """随机 UA + Referer"""
    ua_pool = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
        "Mozilla/5.0 (Linux; Android 12; SM-G9910) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36"
    ]
    return {
        "User-Agent": random.choice(ua_pool),
        "Connection": "close",
        "Referer": "https://map.baidu.com/"
    }


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


# ———————————————————— 百度接口包装 ———————————————————— #
def open_url(url):
    content, status, reason = safe_get(url)
    if content is None:
        print(f"open_url 失败 [{status} {reason}] → {url}")
    return content, status, reason


def grab_img_baidu(url):
    """下载单张街景视图；返回 (bytes or None, status, reason)"""
    return safe_get(url, need_image=True)


def get_panoid(bdmc_x, bdmc_y):
    """根据百度墨卡托坐标查询 panoid"""
    url = (f"https://mapsv0.bdimg.com/?qt=qsdata&x={bdmc_x}&y={bdmc_y}"
           f"&l=17.031000000000002&action=0&t={int(time.time()*1000)}")
    resp, status, reason = open_url(url)
    if resp is None:
        return None

    try:
        pano_ids = re.findall(r'"id":"(.+?)",', resp.decode("utf-8"))
        return pano_ids[0] if pano_ids else None
    except Exception as e:
        print(f"SVID 解析错误: {e}")
        return None


def wgs2bd09mc(wgs_x, wgs_y):
    """WGS‑84 → BD09MC"""
    try:
        bd09ll = transform.wgs84_to_bd09(wgs_x, wgs_y)
        bd09mc = transform.bd09ll_to_bd09mc(*bd09ll)
        return bd09mc
    except Exception as e:
        print(f"坐标转换错误: {e}")
        return None, None


# ———————————————————— 主流程 ———————————————————— #
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch Baidu Street View Panoramas")
    parser.add_argument("--input_csv", type=str, required=True, help="Input CSV file with coordinates and headings")
    parser.add_argument("--output_dir", type=str, required=True, help="Directory to save downloaded images")
    parser.add_argument("--error_log", type=str, default="error_log.csv", help="CSV file to log errors")
    parser.add_argument("--tag_path", type=str, default="pano_download_tag.txt", help="Path to tag file for download completion")
    args = parser.parse_args()
    # ★★★ 自行修改以下 3 行路径 ★★★
    read_fn = args.input_csv
    save_dir = args.output_dir
    error_fn = args.error_log

    # read_fn  = "/data/yangjingqing/baidu_fetching/dir/point.csv"
    # save_dir = "/data/yangjingqing/baidu_fetching/dir/images"
    # error_fn = "/data/yangjingqing/baidu_fetching/dir/eroor_info.csv"

    os.makedirs(save_dir, exist_ok=True)

    # 已有文件列表，避免重复
    finished = {os.path.basename(p) for p in glob.glob(os.path.join(save_dir, "*.png"))}

    table = read_csv(read_fn)
    if not table:
        raise SystemExit("CSV 为空或读取失败，程序退出")

    header, rows = table[0], table[1:]
    err_log = []

    for idx, row in enumerate(rows, 1):
        try:
            print(f"\n处理 {idx}/{len(rows)} …")
            idd, wgs_x, wgs_y = row[2], float(row[4]), float(row[3])
            headings = [row[5]]                 # 单个朝向
            pitch = "0"

            # 坐标转换
            bdmc_x, bdmc_y = wgs2bd09mc(wgs_x, wgs_y)
            if bdmc_x is None:
                continue

            # 是否已抓完
            if all(f"{idd}_{wgs_x}_{wgs_y}_{h}_{pitch}.png" in finished for h in headings):
                print("该点四个方向均已存在，跳过")
                continue

            # 获取 Panoid
            panoid = get_panoid(bdmc_x, bdmc_y)
            if panoid is None:
                print("未获取到 SVID，跳过")
                continue
            print(f"SVID: {panoid}")

            # 下载四张视图
            for h in headings:
                fname = f"{idd}_{h}_{wgs_x}_{wgs_y}.png"
                if fname in finished:
                    print(f"{fname} 已存在，跳过")
                    continue

                url = (f"https://mapsv0.bdimg.com/?qt=pr3d&fovy=90&quality=100"
                       f"&panoid={panoid}&heading={h}&pitch=8&width=1024&height=800")
                print(f"下载 {fname}")
                data, status, reason = grab_img_baidu(url)

                if data:
                    with open(os.path.join(save_dir, fname), "wb") as f:
                        f.write(data)
                    finished.add(fname)
                else:
                    msg = f"下载失败 [{status} {reason}]"
                    print(msg)
                    err_log.append([idd, wgs_x, wgs_y, h, msg])

            time.sleep(6)     # 友好延时

        except Exception as e:
            msg = f"整体处理错误: {e}"
            print(msg)
            err_log.append([idd, wgs_x, wgs_y, "‑", msg])

    # 写错误日志
    if err_log:
        write_csv(error_fn, err_log, ["idd", "wgs_x", "wgs_y", "heading", "error"])
        print(f"\n⚠ 已记录 {len(err_log)} 条错误 → {error_fn}")
    else:
        print("\n全部下载成功，无错误记录")

    print("\n程序执行完毕")
    os.makedirs(os.path.dirname(args.tag_path), exist_ok=True)
    with open(args.tag_path, "w", encoding="utf-8") as f:
        f.write("Done\n")
