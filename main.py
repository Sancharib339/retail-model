"""
Entry point: wires together detection, tracking, counting, heatmap generation,
SQLite logging, and the FastAPI dashboard API into a single running pipeline.

The FastAPI server runs in a background thread while the video capture loop
owns the main thread — both share state via fastapi_app.state.*
"""
import logging
import threading
import time

import cv2
import uvicorn

from cv import config
from cv.detector import PersonDetector
from cv.tracker import Tracker
from cv.counter import LineCounter
from cv.heatmap import HeatmapGenerator
from backend.database import Database
from backend.api import app as fastapi_app

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("main")


def draw_overlay(frame, tracks, stats):
    cv2.line(frame, config.LINE_START, config.LINE_END, (0, 0, 255), 2)
    for t in tracks:
        x1, y1, x2, y2 = [int(v) for v in t["bbox"]]
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.circle(frame, (cx, cy), 3, (0, 255, 255), -1)
        cv2.putText(frame, f"ID {t['id']}", (x1, max(y1 - 8, 0)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
    text = f"Occupancy: {stats['occupancy']}  In: {stats['entries']}  Out: {stats['exits']}"
    cv2.putText(frame, text, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    return frame


def run_api_server():
    uvicorn.run(fastapi_app, host=config.API_HOST, port=config.API_PORT, log_level="warning")


def main():
    logger.info("Initializing Edge AI Retail Intelligence Platform ...")

    detector = PersonDetector(
        model_path=config.MODEL_PATH,
        conf_threshold=config.CONFIDENCE_THRESHOLD,
        iou_threshold=config.IOU_THRESHOLD,
        imgsz=config.INFERENCE_SIZE,
        device=config.DEVICE,
        person_class_id=config.PERSON_CLASS_ID,
    )
    tracker = Tracker(
        max_age=config.MAX_TRACK_AGE,
        min_hits=config.MIN_HITS,
        iou_threshold=config.IOU_MATCH_THRESHOLD,
    )
    counter = LineCounter(
        line_start=config.LINE_START,
        line_end=config.LINE_END,
        margin=config.LINE_MARGIN,
    )
    heatmap = HeatmapGenerator(
        width=config.FRAME_WIDTH,
        height=config.FRAME_HEIGHT,
        blur_kernel_size=config.HEATMAP_BLUR_KERNEL,
        point_radius=config.HEATMAP_POINT_RADIUS,
        decay_factor=config.HEATMAP_DECAY,
    )
    db = Database(config.DB_PATH)

    # Share state with the FastAPI app (read by /stats and /heatmap)
    fastapi_app.state.counter = counter
    fastapi_app.state.tracker = tracker
    fastapi_app.state.heatmap = heatmap
    fastapi_app.state.db = db
    fastapi_app.state.start_time = time.time()

    threading.Thread(target=run_api_server, daemon=True).start()
    logger.info(f"Dashboard API running at http://{config.API_HOST}:{config.API_PORT}")

    cap = cv2.VideoCapture("data/sample.mp4")
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.FRAME_HEIGHT)
    if not cap.isOpened():
        logger.error("Cannot open camera source. Exiting.")
        return

    frame_count = 0
    last_occupancy_log = time.time()
    last_cleanup = time.time()

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                logger.info("End of video file. Restarting loop for testing...")
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0) # Reset video to beginning
                continue

            frame_count += 1
            frame = cv2.resize(frame, (config.FRAME_WIDTH, config.FRAME_HEIGHT))

            if frame_count % config.FRAME_SKIP != 0:
                continue  # skip inference on this frame to save CPU cycles

            detections = detector.detect(frame)
            tracks = tracker.update(detections)

            centroids = [
                ((t["bbox"][0] + t["bbox"][2]) / 2, (t["bbox"][1] + t["bbox"][3]) / 2)
                for t in tracks
            ]
            heatmap.update(centroids)

            events = counter.update(tracks)
            for ev in events:
                db.log_event(ev["track_id"], ev["event_type"], ev["x"], ev["y"])

            if frame_count % config.POSITION_LOG_EVERY_N_FRAMES == 0:
                for t, (x, y) in zip(tracks, centroids):
                    db.log_position(t["id"], x, y)

            if time.time() - last_occupancy_log > config.OCCUPANCY_LOG_INTERVAL_SECONDS:
                stats = counter.get_stats()
                db.log_occupancy(stats["occupancy"], stats["entries"], stats["exits"])
                last_occupancy_log = time.time()

            if time.time() - last_cleanup > 60:
                counter.cleanup()
                last_cleanup = time.time()

            if frame_count % config.HEATMAP_AUTOSAVE_INTERVAL_FRAMES == 0:
                heatmap.save(config.HEATMAP_SAVE_PATH)

            if config.DISPLAY_WINDOW:
                stats = counter.get_stats()
                annotated = draw_overlay(frame.copy(), tracks, stats)
                cv2.imshow("Edge AI Retail Intelligence Platform", annotated)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    logger.info("Quit key pressed, shutting down ...")
                    break

    except KeyboardInterrupt:
        logger.info("Interrupted by user, shutting down ...")
    finally:
        cap.release()
        cv2.destroyAllWindows()
        heatmap.save(config.HEATMAP_SAVE_PATH)
        db.close()
        logger.info("Shutdown complete.")


if __name__ == "__main__":
    main()
