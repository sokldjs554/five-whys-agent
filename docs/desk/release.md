# 데모 배포와 검증 버전

2026-11-27에 검증한 구현은 [`a3613c4`](https://github.com/sokldjs554/five-whys-agent/tree/a3613c498c578f9fec8e206d920b0d7fcc609c23)이다. GitHub Pages는 [`c76ff21`](https://github.com/sokldjs554/five-whys-agent/tree/c76ff21e298c766405d30fbf6ee3eda31523f9b0/desk)에서 같은 정적 파일 네 개를 제공한다. [공개 데모](https://sokldjs554.github.io/five-whys-agent/desk/) · [Pages 배포 실행](https://github.com/sokldjs554/five-whys-agent/actions/runs/45948596433)

| 검증 | 관측 |
|---|---|
| 회귀 테스트 | 로컬 Python 3.12에서 전용 Redis를 연결해 114개 통과. GitHub의 새 Linux 러너에서도 통과. [JUnit 원본](evaluation/pytest.xml) · [GitHub CI](https://github.com/sokldjs554/five-whys-agent/actions/runs/45948584347) |
| 공개 파일 | 실제 공개 서버에서 index.html, style.css, app.js, runs.json을 받아 테스트한 소스와 바이트 단위로 대조했다. 기록 7건의 JSON SHA-256은 `aa033e8409d0c0679cd4067c19b2a84af19bd5b7be8865a9ab4e3a68c7ea3317`이다. [공개 JSON](https://sokldjs554.github.io/five-whys-agent/desk/runs.json) |
| 공개 화면 | 인증하지 않은 Chromium 1440px와 390px에서 HTTP 200 확인. 첫 한국어 기록 dev-01, Qwen 표시, 도구 호출 3건, 원문 이동, hold-05 선택, 판단 보류, 도구 상세 열기, 가로 넘침과 페이지 예외 유무를 검사했다. [PC 캡처](captures/desktop.png) · [모바일 캡처](captures/mobile.png) · [모바일 기록 선택](captures/mobile-selection.png) |
| 로컬 실시간 조사 | 같은 화면에 자유 질문을 접수해 규칙과 Qwen 경로를 확인했다. [로컬 화면](captures/local-inquiry.png) · [브라우저 점검 원본](captures/browser-check.txt) · [HTTP 조사·후속 대화](evaluation/http-rules.json) |

이 버전에서 모델을 실제 호출한 경로는 로컬 Qwen이다. 공개 재생 데이터에는 질문, 도구 입력과 반환값, 출처, 판단 결과, 가능한 경우 모델 요청 ID·토큰 수가 담겨 있다. 기존 Claude 기록에는 그 실행의 별도 소스 리비전이 표시되어 있다.
