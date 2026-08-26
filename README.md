retail-ai/
├── cv/
│   ├── config.py       # Centralized settings (Thresholds, Line Coordinates, API ports)
│   ├── detector.py     # YOLOv8n model initialization and inference
│   ├── tracker.py      # ByteTrack logic and ID persistence
│   ├── counter.py      # Virtual line crossing math and occupancy state
│   └── heatmap.py      # OpenCV spatial accumulation and color mapping
├── backend/
│   ├── api.py          # FastAPI routing and endpoints
│   └── database.py     # SQLite table creation and data logging
├── data/               # Output directory (retail_ai.db, heatmap.png, sample videos)
├── models/             # Local weights (yolov8n.pt)
└── main.py             # Orchestrator tying threads and state together

1. The Dual-Thread Architecture
When you run python3 main.py, your program splits into two parallel tasks:

Thread 1 (The Web Server): It launches FastAPI in the background. This sits quietly at [http://0.0.0.0:8000](http://0.0.0.0:8000), waiting for a frontend dashboard to ask it for data.

Thread 2 (The CV Loop): It opens your video file (sample.mp4) and starts processing it frame by frame in an infinite loop.

2. The Computer Vision Pipeline (Frame-by-Frame)
For every frame of the video, your code performs a sequence of five operations:

Detection (detector.py): Your YOLOv8n model scans the image and draws bounding boxes specifically around people, ignoring cars or bicycles.

Tracking (tracker.py): The ByteTrack algorithm looks at the detections and assigns a unique, persistent ID to each person (e.g., "ID 27"). This ensures the system knows that the person in frame 1 is the same person in frame 2.

Counting (counter.py): The code calculates the center of the bounding box (the person's location). It checks if that point has crossed the virtual red line you saw on your screen. If they cross it in one direction, it triggers an ENTRY; in the other, an EXIT. It updates the live Occupancy accordingly.

Heatmap Generation (heatmap.py): The system takes the coordinates of every tracked person's feet and plots a "heat" point on a blank canvas. Over time, areas with more foot traffic get brighter/warmer. It automatically saves this canvas as heatmap.png every few seconds.

Display (draw_overlay): It draws the bounding boxes, the IDs, the red line, and the text overlay (In/Out/Occupancy) directly onto the video frame and displays it in the popup window.

3. The Database Engine (database.py)
While the CV pipeline is running, it constantly talks to your SQLite database (retail_ai.db):

Every time a person crosses the line, it logs an event (track_id, event_type, timestamp).

Every few frames, it logs the exact X/Y coordinates of every tracked person.

Every few seconds, it logs a snapshot of the current occupancy.

4. The Bridge (State Sharing)
Because your CV loop and your API are running at the same time, main.py shares the live data between them using fastapi_app.state. This means that when someone visits [http://127.0.0.1:8000/stats](http://127.0.0.1:8000/stats) in their browser, the API can instantly grab the absolute latest In/Out numbers from the CV loop and display them as JSON.

In summary: built a system that turns a raw video feed into structured, actionable retail data—all optimized to run entirely on the edge (your Raspberry Pi).
