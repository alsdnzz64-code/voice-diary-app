import calendar
import datetime
import os
import re
import sqlite3
import flet as ft

DB_FILE = "diary_entries.db"

# 키워드 추출 시 제외할 불용어 목록
STOPWORDS = {
    "오늘", "어제", "내일", "나는", "내가", "우리", "그냥", "진짜", "정말", "너무",
    "엄청", "조금", "많이", "생각보다", "그래서", "그리고", "하지만", "그런데",
    "하루", "시간", "생각", "기분", "일기", "정도", "계속", "다시", "먼저", "나중",
    "오전", "오후", "저녁", "아침", "점심", "조금씩", "갑자기", "역시", "일단",
}


def init_db():
    """SQLite 데이터베이스 및 테이블 초기화"""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS diaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT UNIQUE NOT NULL,
                weather TEXT,
                keywords TEXT,
                raw_speech TEXT,
                diary TEXT,
                photo_path TEXT,
                bgm_name TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()


def extract_keywords(text: str, max_keywords: int = 3) -> str:
    """텍스트에서 핵심 키워드 2~3개 추출"""
    words = re.findall(r"[가-힣]{2,}", text)
    candidates = []
    suffix_pattern = re.compile(
        r"(에서|으로|이랑|하고|에게|부터|까지|처럼|보다|에는|에도|은|는|이|가|을|를|에|의|와|과|도|만)$"
    )
    verb_endings = (
        "했어", "었어", "았어", "졌어", "갔어", "왔어", "봤어", "먹었", "시켰",
        "했다", "었다", "았다", "졌다", "갔다", "왔다", "보았", "있었", "없었",
        "하긴", "한데", "같아", "같다", "좋은", "좋았", "맛있", "피곤", "뿌듯",
    )

    for w in words:
        stem = suffix_pattern.sub("", w)
        if len(stem) < 2 or stem in STOPWORDS or w in STOPWORDS:
            continue
        if any(stem.endswith(ve) or w.endswith(ve) for ve in verb_endings):
            continue
        if stem not in candidates:
            candidates.append(stem)
        if len(candidates) >= max_keywords:
            break

    return ", ".join(candidates) if candidates else "일상"


def polish_spoken_to_diary(raw: str) -> str:
    """구어체를 담백한 일기체로 다듬기"""
    tokens = re.split(
        r"(?:그리고|근데|그래서|그러고 나서|또|어쨌든|그다음에|(?<=[었았졌했갔왔봤먹쳤시켰])어\s+|(?<=[다요죠])\s+|\n+)",
        raw.strip(),
    )
    clauses = [t.strip() for t in tokens if t and len(t.strip()) > 1]
    polished = []
    replacements = [
        (r"나왔어$", "나왔다."), (r"먹었는데$", "먹었다."), (r"맛있었고$", "맛있었다."),
        (r"맛있었어$", "맛있었다."), (r"시켰어$", "시켰다."), (r"했어$", "했다."),
        (r"갔어$", "갔다."), (r"왔어$", "왔다."), (r"봤어$", "보았다."),
        (r"좋았어$", "좋았다."), (r"힘들었어$", "힘들었다."), (r"피곤했어$", "피곤했다."),
        (r"재밌었어$", "재미있었다."), (r"하루였어$", "하루였다."), (r"같아$", "같다."), (r"어$", "다."),
    ]
    for clause in clauses:
        sentence = clause
        for pat, rep in replacements:
            if re.search(pat, sentence):
                sentence = re.sub(pat, rep, sentence)
                break
        if not sentence.endswith((".", "!", "?")):
            sentence += "."
        polished.append(sentence)
    return "\n".join(polished)


def main(page: ft.Page):
    page.title = "나의 하루 기록장"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 16
    page.bgcolor = "#F4EFEA"

    init_db()

    # 상태 관리
    today_str = datetime.date.today().strftime("%Y.%m.%d")
    current_date = ft.Ref[ft.TextField]()
    current_weather = ft.Ref[ft.Dropdown]()
    current_keywords = ft.Ref[ft.TextField]()
    raw_input = ft.Ref[ft.TextField]()
    diary_input = ft.Ref[ft.TextField]()
    photo_path = ft.Ref[ft.Text]()
    photo_image = ft.Ref[ft.Image]()
    bgm_title = ft.Ref[ft.Text]()

    # 캘린더 상태
    cal_year = datetime.date.today().year
    cal_month = datetime.date.today().month
    cal_title = ft.Text(f"{cal_year}년 {cal_month}월", size=18, weight=ft.FontWeight.BOLD, color="#3C2F2F")
    cal_grid_column = ft.Column(spacing=4)

    # 알림 스낵바
    def show_msg(text: str):
        page.overlay.append(ft.SnackBar(ft.Text(text), open=True))
        page.update()

    # 사진 파일 피커
    def on_photo_result(e: ft.FilePickerResultEvent):
        if e.files:
            selected_path = e.files[0].path
            photo_path.current.value = selected_path
            photo_image.current.src = selected_path
            photo_image.current.visible = True
            show_msg("사진이 첨부되었습니다 📷")
            page.update()

    file_picker = ft.FilePicker(on_result=on_photo_result)
    page.overlay.append(file_picker)

    # BGM 파일 피커
    def on_bgm_result(e: ft.FilePickerResultEvent):
        if e.files:
            bgm_title.current.value = f"🎶 {e.files[0].name}"
            show_msg(f"BGM 선곡: {e.files[0].name}")
            page.update()

    bgm_picker = ft.FilePicker(on_result=on_bgm_result)
    page.overlay.append(bgm_picker)

    # 일기 생성 로직
    def generate_diary(e):
        text = raw_input.current.value.strip()
        if not text:
            show_msg("먼저 오늘 있었던 일을 입력하거나 말해주세요!")
            return
        kw = extract_keywords(text)
        current_keywords.current.value = kw
        polished = polish_spoken_to_diary(text)
        diary_template = (
            f"날짜: {current_date.current.value}   |   날씨: {current_weather.current.value}\n"
            f"키워드: {kw}\n"
            f"{'─' * 38}\n\n"
            f"{polished}\n"
        )
        diary_input.current.value = diary_template
        show_msg("일기가 생성되었습니다! 상단 '저장하기'를 눌러주세요.")
        page.update()

    # DB 저장 로직
    def save_diary(e):
        d_val = diary_input.current.value.strip()
        r_val = raw_input.current.value.strip()
        if not d_val and not r_val:
            show_msg("저장할 일기 내용이 없습니다.")
            return

        final_content = d_val if d_val else r_val
        date_val = current_date.current.value.strip() or today_str
        weather_val = current_weather.current.value
        kw_val = current_keywords.current.value.strip() or extract_keywords(final_content)
        current_keywords.current.value = kw_val
        p_val = photo_path.current.value or ""
        b_val = bgm_title.current.value or ""

        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO diaries (date, weather, keywords, raw_speech, diary, photo_path, bgm_name, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(date) DO UPDATE SET
                    weather = excluded.weather,
                    keywords = excluded.keywords,
                    raw_speech = excluded.raw_speech,
                    diary = excluded.diary,
                    photo_path = excluded.photo_path,
                    bgm_name = excluded.bgm_name,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (date_val, weather_val, kw_val, r_val, final_content, p_val, b_val),
            )
            conn.commit()

        show_msg(f"'{date_val}' 일기가 DB에 저장되었습니다 ✅")
        render_calendar()
        page.update()

    # 예시 문장 넣기
    def put_sample(e):
        raw_input.current.value = (
            "오늘 수업시간에 파이썬으로 보이스 일기장 앱을 완성했어 "
            "점심에는 학식 돈까스를 먹었는데 정말 맛있었고 오후에는 도서관에서 공부하다가 "
            "저녁에 공원 산책을 다녀왔어 알차고 뿌듯한 하루였어"
        )
        page.update()

    # 캘린더 렌더링 함수
    def render_calendar():
        cal_title.value = f"{cal_year}년 {cal_month}월"
        cal_grid_column.controls.clear()

        # DB에서 해당 월 일기 조회
        month_events = {}
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT date, weather, keywords, diary FROM diaries")
            for row in cur.fetchall():
                month_events[row["date"].replace("-", ".")] = dict(row)

        c = calendar.Calendar(firstweekday=6)
        weeks = c.monthdayscalendar(cal_year, cal_month)

        for week in weeks:
            row_controls = []
            for d in week:
                if d == 0:
                    row_controls.append(ft.Container(expand=1))
                else:
                    d_key = f"{cal_year}.{cal_month:02d}.{d:02d}"
                    has_entry = d_key in month_events
                    entry_kw = month_events[d_key]["keywords"] if has_entry else ""

                    def open_entry(e, target_date=d_key):
                        current_date.current.value = target_date
                        if target_date in month_events:
                            item = month_events[target_date]
                            current_weather.current.value = item["weather"] or "☀️ 맑음"
                            current_keywords.current.value = item["keywords"] or ""
                            diary_input.current.value = item["diary"] or ""
                        tabs.selected_index = 0
                        page.update()

                    cell = ft.Container(
                        content=ft.Column(
                            [
                                ft.Text(str(d), size=12, weight=ft.FontWeight.BOLD, color="#3C2F2F"),
                                ft.Text(
                                    entry_kw,
                                    size=10,
                                    color="#8D6E63",
                                    max_lines=2,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                    weight=ft.FontWeight.W_500,
                                ) if has_entry else ft.Container(),
                            ],
                            spacing=2,
                        ),
                        expand=1,
                        height=68,
                        bgcolor="#FFFDF9" if not has_entry else "#FCE7D2",
                        border=ft.border.all(1, "#E2D9CE"),
                        border_radius=8,
                        padding=4,
                        on_click=open_entry,
                    )
                    row_controls.append(cell)
            cal_grid_column.controls.append(ft.Row(row_controls, spacing=4))
        page.update()

    # 캘린더 월 이동
    def prev_month(e):
        nonlocal cal_year, cal_month
        if cal_month == 1:
            cal_month = 12
            cal_year -= 1
        else:
            cal_month -= 1
        render_calendar()

    def next_month(e):
        nonlocal cal_year, cal_month
        if cal_month == 12:
            cal_month = 1
            cal_year += 1
        else:
            cal_month += 1
        render_calendar()

    # 1. 일기장 뷰 화면 UI
    diary_view = ft.ListView(
        expand=True,
        spacing=12,
        controls=[
            ft.Row(
                [
                    ft.TextField(
                        ref=current_date,
                        label="날짜",
                        value=today_str,
                        width=140,
                        dense=True,
                        bgcolor="#FFFDF9",
                    ),
                    ft.Dropdown(
                        ref=current_weather,
                        label="날씨",
                        value="☀️ 맑음",
                        options=[
                            ft.dropdown.Option("☀️ 맑음"),
                            ft.dropdown.Option("⛅ 구름"),
                            ft.dropdown.Option("☁️ 흐림"),
                            ft.dropdown.Option("🌧️ 비"),
                            ft.dropdown.Option("❄️ 눈"),
                        ],
                        width=110,
                        dense=True,
                        bgcolor="#FFFDF9",
                    ),
                    ft.ElevatedButton(
                        "💾 저장",
                        icon=ft.Icons.SAVE,
                        on_click=save_diary,
                        bgcolor="#3C2F2F",
                        color="#FFFFFF",
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            ft.TextField(
                ref=current_keywords,
                label="핵심 키워드",
                hint_text="자동 추출 또는 직접 입력",
                dense=True,
                bgcolor="#FFFDF9",
            ),
            ft.Text("🎙️ 오늘 있었던 일 (말하거나 입력)", size=13, weight=ft.FontWeight.BOLD, color="#3C2F2F"),
            ft.TextField(
                ref=raw_input,
                hint_text="오늘 있었던 일을 편하게 적어보세요...",
                multiline=True,
                min_lines=3,
                max_lines=4,
                bgcolor="#FFFDF9",
            ),
            ft.Row(
                [
                    ft.OutlinedButton("예시 넣기", on_click=put_sample),
                    ft.ElevatedButton(
                        "🪄 일기 생성",
                        on_click=generate_diary,
                        bgcolor="#8D6E63",
                        color="#FFFFFF",
                    ),
                ],
                alignment=ft.MainAxisAlignment.END,
            ),
            ft.Divider(color="#E2D9CE"),
            ft.Row(
                [
                    ft.ElevatedButton(
                        "📷 사진 첨부",
                        icon=ft.Icons.PHOTO,
                        on_click=lambda _: file_picker.pick_files(allow_multiple=False),
                        bgcolor="#EBE3D9",
                        color="#3C2F2F",
                    ),
                    ft.ElevatedButton(
                        "🎵 BGM 선택",
                        icon=ft.Icons.MUSIC_NOTE,
                        on_click=lambda _: bgm_picker.pick_files(allow_multiple=False),
                        bgcolor="#EBE3D9",
                        color="#3C2F2F",
                    ),
                ],
                spacing=8,
            ),
            ft.Text(ref=photo_path, visible=False),
            ft.Image(ref=photo_image, width=200, height=130, fit=ft.ImageFit.COVER, visible=False, border_radius=8),
            ft.Text(ref=bgm_title, value="선곡된 BGM 없음", size=12, color="#8C7A6B"),
            ft.Text("📖 완성된 일기장", size=13, weight=ft.FontWeight.BOLD, color="#3C2F2F"),
            ft.TextField(
                ref=diary_input,
                multiline=True,
                min_lines=6,
                max_lines=10,
                bgcolor="#FDFBF7",
            ),
        ],
    )

    # 2. 캘린더 뷰 화면 UI
    calendar_view = ft.Column(
        expand=True,
        spacing=8,
        controls=[
            ft.Row(
                [
                    ft.IconButton(ft.Icons.CHEVRON_LEFT, on_click=prev_month),
                    cal_title,
                    ft.IconButton(ft.Icons.CHEVRON_RIGHT, on_click=next_month),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            ft.Row(
                [
                    ft.Container(ft.Text("일", color="#C0392B", weight=ft.FontWeight.BOLD), expand=1, alignment=ft.alignment.center),
                    ft.Container(ft.Text("월", color="#3C2F2F", weight=ft.FontWeight.BOLD), expand=1, alignment=ft.alignment.center),
                    ft.Container(ft.Text("화", color="#3C2F2F", weight=ft.FontWeight.BOLD), expand=1, alignment=ft.alignment.center),
                    ft.Container(ft.Text("수", color="#3C2F2F", weight=ft.FontWeight.BOLD), expand=1, alignment=ft.alignment.center),
                    ft.Container(ft.Text("목", color="#3C2F2F", weight=ft.FontWeight.BOLD), expand=1, alignment=ft.alignment.center),
                    ft.Container(ft.Text("금", color="#3C2F2F", weight=ft.FontWeight.BOLD), expand=1, alignment=ft.alignment.center),
                    ft.Container(ft.Text("토", color="#2980B9", weight=ft.FontWeight.BOLD), expand=1, alignment=ft.alignment.center),
                ]
            ),
            cal_grid_column,
        ],
    )

    # 메인 네비게이션 탭 바
    tabs = ft.Tabs(
        selected_index=0,
        animation_duration=200,
        tabs=[
            ft.Tab(text="일기장", icon=ft.Icons.BOOK, content=diary_view),
            ft.Tab(text="캘린더", icon=ft.Icons.CALENDAR_MONTH, content=calendar_view),
        ],
        expand=True,
    )

    page.add(tabs)
    render_calendar()


if __name__ == "__main__":
    ft.app(target=main)