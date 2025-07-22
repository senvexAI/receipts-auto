from openai import OpenAI
import os
import re
import base64
from datetime import datetime
from collections import defaultdict

# ✅ client를 global로 두지 않고, 함수 호출 시 생성
def create_client(api_key):
    return OpenAI(api_key=api_key)

def encode_image(image_path):
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

def gpt_ocr(client, image_path, prompt):
    base64_image = encode_image(image_path)
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are an OCR assistant for receipts."},
            {"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}" }},
                {"type": "text", "text": prompt}
            ]}
        ],
        max_tokens=500
    )
    return response.choices[0].message.content

def extract_front_info(client, image_path):
    prompt = "영수증인지 확인 후 거래일시(YYYY-MM-DD HH:MM), 결제요금(예: 12,700원)을 출력.\n형식:\n거래일시: ...\n결제요금: ..."
    result = gpt_ocr(client, image_path, prompt)
    date_match = re.search(r"거래일시:\s*(\d{4}-\d{2}-\d{2}\s*\d{2}:\d{2})", result)
    price_match = re.search(r"결제요금:\s*([\d,]+원)", result)
    return {"date": date_match.group(1) if date_match else "", "price": price_match.group(1) if price_match else ""}

def extract_back_info(client, image_path, employee_names):
    employee_list = ", ".join(employee_names)
    prompt = f"뒷면 이미지에서 손글씨 이름과 경로를 추출.\n리스트에서 이름 선택: [{employee_list}]\n형식:\n직원명: ...\n경로: ..."
    result = gpt_ocr(client, image_path, prompt)
    name_match = re.search(r"직원명:\s*([가-힣]+)", result)
    route_match = re.search(r"경로:\s*([^\n]+)", result)
    route_clean = re.sub(r"[→➡>~]+", "-", route_match.group(1).strip() if route_match else "")
    return {"employee": name_match.group(1) if name_match else "", "route": route_clean}

def process_receipts(api_key, image_files, output_text_folder, employee_names, progress_callback=None):
    client = create_client(api_key)
    os.makedirs(output_text_folder, exist_ok=True)
    files = sorted(image_files)
    details, summary = [], defaultdict(int)
    used = set()
    total_images = len(files)

    if progress_callback: progress_callback(15)

    for idx, front in enumerate(files):
        if front in used:
            continue
        front_info = extract_front_info(client, front)

        if progress_callback:
            current_progress = 15 + int(((idx + 1) / total_images) * 45)
            progress_callback(current_progress)

        if not front_info["date"]:
            continue

        back_info = {"employee": "", "route": ""}
        for candidate in files[idx + 1:]:
            if candidate in used:
                continue
            temp_info = extract_back_info(client, candidate, employee_names)
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