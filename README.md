# CCTV Incident Summariser

[![CI](https://github.com/Hassan-GITHUB48/cctv-summariser/actions/workflows/ci.yml/badge.svg)](https://github.com/Hassan-GITHUB48/cctv-summariser/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

AI video analytics pipeline: upload CCTV-style footage → FFmpeg normalisation → scene-change keyframes → YOLOv8 detection → Postgres → LLM-written incident report → React dashboard.

> 🚧 Work in progress. Full documentation, architecture diagram and benchmark results coming soon.

## Stack
Python · FastAPI · FFmpeg · PySceneDetect · OpenCV · YOLOv8 · PostgreSQL · Claude API · React + TypeScript + Tailwind

_Only public or synthetic footage is used in this project._

## Development
```bash
make setup      # venv + dependencies + .env
make test       # starts Postgres, runs pytest (make test-fast skips YOLO tests)
make lint       # ruff, same checks as CI
make run        # API on http://localhost:8000/docs
```
