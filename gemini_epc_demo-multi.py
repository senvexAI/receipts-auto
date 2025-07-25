from google import genai
from google.genai import types
import os
import re
import json # json 파싱을 위해 추가
import csv
import glob
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

def convert_date_format(date_str):
    """YYYY-MM-DD HH:MM 형태를 `(MM/DD)` 형태로 변환"""
    if not date_str or date_str.strip() == "":
        return ""
    
    try:
        # YYYY-MM-DD HH:MM 형태에서 MM/DD 추출
        # 정규식으로 YYYY-MM-DD 패턴 찾기
        match = re.match(r'(\d{4})-(\d{2})-(\d{2})', date_str)
        if match:
            year, month, day = match.groups()
            return f"({month}/{day})"
        else:
            return date_str  # 변환 실패시 원본 반환
    except Exception:
        return date_str  # 오류시 원본 반환

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
                영수증에 최상단에는 hand-written 손글씨로 여러 정보가 있습니다.당신은 손글씨를 무시하고, 출력된 영수증에서만 여러 정보를 추출해야합니다.
                a) 날짜 및 시간 (YYYY-MM-DD HH:MM)
                b) 업체명
                c) 금액 (integer)
                h) 결제카드 정보

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

                ## b) 업체명
                - 영수증에 프린트되어있는 업체명(가맹점 등)을 추출해주세요. 최상단 손글씨를 보지 마세요.
                - 업체명은 [날짜 및 시간] 근처에 있습니다. 예를 들어 2025-07-22 15:06 근처에 있습니다.
                - '엔에이치엔케이씨피 주식회사', '양상관' 은 업체명이 아닙니다.
                - 실제 사용처인 식당 등 가게이름으로 추출하세요.
                ex) 청원, 남원전통추어탕, 탐앤탐스, 오토김밥, GS25 등

                ## c) 금액 (integer)
                - 금액을 integer로 숫자만 추출해주세요
                
                ## h) 결제카드 정보
                - 영수증의 카드정보를 불러오세요. 카드회사명과 카드소유주 이름, 카드번호를 추출하세요.
                - ex)신한카드법인 451844*** 등입니다.

                ## i) 결제주소 정보
                - 영수증의 결제된 장소의 주소 정보를 불러오세요.
                - ex)서울시 영등포구 버드나루로19길 6 등입니다.
                
                다음 JSON 형식으로 정확히 반환해주세요:
                {"a": "...", "b": "...", "c": "...(integer)", "h": "...", "i": "..."}
                """
            ),
        ],
    )
    raw = response.text.strip()
    # 코드블록 백틱이 있을 경우 제거
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.DOTALL).strip()
    front_info = json.loads(raw)   # {'date': '2024-07-25 14:05', 'price': '7,500원'}

    input_text = f"""영수증에 최상단에는 hand-written 손글씨로 여러 정보가 있습니다. 당신은 손글씨에서 정보를 추출해야합니다. 
                프린터로 출력되어있는 영수증의 내용을 참고하여 d), f)를 작성하세요. 영수증의 내용은 {front_info} 입니다.
                
                ## 추출해야할 3가지 정보
                - d) 용도구분 (외근식대, 야근식대, 유류대, 통행료, 주간식대, 교통비, 숙박비, 회식비, 부서간식대 중 1개)
                - e) 야근자 (사람이름) - d)가 "야근식대"인경우만 작성해주세요. 야근식대가 아니면 없습니다.
                - f) 비고 (법인카드 혹은 개인카드)

                ## d) 용도구분 
                - 외근식대, 야근식대, 유류대, 통행료, 주간식대, 교통비, 숙박비, 회식비, 부서간식대 중 1개입니다. 만약 본인이 분류할수 없다고 판단이 된다면(그럴일은 적겠지만) 손글씨 씌여진대로 작성하세요. 
                - 영수증 최상단에 한글 손글씨로 써있습니다.
                - 프린트된 영수증의 내용 를 참고하세요.
                - 외근식대 : "외근" 혹은 "출장" "접대비" 써있습니다.
                - 주간식대 : "주간식대"라고 써있습니다.
                - 야근식대 : "야근식대"라고 써있습니다. 결제시간이 17시30분 이후이고 주소가 서울시 영등포구이면 야근식대입니다.
                - 유류대 : "유류대"라고 써있습니다. 혹은 상호명이 주유소 등입니다.
                - 통행료 : 하이플러스충전, 한국도로공사 등 써있습니다
                - 숙박료 : 무인텔, 모텔 등 써있습니다.
                - 교통비 : 동화운수, 콜택시, 택시 등 써있습니다.

                ## e) 야근자 (사람이름) - 없을 수 있습니다. 없는 경우 빈칸("")으로 반환하세요
                - b)가 "야근식대"인경우만 작성해주세요. 야근식대가 아니면 없습니다. 없는 경우 빈칸("")으로 반환하세요
                - 사람이름 혹은 영어 이니셜 2글자로 되어있습니다. 
                - 사람이름은 그대로 추출해주세요
                    ```사람이름
                    이인호
                    이동혁
                    양상관
                    조준호
                    안형범
                    손근영
                    오형석
                    석영진
                    이관희
                    박주연
                    ```
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
                - {front_info.get('h', '')}를 참고하세요.
                - 추가정보로는 법인카드는 신한카드법인 법카라고 써있습니다.
                - 신한카드법인 카드번호 451844로 시작하니 참고하세요. 
                - 개인카드는 사람이름과 함께 아웃풋해주세요 ex) 개인카드(손근영) 
                - 개인카드인 경우 영어 이니셜 2글자일 수 있습니다. 영어 이니셜과 사람이름 매칭을 참고해서 사람이름 3글자로 추출해주세요.
                
                다음 JSON 형식으로 정확히 반환해주세요:
                {{"d": "...", "e": "...", "f": "..."}}
                """
    
    response_handwritten = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
            (input_text),
        ],
    )
    raw_handwritten = response_handwritten.text.strip()
    # 코드블록 백틱이 있을 경우 제거
    if raw_handwritten.startswith("```"):
        raw_handwritten = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_handwritten, flags=re.DOTALL).strip()
    handwritten_info = json.loads(raw_handwritten) 


    return front_info, handwritten_info

def process_single_receipt(api_key, image_path, index):
    """단일 영수증 처리 함수 (멀티스레딩용)"""
    print(f"{index}번째 영수증 처리 시작: {os.path.basename(image_path)}")
    try:
        front_info, handwritten_info = extract_front_info_gemini(api_key, image_path)
        print(f"{index}번째 영수증 완료: {os.path.basename(image_path)}")
        print("프린트된 정보:", front_info)
        print("손글씨 정보:", handwritten_info)
        return [
            os.path.basename(image_path), 
            convert_date_format(front_info.get('a', '')),    # 날짜시간 변환
            handwritten_info.get('d', ''),    # 용도구분  
            front_info.get('b', ''),    # 업체명
            front_info.get('c', ''),    # 금액
            handwritten_info.get('e', ''),    # 야근자
            handwritten_info.get('f', '')     # 비고
        ]
    except Exception as e:
        print(f"{index}번째 영수증 오류: {e}")
        return [os.path.basename(image_path), '', '', '', '', '', '']

def process_receipts(api_key, max_workers=4):
    """img 폴더의 영수증들을 동시에 처리하여 정보를 추출하고 CSV로 저장"""
    
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
    
    print(f"총 {len(image_files)}개 영수증을 {max_workers}개 스레드로 동시 처리합니다.")
    
    results = [None] * len(image_files)  # 순서 보장을 위한 리스트
    
    # ThreadPoolExecutor를 사용한 동시 처리
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 모든 작업 제출
        future_to_index = {
            executor.submit(process_single_receipt, api_key, image_path, i+1): i 
            for i, image_path in enumerate(image_files)
        }
        
        # 완료된 작업들 수집
        for future in as_completed(future_to_index):
            index = future_to_index[future]
            try:
                result = future.result()
                results[index] = result
            except Exception as e:
                print(f"작업 실패: {e}")
                results[index] = [os.path.basename(image_files[index]), '', '', '', '', '', '']
    
    # CSV 저장 - 타임스탬프로 고유한 파일명 생성
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_filename = f'results_{timestamp}.csv'
    
    try:
        with open(csv_filename, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(['filename', 'date', 'purpose', 'company', 'price', 'worker', 'note'])
            writer.writerows(results)
        
        print(f"{csv_filename}에 저장완료!")
            
    except Exception as e:
        print(f"❌ CSV 저장 중 오류 발생: {e}")
        print("\n📋 결과 데이터:")
        print("filename,date,purpose,company,price,worker,note")
        for row in results:
            print(','.join(str(item) for item in row))

if __name__ == "__main__":
    # API 키 설정 (환경변수에서 가져오거나 직접 입력)
    api_key = os.getenv('GEMINI_API_KEY')
    
    if not api_key:
        api_key = input("Gemini API 키를 입력하세요: ")
    
    if api_key:
        # max_workers 파라미터로 동시 처리할 스레드 수 조절 (기본값: 4)
        process_receipts(api_key, max_workers=4)
    else:
        print("API 키가 필요합니다.")