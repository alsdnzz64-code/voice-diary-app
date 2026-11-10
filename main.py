import calendar
import datetime
import os
import re
import sqlite3
import flet as ft

# 안드로이드 앱 내부 쓰기 가능 경로 설정 (Flet 1.0 호환)
DATA_DIR = os.environ.get("FLET_APP_STORAGE_DATA") or os.path.expanduser("~")
try:
    os.makedirs(DATA_DIR, exist_ok=True)
    DB_FILE = os.path.join(DATA_DIR, "diary_entries.db")
except Exception:
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


def load_all_entries() -> list[dict]:
    """DB에서 전체 일기 목록을 날짜 최신순으로 조회"""
    entries = []
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(
                "SELECT id, date, weather, keywords, raw_speech, diary, photo_path, bgm_name FROM diaries ORDER BY date DESC, id DESC"
            )
            for row in cur.fetchall():
                entries.append(dict(row))
    except Exception:
        pass
    return entries


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
    page.padding = 0
    page.bgcolor = "#F4EFEA"

    init_db()

    today_str = datetime.date.today().strftime("%Y.%m.%d")

    # 상태 컨트롤 생성 (Flet 1.0 호환)
    status_banner = ft.Text(
        "오늘 있었던 일을 기록해 보세요",
        size=12,
        color="#8D6E63",
        weight=ft.FontWeight.W_500,
    )
    date_field = ft.TextField(
        label="날짜",
        value=today_str,
        width=135,
        dense=True,
        bgcolor="#FFFDF9",
    )
    weather_dropdown = ft.Dropdown(
        label="날씨",
        value="☀️ 맑음",
        options=[
            ft.DropdownOption(key="☀️ 맑음", text="☀️ 맑음"),
            ft.DropdownOption(key="⛅ 구름", text="⛅ 구름"),
            ft.DropdownOption(key="☁️ 흐림", text="☁️ 흐림"),
            ft.DropdownOption(key="🌧️ 비", text="🌧️ 비"),
            ft.DropdownOption(key="❄️ 눈", text="❄️ 눈"),
            ft.DropdownOption(key="🌙 밤", text="🌙 밤"),
        ],
        width=120,
        dense=True,
    )
    keywords_field = ft.TextField(
        label="핵심 키워드 (캘린더/목록에 표시)",
        hint_text="자동 추출 또는 직접 입력",
        dense=True,
        bgcolor="#FFFDF9",
    )
    raw_field = ft.TextField(
        hint_text="오늘 있었던 일을 편하게 적어보세요 (키보드 마이크 버튼으로도 음성 입력 가능)...",
        multiline=True,
        min_lines=3,
        max_lines=4,
        bgcolor="#FFFDF9",
    )
    diary_field = ft.TextField(
        multiline=True,
        min_lines=6,
        max_lines=10,
        bgcolor="#FDFBF7",
    )

    current_photo_path = {"value": ""}
    photo_preview = ft.Image(
        src="",
        width=220,
        height=150,
        visible=False,
        border_radius=ft.BorderRadius.all(8),
    )
    photo_name_text = ft.Text("첨부된 사진 없음", size=12, color="#8C7A6B")
    bgm_title_text = ft.Text("선곡된 BGM 없음", size=12, color="#8C7A6B")

    saved_list_column = ft.Column(spacing=6)

    # Flet 1.0 FilePicker 서비스 인스턴스 유지
    file_picker = ft.FilePicker()

    # 캘린더 상태
    cal_state = {
        "year": datetime.date.today().year,
        "month": datetime.date.today().month,
    }
    cal_title = ft.Text(
        f"{cal_state['year']}년 {cal_state['month']}월",
        size=18,
        weight=ft.FontWeight.BOLD,
        color="#3C2F2F",
    )
    cal_grid_column = ft.Column(spacing=4)

    def show_msg(msg: str):
        status_banner.value = msg
        try:
            page.show_dialog(ft.SnackBar(content=ft.Text(msg)))
        except Exception:
            pass
        page.update()

    # 사진 선택 (Flet 1.0 비동기 서비스 방식)
    async def pick_photo(e):
        try:
            files = await file_picker.pick_files(allow_multiple=False)
            if files and len(files) > 0:
                f = files[0]
                if f.path:
                    current_photo_path["value"] = f.path
                    photo_preview.src = f.path
                    photo_preview.visible = True
                photo_name_text.value = f"📷 {f.name}"
                show_msg(f"사진 첨부 완료: {f.name}")
        except Exception as ex:
            show_msg(f"사진 선택 안내: {ex}")

    def clear_photo(e):
        current_photo_path["value"] = ""
        photo_preview.visible = False
        photo_name_text.value = "첨부된 사진 없음"
        page.update()

    # BGM 선택 (Flet 1.0 비동기 서비스 방식)
    async def pick_bgm(e):
        try:
            files = await file_picker.pick_files(allow_multiple=False)
            if files and len(files) > 0:
                bgm_title_text.value = f"🎶 {files[0].name}"
                show_msg(f"BGM 선곡 완료: {files[0].name}")
        except Exception as ex:
            show_msg(f"음원 선택 안내: {ex}")

    # 일기 생성 버튼
    def generate_diary(e):
        text = (raw_field.value or "").strip()
        if not text:
            show_msg("먼저 오늘 있었던 일을 입력해 주세요!")
            return
        kw = extract_keywords(text)
        keywords_field.value = kw
        polished = polish_spoken_to_diary(text)
        w_val = weather_dropdown.value or "☀️ 맑음"
        diary_template = (
            f"날짜: {date_field.value}   |   날씨: {w_val}\n"
            f"키워드: {kw}\n"
            f"{'─' * 34}\n\n"
            f"{polished}\n"
        )
        diary_field.value = diary_template
        show_msg("일기가 생성되었습니다! 상단 [💾 일기 저장]을 눌러주세요.")

    # 새 일기 폼 초기화
    def reset_form(e=None):
        date_field.value = datetime.date.today().strftime("%Y.%m.%d")
        weather_dropdown.value = "☀️ 맑음"
        keywords_field.value = ""
        raw_field.value = ""
        diary_field.value = ""
        current_photo_path["value"] = ""
        photo_preview.visible = False
        photo_name_text.value = "첨부된 사진 없음"
        bgm_title_text.value = "선곡된 BGM 없음"
        show_msg("새 일기 작성 화면입니다")

    # 특정 일기 데이터를 폼에 불러오기
    def load_entry_into_form(item: dict):
        date_field.value = item.get("date", today_str)
        weather_dropdown.value = item.get("weather") or "☀️ 맑음"
        keywords_field.value = item.get("keywords") or ""
        raw_field.value = item.get("raw_speech") or ""
        diary_field.value = item.get("diary") or ""
        p_path = item.get("photo_path") or ""
        current_photo_path["value"] = p_path
        if p_path and os.path.exists(p_path):
            photo_preview.src = p_path
            photo_preview.visible = True
            photo_name_text.value = f"📷 {os.path.basename(p_path)}"
        else:
            photo_preview.visible = False
            photo_name_text.value = "첨부된 사진 없음"
        bgm_title_text.value = item.get("bgm_name") or "선곡된 BGM 없음"
        switch_to_diary()
        show_msg(f"'{item.get('date')}' 일기를 불러왔습니다")

    # 특정 날짜 일기 삭제
    def delete_entry_by_date(target_date: str):
        try:
            with sqlite3.connect(DB_FILE) as conn:
                cur = conn.cursor()
                cur.execute("DELETE FROM diaries WHERE date = ?", (target_date,))
                conn.commit()
            refresh_saved_list()
            render_calendar()
            show_msg(f"'{target_date}' 일기가 삭제되었습니다")
        except Exception as ex:
            show_msg(f"삭제 오류: {ex}")

    # 하단 저장된 일기 목록 갱신
    def refresh_saved_list():
        saved_list_column.controls.clear()
        entries = load_all_entries()
        if not entries:
            saved_list_column.controls.append(
                ft.Text("아직 저장된 일기가 없습니다.", size=12, color="#8C7A6B")
            )
            return

        for item in entries:
            d_str = item["date"]
            kw_str = item.get("keywords") or extract_keywords(item.get("diary", ""))
            row_card = ft.Container(
                content=ft.Row(
                    [
                        ft.Column(
                            [
                                ft.Text(
                                    f"{d_str}  |  {kw_str}",
                                    size=13,
                                    weight=ft.FontWeight.BOLD,
                                    color="#3C2F2F",
                                ),
                                ft.Text(
                                    f"{item.get('weather', '')}  {item.get('bgm_name', '')}".strip(),
                                    size=11,
                                    color="#8C7A6B",
                                ),
                            ],
                            spacing=2,
                            expand=True,
                        ),
                        ft.Button(
                            content="열기",
                            on_click=lambda e, ent=item: load_entry_into_form(ent),
                            bgcolor="#EBE3D9",
                            color="#3C2F2F",
                        ),
                        ft.Button(
                            content="삭제",
                            on_click=lambda e, dt=d_str: delete_entry_by_date(dt),
                            bgcolor="#F5E1DF",
                            color="#9E4747",
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                bgcolor="#FFFDF9",
                border=ft.Border.all(1, "#E2D9CE"),
                border_radius=ft.BorderRadius.all(8),
                padding=10,
            )
            saved_list_column.controls.append(row_card)

    # DB 저장 버튼
    def save_diary(e):
        d_val = (diary_field.value or "").strip()
        r_val = (raw_field.value or "").strip()
        if not d_val and not r_val:
            show_msg("저장할 일기 내용이 없습니다. 먼저 일기를 작성해 주세요!")
            return

        final_content = d_val if d_val else r_val
        date_val = (date_field.value or "").strip() or today_str
        weather_val = weather_dropdown.value or "☀️ 맑음"
        kw_val = (keywords_field.value or "").strip() or extract_keywords(r_val or final_content)
        keywords_field.value = kw_val
        p_val = current_photo_path["value"]
        b_val = bgm_title_text.value if bgm_title_text.value != "선곡된 BGM 없음" else ""

        try:
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
        except Exception as ex:
            show_msg(f"DB 저장 오류: {ex}")
            return

        refresh_saved_list()
        render_calendar()
        show_msg(f"'{date_val}' 일기가 저장되었습니다 ✅ (목록 및 캘린더 반영 완료)")

    # 예시 문장 넣기
    def put_sample(e):
        raw_field.value = (
            "오늘 수업시간에 파이썬으로 보이스 일기장 앱을 완성했어 "
            "점심에는 학식 돈까스를 먹었는데 정말 맛있었고 오후에는 도서관에서 공부하다가 "
            "저녁에 공원 산책을 다녀왔어 알차고 뿌듯한 하루였어"
        )
        show_msg("예시 문장이 입력되었습니다 · [일기 생성]을 눌러보세요")

    # 캘린더 렌더링
    def render_calendar():
        y, m = cal_state["year"], cal_state["month"]
        cal_title.value = f"{y}년 {m}월"
        cal_grid_column.controls.clear()

        month_events = {}
        for entry in load_all_entries():
            norm_date = entry["date"].replace("-", ".").strip()
            month_events[norm_date] = entry

        c = calendar.Calendar(firstweekday=6)
        weeks = c.monthdayscalendar(y, m)

        for week in weeks:
            row_controls = []
            for d in week:
                if d == 0:
                    row_controls.append(ft.Container(expand=1, height=70))
                else:
                    d_key = f"{y}.{m:02d}.{d:02d}"
                    has_entry = d_key in month_events
                    entry_kw = month_events[d_key]["keywords"] if has_entry else ""

                    def on_cell_tap(e, target_date=d_key):
                        if target_date in month_events:
                            load_entry_into_form(month_events[target_date])
                        else:
                            reset_form()
                            date_field.value = target_date
                            switch_to_diary()
                            show_msg(f"'{target_date}' 새 일기를 작성합니다")

                    cell = ft.Container(
                        content=ft.Column(
                            [
                                ft.Text(
                                    str(d),
                                    size=12,
                                    weight=ft.FontWeight.BOLD,
                                    color="#3C2F2F",
                                ),
                                ft.Text(
                                    entry_kw,
                                    size=10,
                                    color="#795548",
                                    max_lines=2,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                    weight=ft.FontWeight.W_500,
                                )
                                if has_entry
                                else ft.Container(),
                            ],
                            spacing=2,
                        ),
                        expand=1,
                        height=70,
                        bgcolor="#FCE7D2" if has_entry else "#FFFDF9",
                        border=ft.Border.all(1, "#E2D9CE"),
                        border_radius=ft.BorderRadius.all(8),
                        padding=4,
                        on_click=on_cell_tap,
                    )
                    row_controls.append(cell)
            cal_grid_column.controls.append(ft.Row(controls=row_controls, spacing=4))

    def prev_month(e):
        if cal_state["month"] == 1:
            cal_state["month"] = 12
            cal_state["year"] -= 1
        else:
            cal_state["month"] -= 1
        render_calendar()
        page.update()

    def next_month(e):
        if cal_state["month"] == 12:
            cal_state["month"] = 1
            cal_state["year"] += 1
        else:
            cal_state["month"] += 1
        render_calendar()
        page.update()

    # [📖 일기장] / [📅 캘린더] 화면 전환 버튼 및 컨테이너
    diary_section = ft.Column(
        visible=True,
        spacing=10,
        controls=[
            ft.Row(
                [
                    date_field,
                    weather_dropdown,
                    ft.Button(
                        content="💾 일기 저장",
                        on_click=save_diary,
                        bgcolor="#3C2F2F",
                        color="#FFFFFF",
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                wrap=True,
            ),
            keywords_field,
            ft.Text(
                "🎙️ 오늘 있었던 일 말하기 / 적기",
                size=13,
                weight=ft.FontWeight.BOLD,
                color="#3C2F2F",
            ),
            raw_field,
            ft.Row(
                [
                    ft.Button(
                        content="+ 새 일기",
                        on_click=reset_form,
                        bgcolor="#EBE3D9",
                        color="#3C2F2F",
                    ),
                    ft.Button(
                        content="예시 넣기",
                        on_click=put_sample,
                        bgcolor="#EBE3D9",
                        color="#4A3F35",
                    ),
                    ft.Button(
                        content="일기 생성",
                        on_click=generate_diary,
                        bgcolor="#8D6E63",
                        color="#FFFFFF",
                    ),
                ],
                alignment=ft.MainAxisAlignment.END,
                spacing=6,
            ),
            ft.Divider(color="#E2D9CE"),
            ft.Row(
                [
                    ft.Button(
                        content="📷 사진 첨부",
                        on_click=pick_photo,
                        bgcolor="#EBE3D9",
                        color="#3C2F2F",
                    ),
                    ft.Button(
                        content="사진 제거",
                        on_click=clear_photo,
                        bgcolor="#FAF6F0",
                        color="#8C7A6B",
                    ),
                    ft.Button(
                        content="🎵 BGM 선곡",
                        on_click=pick_bgm,
                        bgcolor="#EBE3D9",
                        color="#3C2F2F",
                    ),
                ],
                spacing=6,
                wrap=True,
            ),
            photo_preview,
            ft.Row([photo_name_text, ft.Text(" | ", color="#E2D9CE"), bgm_title_text]),
            ft.Text(
                "📖 오늘의 일기장",
                size=13,
                weight=ft.FontWeight.BOLD,
                color="#3C2F2F",
            ),
            diary_field,
            ft.Divider(color="#E2D9CE"),
            ft.Text(
                "🔖 저장된 일기 목록 (날짜 | 키워드)",
                size=13,
                weight=ft.FontWeight.BOLD,
                color="#3C2F2F",
            ),
            saved_list_column,
            # 갤럭시 하단 내비게이션 바(홈/뒤로가기 버튼)와 겹치지 않도록 여유 공간 확보
            ft.Container(height=40),
        ],
    )

    calendar_section = ft.Column(
        visible=False,
        spacing=8,
        controls=[
            ft.Text(
                "날짜를 터치하면 해당 일기를 보거나 새로 작성할 수 있습니다.",
                size=12,
                color="#8C7A6B",
            ),
            ft.Row(
                [
                    ft.Button(
                        content="◀ 이전 달",
                        on_click=prev_month,
                        bgcolor="#EBE3D9",
                        color="#3C2F2F",
                    ),
                    cal_title,
                    ft.Button(
                        content="다음 달 ▶",
                        on_click=next_month,
                        bgcolor="#EBE3D9",
                        color="#3C2F2F",
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            ft.Row(
                [
                    ft.Container(
                        content=ft.Text("일", color="#C0392B", weight=ft.FontWeight.BOLD),
                        expand=1,
                        alignment=ft.Alignment.CENTER,
                    ),
                    ft.Container(
                        content=ft.Text("월", color="#3C2F2F", weight=ft.FontWeight.BOLD),
                        expand=1,
                        alignment=ft.Alignment.CENTER,
                    ),
                    ft.Container(
                        content=ft.Text("화", color="#3C2F2F", weight=ft.FontWeight.BOLD),
                        expand=1,
                        alignment=ft.Alignment.CENTER,
                    ),
                    ft.Container(
                        content=ft.Text("수", color="#3C2F2F", weight=ft.FontWeight.BOLD),
                        expand=1,
                        alignment=ft.Alignment.CENTER,
                    ),
                    ft.Container(
                        content=ft.Text("목", color="#3C2F2F", weight=ft.FontWeight.BOLD),
                        expand=1,
                        alignment=ft.Alignment.CENTER,
                    ),
                    ft.Container(
                        content=ft.Text("금", color="#3C2F2F", weight=ft.FontWeight.BOLD),
                        expand=1,
                        alignment=ft.Alignment.CENTER,
                    ),
                    ft.Container(
                        content=ft.Text("토", color="#2980B9", weight=ft.FontWeight.BOLD),
                        expand=1,
                        alignment=ft.Alignment.CENTER,
                    ),
                ]
            ),
            cal_grid_column,
            ft.Container(height=40),
        ],
    )

    btn_tab_diary = ft.Button(
        content="📖 일기장",
        bgcolor="#8D6E63",
        color="#FFFFFF",
        expand=True,
    )
    btn_tab_calendar = ft.Button(
        content="📅 캘린더",
        bgcolor="#EBE3D9",
        color="#3C2F2F",
        expand=True,
    )

    def switch_to_diary(e=None):
        diary_section.visible = True
        calendar_section.visible = False
        btn_tab_diary.bgcolor = "#8D6E63"
        btn_tab_diary.color = "#FFFFFF"
        btn_tab_calendar.bgcolor = "#EBE3D9"
        btn_tab_calendar.color = "#3C2F2F"
        page.update()

    def switch_to_calendar(e=None):
        diary_section.visible = False
        calendar_section.visible = True
        btn_tab_calendar.bgcolor = "#8D6E63"
        btn_tab_calendar.color = "#FFFFFF"
        btn_tab_diary.bgcolor = "#EBE3D9"
        btn_tab_diary.color = "#3C2F2F"
        render_calendar()
        page.update()

    btn_tab_diary.on_click = switch_to_diary
    btn_tab_calendar.on_click = switch_to_calendar

    # SafeArea로 감싸서 갤럭시 상단 상태바 및 하단 홈버튼(내비게이션 바) 영역 침범 방지
    page.add(
        ft.SafeArea(
            expand=True,
            content=ft.Container(
                padding=ft.Padding.only(left=16, top=10, right=16, bottom=24),
                expand=True,
                content=ft.Column(
                    scroll=ft.ScrollMode.AUTO,
                    expand=True,
                    spacing=10,
                    controls=[
                        ft.Text(
                            "나의 하루 기록장",
                            size=20,
                            weight=ft.FontWeight.BOLD,
                            color="#3C2F2F",
                        ),
                        status_banner,
                        ft.Row([btn_tab_diary, btn_tab_calendar], spacing=8),
                        ft.Divider(color="#E2D9CE"),
                        diary_section,
                        calendar_section,
                    ],
                ),
            ),
        )
    )

    refresh_saved_list()
    render_calendar()


if __name__ == "__main__":
    if hasattr(ft, "run"):
        ft.run(main)
    else:
        ft.app(target=main)
