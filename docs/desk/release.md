# 데모 배포와 검증 버전

[최종 회귀 수정·평가·공개 파일 대조](audit.md)

## 두 보고서 비교 배포

근본 원인 구절 두 개를 독립적으로 검색·검증하는 버전은 [`3b2f3ee`](https://github.com/sokldjs554/five-whys-agent/tree/3b2f3eeffe19454a11e6fd393b57fbd4eab0470c)이다. Redis를 포함한 CI에서 테스트 131개가 통과했다. 공개 재생본은 [`b4a6df1`](https://github.com/sokldjs554/five-whys-agent/tree/b4a6df16480be6491372812a7c8b6fd5c5ece516/desk)이며 첫 버전의 보류 기록과 개선 뒤의 성공 기록을 모두 포함한다. [회귀 테스트](https://github.com/sokldjs554/five-whys-agent/actions/runs/45957281724) · [비교 화면](https://sokldjs554.github.io/five-whys-agent/desk/?run=claude-hold-03) · [실행 기록과 비교 평가](evaluation/comparison/) · [PC 화면](captures/comparison-1440.png) · [모바일 화면](captures/comparison-390.png)

## Claude 추가 검증

같은 합성 주문 장애의 기존 개발 질문 2개를 GitHub Actions에서 한 번씩 실행했다. Claude Haiku 5.5가 각 요청에서 세 개의 네이티브 도구 호출을 제안했다. Python에서 인자를 검사하고 MCP로 실행한 뒤 두 답변 모두 배포·로그·과거 문서 인용 기준을 통과했다. 각 실행에서 실제 모델 요청은 한 번이었다. 독립 블라인드 평가 결과는 기존 문서에 따로 집계돼 있다. [검증 코드 버전](https://github.com/sokldjs554/five-whys-agent/tree/fe9f0ecb6de2210359888b37c34548fd82ce2819) · [Actions 실행](https://github.com/sokldjs554/five-whys-agent/actions/runs/45952285053) · [실행 원본·채점](evaluation/claude-actions.json) · [한국어 공개 기록](https://sokldjs554.github.io/five-whys-agent/desk/?run=claude-dev-01)

## 첫 배포 검증 기록

2026-11-27에 검증한 구현은 [`a3613c4`](https://github.com/sokldjs554/five-whys-agent/tree/a3613c498c578f9fec8e206d920b0d7fcc609c23)이다. GitHub Pages는 [`c76ff21`](https://github.com/sokldjs554/five-whys-agent/tree/c76ff21e298c766405d30fbf6ee3eda31523f9b0/desk)에서 같은 정적 파일 네 개를 제공한다. [공개 데모](https://sokldjs554.github.io/five-whys-agent/desk/) · [Pages 배포 실행](https://github.com/sokldjs554/five-whys-agent/actions/runs/45948596433)

| 검증 | 관측 |
|---|---|
| 회귀 테스트 | 로컬 Python 3.12에서 전용 Redis를 연결해 114개 통과. GitHub의 새 Linux 러너에서도 통과. [JUnit 원본](evaluation/pytest.xml) · [GitHub CI](https://github.com/sokldjs554/five-whys-agent/actions/runs/45948584347) |
| 공개 파일 | 실제 공개 서버에서 index.html, style.css, app.js, runs.json을 받아 테스트한 소스와 바이트 단위로 대조했다. 기록 7건의 JSON SHA-256은 `aa033e8409d0c0679cd4067c19b2a84af19bd5b7be8865a9ab4e3a68c7ea3317`이다. [첫 배포 JSON](https://github.com/sokldjs554/five-whys-agent/blob/c76ff21e298c766405d30fbf6ee3eda31523f9b0/desk/runs.json) |
| 공개 화면 | 인증하지 않은 Chromium 1440px와 390px에서 HTTP 200 확인. 첫 한국어 기록 dev-01, Qwen 표시, 도구 호출 3건, 원문 이동, hold-05 선택, 판단 보류, 도구 상세 열기, 가로 넘침과 페이지 예외 유무를 검사했다. [PC 캡처](captures/desktop.png) · [모바일 캡처](captures/mobile.png) · [모바일 기록 선택](captures/mobile-selection.png) |
| 로컬 실시간 조사 | 같은 화면에 자유 질문을 접수해 규칙과 Qwen 경로를 확인했다. [로컬 화면](captures/local-inquiry.png) · [브라우저 점검 원본](captures/browser-check.txt) · [HTTP 조사·후속 대화](evaluation/http-rules.json) |

이 버전에서 모델을 실제 호출한 경로는 로컬 Qwen이다. 공개 재생 데이터에는 질문, 도구 입력과 반환값, 출처, 판단 결과, 가능한 경우 모델 요청 ID·토큰 수가 담겨 있다. 기존 Claude 기록에는 그 실행의 별도 소스 리비전이 표시되어 있다.
