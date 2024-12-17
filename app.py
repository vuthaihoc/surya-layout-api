from fastapi import FastAPI, File, UploadFile, Query, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import io
from PIL import Image
import pypdfium2
from surya.detection import batch_text_detection
from surya.layout import batch_layout_detection  # Import your layout detection function
# from surya.model.detection.model import load_model, load_processor  # Import model loading functions
from surya.model.layout.model import load_model
from surya.model.layout.processor import load_processor
from surya.ocr import run_ocr
from surya.postprocessing.heatmap import draw_polys_on_image

from surya.model.detection.model import load_model as load_det_model, load_processor as load_det_processor
from surya.model.recognition.model import load_model as load_rec_model
from surya.model.recognition.processor import load_processor as load_rec_processor

# Initialize FastAPI
app = FastAPI()

# Allow CORS for all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load models once when the application starts
model = load_model()
processor = load_processor()
det_processor, det_model = load_det_processor(), load_det_model()
rec_model, rec_processor = load_rec_model(), load_rec_processor()

@app.post("/detect_text/")
async def detect_text(file: UploadFile = File(...), lang: str = "en,vi"):
    try:
        image = Image.open(file.file)
        langs = lang.split(",")  # Chia tách ngôn ngữ
        predictions = run_ocr([image], [langs], det_model, det_processor, rec_model, rec_processor)

        # Ghép văn bản thành các đoạn văn
        text_output = []
        for prediction in predictions:
            for line in prediction.text_lines:
                text_output.append(line.text)

        return {"text": "\n".join(text_output), "predictions": predictions}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/detect_layout/")
async def detect_layout(file: UploadFile = File(...), return_image: bool = Query(False)):
    try:
        # Read the uploaded file
        contents = await file.read()
        file_type = file.content_type

        # Check if the file is a PDF or an image
        pil_image = Image.open(io.BytesIO(contents)).convert("RGB")

        # Perform layout detection
        # line_predictions = batch_text_detection([pil_image], model, processor)
        layout_predictions = batch_layout_detection([pil_image], model, processor)

        # Create a result image with bounding boxes
        layout_image = draw_polys_on_image([p.polygon for p in layout_predictions[0].bboxes], pil_image.copy(), labels=[p.label for p in layout_predictions[0].bboxes])

        if return_image:
            # Return the image with layout bounding boxes
            img_byte_arr = io.BytesIO()
            layout_image.save(img_byte_arr, format='PNG')
            img_byte_arr.seek(0)
            return StreamingResponse(img_byte_arr, media_type="image/png")
        else:
            # Return JSON response with layout data
            layout_data = [p.model_dump() for p in layout_predictions[0].bboxes]
            return JSONResponse(content={"layout": layout_data})

    except Exception as e:
        return JSONResponse(status_code=500, content={"message": str(e)})

# Run the application
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=5000, workers=2)