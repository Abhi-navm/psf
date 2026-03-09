"""
Face region detection for videos with webcam overlays.
Dynamically detects if a video has a small face overlay (e.g., presentation + webcam)
and returns the crop region to focus on for facial/pose analysis.
"""

from typing import Dict, Any, List, Optional, Tuple
import os

from app.core.logging import logger


class FaceRegionDetector:
    """
    Detect face regions in video frames to handle webcam overlay layouts.
    
    Supports:
    - Full-frame person (regular video) → no cropping needed
    - Small webcam overlay (presentation + person in corner) → crop to overlay region
    - No person visible → returns None
    """
    
    # If face bounding box is smaller than this fraction of frame, it's an overlay
    OVERLAY_THRESHOLD = 0.25  # face region < 25% of frame area = overlay
    
    # Padding around detected face region (as fraction of region size)
    PADDING_FACTOR = 0.8  # 80% padding around face for body inclusion
    
    # Minimum number of frames with face detected to consider valid
    MIN_DETECTIONS = 2
    
    # Number of sample frames to check
    SAMPLE_COUNT = 5
    
    def __init__(self):
        self._face_cascade = None
    
    @property
    def face_cascade(self):
        """Lazy load OpenCV Haar cascade face detector."""
        if self._face_cascade is None:
            import cv2
            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            self._face_cascade = cv2.CascadeClassifier(cascade_path)
            logger.info("Haar cascade face detector loaded")
        return self._face_cascade
    
    def detect_face_region(
        self, frames: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Analyze sample frames to detect the face/person region.
        
        Args:
            frames: List of frame info dicts with 'path' and 'timestamp'
            
        Returns:
            Dict with:
                - 'has_face': bool - whether a face was detected
                - 'is_overlay': bool - whether the face is a small overlay
                - 'crop_region': Optional tuple (x, y, w, h) - region to crop to
                - 'frame_size': tuple (width, height) of original frame
                - 'face_area_ratio': float - ratio of face region to frame area
        """
        import cv2
        
        if not frames:
            return {
                "has_face": False,
                "is_overlay": False,
                "crop_region": None,
                "frame_size": (0, 0),
                "face_area_ratio": 0.0,
            }
        
        # Sample evenly spaced frames
        sample_indices = self._get_sample_indices(len(frames), self.SAMPLE_COUNT)
        
        detections = []
        frame_size = None
        
        for idx in sample_indices:
            frame_path = frames[idx].get("path")
            if not frame_path or not os.path.exists(frame_path):
                continue
            
            image = cv2.imread(frame_path)
            if image is None:
                continue
            
            h, w = image.shape[:2]
            frame_size = (w, h)
            
            # Detect faces
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            faces = self.face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(30, 30),
            )
            
            if len(faces) > 0:
                # Pick the largest face (most likely the real person)
                largest_face = max(faces, key=lambda f: f[2] * f[3])
                fx, fy, fw, fh = largest_face
                detections.append({
                    "x": fx, "y": fy, "w": fw, "h": fh,
                    "frame_w": w, "frame_h": h,
                })
        
        if len(detections) < self.MIN_DETECTIONS:
            logger.info("No consistent face detected in sample frames")
            return {
                "has_face": False,
                "is_overlay": False,
                "crop_region": None,
                "frame_size": frame_size or (0, 0),
                "face_area_ratio": 0.0,
            }
        
        # Calculate the average/consensus face position
        avg_x = int(sum(d["x"] for d in detections) / len(detections))
        avg_y = int(sum(d["y"] for d in detections) / len(detections))
        avg_w = int(sum(d["w"] for d in detections) / len(detections))
        avg_h = int(sum(d["h"] for d in detections) / len(detections))
        frame_w = detections[0]["frame_w"]
        frame_h = detections[0]["frame_h"]
        
        # Calculate area ratio
        face_area = avg_w * avg_h
        frame_area = frame_w * frame_h
        face_area_ratio = face_area / frame_area if frame_area > 0 else 0
        
        is_overlay = face_area_ratio < self.OVERLAY_THRESHOLD
        
        if is_overlay:
            # Calculate expanded crop region (include body below face)
            crop_region = self._calculate_crop_region(
                avg_x, avg_y, avg_w, avg_h, frame_w, frame_h
            )
            logger.info(
                f"Webcam overlay detected: face at ({avg_x},{avg_y}) size {avg_w}x{avg_h}, "
                f"area ratio={face_area_ratio:.3f}, crop region={crop_region}"
            )
        else:
            crop_region = None
            logger.info(
                f"Full-frame person detected: face area ratio={face_area_ratio:.3f}, "
                f"no cropping needed"
            )
        
        return {
            "has_face": True,
            "is_overlay": is_overlay,
            "crop_region": crop_region,
            "frame_size": (frame_w, frame_h),
            "face_area_ratio": round(face_area_ratio, 4),
        }
    
    def crop_frame(
        self, image, crop_region: Tuple[int, int, int, int]
    ):
        """
        Crop an image to the specified region.
        
        Args:
            image: OpenCV image (numpy array)
            crop_region: (x, y, w, h) tuple
            
        Returns:
            Cropped image
        """
        x, y, w, h = crop_region
        return image[y:y+h, x:x+w]
    
    def create_cropped_frames(
        self,
        frames: List[Dict[str, Any]],
        crop_region: Tuple[int, int, int, int],
        output_dir: str,
    ) -> List[Dict[str, Any]]:
        """
        Create cropped versions of frames focused on the person region.
        
        Args:
            frames: Original frame info dicts
            crop_region: (x, y, w, h) tuple to crop to
            output_dir: Directory to save cropped frames
            
        Returns:
            New list of frame info dicts pointing to cropped images
        """
        import cv2
        
        os.makedirs(output_dir, exist_ok=True)
        cropped_frames = []
        
        for frame_info in frames:
            frame_path = frame_info.get("path")
            if not frame_path or not os.path.exists(frame_path):
                continue
            
            image = cv2.imread(frame_path)
            if image is None:
                continue
            
            cropped = self.crop_frame(image, crop_region)
            
            # Save cropped frame
            filename = f"cropped_{os.path.basename(frame_path)}"
            cropped_path = os.path.join(output_dir, filename)
            cv2.imwrite(cropped_path, cropped)
            
            cropped_frames.append({
                "path": cropped_path,
                "timestamp": frame_info.get("timestamp", 0),
                "frame_number": frame_info.get("frame_number", 0),
                "original_path": frame_path,
            })
        
        logger.info(f"Created {len(cropped_frames)} cropped frames in {output_dir}")
        return cropped_frames
    
    def _calculate_crop_region(
        self,
        face_x: int, face_y: int,
        face_w: int, face_h: int,
        frame_w: int, frame_h: int,
    ) -> Tuple[int, int, int, int]:
        """
        Calculate the crop region around the face, expanded to include body.
        
        The region extends:
        - Horizontally: PADDING_FACTOR * face_w on each side
        - Vertically: PADDING_FACTOR * face_h above, 3x face_h below (for body)
        """
        pad_x = int(face_w * self.PADDING_FACTOR)
        pad_top = int(face_h * self.PADDING_FACTOR)
        pad_bottom = int(face_h * 3.0)  # More space below for body/shoulders
        
        x = max(0, face_x - pad_x)
        y = max(0, face_y - pad_top)
        x2 = min(frame_w, face_x + face_w + pad_x)
        y2 = min(frame_h, face_y + face_h + pad_bottom)
        
        w = x2 - x
        h = y2 - y
        
        return (x, y, w, h)
    
    def _get_sample_indices(self, total: int, count: int) -> List[int]:
        """Get evenly spaced sample indices."""
        if total <= count:
            return list(range(total))
        
        step = total / count
        return [int(i * step) for i in range(count)]
