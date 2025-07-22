from google import genai
from google.genai import types
import os
import re
import json # json 파싱을 위해 추가
import base64
from datetime import datetime
from collections import defaultdict

# client = genai.Client(api_key="AIzaSyCvoifyvGiq17O4a7cqr7RSiyZEdyp-VCc")


def extract_front_info_gemini(api_key, image_path: str) -> str:
    client = genai.Client(api_key=api_key)
    with open(image_path, "rb") as f:
        image_bytes = f.read()

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
            (
                """
                Extract the date(YYYY-MM-DD HH:MM), and paid amount(integer, so called price) from this image. Return the data in a JSON format. The JSON should be in the following format: 
                '{"date": "2021-01-01 23:02", "price": "23000"}'
                """
            ),
        ],
    )
    raw = response.text.strip()
    # 코드블록 백틱이 있을 경우 제거
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.DOTALL).strip()
    front_info = json.loads(raw)   # {'date': '2024-07-25 14:05', 'price': '7,500원'}
    return front_info


def extract_back_info_gemini(api_key, image_path: str) -> str:
    client = genai.Client(api_key=api_key)
    with open(image_path, "rb") as f:
        image_bytes = f.read()

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
            (
                """
                Extract the employee (which means the name), route from this image. Return the data in a JSON format. 
                employee은 "최홍영", "박다혜", "박상현", "김민주", "최윤선", "김익현", "장수현", "이한울", "김호연", "박성진" 중 하나이다. 
                route는 출발지-도착지 형식으로 출력한다. 
                The JSON should be in the following format: 
                '{"employee": "김익현", "route": "회사-집"}'
                """
            ),
        ],
    )
    raw = response.text.strip()
    # 코드블록 백틱이 있을 경우 제거
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.DOTALL).strip()
    back_info = json.loads(raw)   # {'employee': '김익현', 'route': '회사-집'}
    return back_info



def process_receipts(api_key, image_files, output_text_folder, employee_names, progress_callback=None):
    client = genai.Client(api_key=api_key)
    os.makedirs(output_text_folder, exist_ok=True)
    files = sorted(image_files)
    details, summary = [], defaultdict(int)
    used = set()
    total_images = len(files)

    if progress_callback: progress_callback(15)

    for idx, front in enumerate(files):
        if front in used:
            continue
        front_info = extract_front_info_gemini(api_key, front)

        if progress_callback:
            current_progress = 15 + int(((idx + 1) / total_images) * 45)
            progress_callback(current_progress)

        if not front_info["date"]:
            continue

        back_info = {"employee": "", "route": ""}
        for candidate in files[idx + 1:]:
            if candidate in used:
                continue
            temp_info = extract_back_info_gemini(api_key, candidate)
            if temp_info["employee"]:
                back_info = temp_info
                used.add(candidate)
                break

        month_day, task = "", ""
        try:
            dt = datetime.strptime(front_info["date"], "%Y-%m-%d %H:%M")
            month_day = f"{dt.month}월 {dt.day}일"
            task = "외근" if dt.hour < 17 or (dt.hour == 17 and dt.minute <= 30) else "야근"
        except:
            pass

        details.append([
            os.path.splitext(os.path.basename(front))[0],
            month_day,
            back_info["employee"],
            task,
            back_info["route"],
            front_info["price"],
            ""
        ])

        if back_info["employee"] and front_info["price"]:
            try:
                summary[back_info["employee"]] += int(front_info["price"].replace(",", "").replace("원", ""))
            except:
                pass

        used.add(front)

    if progress_callback: progress_callback(60)

    details_path = os.path.join(output_text_folder, "교통비내역.txt")
    with open(details_path, "w", encoding="utf-8") as f:
        f.write("영수증번호\t사용일자\t직원명\t업무내용\t출발-도착\t사용요금\t비고\n")
        for row in details:
            f.write("\t".join(str(item) for item in row) + "\n")

    summary_path = os.path.join(output_text_folder, "직원별합계.txt")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("직원명\t총액\n")
        for name, total in summary.items():
            f.write(f"{name}\t{total:,}원\n")

    return len(details)