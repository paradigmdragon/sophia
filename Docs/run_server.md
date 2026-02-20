# Sophia API 실행 가이드

## 단일 서버 실행 (권장)

프로젝트 루트에서 실행:

```bash
make api
```

동일 동작(직접 스크립트):

```bash
./scripts/run_api.sh
```

- 내부 동작:
  - `.venv` 활성화
  - FastAPI ASGI 엔트리포인트 자동 탐색 (`scripts/find_asgi_app.py`)
  - `uvicorn <module>:<app> --host 0.0.0.0 --port 8090` 실행

## 로컬 전용 실행

```bash
make api-local
# 또는
./scripts/run_api_local.sh
```

- `127.0.0.1:8090` 로만 바인딩됩니다.
- 같은 Wi-Fi의 iPhone/iPad/다른 PC에서는 접근할 수 없습니다.

## iPhone/LAN 접속 조건

1. 서버를 `0.0.0.0`으로 실행 (`make api`)
2. Mac과 iPhone이 같은 Wi-Fi
3. Mac 방화벽에서 Python/uvicorn 인바운드 허용
4. iPhone에서 접속:

```text
http://<맥의 LAN IP>:8090/docs
```

LAN IP 확인 예시:

```bash
ipconfig getifaddr en0
```

## 실행 확인 (DOD 자동화)

```bash
make test-smoke
```

검증 항목:

1. `lsof`로 `8090` LISTEN 확인 (`0.0.0.0` 또는 `*`)
2. `POST /chat/messages` HTTP 200 확인
3. `/docs` HTTP 200/302 확인
4. `/openapi.json` HTTP 200 확인

## 문제 해결

### 증상: 로컬에서는 되는데 iPhone에서 접속 불가
- 원인: `127.0.0.1` 바인딩으로 실행됨
- 해결: `make api`로 재실행 (0.0.0.0 바인딩)

### 증상: `make test-smoke`가 포트 충돌로 실패
- 원인: 이미 8090 서버가 실행 중
- 해결: 기존 프로세스 종료 후 재실행

### 증상: `/docs`가 안 열림
- 원인: 서버 미기동/방화벽/잘못된 IP
- 해결: `make test-smoke`로 상태 점검 후 방화벽 허용 확인
