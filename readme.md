# Surya Layout Api


## Require 
- fastapi 
- uvicorn
- surya-ocr

## Routes

- `/detect_layout/`
  - Return layout in json format
- `/detect_layout/?return_image=true`
  - Return image of detected layout bboxes

## Run
- make venv
- install requirements
- run

```bash
python -m uvicorn app:app --port 5000
```
