from google import genai
from google.genai import types
import os
import re
import json # json 파싱을 위해 추가
import csv
import glob

def extract_front_info_gemini(api_key, image_path: str) -> dict:
    client = genai.Client(api_key=api_key)
    with open(image_path, "rb") as f:
        image_bytes = f.read()

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
            (
                """
                영수증에서 여러 정보를 추출해야합니다. 당신은 매우 잘 할 수 있습니다.
                a) 날짜 및 시간 (YYYY-MM-DD HH:MM)
                b) 용도구분 (외근식대, 야근식대, 유류대, 통행료, 주간식대, 숙박비 중 1개)
                c) 업체명
                d) 금액 (integer)
                e) 야근자 (사람이름) - b)가 "야근식대"인경우만 작성해주세요. 야근식대가 아니면 없습니다.
                f) 비고 (법인카드 혹은 개인카드)

                ## a) 날짜 및 시간
                - 출력 형식은 반드시 YYYY-MM-DD HH:MM 이어야 합니다.  
                - 초 단위(SS)는 무시하고, 분까지만 표시하세요.  
                - 시간이 누락되었다면 **추출하지 않고 빈 문자열**("")로 남겨주세요.

                아래 예시를 참고하세요

                ### 예시 맵핑
                "승인일시 2025-07-22 18:34:23"          → "2025-07-22 18:34"  
                "거래일시:25-07-22(화) 15:06:04"        → "2025-07-22 15:06"  
                "2025/07/17 15:26:23"                → "2025-07-17 15:26"  
                "[일시] 2025/07/14 11:43"             → "2025-07-14 11:43"  
                "발행일시: 2025-07-16 12:45:47"       → "2025-07-16 12:45"  
                "[등록] 2025-07-24 13:56"            → "2025-07-24 13:56"  
                "2025-07-23 22:21:51"                → "2025-07-23 22:21"

                ## b) 용도구분
                - 외근식대, 야근식대, 유류대, 통행료, 주간식대, 숙박비 중 1개
                - 영수증 최상단에 한글 손글씨로 써있습니다. 참고하여 작성하세요.
                - 외근식대는 "외근" 혹은 "출장" "접대비" 써있습니다.
                - 주간식대 : "주간식대"라고 써있습니다.
                - 야근식대 : "야근식대"라고 써있습니다.
                - 유류대 : "유류대"라고 써있습니다. 혹은 상호명 주요소.
                - 통행료 : 하이플러스충전, 한국도로공사 등 써있습니다
                - 숙박료 : 무인텔, 모텔 등 써있습니다.
                - 교통비 : 동화운수, 콜택시, 택시 등 써있습니다.

                ## c) 업체명
                - 영수증에 프린트되어있는 업체명을 추출해주세요. 양상관은 업체명이 아닙니다
                - 

                ## d) 금액 (integer)
                - 금액을 integer로 숫자만 추출해주세요

                ## e) 야근자 (사람이름) - 없을 수 있습니다. 없는 경우 빈칸("")으로 반환하세요
                - b)가 "야근식대"인경우만 작성해주세요. 야근식대가 아니면 없습니다. 없는 경우 빈칸("")으로 반환하세요
                - 사람이름 혹은 영어 이니셜 2글자로 되어있습니다. 사람이름은 그대로 추출해주세요
                - 영어이니셜 2글자인 경우에는 아래를 참고해서 사람이름 3글자로 출력해주세요.
                    ```영어 이니셜과 사람이름 매칭
                    이인호 - IH
                    이동혁 - DH
                    양상관 - SK
                    조준호 - JH
                    안형범 - HB
                    손근영 - KY
                    오형석 - HS
                    석영진 - YJ
                    이관희 - GH
                    박주연 - JY
                    ```

                ## f) 비고
                - 영수증 최상단에 법인카드 혹은 개인카드 써있습니다. 
                - 추가정보로는 법인카드는 신한카드법인 법카라고 써있습니다.
                - 신한카드법인 카드번호 451844로 시작하니 참고하세요. 
                - 개인카드는 사람이름과 함께 아웃풋해주세요 ex) 개인카드(손근영) 
                - 개인카드인 경우 영어 이니셜 2글자일 수 있습니다. 영어 이니셜과 사람이름 매칭을 참고해서 사람이름 3글자로 추출해주세요.
                
                다음 JSON 형식으로 정확히 반환해주세요:
                {"a": "날짜시간", "b": "용도구분", "c": "업체명", "d": 금액숫자, "e": "야근자", "f": "비고"}
                """
            ),
        ],
    )
    raw = response.text.strip()
    print(raw)
    # 코드블록 백틱이 있을 경우 제거
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.DOTALL).strip()
    front_info = json.loads(raw)   # {'date': '2024-07-25 14:05', 'price': '7,500원'}
    return front_info

def process_receipts(api_key):
    """img 폴더의 영수증들을 순회하면서 정보를 추출하고 CSV로 저장"""
    
    # img 폴더가 없으면 생성
    if not os.path.exists("img"):
        os.makedirs("img")
        print("img 폴더를 생성했습니다. 영수증 이미지를 넣어주세요.")
        return
    
    # 이미지 파일들 찾기
    image_files = []
    for ext in ['*.jpg', '*.jpeg', '*.png']:
        image_files.extend(glob.glob(os.path.join("img", ext)))
    image_files.sort()
    
    if not image_files:
        print("img 폴더에 이미지 파일이 없습니다.")
        return
    
    results = []
    
    # 영수증 순회 처리
    for i, image_path in enumerate(image_files, 1):
        print(f"{i}번째 영수증")
        try:
            info = extract_front_info_gemini(api_key, image_path)
            print(image_path)
            print(info)
            results.append([
                os.path.basename(image_path), 
                info.get('a', ''),    # 날짜시간
                info.get('b', ''),    # 용도구분
                info.get('c', ''),    # 업체명
                info.get('d', ''),    # 금액
                info.get('e', ''),    # 야근자
                info.get('f', '')     # 비고
            ])
        except Exception as e:
            print(f"오류: {e}")
            results.append([os.path.basename(image_path), '', '', '', '', '', ''])
        print()
    
    # CSV 저장
    with open('results.csv', 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(['filename', 'date', 'purpose', 'company', 'price', 'worker', 'note'])
        writer.writerows(results)
    
    print("results.csv에 저장완료!")

if __name__ == "__main__":
    # API 키 설정 (환경변수에서 가져오거나 직접 입력)
    api_key = os.getenv('GEMINI_API_KEY')
    
    if not api_key:
        api_key = input("Gemini API 키를 입력하세요: ")
    
    if api_key:
        process_receipts(api_key)
    else:
        print("API 키가 필요합니다.")