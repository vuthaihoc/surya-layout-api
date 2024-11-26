from fastapi import FastAPI, File, UploadFile, Query
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import io
from PIL import Image
import pypdfium2
from surya.detection import batch_text_detection
from surya.layout import batch_layout_detection  # Import your layout detection function
from surya.model.detection.model import load_model, load_processor  # Import model loading functions
from surya.postprocessing.heatmap import draw_polys_on_image
from surya.settings import settings

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
layout_model = load_model(checkpoint=settings.LAYOUT_MODEL_CHECKPOINT)
layout_processor = load_processor(checkpoint=settings.LAYOUT_MODEL_CHECKPOINT)

@app.post("/detect_layout/")
async def detect_layout(file: UploadFile = File(...), return_image: bool = Query(False)):
    try:
        # Read the uploaded file
        contents = await file.read()
        file_type = file.content_type

        # Check if the file is a PDF or an image
        pil_image = Image.open(io.BytesIO(contents)).convert("RGB")

        # Perform layout detection
        line_predictions = batch_text_detection([pil_image], model, processor)
        layout_predictions = batch_layout_detection([pil_image], layout_model, layout_processor, line_predictions)

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