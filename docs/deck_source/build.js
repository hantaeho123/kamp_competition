const pptxgen = require("pptxgenjs");
const fs = require("fs");
const path = require("path");
const { applyTheme } = require("/Users/hantaeho/.claude/skills/synced/b3c08a02-3d0d-4da4-9730-42f08b7f2756_b27599ee-4ece-49ae-aa40-8309977775c7/pptx/scripts/apply_theme.js");

const ROOT = "/Users/hantaeho/Documents/ETC/kamp/kamp_competition";
const FONT = process.env.DECK_FONT || "Malgun Gothic";
const OUTF = process.env.DECK_OUT || path.join(ROOT, "발표자료_과제5.pptx");
const IMG = (p) => { const a = path.join(ROOT, "outputs", p); return require("fs").existsSync(a) ? a : path.join(ROOT, "analysis/outputs", p); };
const CROP = (n) => path.join(__dirname, "crops", n + ".png");

const THEME = {
  name: "PowerPeak", headFontFace: FONT, bodyFontFace: FONT,
  colors: { dk1: "14213D", lt1: "FFFFFF", dk2: "2B2D42", lt2: "F1F4F9", accent1: "FCA311", accent2: "D1495B",
            accent3: "2A6FDB", accent4: "00798C", accent5: "8D99AE", accent6: "DDE3EC", hlink: "2A6FDB", folHlink: "8D99AE" },
};
const HX = THEME.colors;
const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";            // 13.33 x 7.5
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
pres.title = "제조 생산데이터 기반 전력사용량 예측 및 최대피크 위험조건 분석";
const C = pres.SchemeColor;
const W = 13.33, MX = 0.6, CW = W - 2 * MX;
const FOOT = "제조 생산데이터 기반 전력사용량 예측 및 최대피크 위험조건 분석";

// ---------------- 레이아웃 ----------------
pres.defineSlideMaster({
  title: "COVER", background: { color: HX.dk1 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.9, y: 2.2, w: 11.5, h: 1.9, fontSize: 40, bold: true, color: C.background1, valign: "top", align: "left", margin: 0 }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: 0.9, y: 4.5, w: 11.5, h: 1.2, fontSize: 18, color: C.accent6, valign: "top", margin: 0 }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "SECTION", background: { color: HX.dk1 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 2.6, y: 2.7, w: 9.8, h: 1.1, fontSize: 38, bold: true, color: C.background1, valign: "top", align: "left", margin: 0 }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: 2.6, y: 3.95, w: 9.8, h: 1.6, fontSize: 17, color: C.accent6, valign: "top", margin: 0 }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "CONTENT", background: { color: "FFFFFF" }, margin: [1.6, 0.6, 0.7, 0.6],
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: MX, y: 0.62, w: CW, h: 0.75, fontSize: 25, bold: true, color: C.text1, valign: "middle", align: "left", margin: 0 }, text: "" } },
    { text: { text: FOOT, options: { x: MX, y: 7.02, w: 9, h: 0.3, fontSize: 10, color: C.accent5, margin: 0 } } },
  ],
  slideNumber: { x: 12.0, y: 7.02, w: 0.75, h: 0.3, fontSize: 10, color: HX.accent5, align: "right" },
});

// ---------------- 도우미 ----------------
let SEC = "";
function section(title) { SEC = title; pres.addSection({ title }); }
function content(title, step, notes) {
  const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: SEC });
  s.addText(title, { placeholder: "title" });
  s.addText(step, { x: MX, y: 0.3, w: 8, h: 0.3, fontSize: 12, bold: true, color: C.accent1, margin: 0, isTextBox: true, charSpacing: 1, objectName: "단계 표시" });
  if (notes) s.addNotes(notes);
  return s;
}
function card(s, x, y, w, h, name) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.08, fill: { color: C.background2 }, line: { color: C.background2, width: 0 }, objectName: name || "카드" });
}
function text(s, t, x, y, w, h, o = {}) {
  s.addText(t, Object.assign({ x, y, w, h, fontSize: 14, color: C.text2, margin: 0, valign: "top", isTextBox: true, paraSpaceAfter: 5 }, o));
}
function bullets(s, items, x, y, w, h, o = {}) {
  const runs = [];
  items.forEach((it, i) => {
    const last = i === items.length - 1;
    if (Array.isArray(it)) {
      runs.push({ text: it[0] + " ", options: { bold: true, color: C.text1, bullet: true } });
      runs.push({ text: it[1], options: { breakLine: !last } });
    } else runs.push({ text: it, options: { bullet: true, breakLine: !last } });
  });
  text(s, runs, x, y, w, h, Object.assign({ paraSpaceAfter: 7 }, o));
}
function stat(s, x, y, w, value, label, color) {
  card(s, x, y, w, 1.45, "수치 카드");
  text(s, value, x + 0.2, y + 0.14, w - 0.4, 0.75, { fontSize: value.length > 9 ? 23 : value.length > 7 ? 28 : 32, bold: true, color: color || C.text1, valign: "middle" });
  text(s, label, x + 0.2, y + 0.9, w - 0.4, 0.45, { fontSize: 12, color: C.text2 });
}
function pngSize(p) { const b = Buffer.alloc(24); const fd = fs.openSync(p, "r"); fs.readSync(fd, b, 0, 24, 0); fs.closeSync(fd); return [b.readUInt32BE(16), b.readUInt32BE(20)]; }
function image(s, p, x, y, maxW, maxH, alt) {
  const [pw, ph] = pngSize(p); const r = pw / ph;
  let w = maxW, h = maxW / r; if (h > maxH) { h = maxH; w = maxH * r; }
  s.addImage({ path: p, x: x + (maxW - w) / 2, y: y + (maxH - h) / 2, w, h, altText: alt, objectName: alt });
}
function table(s, head, rows, x, y, w, colW, o = {}) {
  const fs_ = o.fontSize || 12;
  const hrow = head.map((t) => ({ text: t, options: { bold: true, color: C.background1, fill: { color: C.text1 }, align: "left" } }));
  const body = rows.map((r, i) => r.map((c) => {
    const isObj = c && typeof c === "object";
    const opt = Object.assign({ color: C.text2, fill: { color: i % 2 ? C.background2 : C.background1 } }, isObj ? c.options : {});
    return { text: isObj ? c.text : String(c), options: opt };
  }));
  s.addTable([hrow, ...body], { x, y, w, colW, fontSize: fs_, border: { type: "solid", color: HX.accent6, pt: 0.5 }, margin: [0.05, 0.08, 0.05, 0.08], valign: "middle", rowH: o.rowH || 0.34, objectName: o.name || "표" });
}
const B = (t) => ({ text: t, options: { bold: true, color: C.text1 } });
const HL = (t) => ({ text: t, options: { bold: true, color: C.accent2 } });
// 차트는 그림으로 넣는다: PowerPoint 내장 차트는 macOS 미리보기·Keynote에서 빈칸으로 보이기 때문.
// 1차 실행(DECK_SPEC_ONLY=1)에서 차트 사양을 charts/specs.json으로 내보내고, render_charts.py가 PNG로 그린 뒤 2차 실행에서 삽입한다.
const SPEC_ONLY = !!process.env.DECK_SPEC_ONLY;
const CHART_SPECS = [];
function barChart(s, cats, series, x, y, w, h, o = {}) {
  const id = CHART_SPECS.length + 1;
  CHART_SPECS.push({ id, cats, series, w, h, dir: o.dir || "bar", colors: o.colors || [HX.accent3], title: o.title || "", fmt: o.fmt || "0.00", min: o.min, max: o.max });
  if (!SPEC_ONLY) s.addImage({ path: path.join(__dirname, "charts", `chart_${id}.png`), x, y, w, h, altText: o.title || "차트", objectName: o.name || "차트" });
}

// =====================================================================
// 표지
// =====================================================================
section("개요");
{
  const s = pres.addSlide({ masterName: "COVER", sectionTitle: SEC });
  s.addText("제6회 K-인공지능 제조데이터 분석 경진대회 · 과제 ⑤ 자원 최적화 AI 데이터셋", { x: 0.9, y: 1.45, w: 11.5, h: 0.4, fontSize: 15, bold: true, color: C.accent1, margin: 0, isTextBox: true });
  s.addText("제조 생산데이터 기반 전력사용량 예측 및\n최대피크 위험조건 분석", { placeholder: "title" });
  s.addText("하루 전 15분 단위 전력 예측, 피크 두 유형 규명, 유형별 저감방안", { placeholder: "body" });
  s.addNotes("과제 5번, 자원 최적화 AI 데이터셋 분석 결과를 발표합니다. 핵심은 세 가지입니다. 하루 전에 다음 날 15분 단위 전력을 예측했고, 실제 피크가 두 유형으로 나뉜다는 것을 밝혔고, 유형별 저감방안의 효과를 수치로 제시했습니다.");
}

// 요약
{
  const s = content("하루 전에 피크를 예측하고, 유형별 조치로 최대수요전력을 낮춘다", "요약",
    "전체 결과를 한 장으로 요약합니다. 시험 구간 예측오차는 6.47킬로와트이고, 일 최대수요전력은 5.8킬로와트 오차로 맞힙니다. 공장인원은 정답에서 계산된 변수라 입력에서 뺐습니다. 피크는 두 유형으로 나뉘며 두 조치를 함께 써야 효과가 납니다. 예측에 연동한 운영 규칙으로 시험 2주의 최대수요전력을 204에서 189킬로와트로 낮췄습니다.");
  const y = 1.65, w = 2.9, g = 0.17;
  stat(s, MX, y, w, "6.47 kW", "시험 구간 15분 예측 MAE\n(베이스라인 11.52 kW)", C.accent3);
  stat(s, MX + (w + g), y, w, "5.82 kW", "일 최대수요전력 예측 MAE\n(가동일, 오차율 3.0%)", C.accent3);
  stat(s, MX + 2 * (w + g), y, w, "2 유형", "실제 피크 구간 267개를\n상승폭·지속시간으로 구분", C.accent4);
  stat(s, MX + 3 * (w + g), y, w, "204 → 189 kW", "예측 연동 운영 시\n시험 2주 최대수요전력", C.accent2);
  text(s, "핵심 발견", MX, 3.4, 4, 0.35, { fontSize: 16, bold: true, color: C.text1 });
  bullets(s, [
    ["데이터의 62%가 복사본:", "257일 중 160일이 다른 날과 전력 패턴이 완전히 같다(1~6월 내부 복사). 무작위 분할 검증은 시험 표본의 58%가 학습셋에 복사본을 갖는다."],
    ["공장인원은 정답이 섞인 변수다:", "공장인원 = 생산량 ÷ 4구간 전력 합(3,511행 모두 일치)이라 입력에서 뺐다. 전날·전주 전력값도 MAE를 8.19 → 12.93 kW로 나쁘게 해 뺐다."],
    ["피크 시간에는 예측이 약 11 kW 낮다:", "일 최대 전용 예측과 피크 발생 확률 모델로 보완했다."],
    ["한 유형만 줄이면 일 최대는 거의 안 줄어든다:", "조치 A 3.3 kW, 조치 B 4.5 kW, 동시 적용 11.5 kW."],
  ], MX, 3.8, CW, 1.75, { fontSize: 14 });
  const cy = 5.6, cw = 3.9, cg = 0.215;
  [["요구 1. 전력사용량 예측", "11개 모델·설정 85가지·앙상블 5종 중 검증 오차가 가장 낮은 ExtraTrees로 하루 전 15분 예측. 일 최대와 피크 경보는 따로 보완"],
   ["요구 2. 오차·피크 조건 분석", "피크 시간·특수일·저녁에서 오차가 큼. 피크는 시작·재개 직후형과 가동 중형 두 유형"],
   ["요구 3. 피크 저감방안", "유형1은 설비 가동시점 분산, 유형2는 생산일정 저녁 이동. 예측에 연동해 운영"]].forEach((c, i) => {
    const x = MX + i * (cw + cg);
    card(s, x, cy, cw, 1.25, "요구사항 대응 카드");
    text(s, c[0], x + 0.22, cy + 0.12, cw - 0.44, 0.35, { fontSize: 14, bold: true, color: C.text1 });
    text(s, c[1], x + 0.22, cy + 0.5, cw - 0.44, 0.7, { fontSize: 12 });
  });
}

// 과제 정의와 분석 흐름
{
  const s = content("과제의 세 요구사항을 7단계 분석으로 풀었다", "과제 정의와 분석 흐름",
    "과제는 예측 모델 개발, 오차와 피크 조건 분석, 저감방안 제안 세 가지를 요구합니다. 이를 0단계 전처리부터 6단계 저감방안까지 일곱 단계로 나눠 진행했습니다. 주최 측이 시험 데이터를 따로 주지 않아, 가이드북 실습과 같은 9월 1일부터 14일까지를 시험 구간으로 정했습니다.");
  const steps = [["0", "전처리·분할", "결측·이상치, 복사일, 누수 변수, 시간 순 분할"], ["1", "전력 예측", "베이스라인 대 11개 모델, 탐색, 앙상블"], ["2", "예측오차 분석", "피크 시간, 조건별, 놓친 피크·헛경보"],
    ["3", "피크 추출", "180 kW 이상 연속 구간"], ["4", "피크 두 유형", "상승폭·지속시간·직전 부하"], ["5", "유형별 조건", "시각, 생산량, 운영상태, 기온"], ["6", "저감방안", "유형별 조치, 예측 연동 운영"]];
  const w = 1.62, g = 0.13, y = 1.75;
  steps.forEach((st, i) => {
    const x = MX + i * (w + g);
    card(s, x, y, w, 2.25, "단계 카드");
    s.addShape(pres.shapes.OVAL, { x: x + 0.2, y: y + 0.2, w: 0.55, h: 0.55, fill: { color: i === 1 || i === 6 ? C.accent1 : C.text1 }, line: { color: C.background2, width: 0 }, objectName: "단계 번호" });
    text(s, st[0], x + 0.2, y + 0.2, 0.55, 0.55, { fontSize: 18, bold: true, color: C.background1, align: "center", valign: "middle" });
    text(s, st[1], x + 0.2, y + 0.9, w - 0.3, 0.4, { fontSize: 15, bold: true, color: C.text1 });
    text(s, st[2], x + 0.2, y + 1.3, w - 0.3, 0.9, { fontSize: 12 });
  });
  table(s, ["항목", "이 분석의 정의", "근거"], [
    ["예측 대상", "15분 단위 최대수요전력, 하루 96개", "한전 기본요금이 15분 최대수요전력 기준"],
    ["예측 시점", "전날 24시에 다음 날 하루 전체", "생산일정을 바꿀 수 있는 마지막 시점"],
    ["시험 구간", "2021-09-01~14 (1,342개 15분 슬롯)", "가이드북 실습과 같은 구간, 마지막에 한 번만 평가"],
    ["피크 정의", "15분 최대수요전력 180 kW 이상", "180 kW 이상 슬롯이 전체의 5.0%(상위 5%)"],
  ], MX, 4.35, CW, [2.0, 5.2, 4.93], { fontSize: 13, rowH: 0.42 });
}

// =====================================================================
section("0단계. 데이터 전처리 및 분할");
{
  const s = pres.addSlide({ masterName: "SECTION", sectionTitle: SEC });
  s.addShape(pres.shapes.OVAL, { x: 0.9, y: 2.65, w: 1.3, h: 1.3, fill: { color: C.accent1 }, line: { color: C.accent1, width: 0 }, objectName: "단계 번호" });
  s.addText("0", { x: 0.9, y: 2.65, w: 1.3, h: 1.3, fontSize: 48, bold: true, color: C.text1, align: "center", valign: "middle", margin: 0, isTextBox: true });
  s.addText("데이터 전처리 및 분할", { placeholder: "title" });
  s.addText("결측·이상치 처리, 중복 데이터 확인, 누수 변수 제거, 시간 순 Train / Valid / Test 분할", { placeholder: "body" });
}
{
  const s = content("1행은 공장 전체의 1시간이고, 예측 단위는 그 안의 15분이다", "0단계 · 데이터 구조와 변수 의미",
    "데이터는 선박엔진용 볼트 너트 공장 한 곳의 2021년 1월부터 9월 14일까지 기록입니다. 한 행이 한 시간이고 그 안에 15분 최대수요전력 네 개가 들어 있어, 실제 예측 단위는 24,672개의 15분 슬롯입니다. 설비별 전력과 제품 구분 컬럼은 없다는 점을 분명히 했습니다.");
  table(s, ["묶음", "컬럼", "의미", "모델에서의 역할"], [
    ["전력", "15분·30분·45분·60분", "해당 시간의 15분 구간별 최대수요전력(kW)", HL("예측 대상")],
    ["전력", "평균", "위 4개 값의 평균", "제외(목표값에서 계산됨)"],
    ["생산", "생산량", "해당 시점에 생산해야 할 생산량(ERP 계획)", B("핵심 입력(사전에 아는 값)")],
    ["생산", "공장인원", "생산량 ÷ (4구간 전력 합)과 정확히 일치", HL("제외(정답에서 계산됨)")],
    ["기상", "기온·풍속·습도·강수량", "기상청 관측값(강수량은 일 누적)", "입력(예보의 대리변수)"],
    ["달력", "날짜·시간·day·d·m", "요일은 날짜와 100% 일치", "입력"],
    ["비용", "전기요금(계절)·인건비", "월·시각만으로 결정되는 값", "제외(월·시각과 중복)"],
  ], MX, 1.65, 7.6, [0.9, 2.2, 2.75, 1.75], { fontSize: 12, rowH: 0.42 });
  card(s, 8.5, 1.65, 4.23, 5.05, "관계 카드");
  text(s, "생산단위와 시간·설비·제품 간 관계", 8.75, 1.83, 3.8, 0.4, { fontSize: 15, bold: true, color: C.text1 });
  bullets(s, [
    ["생산단위:", "257일 × 24시간 = 6,168행. 생산량은 시간당 계획 개수"],
    ["시간:", "15분 4개 → 1시간 → 하루 24행. 15분 슬롯 24,672개로 펼쳐 분석"],
    ["설비:", "전력은 변압기 한 곳의 공장 전체 합계. 설비 상태는 시각·생산계획으로 간접 파악"],
    ["제품:", "제품 구분 컬럼 없음. 제품 전환은 시간당 계획량 변화로만 반영"],
  ], 8.75, 2.3, 3.75, 4.3, { fontSize: 13 });
}
{
  const s = content("이상값은 근거를 확인한 뒤 제외하거나 변환했다", "0단계 · 결측·이상치 진단과 처리",
    "이상값 다섯 가지를 찾아 처리했습니다. 가장 중요한 것은 7월 13일과 15일입니다. 시간 값이 깨졌을 뿐 아니라 그 값 기준으로 행이 정렬돼 있어 실제 시각을 알 수 없었습니다. 기상 매칭으로 복원도 시도했지만 정상 가동일 모양과 달라 두 날의 전력은 제외했습니다.");
  table(s, ["항목", "범위", "근거", "처리"], [
    [B("시간 손상·행 정렬 오류"), "07-13, 07-15 (48행)", "시간에 70~188 값. 그 값 순서로 행이 정렬돼 실제 시각 불명. 기상 매칭 복원도 정상 모양과 불일치", "두 날 전력 제외"],
    [B("전력 0 연속 구간"), "08-28 18시~08-29 10시 (17행)", "4개 값 모두 0, 공장인원도 결측", "결측 처리"],
    [B("15분 단발 0값"), "6개 슬롯", "대기전력(약 21 kW)보다 낮아 물리적으로 불가능", "결측 처리"],
    [B("강수량 누적값"), "전 기간", "1시에 초기화, 0시 행에 전날 합계", "시간 강수량으로 변환"],
    [B("산발 결측"), "풍속 3, 강수량 1", "드문 결측", "보간"],
  ], MX, 1.65, CW, [2.3, 2.6, 5.5, 1.73], { fontSize: 12, rowH: 0.48 });
  image(s, IMG("step0_preprocess_split/eda_profiles.png"), MX, 5.15, 7.6, 1.75, "요일별 평균 15분 프로파일과 생산계획 대 전력");
  card(s, 8.5, 5.15, 4.23, 1.75, "가동 패턴 카드");
  text(s, [{ text: "가동 패턴", options: { bold: true, color: C.text1, breakLine: true } }, { text: "8시에 약 170 kW로 오르고 12시 점심에 약 95 kW로 내려갔다가 13시에 다시 오른다. 비가동 대기전력은 약 21 kW." }], 8.7, 5.28, 3.85, 1.55, { fontSize: 13 });
}
{
  const s = content("257일 중 160일은 1~6월 안에서 서로 복사한 날이다", "0단계 · 중복 데이터 확인",
    "하루 96개 전력값을 통째로 비교했더니 160일이 다른 날과 완전히 같았습니다. 복사는 1월부터 6월 안에서만 일어났고, 7월부터 9월은 원본입니다. 1~6월의 어떤 날도 7~9월과 일치하지 않는다는 것도 확인했습니다. 이 사실이 검증 방식, 집계 방식, 입력 변수 선택을 모두 좌우했습니다.");
  image(s, IMG("step0_preprocess_split/eda_augmentation_calendar.png"), MX, 1.6, CW, 2.75, "월·일별 복사 그룹 크기 달력");
  const y = 4.55, w = 3.9, g = 0.215;
  [["160일 / 45개 그룹", "하루 96개 전력값이 다른 날과 완전히 같은 날. 1월 → 2·3·6월, 4월 → 5월로 복사(요일이 달라도 복사)"],
   ["0건", "1~6월 181일 중 7~9월과 같은 날, 가동 시간 2,892개 중 7~9월과 같은 시간. 7~9월은 원본 구간"],
   ["3가지 결정", "평가는 7~9월 원본에서만 / 조건별 집계는 복사일을 한 번만 / 전날·전주 전력값은 입력에서 제외"]].forEach((c, i) => {
    const x = MX + i * (w + g);
    card(s, x, y, w, 2.2, "근거 카드");
    text(s, c[0], x + 0.22, y + 0.18, w - 0.44, 0.55, { fontSize: 22, bold: true, color: i === 2 ? C.accent2 : C.text1, valign: "middle" });
    text(s, c[1], x + 0.22, y + 0.82, w - 0.44, 1.3, { fontSize: 13 });
  });
}
{
  const s = content("피크는 전체의 5%뿐이고, 검증은 시간 순서로만 한다", "0단계 · 불균형, 누수 변수, 분할",
    "피크는 전체 슬롯의 5퍼센트뿐인 불균형 문제입니다. 그래서 평균 오차와 함께 피크 전용 지표를 씁니다. 분할은 시간 순서로 했습니다. 가이드북처럼 무작위로 나누면 시험 표본의 58퍼센트가 학습셋에 복사본을 갖고 있어 성능이 부풀려지기 때문입니다.");
  image(s, IMG("step0_preprocess_split/imbalance.png"), MX, 1.6, 6.6, 2.35, "전력 분포와 부하 수준별 비율");
  card(s, 7.45, 1.6, 5.28, 2.35, "누수 변수 카드");
  text(s, "누수·중복 변수 제거", 7.67, 1.75, 4.8, 0.35, { fontSize: 15, bold: true, color: C.text1 });
  bullets(s, [["공장인원:", "생산량 ÷ 4구간 전력 합과 3,511행 모두 일치. 정답이 들어 있어 제외"], ["평균:", "목표값 4개의 평균"], ["전기요금(계절)·인건비:", "월·시각과 같은 정보"], ["전날·전주 전력값:", "복사일이 연속성을 끊어 MAE 8.19 → 12.93 kW"]], 7.67, 2.12, 4.85, 1.78, { fontSize: 12 });
  table(s, ["구분", "학습 구간", "평가 구간", "평가 구간 내 복사일"], [
    ["Valid 8개 구간(롤링)", "각 구간 시작일 이전 전체", "2021-07-05 ~ 09-05, 주 단위", "8개 구간 중 1개 구간에 2일"],
    [B("Test(최종 1회)"), "2021-01-01 ~ 08-31", "2021-09-01 ~ 09-14 (1,342 슬롯)", "0일"],
  ], MX, 4.2, CW, [2.8, 3.1, 3.6, 2.63], { fontSize: 13, rowH: 0.42 });
  card(s, MX, 5.65, CW, 1.15, "누수 검증 카드");
  text(s, [{ text: "무작위 분할을 쓰지 않는 근거  ", options: { bold: true, color: C.accent2 } }, { text: "가이드북의 무작위 70:30 분할에서는 시험 표본의 58.3%가 학습셋에 같은 패턴의 복사본을 갖고 있었다. MSE도 106.8로 시간 순 분할(113.1)보다 낙관적으로 나온다." }], MX + 0.25, 5.8, CW - 0.5, 0.9, { fontSize: 14, valign: "middle" });
}

// =====================================================================
section("1단계. 전력 예측");
{
  const s = pres.addSlide({ masterName: "SECTION", sectionTitle: SEC });
  s.addShape(pres.shapes.OVAL, { x: 0.9, y: 2.65, w: 1.3, h: 1.3, fill: { color: C.accent1 }, line: { color: C.accent1, width: 0 }, objectName: "단계 번호" });
  s.addText("1", { x: 0.9, y: 2.65, w: 1.3, h: 1.3, fontSize: 48, bold: true, color: C.text1, align: "center", valign: "middle", margin: 0, isTextBox: true });
  s.addText("전력 예측", { placeholder: "title" });
  s.addText("베이스라인 대 11개 모델 비교, 하이퍼파라미터 85가지 탐색, 앙상블 5종 비교, 피크 발생 확률 예측", { placeholder: "body" });
}
{
  const s = content("부스팅 3종이 베이스라인보다 MAE를 절반 넘게 줄였다", "1단계 · 기본 설정 모델 비교",
    "먼저 기본 설정으로 8개 모델을 같은 조건에서 비교했습니다. 부스팅 세 종이 지난주 같은 시각을 쓰는 베이스라인보다 오차를 절반 넘게 줄였습니다. 다만 일 최대는 직전 가동일 모양을 그대로 쓰는 규칙이 더 잘 맞혀, 피크는 따로 보완해야 한다는 것을 알 수 있습니다.");
  barChart(s, ["베이스라인1 지난주 같은 시각", "베이스라인2 직전 가동일 프로파일", "Ridge 회귀", "MLP(심층신경망)", "RandomForest(가이드북 설정)", "CatBoost", "LightGBM", "XGBoost"],
    [{ name: "백테스트 MAE(kW)", values: [19.88, 17.30, 22.37, 15.75, 9.33, 8.56, 8.19, 8.12] }], MX, 1.6, 7.3, 5.25, { title: "롤링 백테스트 8주(7~8월) MAE, 낮을수록 좋음", colors: [HX.accent3], name: "기본 모델 비교 차트" });
  card(s, 8.15, 1.6, 4.58, 5.25, "해석 카드");
  text(s, "입력 39개(예측 시점에 아는 정보만)", 8.37, 1.78, 4.2, 0.35, { fontSize: 15, bold: true, color: C.text1 });
  bullets(s, [["생산계획 21개:", "당시간·전후 시간 계획량, 첫·마지막 생산 시각, 일 계획량, 재가동일"], ["달력 10개:", "시각, 15분 구간, 요일, 공휴일, 월"], ["기상 8개:", "기온, 습도, 풍속, 강수, 냉방도·난방도"]], 8.37, 2.2, 4.15, 2.35, { fontSize: 13 });
  text(s, "읽을 점", 8.37, 4.6, 4.2, 0.35, { fontSize: 15, bold: true, color: C.text1 });
  bullets(s, ["부스팅 3종이 8.1~8.6 kW로 가장 좋다", "일 최대 오차는 베이스라인2(8.6 kW)가 부스팅(13 kW)보다 작다. 회귀모델은 피크를 평탄하게 예측한다"], 8.37, 5.0, 4.15, 1.75, { fontSize: 13 });
}
{
  const s = content("전날·전주 전력값을 넣으면 오히려 나빠진다", "1단계 · 입력 구성 검증",
    "같은 LightGBM에서 입력만 바꿔 봤습니다. 전날과 전주의 전력값을 넣으면 오차가 8.19에서 12.93으로 나빠집니다. 복사일이 날짜 간 연속성을 끊어 놓았기 때문입니다. 직전 값을 쓸 수 있는 1시간 전 예측조차 하루 전 계획 기반 모델보다 나빴습니다. 그래서 입력을 생산계획, 달력, 기상으로 확정했습니다.");
  barChart(s, ["기본: 생산계획 + 달력 + 기상", "+ 복사일 가중(1/n)", "- 기상 제외", "1시간 전 예측(직전 전력값 포함)", "+ 전날·전주 전력값 + 복사일 가중", "+ 전날·전주 전력값"],
    [{ name: "백테스트 MAE(kW)", values: [8.19, 8.88, 9.51, 8.44, 11.74, 12.93] }], MX, 1.6, 7.3, 4.2, { title: "LightGBM 입력 구성별 백테스트 MAE", colors: [HX.accent3], name: "입력 구성 검증 차트" });
  card(s, 8.15, 1.6, 4.58, 4.2, "해석 카드");
  text(s, "해석", 8.37, 1.78, 4.2, 0.35, { fontSize: 15, bold: true, color: C.text1 });
  bullets(s, [["전력 지연값:", "복사일에서는 전날과 당일이 이어지지 않아 잡음이 된다"], ["1시간 전 예측:", "최신 전력값이 있어도 8.44 kW로 더 나쁘다"], ["기상:", "기여는 약 1.3 kW. 예보 오차가 있어도 영향은 이 범위 안"]], 8.37, 2.2, 4.15, 3.5, { fontSize: 13 });
  card(s, MX, 6.0, CW, 0.85, "결론 카드");
  text(s, [{ text: "결론  ", options: { bold: true, color: C.accent2 } }, { text: "이 데이터에서 전력은 과거 전력이 아니라 그날의 생산계획으로 설명된다. 입력은 생산계획 + 달력 + 기상으로 확정했다." }], MX + 0.25, 6.08, CW - 0.5, 0.7, { fontSize: 15, valign: "middle" });
}
{
  const s = content("설정 85가지를 탐색했고, 탐색 이득은 모델마다 크게 달랐다", "1단계 · 하이퍼파라미터 탐색",
    "기본 설정 한 벌로는 우열이 설정 운에 좌우될 수 있어 85가지 설정을 탐색했습니다. LightGBM과 ExtraTrees는 탐색해도 거의 그대로였고, XGBoost와 CatBoost, 신경망은 개선됐습니다. 탐색한 뒤에는 ExtraTrees가 7.36으로 가장 낮습니다. 최종 선택은 다음 장에서 앙상블까지 같은 검증으로 비교해 정합니다.");
  table(s, ["모델", "탐색 방법", "시작 설정 MAE", "탐색 최적 MAE"], [
    ["LightGBM", "Optuna 30회", "8.19", "8.17"],
    ["XGBoost", "Optuna 30회", "8.06", B("7.75")],
    ["CatBoost", "Optuna 15회", "8.78", B("8.20")],
    ["ExtraTrees", "격자 2가지", "7.36", HL("7.36")],
    ["HistGradientBoosting", "격자 2가지", "8.09", "8.09"],
    ["RandomForest", "격자 3가지", "9.42", "8.58"],
    ["MLP", "격자 3가지(층 구성)", "15.75", "12.64"],
  ], MX, 1.65, 6.9, [2.3, 1.9, 1.3, 1.4], { fontSize: 13, rowH: 0.42 });
  card(s, 7.75, 1.65, 4.98, 3.42, "탐색 방법 카드");
  text(s, "탐색 설계", 7.97, 1.82, 4.5, 0.35, { fontSize: 15, bold: true, color: C.text1 });
  bullets(s, [["목적함수:", "Valid 8개 구간의 표본 외 MAE. 시험 구간은 탐색에 쓰지 않음"], ["탐색 범위:", "나무 수, 학습률, 깊이·잎 수, 최소 표본, 표본 비율, 규제, 손실함수"], ["안전장치:", "기본 설정을 첫 시도로 넣어 탐색 결과가 기본보다 나빠지지 않게 함"]], 7.97, 2.23, 4.55, 2.75, { fontSize: 13 });
  card(s, MX, 5.6, CW, 1.25, "주의 카드");
  text(s, [{ text: "읽을 점  ", options: { bold: true, color: C.accent2 } }, { text: "LightGBM·ExtraTrees·HistGradientBoosting은 탐색해도 0.02 kW 이내로 그대로였다. XGBoost는 0.31, CatBoost는 0.58, MLP는 3.11 kW 좋아졌다. 탐색 뒤 가장 낮은 것은 ExtraTrees(7.36 kW)이며, 다음 장에서 앙상블과 함께 비교해 최종 모델을 정한다." }], MX + 0.25, 5.68, CW - 0.5, 1.1, { fontSize: 14, valign: "middle" });
}
{
  const s = content("검증 오차가 가장 낮은 ExtraTrees를 최종 모델로 선정했다", "1단계 · 앙상블 비교와 최종 모델 선정",
    "탐색된 일곱 개 모델로 앙상블 다섯 종을 비교했습니다. 최종 모델은 검증 오차가 가장 낮은 것으로 한다고 미리 정했고, 그 결과 단일 ExtraTrees가 7.36으로 선정됐습니다. 앙상블 다섯 종은 모두 이를 넘지 못했습니다. 시험 구간에서는 스태킹과 가중 평균이 조금 더 낮지만, 시험 성적으로는 고르지 않았습니다.");
  barChart(s, ["ExtraTrees(탐색, 최종)", "앙상블: 비음수 가중 평균", "앙상블: 전체 7종 중앙값", "XGBoost(탐색)", "앙상블: 스태킹(Ridge)", "앙상블: 부스팅 3종 평균", "앙상블: 전체 7종 평균", "LightGBM(탐색)", "LightGBM(기본 설정)"],
    [{ name: "백테스트 MAE(7~8월)", values: [7.36, 7.46, 7.62, 7.75, 7.78, 7.84, 7.86, 8.17, 8.19] }, { name: "시험 MAE(9/1~14)", values: [6.47, 6.40, 6.46, 6.67, 6.32, 6.57, 6.47, 6.71, 6.85] }],
    MX, 1.6, 7.6, 5.25, { title: "탐색 모델과 앙상블의 MAE(kW)", colors: [HX.accent5, HX.accent3], min: 5, name: "앙상블 비교 차트" });
  card(s, 8.45, 1.6, 4.28, 5.25, "선정 근거 카드");
  text(s, "최종 모델: ExtraTrees(탐색)", 8.67, 1.78, 3.9, 0.4, { fontSize: 15, bold: true, color: C.accent2 });
  bullets(s, [["선정 규칙:", "백테스트 MAE가 가장 낮은 후보. 시험 성적은 선정에 쓰지 않는다"], ["검증 최저:", "MAE 7.36 kW로 15개 후보 중 가장 낮다"], ["일관성:", "8개 구간 중 6개에서 LightGBM보다 좋고, 구간별 표준편차 1.06 kW"], ["앙상블:", "5종 모두 ExtraTrees를 넘지 못했다. 비음수 가중 평균은 가중치의 75%를 ExtraTrees에 줬다"], ["시험:", "6.47 kW. 스태킹 6.32, 가중 평균 6.40이 조금 낮지만 사후 선택은 하지 않았다"]], 8.67, 2.3, 3.88, 4.5, { fontSize: 12 });
}
{
  const s = content("시험 구간 MAE 6.47 kW로 베이스라인보다 44% 낮다", "1단계 · 시험 구간 결과",
    "최종 모델을 9월 1일 이전 전체로 다시 학습해 시험 구간을 한 번 예측했습니다. 평균 절대오차는 6.47킬로와트, 변동계수 기준으로 8.7퍼센트입니다. 지난주 같은 시각을 쓰는 베이스라인보다 44퍼센트 낮습니다. 가장 큰 오차는 9월 8일 계측 누락 직후 재기동 구간에서 났습니다.");
  image(s, IMG("step1_forecast/test_forecast.png"), MX, 1.55, 8.55, 5.3, "시험 구간 실측 대 예측, 80% 예측구간, 피크 경보");
  const x = 9.4, w = 3.33;
  stat(s, x, 1.6, w, "6.47 kW", "MAE (베이스라인1 11.52 kW)", C.accent3);
  stat(s, x, 3.2, w, "8.91 kW", "RMSE (LightGBM 기본 9.33 kW)", C.text1);
  stat(s, x, 4.8, w, "8.7 %", "CV(RMSE) = RMSE ÷ 실측 평균", C.text1);
  text(s, "가장 큰 오차: 09-08 12시 계측 누락 직후 재기동", x, 6.38, w, 0.5, { fontSize: 12, color: C.accent5 });
}
{
  const s = content("15분 예측은 일 최대를 15 kW 낮게 봐서 따로 예측한다", "1단계 · 일 최대 전용 예측과 예측구간",
    "15분 예측의 최댓값은 실제 일 최대보다 약 15킬로와트 낮습니다. 회귀모델이 급등을 평균해 버리기 때문입니다. 그래서 일 단위 모델과 직전 가동일 최대값 규칙을 반반 섞은 일 최대 전용 예측을 만들었고, 시험 오차가 5.82킬로와트로 가장 작습니다. 예측구간은 검증 잔차로 폭을 넓혀 실제 포함률을 86퍼센트로 맞췄습니다.");
  barChart(s, ["15분 예측의 최댓값", "일 단위 LightGBM", "규칙(직전 가동일 최대값)", "P90 분위수의 최댓값", "일 최대 앙상블(제안)"], [{ name: "백테스트", values: [14.65, 10.67, 8.55, 9.87, 8.04] }, { name: "시험", values: [14.70, 7.94, 7.10, 6.72, 5.82] }],
    MX, 1.6, 6.3, 3.3, { title: "가동일 일 최대수요전력 예측 MAE(kW)", colors: [HX.accent5, HX.accent2], name: "일 최대 예측 비교 차트" });
  image(s, IMG("step1_forecast/test_daily_peak.png"), 7.1, 1.6, 5.63, 3.3, "시험 구간 일 최대 실측 대 예측");
  const y = 5.15, w = 3.9, g = 0.215;
  [["일 최대 앙상블", "일 단위 모델(생산계획·달력·기상) 50% + 직전 가동일 최대값 규칙 50%. 오차 방향이 달라 섞으면 둘 다보다 좋다"],
   ["예측구간(불확실성 추정)", "P10~P90 구간을 검증 잔차로 ±3.38 kW 넓힘(컨포멀 보정). 시험 포함률 74.7% → 85.7%(목표 80%)"],
   ["활용", "일 최대 예측은 6단계의 하루 전 경보 기준으로, 예측구간은 여유 판단에 쓴다"]].forEach((c, i) => {
    const x = MX + i * (w + g);
    card(s, x, y, w, 1.7, "설명 카드");
    text(s, c[0], x + 0.22, y + 0.15, w - 0.44, 0.35, { fontSize: 14, bold: true, color: C.text1 });
    text(s, c[1], x + 0.22, y + 0.55, w - 0.44, 1.1, { fontSize: 12 });
  });
}
{
  const s = content("피크 경보는 예측값 170 kW 기준이 가장 좋았고, 확률은 보정해 위험도로 쓴다", "1단계 · 피크 발생 확률 예측(불균형 학습, 확률보정)",
    "15분 슬롯마다 180킬로와트 이상이 되는지를 맞히는 방식을 베이스라인 포함 여섯 가지로 비교했습니다. 경보 규칙은 검증 F1이 가장 높은 것으로 한다고 미리 정했고, 전력량 예측값이 170킬로와트 이상이면 경보하는 방식이 0.69로 선정됐습니다. 시험 F1은 0.46으로 베이스라인 0.37과 0.39보다 높습니다. 확률 모델은 보정해서 시간대별 위험도로 함께 제공합니다.");
  barChart(s, ["베이스라인1 지난주 같은 시각", "베이스라인2 직전 가동일 프로파일", "전력량 예측값 170 kW 이상(경보 규칙)", "LightGBM 분류 + 확률보정", "LightGBM 분류(불균형 가중)", "로지스틱 회귀(불균형 가중)+확률보정"],
    [{ name: "백테스트 F1", values: [0.50, 0.63, 0.69, 0.66, 0.64, 0.60] }, { name: "시험 F1", values: [0.37, 0.39, 0.46, 0.44, 0.48, 0.43] }],
    MX, 1.6, 6.9, 3.05, { title: "피크 판정 F1(높을수록 좋음)", colors: [HX.accent5, HX.accent2], max: 0.9, name: "피크 확률 F1 차트" });
  image(s, CROP("prob_calibration"), MX, 4.75, 6.9, 2.15, "확률보정 전후 신뢰도 곡선과 시험 구간 피크 발생 확률");
  card(s, 7.75, 1.6, 4.98, 5.3, "해석 카드");
  text(s, "경보: 예측값 170 kW 이상 / 위험도: LightGBM 분류 + 확률보정", 7.97, 1.78, 4.55, 0.6, { fontSize: 15, bold: true, color: C.accent2 });
  bullets(s, [["선정 규칙:", "백테스트 F1이 가장 높은 방식을 경보 규칙으로. 0.69로 예측값 170 kW 기준이 선정"],
    ["시험:", "F1 0.46(재현율 0.72, 정밀도 0.34). 베이스라인은 0.37, 0.39. 시험 피크는 87개 슬롯뿐이라 변동이 크다"],
    ["불균형 가중:", "재현율이 0.92로 오르지만 정밀도 0.33. 놓치지 않는 것이 중요할 때 쓴다"],
    ["확률보정(등위 회귀):", "Brier 0.049 → 0.047. 보정한 확률을 날짜별 점검 우선순위로 제공"]], 7.97, 2.45, 4.55, 4.35, { fontSize: 13 });
}
{
  const s = content("전력을 가장 크게 움직이는 것은 당시간 생산계획량이다", "1단계 · 주요 영향변수와 상호작용",
    "SHAP 값으로 본 영향변수입니다. 당시간 생산계획량이 압도적으로 크고, 같은 생산량이라도 그날 생산이 저녁까지 이어지는지, 몇 시인지에 따라 전력이 달라집니다.");
  image(s, IMG("step1_forecast/forecast_shap_importance.png"), MX, 1.55, 6.3, 5.3, "15분 전력 예측 주요 영향변수(SHAP)");
  text(s, "변수 간 상호작용 상위 3개", 7.2, 1.65, 5.5, 0.4, { fontSize: 16, bold: true, color: C.text1 });
  table(s, ["변수 쌍", "크기(kW)", "의미"], [
    ["생산계획량 × 마지막 생산 시각", "2.35", "같은 생산량이라도 그날 생산이 저녁까지 이어지면 전력이 달라진다(잔업 여부)"],
    ["시각 × 생산계획량", "1.76", "오전에는 적은 생산에도 부하가 높다. 시작 직후에는 생산과 무관한 기동 부하가 있다"],
    ["마지막 생산까지 남은 시간 × 마지막 생산 시각", "1.58", "생산 종료가 가까울수록 부하가 내려가는데, 그 속도가 종료 시각(주간 종료·잔업)에 따라 다르다"],
  ], 7.2, 2.15, 5.53, [2.0, 0.85, 2.68], { fontSize: 12, rowH: 0.85 });
  card(s, 7.2, 5.55, 5.53, 1.3, "주석 카드");
  text(s, "같은 입력 39개로 학습한 LightGBM으로 본 결과다. 중요도 상위는 생산계획량(18.3 kW), 시각(9.4), 마지막 생산 시각(6.4) 순이다.", 7.42, 5.68, 5.1, 1.05, { fontSize: 13, valign: "middle" });
}

// =====================================================================
section("2단계. 예측오차 분석");
{
  const s = content("피크 시간의 오차는 전체의 1.7배이고 거의 전부 낮게 예측한다", "2단계 · 피크 시간 MAE 대 전체 MAE",
    "모델이 보지 못한 10주의 예측을 분석했습니다. 전체 오차는 7.18이지만 피크 시간에는 12.54로 1.7배입니다. 편향이 마이너스 11로, 거의 전부 낮게 예측합니다. 두 유형 모두 비슷하게 낮습니다. 그래서 피크는 일 최대 전용 예측과 낮춘 경보 기준으로 보완했습니다.");
  barChart(s, ["전체", "피크 아닌 시간", "피크 시간(180 kW 이상)", "유형1 피크 구간", "유형2 피크 구간"], [{ name: "MAE(kW)", values: [7.18, 6.55, 12.54, 11.73, 12.81] }],
    MX, 1.6, 6.2, 3.6, { dir: "col", title: "구간별 MAE(kW)", colors: [HX.accent3], name: "피크 시간 MAE 차트" });
  table(s, ["구간", "슬롯 수", "MAE", "Bias(예측-실측)"], [
    ["전체", "6,454", "7.18", "-0.77"], ["피크 아닌 시간", "5,776", "6.55", "+0.47"],
    [B("피크 시간(실측 180 kW 이상)"), "678", HL("12.54"), HL("-11.34")], ["유형1 피크 구간(시작·재개 직후)", "479", "11.73", "-9.79"], ["유형2 피크 구간(가동 중)", "277", "12.81", "-11.53"],
  ], 7.0, 1.65, 5.73, [2.75, 0.9, 0.8, 1.28], { fontSize: 12, rowH: 0.45 });
  card(s, 7.0, 4.45, 5.73, 0.75, "분석 대상 카드");
  text(s, "분석 대상: 표본 외 예측 10주(Valid 8주 + Test 2주, 6,454 슬롯)", 7.2, 4.5, 5.35, 0.65, { fontSize: 13, valign: "middle" });
  card(s, MX, 5.45, CW, 1.4, "결론 카드");
  text(s, [{ text: "의미와 대응  ", options: { bold: true, color: C.accent2 } }, { text: "평균 오차만 보면 드러나지 않지만, 정작 중요한 피크에서 약 11 kW 낮게 예측한다. 그래서 피크는 15분 예측을 그대로 쓰지 않고 일 최대 전용 예측(오차 5.82 kW)과, 180이 아닌 170 kW로 낮춘 경보 기준으로 보완했다." }], MX + 0.25, 5.55, CW - 0.5, 1.2, { fontSize: 15, valign: "middle" });
}
{
  const s = content("오차는 저녁 잔업, 재가동일, 고온, 특수일에서 커진다", "2단계 · 시간대·생산조건·가동상태별 오차",
    "조건별로 나누면 저녁과 야간이 전체 오차의 26퍼센트를 차지합니다. 잔업 범위가 생산계획에 덜 드러나기 때문입니다. 재가동일은 높게, 26도 이상은 낮게 예측합니다. 가장 큰 오차는 하계휴가 직전일과 대체공휴일 같은 특수일에서 났습니다. 생산계획이 설비 가동을 대표하지 못한 날입니다.");
  image(s, IMG("step2_error_analysis/error_heatmap_oos.png"), MX, 1.55, 7.4, 2.1, "시각 × 요일별 평균 절대오차와 운영상태별 오차");
  table(s, ["조건", "MAE", "Bias", "해석"], [
    ["비가동일 / 새벽", "3.05 / 5.68", "+0.20 / -0.77", "부하가 낮고 안정적"],
    ["오전 가동 시작(7~9시)", "10.48", "-1.35", "15분 사이 100 kW 변동"],
    ["오전·오후 가동 중", "10.84 / 11.62", "-1.48 / -2.05", "고부하 구간의 15분 변동"],
    [B("저녁·야간(17시~)"), "9.07", "-1.11", "잔업이 계획에 덜 드러남(기여 26%)"],
    [B("재가동일"), "8.30", HL("+2.02"), "주말 후 시작을 높게 예측"],
    [B("기온 26℃ 이상"), "8.39", HL("-2.76"), "냉방 부하를 낮게 예측"],
  ], MX, 3.8, 7.4, [2.15, 1.2, 1.35, 2.7], { fontSize: 12, rowH: 0.38 });
  card(s, 8.25, 1.55, 4.48, 5.35, "특수일 카드");
  text(s, "큰 오차(상위 10%, 16.8 kW 이상)의 실체", 8.47, 1.72, 4.1, 0.6, { fontSize: 15, bold: true, color: C.text1 });
  text(s, "의사결정나무 규칙: 일 생산계획이 12,766개 이하로 적은 날 → 340개 슬롯 중 28~36%가 큰 오차(전체 평균 10%). 계획이 많은 날의 고생산 시간도 37%", 8.47, 2.35, 4.05, 1.0, { fontSize: 13 });
  bullets(s, [["07-30(하계휴가 직전):", "계획은 적었지만 설비는 평소처럼 가동. 평균 18.5 kW 낮게 예측"], ["08-16(대체공휴일):", "부분 가동. 평균 18.6 kW 높게 예측"]], 8.47, 3.4, 4.05, 1.9, { fontSize: 13 });
  text(s, [{ text: "개선안  ", options: { bold: true, color: C.accent2 } }, { text: "ERP에 설비 가동시간과 특수일 항목을 추가하면 줄일 수 있는 오차다." }], 8.47, 5.45, 4.05, 1.3, { fontSize: 13 });
}
{
  const s = content("놓친 피크는 저녁과 오후에, 헛경보는 오전·오후 가동 중에 몰린다", "2단계 · 놓친 피크(FN)와 헛경보(FP)",
    "예측값 170킬로와트 이상 경보와 실제 피크를 비교했습니다. 전체로는 피크의 83퍼센트를 잡습니다. 놓친 피크는 비율로 보면 저녁이 가장 나빠 재현율이 12퍼센트이고, 건수로는 오후 가동 중이 가장 많습니다. 헛경보는 오전과 오후 가동 중에 몰리고, 정밀도는 오후가 46퍼센트로 낮습니다.");
  barChart(s, ["오전 가동 시작(7~9시)", "오전 가동 중(9~12시)", "점심 정지·재개(12~14시)", "오후 가동 중(14~17시)", "저녁·야간(17시~)"],
    [{ name: "맞힌 피크(TP)", values: [89, 265, 62, 141, 3] }, { name: "놓친 피크(FN)", values: [9, 32, 7, 49, 21] }, { name: "헛경보(FP)", values: [47, 193, 62, 168, 8] }],
    MX, 1.6, 6.9, 3.5, { title: "운영상태별 경보 결과(15분 슬롯 수)", colors: [HX.accent4, HX.accent2, HX.accent1], fmt: "0", name: "놓친 피크·헛경보 차트" });
  table(s, ["운영상태", "정밀도", "재현율"], [
    ["오전 가동 시작(7~9시)", "65%", "91%"], ["오전 가동 중(9~12시)", "58%", "89%"], ["점심 정지·재개(12~14시)", "50%", "90%"], ["오후 가동 중(14~17시)", HL("46%"), "74%"], ["저녁·야간(17시~)", "27%", HL("12%")],
  ], 7.75, 1.65, 4.98, [2.9, 1.04, 1.04], { fontSize: 13, rowH: 0.42 });
  text(s, "전체: 맞힌 피크 560, 놓친 피크 118, 헛경보 478 (재현율 83%, 정밀도 54%)", 7.75, 4.3, 4.98, 0.4, { fontSize: 12, color: C.accent5 });
  const y = 5.3, w = 3.9, g = 0.215;
  [["놓친 피크(FN) 집중 조건", "저녁·야간(재현율 12%)과 오후 가동 중(49건). 기온 26℃ 이상에서 55건으로 가장 많다. 더운 날 오후·저녁 부하를 낮게 본다"],
   ["헛경보(FP) 집중 조건", "오전 가동 중(193건)과 오후 가동 중(168건, 정밀도 46%). 22~26℃에서 271건. 기준을 170 kW로 낮춘 대가다"],
   ["개선 방향", "저녁 잔업 계획과 점심 정지 여부를 생산계획에 넣으면 저녁의 놓친 피크와 가동 중 헛경보를 줄일 수 있다"]].forEach((c, i) => {
    const x = MX + i * (w + g);
    card(s, x, y, w, 1.55, "해석 카드");
    text(s, c[0], x + 0.22, y + 0.13, w - 0.44, 0.35, { fontSize: 14, bold: true, color: i === 0 ? C.accent2 : C.text1 });
    text(s, c[1], x + 0.22, y + 0.5, w - 0.44, 1.0, { fontSize: 12 });
  });
}

// =====================================================================
section("3~5단계. 피크 추출, 두 유형, 발생조건");
{
  const s = pres.addSlide({ masterName: "SECTION", sectionTitle: SEC });
  s.addShape(pres.shapes.OVAL, { x: 0.9, y: 2.65, w: 1.3, h: 1.3, fill: { color: C.accent1 }, line: { color: C.accent1, width: 0 }, objectName: "단계 번호" });
  s.addText("3-5", { x: 0.9, y: 2.65, w: 1.3, h: 1.3, fontSize: 34, bold: true, color: C.text1, align: "center", valign: "middle", margin: 0, isTextBox: true });
  s.addText("피크 추출, 두 유형, 발생조건", { placeholder: "title" });
  s.addText("실제 피크 구간을 뽑고, 상승폭·지속시간·전후 패턴으로 두 유형을 구분한 뒤, 유형별 발생조건을 비교", { placeholder: "body" });
}
{
  const s = content("180 kW 이상이 이어지는 구간 426개를 실제 피크로 뽑았다", "3단계 · 실제 피크 추출",
    "15분 최대수요전력이 180킬로와트 이상인 연속 구간을 피크 구간으로 정의했습니다. 180 이상 슬롯은 전체의 5퍼센트입니다. 426개 구간이 나왔고, 복사일을 한 번만 세면 267개입니다. 7월부터 9월 정상 가동일 47일 중 46일에 피크 구간이 있었습니다.");
  image(s, IMG("step3_peak_extraction/peak_extraction.png"), MX, 1.55, CW, 3.3, "피크 구간 추출 예시와 기준값별 구간 수");
  const y = 5.1, w = 2.9, g = 0.17;
  stat(s, MX, y, w, "180 kW", "기준. 이 값 이상 슬롯이\n전체의 5.0%(상위 5%)", C.accent2);
  stat(s, MX + (w + g), y, w, "426개", "전체 피크 구간\n(15분 한 칸 끊김은 이어 붙임)", C.text1);
  stat(s, MX + 2 * (w + g), y, w, "267개 / 78일", "복사일을 한 번만 셌을 때\n(유형 구분에 사용)", C.text1);
  stat(s, MX + 3 * (w + g), y, w, "46 / 47일", "7~9월 정상 가동일 중\n피크 구간이 있는 날", C.text1);
}
{
  const s = content("피크는 상승폭과 지속시간이 뚜렷이 다른 두 유형으로 나뉜다", "4단계 · 피크 두 유형 구분",
    "구간마다 상승폭, 지속시간, 직전 한 시간 부하를 계산해 묶었습니다. 묶음 수는 실루엣 점수가 가장 높은 두 개로 정했습니다. 유형 1은 낮은 부하에서 65킬로와트 급등해 90분 이어지고, 유형 2는 이미 높은 부하 위에서 19킬로와트 더 올라 30분 안에 끝납니다. 여섯 특성 모두 통계적으로 유의하게 다릅니다.");
  image(s, IMG("step4_peak_types/peak_types.png"), MX, 1.55, CW, 2.95, "피크 두 유형: 상승폭과 직전 부하, 전후 평균 부하, 지속시간");
  table(s, ["특성(중앙값)", "유형1: 시작·재개 직후 크게 오르는 피크", "유형2: 가동 중 잠깐 더 오르는 피크"], [
    ["구간 수", "86", "181"], ["직전 1시간 평균 부하", "128 kW", "168 kW"], ["상승폭", HL("64.5 kW"), "19.3 kW"], ["지속시간", HL("90분"), "30분"], ["최대값", "194.5 kW", "185.0 kW"],
  ], MX, 4.65, 7.9, [2.3, 2.9, 2.7], { fontSize: 12, rowH: 0.37 });
  card(s, 8.75, 4.65, 3.98, 2.22, "근거 카드");
  text(s, "구분의 근거", 8.95, 4.78, 3.6, 0.35, { fontSize: 14, bold: true, color: C.text1 });
  bullets(s, ["K-means, 고유한 날의 267개 구간으로 학습", "묶음 수 2개일 때 실루엣 0.51로 최고(3개 0.42)", "6개 특성 모두 순위합 검정 p < 0.001"], 8.95, 5.15, 3.6, 1.65, { fontSize: 12 });
}
{
  const s = content("유형1은 설비가 한꺼번에 켜질 때, 유형2는 생산이 많을 때 생긴다", "5단계 · 유형별 발생조건",
    "두 유형은 생기는 조건이 다릅니다. 유형 1은 8시대와 13시대, 직전 시간 생산계획이 적다가 늘어나는 시점에 생깁니다. 설비가 쉬다가 한꺼번에 켜질 때입니다. 유형 2는 9시에서 11시, 14시에서 16시, 생산이 계속 많을 때 생깁니다. 둘 다 최고기온 27도 이상인 날에 급증합니다. 원인이 다르므로 대책도 달라야 합니다.");
  image(s, IMG("step5_peak_conditions/type_conditions.png"), MX, 1.55, CW, 2.5, "유형별 시작 시각, 생산계획 변화, 기온별 발생 빈도");
  table(s, ["조건", "유형1(시작·재개 직후)", "유형2(가동 중)"], [
    ["시작 시각", "8시대 43건, 13시대 41건(전체의 98%)", "9~11시 68건, 14~16시 68건"],
    ["직전 시간 생산계획(중앙값)", HL("198개"), "946개 (p < 0.001)"],
    ["생산계획 변화(중앙값)", HL("시간당 +359개"), "0개 (p = 0.006)"],
    ["재가동일 발생일 비율", "72% (일반 가동일 56%)", "72% (일반 가동일 75%)"],
    ["일 최고 27℃ 이상", "1.62개/일 (20℃ 미만 0.66개)", "2.42개/일 (20℃ 미만 1.55개)"],
  ], MX, 4.2, 8.2, [2.5, 3.2, 2.5], { fontSize: 12, rowH: 0.4 });
  card(s, 9.05, 4.2, 3.68, 2.6, "해석 카드");
  bullets(s, [["유형1:", "아침 시작과 점심 후 재개. 재가동일에 더 자주"], ["유형2:", "생산이 많은 시간대. 재가동일과 무관"], ["공통:", "27℃ 이상 가동일의 96%에서 발생"]], 9.25, 4.38, 3.3, 2.3, { fontSize: 13 });
}

// =====================================================================
section("6단계. 저감방안");
{
  const s = pres.addSlide({ masterName: "SECTION", sectionTitle: SEC });
  s.addShape(pres.shapes.OVAL, { x: 0.9, y: 2.65, w: 1.3, h: 1.3, fill: { color: C.accent1 }, line: { color: C.accent1, width: 0 }, objectName: "단계 번호" });
  s.addText("6", { x: 0.9, y: 2.65, w: 1.3, h: 1.3, fontSize: 48, bold: true, color: C.text1, align: "center", valign: "middle", margin: 0, isTextBox: true });
  s.addText("저감방안", { placeholder: "title" });
  s.addText("유형별 조치 시뮬레이션, 예측 연동 운영 검증, 요금 환산과 현장 운영 절차", { placeholder: "body" });
}
{
  const s = content("한 유형만 줄이면 다른 유형이 최대가 되므로 두 조치를 함께 쓴다", "6단계 · 유형별 조치 시뮬레이션",
    "7월부터 9월 실측 프로파일에 전력량을 보존하는 부하 이동 선형계획을 적용했습니다. 유형 1에는 설비 가동시점 분산, 유형 2에는 생산일정 저녁 이동을 적용합니다. 한 조치만 쓰면 3에서 5킬로와트에 그치지만, 함께 쓰면 11.5킬로와트가 줄어듭니다. 한 유형을 낮추면 다른 유형의 피크가 그날의 최대가 되기 때문입니다.");
  barChart(s, ["조치A 가동시점 분산(유형1)", "조치B 생산일정 이동(유형2)", "조치 A + B 동시", "상한: ±2시간 자유 이동"], [{ name: "일 최대 평균 감소(kW)", values: [3.3, 4.5, 11.5, 22.5] }],
    MX, 1.6, 4.7, 2.85, { title: "피크 발생일 일 최대 평균 감소(kW)", colors: [HX.accent4], fmt: "0.0", name: "조치별 효과 차트" });
  image(s, CROP("mitigation_profile"), 5.5, 1.6, 7.23, 2.85, "유형별 조치 전후 하루 부하 프로파일(7월 19일)");
  table(s, ["조치", "대상", "내용", "유형1 구간 최대", "유형2 구간 최대", "일 최대 감소"], [
    ["A. 설비 가동시점 분산", "유형1", "시작·재개 후 2시간 부하를 직전 2시간으로", "197.4 → 194.6", "변화 없음", "3.3 kW (재가동일 5.7)"],
    ["B. 생산일정 이동", "유형2", "피크 구간 생산을 같은 날 17~22시로", "변화 없음", "187.6 → 184.4", "4.5 kW"],
    [B("A + B 동시"), "둘 다", "두 조치 동시 적용", "197.4 → 190.7", "187.6 → 181.3", HL("11.5 kW (5.8%)")],
  ], MX, 4.7, CW, [2.2, 0.8, 3.9, 1.6, 1.6, 2.03], { fontSize: 12, rowH: 0.42 });
  text(s, "가정: 기저부하를 넘는 부하의 20%만 이동 가능, 하루 총 전력량은 유지. A + B는 7~9월 최대수요전력을 222 → 212 kW로 낮춘다.", MX, 6.6, CW, 0.3, { fontSize: 12, color: C.accent5 });
}
{
  const s = content("하루 전 예측만으로 최대수요전력을 204에서 189 kW로 낮췄다", "6단계 · 예측 연동 운영 검증",
    "앞의 시뮬레이션은 그날의 실측을 안다고 가정합니다. 현실에서는 하루 전 예측만 보고 계획을 세워야 하므로 시험 구간에서 따로 검증했습니다. 일 최대 예측이 185 이상인 날에 주간 15킬로와트 블록을 저녁으로 옮겼더니 최대수요전력이 204에서 189로 내려갔습니다. 기준을 목표값 190 그대로 두면 9월 10일을 놓쳐 효과가 없습니다. 경보 기준은 목표에서 예측오차를 뺀 값이어야 합니다.");
  barChart(s, ["조치 없음", "예측 195 kW 이상(1일 조치)", "예측 190 kW 이상(5일 조치)", "예측 185 kW 이상(10일 조치)"], [{ name: "시험 2주 최대수요전력(kW)", values: [204.0, 204.0, 204.0, 189.0] }],
    MX, 1.6, 6.6, 3.6, { dir: "col", title: "경보 기준별 시험 2주 최대수요전력(kW)", colors: [HX.accent2], fmt: "0.0", min: 170, max: 210, name: "예측 연동 운영 차트" });
  card(s, 7.45, 1.6, 5.28, 3.6, "규칙 카드");
  text(s, "운영 규칙", 7.67, 1.78, 4.8, 0.35, { fontSize: 15, bold: true, color: C.text1 });
  bullets(s, ["전날 일 최대 예측이 경보 기준 이상이면 조치일로 지정", "주간(8~17시) 설비 블록 15 kW를 저녁(17~24시)으로 이동", "옮긴 전력량은 예측 프로파일에서 여유가 큰 시간에 배분", "이 계획을 실측 부하에 적용해 평가(실측을 미리 알 필요 없음)"], 7.67, 2.2, 4.85, 2.9, { fontSize: 13 });
  const y = 5.45, w = 3.9, g = 0.215;
  [["-15 kW (-7.4%)", "기준 185 kW에서 시험 2주 최대수요전력 204 → 189 kW"],
   ["목표 - 예측오차", "기준을 190 kW로 두면 09-10(실측 204, 예측 187)을 놓쳐 효과 0. 일 최대 예측오차 약 6 kW를 빼야 한다"],
   ["-13,913원 / 2주", "저녁 일부가 22~24시 경부하 시간대로 가서 전력량요금도 줄어든다"]].forEach((c, i) => {
    const x = MX + i * (w + g);
    card(s, x, y, w, 1.42, "결과 카드");
    text(s, c[0], x + 0.22, y + 0.12, w - 0.44, 0.45, { fontSize: 19, bold: true, color: i === 0 ? C.accent2 : C.text1, valign: "middle" });
    text(s, c[1], x + 0.22, y + 0.62, w - 0.44, 0.75, { fontSize: 12 });
  });
}
{
  const s = content("예측 → 경보 → 유형별 조치 → 점검 → 재학습 절차로 현장에 적용한다", "6단계 · 현장 운영 절차와 요금 환산",
    "현장 적용 절차입니다. 전날 오후 생산계획이 확정되면 모델을 돌리고, 일 최대 예측이 185 이상이면 경보일로 지정합니다. 유형 1에는 설비를 한두 시간 먼저 켜고, 유형 2에는 생산 일부를 저녁으로 옮깁니다. 당일에는 피크 확률이 높은 시간대를 먼저 점검합니다. 여름 피크 1킬로와트를 줄이면 기본요금이 연 약 9만 원 줄어듭니다.");
  const steps = [["전일 오후", "생산계획 확정 직후 모델 실행. 96개 15분 예측, 80% 구간, 일 최대 예측"], ["경보일 지정", "일 최대 예측이 185 kW 이상이면 생산관리자에게 알림"], ["유형1 대비", "8시·13시에 한꺼번에 켜던 설비 일부를 1~2시간 먼저 가동. 재가동일은 반드시"], ["유형2 대비", "9~11시, 14~15시 생산 일부를 17시 이후로. 27℃ 이상 예보일 우선"], ["당일 점검", "예측값 170 kW 이상이거나 피크 확률이 높은 시간대를 먼저 점검하고 설비 추가 기동을 미룸"], ["사후 관리", "예측과 실측 비교, 특수일·점심 정지 여부 기록, 매주 재학습"]];
  const w = 1.92, g = 0.123, y = 1.65;
  steps.forEach((st, i) => {
    const x = MX + i * (w + g);
    card(s, x, y, w, 2.5, "절차 카드");
    s.addShape(pres.shapes.OVAL, { x: x + 0.2, y: y + 0.2, w: 0.5, h: 0.5, fill: { color: i === 2 || i === 3 ? C.accent1 : C.text1 }, line: { color: C.background2, width: 0 }, objectName: "절차 번호" });
    text(s, String(i + 1), x + 0.2, y + 0.2, 0.5, 0.5, { fontSize: 16, bold: true, color: C.background1, align: "center", valign: "middle" });
    text(s, st[0], x + 0.2, y + 0.82, w - 0.35, 0.4, { fontSize: 15, bold: true, color: C.text1 });
    text(s, st[1], x + 0.2, y + 1.22, w - 0.35, 1.2, { fontSize: 12 });
  });
  text(s, "요금 환산", MX, 4.35, 4, 0.35, { fontSize: 16, bold: true, color: C.text1 });
  table(s, ["항목", "값", "설명"], [
    ["요금 기준", "산업용(갑)Ⅱ 고압A 선택Ⅱ", "최대 222 kW로 계약전력 300 kW 미만 가정(한전 전기요금표 2023.05.16 시행)"],
    ["기본요금", "7,470원 / kW·월", "요금적용전력 = 직전 12개월 중 12·1·2·7·8·9월과 당월 최대수요전력의 최댓값"],
    ["1 kW 감소 효과", HL("연 89,640원"), "여름 피크를 낮추면 1년 동안 효과가 이어진다. 15 kW 감소는 연 약 134만 원"],
  ], MX, 4.75, CW, [2.1, 2.9, 7.13], { fontSize: 12, rowH: 0.4 });
  text(s, "금액이 작은 것은 이 공장이 200 kW 규모이기 때문이며, 감소 비율(약 6~7%)은 규모와 무관하다.", MX, 6.6, CW, 0.3, { fontSize: 12, color: C.accent5 });
}

// =====================================================================
section("정리");
{
  const s = content("차별점: 데이터 구조를 먼저 밝히고, 예측과 운영을 피크에 맞췄다", "정리 · 창의성과 차별성",
    "차별점 여섯 가지입니다. 복사일과 공장인원 누수를 찾아 검증과 입력 구성을 그에 맞췄고, 불균형 가중과 확률보정을 적용했고, 앙상블 다섯 종을 비교하고 일 최대 앙상블을 썼고, 예측구간을 보정했고, 재가동일과 피크 유형 같은 제조 지식을 결합했고, 예측을 선형계획과 요금으로 연결했습니다.");
  const items = [["증강·손상·누수 진단", "96개 값 비교로 복사일 160일 탐지, 행 정렬 오류와 공장인원 누수 발견", "무작위 분할 누수 58.3% 정량화"],
    ["불균형 학습과 확률보정", "피크 확률 모델에 불균형 가중, 등위 회귀 보정", "가중 시 재현율 0.92, Brier 0.049 → 0.047. 경보 시험 F1 0.46(베이스라인 0.37~0.39)"],
    ["앙상블", "설정 85가지 탐색, 앙상블 5종 비교, 일 최대 앙상블", "15분 예측은 검증 최저인 ExtraTrees 채택. 일 최대 MAE 14.7 → 5.82 kW"],
    ["불확실성 추정", "분위수 회귀 + 컨포멀 보정", "80% 구간 포함률 74.7% → 85.7%"],
    ["제조지식 결합", "재가동일, 첫·마지막 생산 시각, 냉방도, 피크 두 유형", "유형별로 원인과 대책을 분리"],
    ["예측과 운영·비용 연결", "전력량 보존 부하 이동 선형계획, 예측오차를 반영한 경보 기준, 한전 요금 환산", "시험 2주 최대수요전력 -15 kW(-7.4%)"]];
  const w = 3.9, g = 0.215, h = 2.5;
  items.forEach((it, i) => {
    const x = MX + (i % 3) * (w + g), y = 1.65 + Math.floor(i / 3) * (h + 0.2);
    card(s, x, y, w, h, "차별점 카드");
    text(s, it[0], x + 0.22, y + 0.17, w - 0.44, 0.4, { fontSize: 16, bold: true, color: C.text1 });
    text(s, it[1], x + 0.22, y + 0.65, w - 0.44, 0.95, { fontSize: 13 });
    text(s, it[2], x + 0.22, y + 1.65, w - 0.44, 0.75, { fontSize: 13, bold: true, color: C.accent2 });
  });
}
{
  const s = content("평가 6개 항목에 모두 대응했고, 노트북 한 번 실행으로 재현된다", "정리 · 평가 항목 대응과 재현성",
    "서면평가 여섯 항목에 대한 대응을 정리했습니다. 평가 문구가 분류 과제용이라, 180킬로와트 이상을 사건으로 정의해 F1과 놓친 피크, 헛경보를 계산했습니다. 코드는 노트북 한 번 실행으로 전처리부터 결과 생성까지 자동으로 진행됩니다.");
  table(s, ["평가 항목(배점)", "대응 내용", "단계"], [
    ["1. 데이터 이해 및 진단(15)", "변수 의미, 생산단위와 시간·설비·제품 관계, 결측·중복(복사일)·이상치·불균형, 전처리, 시간 순 검증전략", "0"],
    ["2. AI 예측모델 개발(40)", "전력량: 베이스라인 포함 11개 모델, 입력 검증, 설정 85가지 탐색, 앙상블 5종, 선정 근거. 피크 확률: 6개 방식 F1·PR-AUC 비교", "1"],
    ["3. 영향요인 및 오류분석(15)", "SHAP 영향변수·상호작용, 조건별 오차, 놓친 피크(FN)·헛경보(FP) 집중 조건", "1, 2, 5"],
    ["4. 현장 활용방안(10)", "하루 전 경보, 확률 기반 점검 우선순위, 유형별 조치, 작업자 알림 절차, 예측 연동 검증", "1, 6"],
    ["5. 창의성·차별성(10)", "불균형 학습, 앙상블, 불확실성 추정, 확률보정, 제조지식 결합, 선형계획", "0, 1, 4, 6"],
    ["6. 코드 및 재현성(10)", "노트북 한 번 실행으로 전처리 → 학습 → 추론 → 분석 → 결과 생성. 시드·스레드·패키지 버전 고정", "전체"],
  ], MX, 1.65, CW, [2.9, 8.1, 1.13], { fontSize: 12, rowH: 0.5 });
  card(s, MX, 5.3, 6.0, 1.55, "제출물 카드");
  text(s, "소스코드 제출물 구성", MX + 0.22, 5.42, 5.5, 0.35, { fontSize: 14, bold: true, color: C.text1 });
  text(s, "analysis.ipynb(모든 코드·설명·결과) / requirements.txt / data(학습용 데이터) / README / predictions(테스트 예측결과 3개 파일)", MX + 0.22, 5.8, 5.55, 1.0, { fontSize: 12 });
  card(s, 6.8, 5.3, 5.93, 1.55, "재현성 카드");
  text(s, "재현성", 7.02, 5.42, 5.5, 0.35, { fontSize: 14, bold: true, color: C.text1 });
  text(s, "제출 폴더 안에서 처음부터 실행해 오류 없이 완료(약 15~25분). 탐색 30분은 기록된 최적 설정으로 대체하며 옵션으로 재실행 가능", 7.02, 5.8, 5.5, 1.0, { fontSize: 12 });
}
{
  const s = content("외부 데이터는 두 가지만 썼고, 가정과 한계를 분명히 한다", "정리 · 외부 데이터와 한계",
    "외부 데이터는 공휴일 달력과 한전 전기요금표 두 가지이며 모두 공개 자료입니다. 한계도 분명히 합니다. 기상은 실측을 예보 대신 썼고, 옮길 수 있는 부하 비율은 가정값이며, 저녁 생산은 인건비가 1.5배인 시간대이고, 원본 구간이 여름뿐이라 겨울 피크는 검증하지 못했습니다.");
  text(s, "외부 데이터 활용 내역", MX, 1.6, 6, 0.35, { fontSize: 16, bold: true, color: C.text1 });
  table(s, ["데이터", "출처", "활용 사유", "활용 방법"], [
    ["대한민국 법정공휴일(2021)", "python-holidays 패키지(공개 오픈소스)", "공휴일 가동 패턴 반영", "공휴일 여부 변수"],
    ["전기요금표", "한국전력공사 전기요금표(종합), 2023.05.16 시행", "피크 저감량을 비용으로 환산", "기본요금 7,470원/kW·월, 시간대별 전력량요금"],
  ], MX, 2.0, CW, [2.8, 4.1, 2.6, 2.63], { fontSize: 12, rowH: 0.5 });
  text(s, "한계와 다음 단계", MX, 3.75, 6, 0.35, { fontSize: 16, bold: true, color: C.text1 });
  const lim = [["기상 예보", "실측 기상을 예보 대신 썼다. 기상을 빼도 오차 증가는 약 1.3 kW라 영향은 이 범위 안이다"],
    ["이동 가능 부하", "옮길 수 있는 비율 20%와 블록 15 kW는 가정값이다. 설비별 전력 계측으로 확인해야 한다"],
    ["인건비", "저녁 생산은 인건비가 1.5배인 시간대다. 인력 운영과 함께 설계해야 한다"],
    ["계절", "원본 구간이 7~9월뿐이라 겨울(난방) 피크는 검증하지 못했다"]];
  const w = 2.87, g = 0.207, y = 4.2;
  lim.forEach((c, i) => {
    const x = MX + i * (w + g);
    card(s, x, y, w, 2.0, "한계 카드");
    text(s, c[0], x + 0.2, y + 0.15, w - 0.4, 0.35, { fontSize: 15, bold: true, color: C.text1 });
    text(s, c[1], x + 0.2, y + 0.58, w - 0.4, 1.35, { fontSize: 12 });
  });
  text(s, "데이터 출처: 중소벤처기업부, Korea AI Manufacturing Platform(KAMP), 자원 최적화 AI 데이터셋, KAIST(울산과학기술원, (주)유피시앤에스), 2021.12.27., www.kamp-ai.kr", MX, 6.4, CW, 0.5, { fontSize: 11, color: C.accent5 });
}
{
  const s = pres.addSlide({ masterName: "COVER", sectionTitle: SEC });
  s.addText("결론", { x: 0.9, y: 1.45, w: 11.5, h: 0.4, fontSize: 15, bold: true, color: C.accent1, margin: 0, isTextBox: true });
  s.addText("피크를 하루 전에 알고,\n유형에 맞춰 줄인다", { placeholder: "title" });
  s.addText("시험 MAE 6.47 kW · 일 최대 예측 오차 5.82 kW · 피크 두 유형 · 최대수요전력 204 → 189 kW", { placeholder: "body" });
  s.addNotes("정리하면, 생산계획만으로 하루 전에 15분 단위 전력과 일 최대를 예측하고, 피크가 두 유형이라는 것을 밝혀 유형별 조치를 제안했습니다. 예측에 연동한 운영으로 최대수요전력을 7퍼센트 낮출 수 있었습니다. 감사합니다.");
}

(async () => {
  if (SPEC_ONLY) {
    fs.mkdirSync(path.join(__dirname, "charts"), { recursive: true });
    fs.writeFileSync(path.join(__dirname, "charts", "specs.json"), JSON.stringify(CHART_SPECS, null, 1));
    console.log("chart specs", CHART_SPECS.length);
    return;
  }
  await pres.writeFile({ fileName: OUTF });
  await applyTheme(OUTF, THEME);
  console.log("written", OUTF);
})();
