# CCTV Incident Summariser

AI video analytics pipeline: upload CCTV-style footage → FFmpeg normalisation → scene-change keyframes → YOLOv8 detection → Postgres → LLM-written incident report → React dashboard.

> 🚧 Work in progress. Full documentation, architecture diagram and benchmark results coming soon.

## Stack
Python · FastAPI · FFmpeg · PySceneDetect · OpenCV · YOLOv8 · PostgreSQL · Claude API · React + TypeScript + Tailwind

_Only public or synthetic footage is used in this project._
