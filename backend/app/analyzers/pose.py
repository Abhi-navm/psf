"""
Body pose and gesture analysis using MediaPipe.
"""

from typing import Dict, Any, List, Optional, Tuple
import math

from app.core.logging import logger


class PoseAnalyzer:
    """Analyze body pose and gestures from video frames."""
    
    # MediaPipe pose landmarks indices
    LANDMARKS = {
        "nose": 0,
        "left_shoulder": 11,
        "right_shoulder": 12,
        "left_elbow": 13,
        "right_elbow": 14,
        "left_wrist": 15,
        "right_wrist": 16,
        "left_hip": 23,
        "right_hip": 24,
    }
    
    # Thresholds
    SHOULDER_ALIGNMENT_THRESHOLD = 0.05  # Max acceptable tilt
    CROSSED_ARMS_THRESHOLD = 0.15  # Wrist distance threshold
    SLOUCH_THRESHOLD = 0.1  # Hip-shoulder alignment threshold
    
    def __init__(self):
        """Initialize the pose analyzer."""
        self._pose_model = None
        self._pose_failed = False
        self._mp_pose = None
        self._mp_drawing = None
        self._use_new_api = False
    
    @property
    def pose_model(self):
        """Lazy load MediaPipe pose model."""
        if self._pose_model is None and not self._pose_failed:
            try:
                import mediapipe as mp
                # Try the legacy solutions API first
                if hasattr(mp, 'solutions') and hasattr(mp.solutions, 'pose'):
                    self._mp_pose = mp.solutions.pose
                    self._mp_drawing = mp.solutions.drawing_utils
                    self._use_new_api = False
                    self._pose_model = self._mp_pose.Pose(
                        static_image_mode=True,
                        model_complexity=1,
                        min_detection_confidence=0.5,
                        min_tracking_confidence=0.5,
                    )
                    logger.info("MediaPipe Pose model loaded (legacy API)")
                else:
                    # Try new task-based API for mediapipe >= 0.10.9
                    try:
                        from mediapipe.tasks import python
                        from mediapipe.tasks.python import vision
                        import urllib.request
                        import os
                        
                        model_path = "models/pose_landmarker.task"
                        if not os.path.exists(model_path):
                            os.makedirs("models", exist_ok=True)
                            url = "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task"
                            logger.info("Downloading pose landmarker model...")
                            urllib.request.urlretrieve(url, model_path)
                        
                        base_options = python.BaseOptions(model_asset_path=model_path)
                        options = vision.PoseLandmarkerOptions(
                            base_options=base_options,
                            output_segmentation_masks=False
                        )
                        self._pose_model = vision.PoseLandmarker.create_from_options(options)
                        self._use_new_api = True
                        logger.info("MediaPipe Pose model loaded (new task API)")
                    except Exception as e2:
                        logger.warning(f"Could not load new MediaPipe API: {e2}")
                        self._pose_failed = True
            except ImportError as e:
                logger.error(f"Failed to load MediaPipe: {e}")
                self._pose_failed = True
                raise
        return self._pose_model
    
    def _process_frame(self, image_rgb):
        """Process a frame using the appropriate MediaPipe API."""
        if self.pose_model is None:
            return None
        
        # Check which API we're using
        if hasattr(self, '_use_new_api') and self._use_new_api:
            # New task-based API
            import mediapipe as mp
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=image_rgb)
            results = self.pose_model.detect(mp_image)
            if results.pose_landmarks and len(results.pose_landmarks) > 0:
                # Convert to legacy-like format for compatibility
                return results.pose_landmarks[0]
            return None
        else:
            # Legacy solutions API
            results = self.pose_model.process(image_rgb)
            if results.pose_landmarks:
                return results.pose_landmarks.landmark
            return None
    
    def analyze_frames(self, frames: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze body pose across video frames.
        
        Args:
            frames: List of frame info dicts with 'path' and 'timestamp'
            
        Returns:
            Dict with pose analysis results
        """
        import cv2
        
        logger.info(f"Analyzing {len(frames)} frames for body pose")
        
        pose_timeline = []
        issues = []
        
        # Check if pose model is available
        if self.pose_model is None:
            logger.warning("Pose model not available, returning minimal results")
            return {
                "success": True,
                "pose_model_available": False,
                "summary": {
                    "average_shoulder_alignment": 0.5,
                    "gesture_frequency": 0,
                    "posture_score": 50,
                    "movement_score": 50,
                    "primary_issues": ["Pose detection unavailable"],
                },
                "timeline": [],
                "issues": [],
                "recommendations": ["Pose detection is unavailable due to MediaPipe compatibility issues"],
                "metrics": {
                    "crossed_arms_percentage": 0,
                    "poor_posture_percentage": 0,
                    "fidget_percentage": 0,
                    "gesture_count": 0,
                },
            }
        
        # Metrics tracking
        shoulder_alignments = []
        hand_positions = []
        previous_landmarks = None
        movement_deltas = []
        
        # Issue counters
        crossed_arms_count = 0
        poor_posture_count = 0
        fidget_count = 0
        
        for frame_info in frames:
            frame_path = frame_info.get("path")
            timestamp = frame_info.get("timestamp", 0)
            
            if not frame_path:
                continue
            
            try:
                # Load image
                image = cv2.imread(frame_path)
                if image is None:
                    continue
                
                image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                
                # Process with MediaPipe (handles both APIs)
                landmarks = self._process_frame(image_rgb)
                
                if landmarks is not None:
                    # Analyze this frame
                    frame_analysis = self._analyze_frame_pose(landmarks)
                    
                    # Track metrics
                    shoulder_alignments.append(frame_analysis["shoulder_alignment"])
                    
                    # Check for issues
                    if frame_analysis["has_crossed_arms"]:
                        crossed_arms_count += 1
                        issues.append({
                            "type": "crossed_arms",
                            "timestamp": timestamp,
                            "severity": "medium",
                        })
                    
                    if frame_analysis["has_poor_posture"]:
                        poor_posture_count += 1
                        issues.append({
                            "type": "poor_posture",
                            "timestamp": timestamp,
                            "severity": "medium",
                        })
                    
                    # Detect fidgeting (movement between frames)
                    if previous_landmarks is not None:
                        movement = self._calculate_movement(previous_landmarks, landmarks)
                        movement_deltas.append(movement)
                        
                        if movement > 0.1:  # High movement threshold
                            fidget_count += 1
                            issues.append({
                                "type": "fidgeting",
                                "timestamp": timestamp,
                                "severity": "low",
                            })
                    
                    previous_landmarks = landmarks
                    
                    # Add to timeline
                    pose_timeline.append({
                        "timestamp": timestamp,
                        "pose_type": frame_analysis["pose_type"],
                        "shoulder_alignment": frame_analysis["shoulder_alignment"],
                        "confidence": frame_analysis["confidence"],
                    })
                    
            except Exception as e:
                logger.debug(f"Frame pose analysis failed: {e}")
        
        total_frames = len(frames)
        analyzed_frames = len(pose_timeline)
        
        # Calculate aggregate metrics
        avg_shoulder_alignment = (
            sum(shoulder_alignments) / len(shoulder_alignments)
            if shoulder_alignments else 0
        )
        
        avg_movement = (
            sum(movement_deltas) / len(movement_deltas)
            if movement_deltas else 0
        )
        
        fidgeting_frequency = fidget_count / analyzed_frames if analyzed_frames > 0 else 0
        
        # Calculate scores
        scores = self._calculate_scores(
            avg_shoulder_alignment,
            crossed_arms_count / analyzed_frames if analyzed_frames > 0 else 0,
            poor_posture_count / analyzed_frames if analyzed_frames > 0 else 0,
            fidgeting_frequency,
        )
        
        # Consolidate issues
        consolidated_issues = self._consolidate_issues(issues)
        
        return {
            "overall_score": scores["overall"],
            "posture_score": scores["posture"],
            "gesture_score": scores["gesture"],
            "movement_score": scores["movement"],
            "avg_shoulder_alignment": avg_shoulder_alignment,
            "fidgeting_frequency": fidgeting_frequency,
            "gesture_frequency": fidget_count / analyzed_frames if analyzed_frames > 0 else 0,
            "pose_timeline": pose_timeline,
            "issues": consolidated_issues,
        }
    
    def _analyze_frame_pose(self, landmarks) -> Dict[str, Any]:
        """Analyze pose in a single frame."""
        
        # Get relevant landmarks
        left_shoulder = landmarks[self.LANDMARKS["left_shoulder"]]
        right_shoulder = landmarks[self.LANDMARKS["right_shoulder"]]
        left_elbow = landmarks[self.LANDMARKS["left_elbow"]]
        right_elbow = landmarks[self.LANDMARKS["right_elbow"]]
        left_wrist = landmarks[self.LANDMARKS["left_wrist"]]
        right_wrist = landmarks[self.LANDMARKS["right_wrist"]]
        left_hip = landmarks[self.LANDMARKS["left_hip"]]
        right_hip = landmarks[self.LANDMARKS["right_hip"]]
        
        # Calculate shoulder alignment (y-difference)
        shoulder_alignment = abs(left_shoulder.y - right_shoulder.y)
        
        # Check for crossed arms (wrists close together and near opposite elbow)
        wrist_distance = self._calculate_distance(
            (left_wrist.x, left_wrist.y),
            (right_wrist.x, right_wrist.y)
        )
        
        # Wrists near torso center
        torso_center_x = (left_shoulder.x + right_shoulder.x) / 2
        left_wrist_near_center = abs(left_wrist.x - torso_center_x) < 0.2
        right_wrist_near_center = abs(right_wrist.x - torso_center_x) < 0.2
        
        has_crossed_arms = (
            wrist_distance < self.CROSSED_ARMS_THRESHOLD and
            left_wrist_near_center and right_wrist_near_center
        )
        
        # Check for poor posture (shoulders forward of hips significantly)
        avg_shoulder_y = (left_shoulder.y + right_shoulder.y) / 2
        avg_hip_y = (left_hip.y + right_hip.y) / 2
        
        # In normalized coordinates, smaller y = higher in image
        # If shoulders are much lower (higher y) relative to expected, indicates slouch
        has_poor_posture = shoulder_alignment > self.SHOULDER_ALIGNMENT_THRESHOLD
        
        # Determine pose type
        if has_crossed_arms:
            pose_type = "crossed_arms"
        elif has_poor_posture:
            pose_type = "poor_posture"
        else:
            pose_type = "open_confident"
        
        # Confidence based on landmark visibility (handle both APIs)
        def get_visibility(landmark):
            if hasattr(landmark, 'visibility'):
                return landmark.visibility
            return 0.8  # Default confidence for new API
        
        confidence = min(
            get_visibility(left_shoulder),
            get_visibility(right_shoulder),
            get_visibility(left_wrist),
            get_visibility(right_wrist),
        )
        
        return {
            "shoulder_alignment": shoulder_alignment,
            "has_crossed_arms": has_crossed_arms,
            "has_poor_posture": has_poor_posture,
            "pose_type": pose_type,
            "confidence": confidence,
        }
    
    def _calculate_distance(self, p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
        """Calculate Euclidean distance between two points."""
        return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)
    
    def _calculate_movement(self, prev_landmarks, curr_landmarks) -> float:
        """Calculate total movement between frames."""
        total_movement = 0
        
        key_points = [
            self.LANDMARKS["left_shoulder"],
            self.LANDMARKS["right_shoulder"],
            self.LANDMARKS["left_wrist"],
            self.LANDMARKS["right_wrist"],
        ]
        
        for idx in key_points:
            prev = prev_landmarks[idx]
            curr = curr_landmarks[idx]
            movement = self._calculate_distance(
                (prev.x, prev.y),
                (curr.x, curr.y)
            )
            total_movement += movement
        
        return total_movement / len(key_points)
    
    def _consolidate_issues(self, issues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Consolidate similar issues."""
        if not issues:
            return []
        
        issue_groups = {}
        for issue in issues:
            issue_type = issue["type"]
            if issue_type not in issue_groups:
                issue_groups[issue_type] = []
            issue_groups[issue_type].append(issue["timestamp"])
        
        consolidated = []
        
        issue_details = {
            "crossed_arms": {
                "description": "Arms crossed over chest, which can appear defensive",
                "suggestion": "Keep arms open and use hand gestures while speaking",
            },
            "poor_posture": {
                "description": "Shoulders not aligned or slouching detected",
                "suggestion": "Stand or sit up straight with shoulders back",
            },
            "fidgeting": {
                "description": "Excessive movement detected, may indicate nervousness",
                "suggestion": "Practice staying calm and composed during delivery",
            },
        }
        
        for issue_type, timestamps in issue_groups.items():
            if len(timestamps) >= 1:  # Report all detected issues
                details = issue_details.get(issue_type, {
                    "description": f"{issue_type} detected",
                    "suggestion": "Be mindful of your body language",
                })
                
                consolidated.append({
                    "type": issue_type,
                    "timestamps": timestamps[:5],
                    "occurrence_count": len(timestamps),
                    "severity": "medium" if len(timestamps) > 5 else "low",
                    "description": details["description"],
                    "suggestion": details["suggestion"],
                })
        
        return consolidated
    
    def _calculate_scores(
        self,
        avg_shoulder_alignment: float,
        crossed_arms_ratio: float,
        poor_posture_ratio: float,
        fidgeting_frequency: float,
    ) -> Dict[str, float]:
        """Calculate pose scores."""
        
        # Posture score (based on shoulder alignment and poor posture frequency)
        posture_base = 100
        posture_penalty = (poor_posture_ratio * 30) + (avg_shoulder_alignment * 200)
        posture_score = max(0, min(100, posture_base - posture_penalty))
        
        # Gesture score (penalize crossed arms, reward open posture)
        gesture_base = 80
        gesture_penalty = crossed_arms_ratio * 50
        gesture_score = max(0, min(100, gesture_base - gesture_penalty + 20))
        
        # Movement score (moderate movement is good, too much is bad)
        if fidgeting_frequency < 0.1:
            movement_score = 90.0  # Good, minimal fidgeting
        elif fidgeting_frequency < 0.2:
            movement_score = 75.0  # Acceptable
        elif fidgeting_frequency < 0.3:
            movement_score = 60.0  # Some fidgeting
        else:
            movement_score = max(30, 100 - fidgeting_frequency * 200)
        
        # Overall score
        overall = (posture_score * 0.4 + gesture_score * 0.35 + movement_score * 0.25)
        
        return {
            "overall": round(overall, 1),
            "posture": round(posture_score, 1),
            "gesture": round(gesture_score, 1),
            "movement": round(movement_score, 1),
        }
